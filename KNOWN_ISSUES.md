# Known Issues

## Setup Wizard Appears to Freeze While Copying the HDD Image

**Symptom:** Selecting a HDD image in the setup wizard leaves the screen
apparently frozen. The Next button does nothing. Re-selecting the same file
seems to unstick it, as does simply waiting.

**Root cause:** `SetupWizardActivity.copyUriAsync()` copies the chosen image
into app storage on a background thread — correctly — but reports progress only
through a `Toast.LENGTH_SHORT`, which disappears after about two seconds. A
retail HDD image is around a gigabyte (a typical `xbox_hdd.qcow2` is ~985 MB),
and copying that from an exFAT card takes far longer than the toast lasts.
Meanwhile `updateButtons()` disables navigation for the duration, so the wizard
shows a static screen with dead controls and no indication that anything is
happening.

Re-selecting the file does not actually restart anything: `copyUriAsync()`
opens with `if (isCopying) return`, so the second attempt is silently dropped.
Navigating the picker again simply takes long enough for the first copy to
finish, which makes the re-selection look like the fix.

**Workaround:** Wait. The copy completes on its own; how long depends on the
image size and the speed of the card.

**Fix needed:** Show real progress for the duration of the copy. The pattern
already exists in this codebase — `GameLibraryActivity` tracks XISO conversion
across its copy, convert and save phases — so the wizard should use the same
approach rather than a toast. Silently dropping a second selection should also
tell the user a copy is already running.

---

## Diagnostic Frame Capture Freezes Game

**Symptom:** Triggering a multi-frame diagnostic capture (e.g. 10 frames) from the pause menu causes the game to freeze indefinitely.

**Root cause:** Re-read against the code 2026-09; the earlier diagnosis here
was wrong in both halves and is corrected below.

The JSON is *not* written synchronously. It accumulates in memory
(`diag_frame_bufs`, `vk/renderer.c:527-530`) and is written once at session end
by `diag_write_session_json` (`:744`, called from `:1552` and `:1574`).

The per-draw surface dump is the cost, and it is dominated by two things, only
one of which is disk I/O:

1. **A full GPU sync per draw call.** `pgraph_vk_finish(pg,
   VK_FINISH_REASON_SURFACE_DOWN)` runs at `vk/renderer.c:1305` before every
   dump, then `diag_download_surface` (`:341`) submits its own single-time
   command buffer. With 100+ draws a frame that is 100+ pipeline stalls, and it
   is synchronous by construction.
2. **A three-byte `fwrite` per pixel.** `dump_surface_ppm` (`:437-465`) calls
   `fwrite(rgb, 1, 3, f)` inside the inner loop — 307,200 stdio calls for a
   single 640x480 surface, before any bytes reach storage.

**Workaround:** Use single-frame captures only.

**Fix needed:** Not the background writer thread this entry used to prescribe —
that would address neither dominant cost. The GPU flush cannot be moved off the
render thread, and the write pattern is a local defect:

- Build each row (or the whole image) in a buffer and issue one `fwrite`.
  Contained, single-threaded, and probably the larger win of the two.
- Then measure again before touching threading. If the remaining cost is the
  per-draw `pgraph_vk_finish`, a writer thread does not help; batching or
  sampling draws does.

Fixing this matters beyond the annoyance: per-draw-call capture is the
project's only intermediate observability. Without it a rendering defect can
only be observed as a final framebuffer, which is why so much accuracy work
costs a device run. See [`docs/nv2a/pipeline.md`](docs/nv2a/pipeline.md).

---

## VK Texture LRU Exhaustion

**Symptom:** Crash (previously assert failure) in `lru_evict_one` when all texture cache slots are in-flight. Seen in Dead or Alive 3.

**Root cause:** The VK texture cache (1024 entries) is exhausted when a game uses many textures and multiple command buffers are in-flight (triple buffering). All LRU entries are pinned by in-flight frames, leaving no evictable slot.

**Current handling:** Returns NULL and skips the texture bind for the current frame. May cause momentary texture flickering instead of a crash.

**Fix needed:** Increase texture cache size for texture-heavy games, or flush an in-flight frame to free slots when the cache is full.

---

## VK Driver Crash on Adreno (SIGSEGV in vulkan.ad07XX.so)

**Symptom:** SIGSEGV inside the Adreno Vulkan driver during `pgraph_vk_flush_draw`. Signal 11 crash with no xemu assert — the GPU driver itself segfaults.

**Root cause:** Unknown. Likely a driver bug triggered by specific command buffer sequences. Seen sporadically across games.

**Workaround:** Try switching to OpenGL ES renderer. If the crash is reproducible, clearing the shader cache may help.

---

## OpenGL ES Texture Artifacts

**Symptom:** Misplaced geometry, dragged/stretched textures on the GL renderer.

**Root cause:** The GL state cache optimization (state save/restore reduction) introduced state desync between clear/display paths and the draw path. The optimization was reverted. Artifacts may also stem from inherent GL renderer limitations (CPU-side format conversions, surface scaling differences).

**Status:** GL state cache optimization reverted. Some residual artifacts may exist from the x1_box GL port. See [`docs/investigations/gl-artifacts.md`](docs/investigations/gl-artifacts.md)
for detailed analysis — and note its scope header: Android runs Vulkan, so
that document does not describe the shipped renderer.

---

## TB Cache Prewarm Crash on Settings Change

**Symptom:** Assertion failure in `translator.c:310` during `tb_cache_prewarm` at startup.

**Root cause:** Stale `tb_cache.bin` from a previous session with different FP settings or a different build. The cached translation block hints are incompatible with the current code generation configuration.

**Current handling:** FP settings changes delete `tb_cache.bin`. FP state is XORed into the game hash for cache rejection. A "Clear code cache" button is available in Debug settings.

**Remaining risk:** Build-to-build changes that affect code generation (e.g. GLSL changes) don't auto-invalidate the cache. Users must manually clear the code cache after updates.

---

## Xbox Kernel Crashes (BugCheck 0x1E) — Game-Specific Freezes

**Symptom:** Game freezes at a specific gameplay point with the last frame stuck on screen, sound continuing, and the app remaining responsive. The CPU gets stuck at `eip=0x800151ed` (kernel halt loop: `CLI; HLT; JMP $-2`).

**Root cause:** The game code dereferences a NULL object pointer, triggering a kernel BugCheck 0x1E (KMODE_EXCEPTION_NOT_HANDLED) with STATUS_ACCESS_VIOLATION (0xC0000005). A game-internal lookup function returns NULL because an array is empty or a search key isn't found. On desktop xemu the same lookup succeeds — the difference is caused by an upstream xemu rendering pipeline change (primitive rewriting moved from geometry shader to CPU) that alters GPU operation timing on Android.

This is a pre-existing issue in the base Android xemu migration, present since the initial port. It is NOT caused by any hakuX-specific additions (tier-1 recompilation, hint system, VBLANK deferral, safety valves, etc.).

**Detection:** Kernel crashes are automatically detected and logged via `hakuX-crash`:

```
adb logcat | Select-String "hakuX-crash"
```

The crash dump includes BugCheck code, exception type, all CPU registers, CR2 (faulting address), code context around the halt loop, and on NULL page faults: extended code dumps, CALL target analysis, and stack frame walks.

**Affected games:**

| Game | Crash EIP | CR2 | Details |
|------|-----------|-----|---------|
| NightCaster | 0x197ED3 | 0x418 | NULL object pointer at field offset 0x418; lookup function at 0x1FAD07 returns NULL |

**Workaround:** None currently available. The game runs correctly on desktop xemu.
