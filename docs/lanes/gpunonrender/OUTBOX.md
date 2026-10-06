# OUTBOX: gpunonrender (#433)

## 2026-10-05 16:50 PDT: (a) instrument built, control queued

- Commit 16784acb80 on lane/gpunonrender (from origin/master 8522288a77,
  fast-forward, already current). Telemetry only, off by default
  (`HAKUX_GPUXFR=1`), and `HAKUX_GPUXFR_CTRL=N` adds N bracketed 1 MiB copies per
  frame as the control.
- Files: `hw/xbox/nv2a/pgraph/vk/draw.c` (pool, brackets, readback, `xemu-xfr`
  emission), `surface.c` and `texture.c` (12 brackets, one per nondraw scope,
  plus prototypes). No new file, and `renderer.h`/`renderer.c`/`profile.c` are
  untouched, so no grant was needed. The category is a name string, not an enum,
  because a shared enum would need a header change outside territory.
- Desktop build: not checked. This host has no meson or ninja on PATH and the
  headers sit outside the sandbox, so I could not compile. The change was read
  line by line; the Android perflog build through the dispatcher is the first
  compile. Expect a fix round if it fails.
- Control arms queued on Nova, NG Black, route bb-ngb, 150 s, perflog,
  `PERF_REGIMEN=default`, at the committed ref:
  - `1-1791243663-lane.gpunonrender-551868`: `HAKUX_GPUXFR=1`
  - `1-1791243666-lane.gpunonrender-551969`: `HAKUX_GPUXFR=1 HAKUX_GPUXFR_CTRL=16`
  Nova is screening-only until 22:00 PDT unless a perf request is queued there
  by lane.local; these are queued as release-tier 0.5 requests, so the
  dispatcher decides when they run.
- Pass and fail criteria for the control are written in
  `docs/lanes/gpunonrender/NOTES.md` ("Control") before the readings.
- Gap found while reading: the frame-end staging copies (`sync_staging_buffer`,
  `flush_memory_buffer`) are recorded into the aux command buffer, which
  `gpu_nonrender_ms` does not cover. Its time is not measured yet (NOTES, gap 1).
- Spend: I cannot read the session's spend from here, so I cannot report a figure.
  The work so far is a read of the render and nondraw paths and one instrument;
  I have not run anything on a device yet.

## 2026-10-05 17:55 PDT (attempt 2): the control arms ran; their xemu-xfr lines were dropped

- Attempt 1's two arms both ran to DONE on apk fc4e0d3d7a20. Their `xemu-xfr`
  lines never reached logcat: the perflog logcat filter is a tag list ending in
  `*:S`, and `xemu-xfr` is not on it. So attempt 1 had no per-category control
  reading. I should have checked the filter before going to WAITING.
- Fix, commit 9609d0299f: the two `xemu-xfr` lines are logged under the
  `xemu-gpu` tag (in the spec) with the `xemu-xfr` prefix. Adding `xemu-xfr:I`
  to the spec is lane.local's; I have not asked for it since the prefix route
  works without it.
- Read from the attempt-1 `xemu-gpu` lines (NG Black, menu frames): Xfr
  (`gpu_nonrender_ms`) median 0.40 ms in C0 and 1.10 ms in C16; Rnd unchanged
  at 0.30. The rise is the control, about 0.044 ms per copy. Recorded in NOTES.md.
- Re-run queued at 9609d0299f, same route and env: C0 1-1791247925-lane.gpunonrender-863985,
  C16 1-1791247926-lane.gpunonrender-864108. The verdict waits on them.
- The route is the intro-first route; gameplay starts about 150-200 s in, so the
  control reads menu frames. That is fine for the control. The title soaks need
  a longer run (300-360 s).
- Spend: not readable from here, so no figure.

## 2026-10-05 21:52 PDT (attempt 3): control verdict; C0 baseline re-queued

- The attempt-2 C16 re-run (864108) read cleanly: `ctrl` 0.68 ms per frame,
  stable across 105 windows (median, p90 and max 0.68 to 0.69), so 0.043 ms per
  1 MiB copy. The categories plus the residual reconcile to `nr` within 0.07 ms.
  The tag fix works: 210 `xemu-xfr` lines reached logcat.
- The attempt-2 C0 re-run (863985) was voided before any frame: `ROUTE NOT
  PLAYED`, not-foreground on Nova display 0, no input sent. A focus-at-start
  failure, not a performance cause. Re-queued once at the same ref, route, env
  and device: `1-1791262296-lane.gpunonrender-1610133`.
- So the baseline half of the control (C0 reads no `ctrl`; other categories and
  the residual do not move against C0) is not read yet. It waits on that run.
  The `nr` rise (+0.70 ms against `ctrl` 0.68 ms) rests on attempt 1's xemu-gpu
  pair only.
- Milestone (a) is reached in part: the instrument reads the known change. The
  C0 baseline is the open half. Verdict and tables are in NOTES.md, "Control
  verdict (attempt 3)".
- Nothing merged. The branch stays at 9609d0299f for the control; it is 21
  commits behind origin/master and is merged before the title runs.
- Spend: not readable from here, so no figure.

## Next

Milestone (a) completes when the C0 baseline lands. Then milestone (b): the first
title's category table. The overhead arm (HAKUX_GPUXFR unset) goes with the title
batch.
