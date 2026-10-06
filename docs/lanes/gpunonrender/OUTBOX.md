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

## 2026-10-05 22:52 PDT (attempt 4): C0 baseline read; control passes

- C0 `1-1791262296-lane.gpunonrender-1610133` finished DONE, not voided: the route
  played (menus, cutscenes, one black frame). Same apk, ref and env as C16
  864108 except `CTRL=16`.
- `ctrl` reads 0 in all 108 C0 windows. C16 reads 0.68 ms. `nr` moves from 0.62
  (C0 window median) to 1.30 (C16), +0.68, which matches `ctrl`. `download` is
  0.56 in C0 and 0.57 in C16. `res` is 0.06 and 0.07. The control criteria all
  pass (NOTES.md, "Control verdict (attempt 4)").
- Milestone (a) is complete: the instrument reads a known change against a baseline.
- Not yet done: the overhead arm (HAKUX_GPUXFR unset), and gameplay. The control
  runs are menu and cutscene frames. Both belong to the title batch.
- No re-run is needed for the control. WAITING is cleared. No run is queued.
- The title batch needs origin/master merged first (the branch is 21 commits behind).
  I have not merged it, since that changes the tree the title runs use and the
  overnight brief says to stay on the branch.
- Spend: not readable from here, so no figure.

## 2026-10-06 01:10 PDT (attempt 5): scope (A) built, four Nova runs queued

- origin/master merged (4cb9d98c67).
- (A), commit 5eef1dacd9, surface.c only, `HAKUX_SURFSPLICE=1`, off by default.
  When a binding uploads from VRAM bytes that a pending download is about to write,
  the GPU copies those bytes from the download's staging rows into the upload's
  staging. Both buffers hold guest VRAM bytes. The update then needs no finish and
  no wait. The round trip is removed, not deferred: the downloads complete where any
  other reader completes them today. These cases fall back to today's completion:
  swizzled downloads, already-submitted batches, and CPU-unswizzled uploads.
  `[sdcall]` gains `spl=def/up/dl/kB/cmpl`. It compiles clean with NDK clang,
  perflog and plain.
- Forza's remaining forced finishes are fresh zeta bindings at an aliased address
  (forza414 NOTES 29/42). Their old bytes are read, so the upload is needed. That
  is why the fix copies on the GPU rather than skipping the upload.
- Queued at 5eef1dacd9, Nova, perflog, `HAKUX_GPUXFR=1` in every arm. The expected
  results were written in NOTES.md before queueing.
  - F0 Forza (splice off) `1-1791274121-lane.gpunonrender-2621218`
  - F1 Forza (`HAKUX_SURFSPLICE=1`) `1-1791274126-lane.gpunonrender-2621918`
  - S0 Spider-Man 2 `1-1791274133-lane.gpunonrender-2624513`
  - M0 Midnight Club II `1-1791274137-lane.gpunonrender-2624798`
- Spider-Man 2 and Midnight Club II had no route. Their routes
  (`docs/lanes/gpunonrender/routes/`) are built from pathfind's sweep runs of
  10-05 (steps2route.py). Both titles are on the Nova now (pathfind ran them
  there), though the 10-04 titlepush listing still puts them on the Thor.
- (B) is read from `[sdcall]`, not only from the GPU categories. A round trip's cost
  is the PFIFO thread waiting on the fence, and `download`/`surf_up` hold only the
  copies' GPU time.
- **Ask, lane.local:** (C) needs `hw/xbox/nv2a/pgraph/vk/reports.c` (held by
  lane.accuracy804) and `hw/xbox/nv2a/pfifo.c` (held by lane.vcpusleep). Please
  grant them to lane.gpunonrender when those rows are released. Until then (C)
  is not started.
- Spend: not readable from this session.

## Next

| candidate | P | win | cost |
|---|---|---|---|
| (A) splice on Forza (F0/F1 queued) | 0.45. For: it removes the finish and the wait, not just the completion site. Against: forza414 42 saw a removed finish's wait reappear at the next sync point | Forza 27 -> 30 fps if >= 3.6 of the 12.2 ms leaves the PFIFO thread | done; two Nova runs |
| (A) on Spider-Man 2 / Midnight Club II | unknown until S0/M0 read `[sdcall]` | up to 2 more titles | one splice arm each if (B) says yes |
| (C) Simpsons, pfifo.lock across the STALLED finish's fence wait | 0.5 (frametrace) | 40.9 -> ~60 fps | waits on the reports.c/pfifo.c grant |
| the original six-title category study | 0.9 that it names the largest category | targets 5-18 ms/frame on six titles | six Nova/Thor runs, after (A)/(B) |

WAITING lists the four runs.
