# Re-verifying the inherited KNOWN_ISSUES entries (2026-09-12)

Issue [#18](https://github.com/jreinach-alt/hakuX/issues/18). `KNOWN_ISSUES.md`
predates the pgraph harness and the dispatcher, so its entries were written
without a cheap way to re-check them. This is that re-check, over the seven
entries #18 names plus the three that still live in the file.

Measurement only. No `hw/` file was touched, nothing was built, and the device
was not used — every number below comes from evidence already on disk.

## Method, and what it can and cannot see

**Source of the entries.** The seven are the pre-migration text, recovered as
`git show 1a89ae9336^:KNOWN_ISSUES.md`. The three survivors are the current
file.

**Device evidence.** `/home/justin/hakux-work/dispatch/results/` — 104 run
directories, all dated 2026-09-12 between 11:05 and 17:51. That is 109 pgraph
disc runs (3,859 s of guest execution) plus 14 Galleon soak runs (2,430 s),
about **1.75 h of guest execution in one day** on the Retroid Pocket Nova
(Adreno 740, Turnip, Vulkan).

**Why that day is admissible as crash evidence.** The dispatcher captures
logcat with `LOGCAT_SPEC="... hakuX:W ... *:S"` (`docs/testing/dispatcher.sh:179`
and `:240`), which silences `libc`/`DEBUG`, so a bare tombstone would be
invisible. But hakuX installs its own handler —
`android/app/src/main/cpp/android_crash_handler.cpp:174-176` registers
`SIGABRT`, `SIGILL` **and `SIGSEGV`** — and it prints `Caught signal N ...` plus
an FP backtrace to the `hakuX` tag at `E`, which *is* captured. A process-fatal
SIGSEGV anywhere, driver frames included, would therefore appear in these logs.
Absence here is a measurement, not a gap.

**What that day contains.** Across 118 captured logcats, exactly **two**
process-fatal signals, both `signal 6` (SIGABRT):

| run | time | site |
|---|---|---|
| `1789240604b-depth-baseline/logcat1.txt` | 12:27:06 | `abort` inside `libVkLayer_khronos_validation.so`, reached from `pgraph_vk_clear_surface` ← `pgraph_method` ← `pfifo_thread` |
| `1789241862-orchestrator-2566104/logcat1.txt` | 12:48:35 | the same stack; the request records it as "W buffering 97/265" |

**Zero SIGSEGV. Zero frames in `vulkan.ad0*`.** Both aborts are the Vulkan
validation layer on a debug build (`com.jreinach.hakux.debug`), which is #34's
territory, not any entry below.

**Truncation was checked, not assumed.** Of 108 scored runs, 106 carry
`progress_log_proof: true`. The two that do not are exactly the two SIGABRT
runs — so no run in this set is silently truncated, and the "a run without
progress proof is absent, not zero" trap does not apply to anything cited here.

**Goldens are dated.** All 5,608 PNGs under `/home/justin/goldens/results/`
carry mtime 2026-09-09, one batch, no mixed vintages. Nothing here is at risk
from #27's stale-golden trap. Repository file mtimes are checkout times and are
*not* used for dating; every repo artefact below is dated by its commit.

**The limit of all of it.** The sweep runs the pgraph suite and one title
(Galleon). "Seen sporadically across games" is a different workload than
anything measured on 2026-09-12, and this document says so wherever it matters.

---

## Verdicts

Six of the seven are closable. One is not, and it is the only one that was ever
about the emulator running a game wrongly.

| # | entry | verdict | tracker | closable? |
|---|---|---|---|---|
| 1 | Setup Wizard freeze while copying HDD | **no longer reproduces** — fixed `54729ec11a`, 2026-09-07, with 11 JVM tests | none | yes (already noted as user-facing) |
| 2 | Diagnostic frame capture freezes game | **no longer reproduces as written** — four 10-frame captures completed 2026-09-11; the *cost* is real and still at HEAD | none | yes, but file a **perf** issue in its place |
| 3 | VK texture LRU exhaustion | **crash no longer reproduces** (assert deleted 2026-03-27); the exhaustion condition is unchanged and **needs a device run on Dead or Alive 3** | none | **no** — refile with the real symptom |
| 4 | VK driver crash on Adreno (SIGSEGV) | **no longer reproduces**, and was never evidenced — symptom string appears nowhere | none | yes |
| 5 | OpenGL ES texture artifacts | **cause reverted 2026-03-27**; the remainder **was never about the shipping renderer** (Android is Vulkan) | none | yes |
| 6 | TB cache prewarm crash on settings change | **no longer reproduces** — the assert is gone, the function is not called on Android, and the "remaining risk" is closed | none | yes, carrying the new CMake finding forward |
| 7 | Xbox kernel BugCheck 0x1E | **cannot be settled without a device run**, and the disc is not on the host | none | **no** — split out of #18 before closing it |

Three entries still live in `KNOWN_ISSUES.md` as user-facing notes rather than
defects; they are checked at the end of this document and all three are accurate.

---

## 1. Setup Wizard appears to freeze while copying the HDD image

**Verdict: no longer reproduces.** Fixed 2026-09-07 in `54729ec11a`, "fix: show
real progress while the setup wizard copies an image".

**Evidence.** The entry's two mechanisms are both gone from the source:

- The `Toast.LENGTH_SHORT` is replaced by a progress dialog held for the whole
  copy — `SetupWizardActivity.kt:356` builds it, `:367` drives the bar from the
  copy callback, `:364` dismisses it on the UI thread. It is determinate when
  the provider reports a size and indeterminate when it does not
  (`showCopyProgressDialog`, `:386`, `isIndeterminate = totalBytes <= 0L`),
  which is the right call: 0% held for three minutes reads exactly like the
  freeze being fixed.
- The silently-dropped second selection now speaks:
  `copyUriAsync` (`:347`) opens with
  `if (isCopying) { Toast.makeText(this, "A copy is already running. Please wait.", …); return }`
  at `:348-351`, instead of the bare `return` the entry describes.

The size/percentage decision is extracted into `CopyProgress.kt`
(`percentOf`, `:28`) free of Android types, with 11 JVM tests in
`android/app/src/test/java/com/rfandango/haku_x/CopyProgressTest.kt`. So this
one is not merely "changed" — it has a regression test.

**Smallest demonstration if ever doubted:** none needed on device; the JVM test
class is the demonstration.

**Tracker:** no issue; the entry survives in `KNOWN_ISSUES.md` deliberately, as
a note for people still on old builds. That is the right disposition — leave it.

---

## 2. Diagnostic frame capture freezes game

**Verdict: no longer reproduces as written.** The "freezes indefinitely" symptom
did not occur in the only recent on-device multi-frame captures. The *cost* the
entry describes is real, is still in the tree at HEAD, and deserves an issue —
but a performance issue, not a freeze.

**The counter-example, and it is direct.** On 2026-09-11, on a Nova on Turnip
T30, **four ten-frame diagnostic captures were taken by hand from the Debug
Capture button and all four completed** — 303 draws, 299 of them with textures
(`docs/investigations/galleon-flashing-deck.md:248-249`, committed in
`46781ccf18`). One session is committed:
`docs/testing/diag/run-2026-09-11-galleon-session-4122.json`, 1.1 MB, 10 frames,
21 deduplicated shaders, 9 frame diffs, per-frame draw counts
`[0,0,0,0,0,56,135,0,0,0]` — **191 draws**, peaking at 135 in one frame.

The per-draw surface dump — the expensive half — demonstrably ran. Re-running
the committed checker over the committed session reproduces it:

```
$ python3 docs/testing/check_diag_invariants.py \
      docs/testing/diag/run-2026-09-11-galleon-session-4122.json
74 draws checked, 1 violating the pairing
  frame 4122 draw 92: scale 8.0 with a 128-wide texture = 1024 detail texels, expected 2048
      framebuffer after that draw: f6_draw92_color.ppm
```

`f6_draw92_color.ppm` is a per-draw dump filename, and the image differenced
out of that dump and its predecessor is committed as
`docs/investigations/images/galleon-outlier-draw.png` (`46781ccf18`). A capture
that froze indefinitely does not produce a session JSON, a per-draw PPM and a
finding.

**The cost is nonetheless still there, verified in code at HEAD `3996a62804`:**

- A full GPU sync per draw: `pgraph_vk_finish(pg, VK_FINISH_REASON_SURFACE_DOWN)`
  at `hw/xbox/nv2a/pgraph/vk/renderer.c:1370`, unconditionally inside
  `nv2a_diag_log_draw_call` (`:1049`), followed by `diag_download_surface`
  (`:364`) submitting its own single-time command buffer.
- A three-byte `fwrite` per pixel: `fwrite(rgb, 1, 3, f)` at
  `renderer.c:484`, inside the `x` loop of `dump_surface_ppm` (`:446`). That is
  307,200 stdio calls per 640×480 surface.

The JSON is *not* written synchronously — it accumulates in `diag_frame_bufs`
(`:550`) and is flushed once by `diag_write_session_json` (`:767`). That
correction is already recorded in `docs/investigations/diag-capture-cost.md`.

**Why the entry read as a freeze.** The entry's threshold is "100+ draw calls
per frame". Galleon's busiest captured frame is 135, so this workload sits at
the threshold and completes — slowly. A heavier title would be slower still,
and "very slow with no progress indication" is exactly what the original report
would have looked like. Nothing here shows the capture path is *fast*; it shows
it terminates.

**Staleness note, the trap in reverse.** `diag-capture-cost.md` still says
"Status: open, unfixed", and its last commit is `ad5edf0897`, 2026-09-09 — two
days *older* than the Galleon captures that contradict its headline symptom.
The doc was not wrong when written; the evidence arrived after it.

**Tracker:** none. Recommend filing one, scoped as *"per-draw diagnostic
capture is slow enough to look hung: one GPU sync and 307k stdio calls per
draw"*, with the row-at-a-time `fwrite` as the cheap first fix and a
measurement before anyone touches threading. Do **not** file it as a freeze.

**Smallest demonstration:** none on device. Any ten-frame capture on a title
with >100 draws/frame, timed, settles the remaining question (which of the two
costs dominates) — and `diag-capture-cost.md` already names that as its
UNRESOLVED item.

---

## 3. VK texture LRU exhaustion

**Verdict: the crash as written no longer reproduces; the condition behind it is
unchanged and cannot be settled without a device run on Dead or Alive 3.**

**The assert is gone.** `include/qemu/lru.h:149-153` is now a pass-through:

```c
static inline
LruNode *lru_evict_one(Lru *lru)
{
	return lru_try_evict_one(lru);
}
```

`lru_try_evict_one` (`lru.h:133-147`) returns `NULL` when every node is in use
or vetoed, and `lru_lookup` propagates it (`lru.h:207-210`). The
`assert(found != NULL); /* No evictable node! */` was deleted in **`6e60deaf7e`,
2026-03-27** ("android: settings index, section filtering, graceful LRU
handling"). So the literal symptom — an abort inside `lru_evict_one` — is not
reachable.

**The exhaustion condition is unchanged, and on some devices is now tighter.**

- Triple buffering: `NUM_SUBMIT_FRAMES 3`, `hw/xbox/nv2a/pgraph/vk/renderer.h:1124`.
- The in-flight pin the entry describes is still there:
  `texture_cache_entry_pre_evict` (`vk/texture.c:2525-2541`) vetoes eviction for
  any binding in `r->texture_bindings[]` and for any node with
  `snode->submit_time + r->num_active_frames > r->submit_count`.
- The cache is still 1024 by default (`vk/texture.c:2626-2641`) and is now
  budget-driven: **512 entries on a ≤768 MiB budget**
  (`vk/buffer.c:123`), 1024 above (`buffer.c:127`, `:131`), with a user override
  at `buffer.c:138-140`.

The entry's own "fix needed" — flush an in-flight frame to free slots — **was
never applied to this path**. It exists only on the image-creation OOM path
(`vk/texture.c:1971-1976`: `pgraph_vk_flush_all_frames` then up to 64
`lru_try_evict_one` retries), not at the exhaustion site.

**The degraded behaviour is not provably safe, and this is the part worth
handing to an implementer.** The single VK caller is `create_texture`
(`vk/texture.c:1621-1626`):

```c
        LruNode *node = lru_lookup(&r->texture_cache, key_hash, &key);
        if (!node) {
            /* LRU exhausted — all texture slots in-flight. Skip this
             * texture bind and use whatever was previously bound. */
            return;
        }
```

but `pgraph_vk_bind_textures` (`vk/texture.c:2265-2360`) then runs
`pg->texture_dirty[i] = false;` at `texture.c:2359` **unconditionally**, so a
skipped slot is marked clean and is not retried on the next draw until a
register changes. And if the skipped bind is a slot's *first*, the slot stays
`NULL` — `PGRAPHVkState` is `g_malloc0`'d (`vk/renderer.c:180`) and
`pgraph_vk_finalize_textures` nulls the array (`texture.c:2786-2788`) — which is
then dereferenced without a guard at `vk/shaders.c:478-479`, `shaders.c:564-565`
and `vk/draw.c:3021`, with `assert(r->texture_bindings[i] != NULL)` at
`shaders.c:1269`. So the 2026-03-27 change converted an abort into a stale
texture in the common case and into a different abort in the narrow first-bind
case.

Two related caches were *not* given the same treatment:
`get_shader_module_entry_for_key` (`vk/shaders.c:742-745`) and `shaders.c:1152`
do not check for NULL, and those caches do install `pre_node_evict` under
`OPT_ASYNC_COMPILE` (`shaders.c:1062`, `:1089`). The VK pipeline cache *was*
fixed the same way as textures (`vk/draw.c:987-992`, `draw.c:1399-1405`).

**GL does not have this failure mode.** `gl/texture.c:1462-1478` installs no
`pre_node_evict`, so nothing can veto an eviction and `lru_lookup` cannot return
NULL; correspondingly the GL caller at `gl/texture.c:857-860` has no NULL check
and needs none — and GL has no in-flight safety pin either.

**Why no existing log can settle it.** The exhaustion path increments no
counter and prints nothing; the only headroom readout is
`"TexCache: used:%d/%zu miss:%d upload:%d dirty:%d evict:%d(oom:%d) …"`
(`vk/draw.c:333`), which sits behind `NV2A_PERF_LOG`, defined to `0` at
`hw/xbox/nv2a/debug.h:409`, so `OPT_STAT_INC` compiles to a no-op
(`vk/renderer.h:177-181`). Every hit for "texture" in
`/home/justin/hakux-work/**/*logcat*.txt` is a `hakuX-texreplace` init line;
there are zero `TexCache:` lines, zero `DIAG: texture EVICTED while in-flight!`
(`texture.c:2549-2552`, which *is* unconditional but fires only on a violated
pin, not on exhaustion), and **no Dead or Alive 3 run anywhere in the work
tree** — everything there is pgraph-harness runs.

**Tracker:** no issue. Not closable on this evidence, and it should not be
filed as "crash in `lru_evict_one`" either. The honest issue is *"texture-cache
exhaustion is handled by skipping the bind, and the skip both marks the slot
clean and can leave it NULL"*.

**Smallest demonstration:** Dead or Alive 3, on a device, with `NV2A_PERF_LOG`
set to 1 (or a counter added at `texture.c:1622`), reading `hakuX-tex`
`used:N/target` against the `memory_budget: … tex_cache=` line that
`vk/buffer.c:206-224` prints unconditionally at startup. The pgraph suite cannot
demonstrate it: it is a texture-count workload, and the suite is not one.

---

## 4. VK driver crash on Adreno (SIGSEGV in `vulkan.ad07XX.so`)

**Verdict: no longer reproduces on any workload that has been measured, and the
entry was never evidenced.** #18 classified it "environment"; the better reading
is that at least two crashes with this signature were ours and were fixed in
March 2026.

**There is no artefact behind the entry.** `pgraph_vk_flush_draw` — the function
the symptom names — appears in **no** document, log, issue or run record in the
repo or in `/home/justin/hakux-work/`. Neither does `vulkan.ad0`. Zero hits,
both strings. The entry records a symptom nobody kept a trace of.

**The instrumentation that would catch it exists and has caught nothing like
it.** `android/app/src/main/cpp/android_crash_handler.cpp:176` installs a
`SIGSEGV` handler that prints `Caught signal N ...` and an FP backtrace to the
`hakuX` tag, and `HakuXApplication.kt:33` additionally subscribes to `DEBUG`,
`libc`, `crash_dump` and `tombstoned`. Over 1.75 h of guest execution on
2026-09-12 (104 runs, 118 logcats) it fired **twice**, both `signal 6` in the
Vulkan validation layer, **zero** SIGSEGV, zero driver frames.

**Three drivers, one build, no crash.** On 2026-09-11 an 826-capture sweep over
seven suites ran on the same build (`27b583e17c`) against Turnip T30
(Mesa 26.3.0-T30-1.4.359), Turnip T26 (26.1.0-T26-1.4.344) **and the proprietary
Qualcomm stock driver 0676.53** (vendor image, Dec 2023), with the driver swapped
underneath — `docs/investigations/adreno-driver-landscape.md`, committed
`4801bf78b8`. No crash on any arm. Adreno determinism was separately confirmed
on 2026-09-10 (`be7d53fcdd`, 3/3 runs, 80/80 on `Depth_buffer_fixed_function`).

**Two crashes that would have produced this signature were fixed pre-fork:**

- `94aebc29c7`, 2026-03-19, "vk: fix **Freedreno** crash by removing fast-path
  descriptor set rebinds"
- `7a28f4db52`, 2026-03-26, "vk: fix **SIGSEGV** in direct depth-stencil pack
  compute shader"

**And the one crash that did look like driver noise was ours.** The lavapipe
lane died in the flip path about one run in four; `167f44bae9` (2026-09-10)
records the correction — "the docstring still called the crash lavapipe noise.
It was a **use-after-free in the emulator** (issue #29)." Every SIGSEGV recorded
since the fork has been emulator code, including the most recent one
(`pgraph_finish_inline_buffer_vertex`, 2026-09-12, fixed same day in
`878507db2f`).

**The prescribed workaround is not actionable.** "Switch to the OpenGL ES
renderer" cannot be done on Android: the `OPENGL` default in
`config_spec.yml:230` is overridden at `xemu_android.cpp:616` and
`xemu_settings_android.cc:69`. See entry 5.

**What this does *not* settle.** Every measurement above is a pgraph disc run of
seconds to minutes, or a Galleon soak of at most four minutes. "Seen
sporadically across games" is a multi-hour gameplay claim, and nothing in this
corpus tests it.

**Tracker:** no issue. **Closable within #18** as "no evidence, and the two
plausible causes were emulator bugs fixed 2026-03." Do not open a new issue for
it: an issue whose root cause is "Unknown" and whose symptom string appears
nowhere is exactly the noise #18 exists to remove.

**Smallest demonstration if anyone wants one anyway:** not a suite — a long soak.
A multi-hour `soak_title.sh` run would be the only thing that could speak to it,
and it would still be looking for something nobody has a trace of.

---

## 5. OpenGL ES texture artifacts

**Verdict: the named cause no longer exists, and the rest was never about the
renderer this project ships.**

**The cause named in the entry was reverted the same day it landed.** The GL
state-cache optimisation arrived in `9e62f34cad` ("nv2a/gl: GLES performance
optimizations (state cache, NEON expand)") and was reverted in `7d285e9e51`
("Revert ...", 96 insertions / 178 deletions across `display.c`, `draw.c`,
`renderer.c`, `renderer.h`, `surface.c`) — **both on 2026-03-27**. The separate
desync fix `9d7d513d7c` ("nv2a/gl: fix GL state cache desync causing texture
artifacts") survives. So "Status: GL state cache optimization reverted" has been
true for five and a half months, and the code that desynced is gone.

**The document the entry points at was renamed, twice.**
`GL_ARTIFACT_INVESTIGATION.md` → `docs/investigations/gl-texture-artifacts.md`
(`4586837cc6`, 2026-09-08, zero content lines changed) →
`docs/investigations/gl-artifacts.md` (`93405d1778`, 2026-09-09); git's own
rename detection collapses the pair into a single
`GL_ARTIFACT_INVESTIGATION.md -> gl-artifacts.md`, so the content is intact
rather than lost. A filesystem-wide `find` for `*GL_ARTIFACT*` returns nothing:
the old name exists only in history. The document now opens with a scope banner
that settles the entry better than any measurement could:

> **Read the scope before the content: on Android the renderer is Vulkan.**
> `android/app/src/main/cpp/xemu_android.cpp:616` and
> `xemu_settings_android.cc:69` override the `OPENGL` default in
> `config_spec.yml:230`, so nothing here describes what runs on device.

**The residual claim cannot be measured, and should not be.** There is not one
GL arm anywhere in `docs/testing/` — every `run-*.tsv` is a desktop-lane or an
`-adreno`-suffixed Vulkan run. Building one would be measuring a renderer
Android does not use, and the sweep would score a path known to be structurally
behind: `nv2a-sweep-2026-09.md:32-34` records that `window_clip_count`
(`psh.c:67-68`) and `depth_needed` (`psh.c:120-126`) are both non-OpenGL-only,
so **GL emits no clip block and no `gl_FragDepth` write** at all. Those are
larger than any texture artifact.

**GL is maintained as a desktop fallback, not abandoned.** #24 ("GL renderer
aborts on unimplemented colour surface format 0x7") was filed and fixed on
2026-09-10 by `baa6c2ace2`, which mapped four formats in **both** the GL and
Vulkan tables — Blend surface went from aborting at test 5 to 32/32, Clear from
aborting at test 1 to 32/32 with 24 bit-exact. #29 confirms GL is still the live
fallback when Vulkan cannot start.

**Tracker:** no issue. **Closable within #18** as "cause reverted 2026-03-27;
the remainder is about a renderer Android does not ship." If GL artifacts ever
matter again it will be because someone ships GL, and then the first two items
are the missing clip block and the missing depth write, not textures.

**Smallest demonstration:** n/a — see above. Do not queue a device run for this.

---

## 6. TB cache prewarm crash on settings change

**Verdict: no longer reproduces. Three of the entry's four load-bearing claims
are stale, including its "remaining risk".** Closable — with one new finding
that should be recorded before it is.

**The assert the symptom names is gone.** `accel/tcg/translator.c:309-319` now
reads:

```c
    if (unlikely(((base ^ pc) & TARGET_PAGE_MASK) != 0) ||
        unlikely(((base ^ last) & TARGET_PAGE_MASK) != 0)) {
        /* Page crossing spans more than 2 pages or memory layout
         * changed since translation started. Bail out gracefully
         * — the block will be re-translated on demand. */
        tb_unlock_pages(tb);
        tb_set_page_addr0(tb, -1);
        db->max_insns = db->num_insns;
        return false;
    }
```

replacing `assert(((base ^ pc) & TARGET_PAGE_MASK) == 0);` — changed in
**`c58db99386`, 2026-03-29**. (The comment on `translator.c:307` still says "In
the meantime, assert." and is now wrong; cosmetic.)

**And the function the symptom names is not called on Android at all.**
`tb_cache_prewarm` has exactly one call site, `accel/tcg/cpu-exec.c:1412-1423`,
guarded `#if defined(XBOX) && !defined(__ANDROID__)`. The post-flush rewarm is
likewise inert there — `accel/tcg/tb-cache-hints.c:639-647` sets
`rewarm_in_progress = false` under `#ifdef __ANDROID__` with a comment naming
the two deadlocks that forced it. Load, save and `tb_cache_lookup_tier` stay
live; **no pre-translation happens on Android**.

**The "Remaining risk" is closed.** The cache header carries a build fingerprint
since v4 — `tb-cache-hints.c:33-55` defines `tb_cache_build_hash()` over
`__DATE__ " " __TIME__`, and `tb_cache_load` rejects on mismatch at
`tb-cache-hints.c:375-381`, logging `TB cache rejected: built by different build`
to `hakuX-tb`. Landed **`5bd734b02a`, 2026-03-28**, "disable TB prewarm/rewarm on
Android, add build hash to cache". The entry's specific worry — a GLSL change not
invalidating the cache — cannot happen. *Caveat worth keeping:* the fingerprint
is that file's own compile stamp, not a content hash of the binary, so a build
that reused a cached object for `tb-cache-hints.c` would reuse the stamp. In
practice any normal rebuild recompiles it.

**What is still true:** the FP-state XOR into the game hash
(`android/app/src/main/cpp/xemu_android.cpp:1151` load, `:1173` save), and the
Clear code cache button — `activity_settings.xml:908-928` inside `section_debug`,
handler `SettingsActivity.kt:637-639`, implementation `:954-968` deleting
`tb_cache.bin` from both `filesDir/x1box/` and `getExternalFilesDir(null)/x1box/`.

**New finding, not previously recorded — the option's "OFF" is inert.**
`android/app/src/main/cpp/CMakeLists.txt:21` declares
`option(XEMU_OPT_TB_CACHE_HINTS "..." OFF)`, and the only places it is consumed
are `CMakeLists.txt:885` and `:1005`, both of the form
`$<$<BOOL:${XEMU_OPT_TB_CACHE_HINTS}>:XEMU_OPT_TB_CACHE_HINTS=1>`. There is no
`=0` counterpart, and `android/app/build.gradle.kts:41-54` never passes the flag.
So on an Android build **no macro is defined**, and all three consumers fall back
to their own `#ifndef ... #define XEMU_OPT_TB_CACHE_HINTS 1` —
`accel/tcg/tb-cache-hints.c:9-13`, `tb-cache-hints.h:20-24`,
`android/app/src/main/cpp/xemu_android.cpp:1098-1102`. **The subsystem is
compiled in and active on Android despite the option reading OFF**, and the
layout comment at `activity_settings.xml:312` ("hidden while
`XEMU_OPT_TB_CACHE_HINTS` is OFF") describes a state the build does not produce.

This is outside my territory to fix (`android/app/src/main/cpp/CMakeLists.txt`).
The precise change, for whoever is assigned it: make lines 885 and 1005 emit the
macro unconditionally with the option's value —
`XEMU_OPT_TB_CACHE_HINTS=$<IF:$<BOOL:${XEMU_OPT_TB_CACHE_HINTS}>,1,0>` — so that
"OFF" means off. Do not simply flip the option default; anyone reasoning from
"the hint system is off on Android" today is reasoning from a false premise, and
turning it genuinely off is a behaviour change that wants its own A/B.

**Tracker:** no issue; lives only in #18's table, which classified it "fork
(`XEMU_OPT_TB_CACHE_HINTS`)" — correct as to origin, wrong as to state.
**Closable within #18**, provided the CMake finding above is carried forward as
its own small issue rather than lost with it.

**Smallest demonstration:** none on device. Everything above is source, and the
cache-rejection path prints `TB cache rejected: built by different build` to
`hakuX-tb` if anyone wants to see it fire.

---

## 7. Xbox kernel crashes (BugCheck 0x1E) — game-specific freezes

**Verdict: cannot be settled without a device run, and the run is not currently
possible — the disc is not on the host, and no harness in this repo could detect
the symptom if it were.** This is the only one of the seven that is genuinely
open.

**The detector is intact.** `accel/tcg/tcg-accel-ops-mttcg.c:146-216` still
matches the halt loop by bytes — `p[0]==0xFA && p[1]==0xF4 && p[2]==0xEB &&
p[3]==0xFC` (`CLI; HLT; JMP $-2`) at `eip >= 0x80000000` — and dumps
`=== XBOX KERNEL CRASH (BugCheck) ===`, the BugCheck code from EAX, the
exception from ECX, all eight GPRs, CR0/CR2/CR3/CR4, EFLAGS/CS/DS/SS and a
`CODE[-16..+48]` hex dump under tag `hakuX-crash`. The NULL page-fault
diagnostic at `target/i386/tcg/system/excp_helper.c:647-762` also survives, with
the CALL-target scan and EBP stack walk the entry describes.

**But the harness cannot hear it.** The detector logs at priority **2
(VERBOSE)**, and the capture spec used by both `soak_title.sh` and
`dispatcher.sh:179` is
`hakuX-audio:I hakuX-audiocap:I hakuX-build:I hakuX-perf:I hakuX-pages:I hakuX:W VALIDATION:W ValidationLayer:W vulkan:W VulkanLoader:W *:S`
— **`hakuX-crash` is not in it at any level.** A soak that hit this freeze would
print the full BugCheck dump and the capture would drop every line of it. (The
app's own in-app log capture does include `hakuX-crash:V`,
`HakuXApplication.kt:31`; the dispatcher's does not.)

**And no harness could detect the symptom anyway.** `docs/testing/boot-test.sh`
classifies on three signals: `grep -c "Caught signal"` → CRASHED, `ps` liveness →
EXITED, and ≥5 `refresh no nv2a fb` → HUNG. During this freeze the process is
alive, no host signal is raised, and there *is* an nv2a framebuffer — the stale
one. **All three detectors report `RENDERING`.** `soak_title.sh` only polls `ps`,
which stays true throughout. Neither script can drive a controller, so neither
can reach a mid-game trigger point.

**No evidence survives anywhere.** `grep -rI` across the worktree returns zero
hits for `NightCaster`, `800151ed`, `0x197ED3` or `1FAD07`; the table was deleted
on 2026-09-08 in `1a89ae9336` and re-filed only inside #18's body. A search of
`/home/justin/hakux-work/` (309 entries, newest 2026-09-12 17:51) finds zero hits
for `NightCaster`, `800151ed`, `XBOX KERNEL CRASH`, `BugCheck`, `hakuX-crash` or
`Halt loop`. The only titles the harness has ever named are Galleon (the audio
and #54 arms) and Crimson Skies (a perf subject). **There is no NightCaster ISO
on this host.**

**The most recent observation is 2026-03-31**, in
`docs/investigations/freeze-analysis.md`, whose own banner says "Nothing in it
has been re-checked against the current tree." That is five and a half months
old and predates the fork.

**One genuinely untested candidate, and it is cheap.** #54 — every guest memory
barrier is elided under XBOX (`tcg/tcg-op.c:301-334`, the `#elif defined(XBOX)`
branch; `CF_PARALLEL` is never set on a single-CPU Xbox, so `tcg_gen_mb()` emits
nothing) — **landed 2026-03-19, twelve days before `freeze-analysis.md` was
written, and is not among its thirteen eliminated hypotheses.** It is therefore a
new suspect, not a re-tread.

Be careful how much weight that carries.
`docs/investigations/tcg-barriers-elided.md` retracts #54's own mechanism claim
in full: restoring every barrier left #44 at 6 of 10 failures, indistinguishable
from the ~46% base rate, at a measured **+34.1%** game frame time (52.50 ms /
18.0 gfps with `mb_emitted`=0 against 70.40 ms / 14.0 gfps with
`mb_emitted`=347,473, A/B/A/B on Galleon). The doc's standing conclusion is
"#54 remains a real latent correctness issue **with no demonstrated symptom**."
The one part of it that could reach this symptom is the sentence "guest loads
racing device writes (surface downloads, reports, notifies) stay exposed" — a
guest reading a device-written word stale, so a lookup finds an empty array.
That is the right *shape* for entry 7, and it is also the opposite kind of claim
from the entry's own attribution, which is about GPU **timing**, not ordering.
Two independent hypotheses; neither tested against this freeze.

**Tracker:** no issue of its own; #18's table marks it "unclassified", which was
and remains correct. **Not closable.** It should be split out of #18 into its own
issue so that closing #18 does not close it by accident.

**Smallest demonstration, and what it needs first.** No pgraph suite can show
this — it is a guest-kernel state reached by playing a game, and the suite does
not play games. The run needs, in order:

1. **A disc.** NightCaster, on the device. Nothing else in the corpus is known to
   reproduce it.
2. **`hakuX-crash:V` added to `LOGCAT_SPEC`** in `docs/testing/soak_title.sh` and
   `docs/testing/dispatcher.sh:179`. Without this the run cannot produce a
   result even if the freeze occurs. This is a one-line change in my own
   territory and I would have made it, except that a spec change silently alters
   every other lane's capture volume; it should be made deliberately, by the
   harness owner, as its own commit.
3. **A liveness check that is not `ps`** — a repeated-frame or halt-loop probe —
   because the process stays alive and rendering a stale frame throughout.
4. **A way to drive input to the trigger point.** Absent that, the run is a human
   at a device, not a dispatch.

The barrier arm is the cheaper half and is already built: with (1)-(4) in place,
run NightCaster on the elided binary and on the restored one from #54's A/B. If
the freeze survives a full barrier restore, ordering is out and the entry's own
timing attribution is the last hypothesis standing.

---

## The three entries still in `KNOWN_ISSUES.md`

All three are user-facing notes rather than defects, and all three are currently
accurate. No change needed.

**"Setup Wizard appears to freeze while copying the HDD image"** — entry 1 above.
Correctly marked **Fixed**, correctly kept for people on old builds.

**"Networking must be enabled for anything that uses the guest network"** —
**still true, and its own caveat is true too.** Networking is off by default and
a guest waiting on DHCP waits forever. The note's claim that the pgraph harness
no longer needs it is confirmed: `docs/testing/extract_results.py` reads the
qcow2 and walks the FATX E: partition host-side, taking its layout constants
from `android/app/src/main/cpp/xemu_fatx_import.c` rather than re-deriving them,
and emits a flat layout that `collect_results.py` consumes unchanged. No FTP, no
guest network.

**"Two builds can install side by side and are easy to confuse"** — **still
true, and the fix it describes is in place.** `android/app/build.gradle.kts:76`
sets `applicationIdSuffix = ".debug"` on top of `applicationId =
"com.jreinach.hakux"` (`:29`), and the two labels are distinct resource values —
`hakuX (debug)` at `:77`, `hakuX (fork)` at `:90`. Separate application IDs mean
genuinely separate save data, HDD images and settings, exactly as the note says.

---

## Ranking — and why the requested ranking does not apply

**Asked for: rank by how much of the remaining accuracy gap each entry
represents. The honest answer is that six of the seven represent none of it, and
the seventh cannot be measured against it.**

The accuracy gap is the corpus in
`docs/investigations/target-ranking-2026-09-12.md`: 1,444 captures,
**15,337,853 non-precision channels**, ranked suite by suite. Every entry in
that table is a rendering rule — blend, line width, bump, fog, cubemap. Not one
of the seven KNOWN_ISSUES entries appears anywhere in it, because six of them
are crashes, hangs or UI behaviour, and the measurement lane cannot express
them: the device lane is **Vulkan on Adreno 740** (`pgraph-harness.md:255`), and
the one entry that touches rendering — entry 5, GL ES texture artifacts — is
about a renderer that lane does not run.

So ranking these seven by accuracy-gap share would produce seven zeros. Ranked
instead by **what clearing them is worth to the campaign**:

| rank | entry | what the campaign gets |
|---:|---|---|
| **1** | **7 — BugCheck 0x1E** | The only entry describing the emulator running a real game wrongly, and the only one still open. It is also the only one whose *instrumentation gap* blocks other work: `hakuX-crash` is absent from `LOGCAT_SPEC`, so **any** guest-kernel crash in **any** future soak is currently invisible. That is worth fixing whether or not NightCaster is ever found. |
| **2** | **3 — VK texture LRU exhaustion** | The abort is gone but the handling is not safe: a skipped bind is marked clean (`vk/texture.c:2359`) and can leave a slot NULL that four sites dereference. A texture-heavy title is a plausible crash today, and nothing reports it. A real defect, mis-described by its own entry. |
| **3** | **6 — TB cache prewarm** | Closable, but only after recording that `XEMU_OPT_TB_CACHE_HINTS` reads OFF while compiling in at 1. Anyone who reasons about Android performance or determinism from "the hint system is off" is wrong today, and two agents have already reasoned from `#if`-guarded switches in this tree. |
| **4** | **2 — diagnostic capture** | Per-draw capture is the project's only intermediate observability, and `diag-capture-cost.md` argues correctly that its cost is why so much accuracy work needs a device trip. Making it fast is leverage on everything else; the freeze framing was hiding a tractable perf fix behind an intractable-sounding one. |
| **5** | **4 — Adreno SIGSEGV** | Pure noise removal. Closing it removes an entry that says "root cause: Unknown" about a symptom with no surviving trace, on a driver stack since measured three ways. |
| **6** | **5 — GL ES artifacts** | Pure noise removal, and closing it prevents someone spending a sweep on a renderer Android does not ship. |
| **7** | **1 — Setup Wizard** | Already fixed, already tested, already correctly described. Nothing to do. |

**What I could not settle, stated plainly.** Two things:

1. **Entry 3** needs Dead or Alive 3 on the device with texture-cache headroom
   instrumented (`NV2A_PERF_LOG`, or a counter at `vk/texture.c:1622`). The
   pgraph suite is structurally the wrong instrument — it is not a texture-count
   workload.
2. **Entry 7** needs a NightCaster disc that does not exist on this host, plus
   three harness changes before a run could even record a result. Everything
   else about it is five and a half months old.

And one thing I deliberately did not claim: entry 4's absence of SIGSEGV is
measured over 1.75 h of pgraph and short-soak execution. It is not evidence
about multi-hour gameplay, and I have not dressed it as such.

