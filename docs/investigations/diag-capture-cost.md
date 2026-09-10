# Diagnostic frame capture stalls the guest

> Rehomed from `KNOWN_ISSUES.md` when defect tracking moved to GitHub issues.
> The analysis is unchanged; only its address is. It is the corrected reading —
> the entry it replaces was wrong in both halves.

**Status:** open, unfixed. No issue filed yet.

## VERIFIED

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

## UNRESOLVED

Which of the two costs actually dominates. The row-at-a-time `fwrite` is the
cheap thing to fix and should be measured first; if the remaining cost is the
per-draw `pgraph_vk_finish`, a writer thread will not help and the answer is to
batch or sample draws instead.
