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

## 2026-10-06 04:45 PDT (attempt 6): F0/F1/S0/M0 read; what `gpu_nonrender_ms` is; (C) re-scoped; five Nova runs queued

- Attempt 5 ended on a WAITING for four runs, which is a finished wait. All
  four ran DONE between 03:00 and 03:53. Verdicts are in NOTES.md, "The four
  runs read (attempt 6)".
- **(A) Forza splice:**
  - Mechanism holds, and P1 holds: `surfupd` finishes go from 2.00 to 0.00
    per frame.
  - **P2 fails.** The all-caller wait is 24.1 ms/frame without the splice
    and 26.3 with it. The wait moved to `range`, the texture bind's
    surface scan at texture.c:2100 (8.1 to 19.3 ms; `txw scan` 8.2 to
    19.4).
  - So the bytes are read by a texture through VRAM. (A) is correct but is
    not Forza's lever, and it stays default off.
- **(B):**
  - Spider-Man 2 meets the "(A) reaches it" rule: `surfupd` 6.0 ms/frame,
    2.5 per frame, all `stale`. A splice arm, S1, is queued.
  - Midnight Club II does not: it has no `surfupd`, and its 8.0 ms/frame
    is in `range`.
  - `range` (texture.c:2100) is the caller common to Forza-with-splice and
    MC2.
- **`xemu-xfr` is per command buffer, `xemu-gpu` per frame.** Scaled by
  CBs per frame, they agree on all four runs. The control verdict stands,
  because `ctrl` and `nr` are both per CB.
- **Milestone (b), the category tables:**
  - The residual is 34-83% of `nr` (Spider-Man 2: 83%). By the decision
    rules the tables are incomplete.
  - The reason is found in Turnip's source (tu_query_pool.cc:2108). A
    timestamp written inside a render pass is replayed per tile, and the
    last tile wins. Our render-pass stamps are inside the pass, so in a GMEM
    pass "Rnd" is the last tile's draws only. `gpu_nonrender_ms` therefore
    holds binning, the other tiles and the tile loads and stores.
  - That fits belowbar1005's Xfr/Tot of about 0.5 on NG Black, AUF, Otogi,
    DOA3 and Black (two bins, one seen). It also fits TU_DEBUG=sysmem's +8
    gfps on DOA/AUF.
  - **The premise of the brief, that half the GPU frame is not render
    passes, is very likely an artifact of where the stamps sit.** This is a
    hypothesis; X0 measures it.
- **A shipped-build cost found:** the GPU timestamp pool is on in every build
  (renderer.c:490-506, no `NV2A_PERF_LOG` guard), and only telemetry reads it.
  Its in-pass end stamp is BOTTOM_OF_PIPE, which Turnip precedes with a
  wait-for-idle, once per tile per render pass. X1 measures its cost.
- **New in d946e1ba44 (draw.c, defaults unchanged):** outer render-pass stamps
  under `HAKUX_GPUXFR=1` (a new `xemu-xfr XFR rp` line), and
  `HAKUX_GPUTS_INRP=0`.
- **(C) re-scoped:**
  - Releasing pfifo.lock across the STALLED finish's fence wait frees the
    vCPU in the same way vcpusleep's posted DMA_PUT did. That change
    (c2dfca18a1) ran on Simpsons and was reverted (f6ac723228): fps fell
    from 40.0 to 36-38, and the PFIFO's slot-fence wait grew from 8 to 21
    ms a frame. So the lock is not the pacer; the rotation fence wait is,
    about 8.8 times a frame with the GPU 24% busy. P(C as briefed) is about
    0.1. Not built.
  - **(C') instead, 6f6af20088 (reports.c only, default off):**
    `HAKUX_STALLFIN=reports` submits at a caught-up FIFO only when a zpass
    report is queued. That is the only guest-visible value written after a
    finish: semaphores are written at the method, and surface reads have
    their own finishes. This removes the per-catch-up rotation and its fence
    wait. Simpsons K0/K1 A/B is queued.
- **Queued, Nova, expected results in NOTES.md before queueing:**
  - X0 NG Black outer stamps `1-1791284834-lane.gpunonrender-3228352`
  - X1 NG Black `HAKUX_GPUTS_INRP=0` `1-1791284845-lane.gpunonrender-3230278`
  - S1 Spider-Man 2 splice `1-1791284850-lane.gpunonrender-3230633`
  - K0 Simpsons baseline `1-1791285173-lane.gpunonrender-3251320`
  - K1 Simpsons `HAKUX_STALLFIN=reports` `1-1791285177-lane.gpunonrender-3251434`
- About 42 min of Nova time. That is over the 30-min gate, so the lane's
  pilot verdict (F0/F1/S0/M0 reviewed) is recorded in
  `dispatch/pilots/lane.gpunonrender.ok`.
- This is more than the PM's 3-5 runs for (A)-(C). X0/X1 belong to the
  brief's own question, S1 is (B)'s pre-stated next run, and K0/K1 are (C).
- Spend: not readable from this session.

## Next

| candidate | P | win | cost |
|---|---|---|---|
| (C') Simpsons `HAKUX_STALLFIN=reports` (K0/K1 queued) | 0.4. For: simp2 measured the rotation fence wait as the pacer once the vCPU was freed (8 to 21 ms/frame), and this removes most rotations. Against: the guest's own 16.2 ms sits just under the 17.9 ms deadline, and an unknown report-free guest dependency on a submit would show as a hang | Simpsons 40.9 to ~50-60 fps (ledger title, the owner's 60-fps direction) | done; two runs queued |
| In-pass stamp cost in the shipped build (X1) | 0.3 that it is at least 1 ms/frame (a wait-for-idle per tile per pass on every GMEM pass; size unknown) | every GMEM title, every frame; if real, a fix is a few lines (gate the stamps on `NV2A_PERF_LOG`, or move them outside the pass) | one A/B, queued |
| Re-read the six-title "non-render" study with the outer stamps (X0 first) | 0.8 that X0 shows most of `nr` is render-pass work | it decides whether any copy/upload fix can win the 10-18 ms the survey promised (probably not), and points the GPU work at tile load/store and binning (GMEM vs sysmem per pass, lane.rendermode474's area) | X0 queued; the other titles after it |
| Forza/MC2: texture.c:2100 range scan (texture reads a rendered surface through VRAM) | 0.35, needs one counter first (why the bind does not take the surface-to-texture path) | Forza 8-19 ms/frame of PFIFO wait, MC2 8.0 | a counter, then the fix lane |
| (A) on Spider-Man 2 (S1 queued) | 0.25 after F1 (the wait may move as on Forza) | up to 6 ms/frame, 26.8 to ~30 fps | one run, queued |

## 2026-10-06 05:10 PDT (attempt 7): X0/X1/S1/K0/K1 read; two confirmation runs queued

- Attempt 6 ended on a WAITING for five runs. That is a finished wait. All five
  ran DONE on the Nova between 04:12 and 04:50. Verdicts are in NOTES.md, "The
  five runs read (attempt 7)". origin/master had not moved, so there was
  nothing to merge.
- **X0, NG Black, outer render-pass stamps: the brief's premise is a stamp
  artifact.**
  - Of `gpu_nonrender_ms`'s 10.75 ms per frame, 10.36 (96%) is render-pass work
    that the in-pass stamps miss. That is Turnip's binning, the other tiles,
    and the tile loads and stores.
  - The GPU's time outside every render pass is **0.39 ms per frame**:
    download 0.35, s2t 0.01, unbracketed 0.02 (5%, under the 15% bar).
  - The GPU frame is 97% render passes, at 680 MHz in both arms.
  - No copy or upload category can win the 10-18 ms the survey promised.
- **X1:** removing the in-pass stamp pair moves the per-pass span by +0.5%.
  Nothing measurable, so the shipped-build stamp cost is not a candidate.
- **S1, Spider-Man 2 splice:** never engaged (`spl def` 0). The eligibility
  check refused every update, and the `surfupd` wait is unchanged (6.0 to 6.3
  ms). The refusal reason is not counted. (A) does not reach Spider-Man 2 as
  built.
- **K0/K1, Simpsons `HAKUX_STALLFIN=reports`: refuted.**
  - Mechanism holds: STALLED finishes go from 5.36 to 1.05 per frame.
  - **fps fell from 30.3 to 25.8.** The vCPU's DMA_PUT wait on pfifo.lock grew
    by 4.3 ms per frame, and the GPU frame grew 6.1 ms at the same 401 MHz.
  - On this route the rotation wait was only ~0.37 ms per frame to begin with.
  - Both halves of (C) have now been tried (simp2, the lock; K1, the submit),
    and both lost fps. It stays off.
- **Milestone (b)/(c), partial:** NG Black's table is complete under the outer
  stamps. Two confirmation runs are queued, same build (d946e1ba44),
  `HAKUX_GPUXFR=1`, expected results in NOTES.md:
  - T0 ToeJam & Earl III (largest `nr`, 17.9; lowest Xfr/Tot):
    `1-1791288045-lane.gpunonrender-3440051`, 300 s.
  - D0 DOA3 (dojo): `1-1791288049-lane.gpunonrender-3440825`, 480 s.
  - Otogi is on the Thor (out of service, fan). AUF and DOA Ultimate have no
    route.
  - About 23 min of Nova time.
- New file: `docs/lanes/gpunonrender/routes/gnr-toejam.route` is
  uberdefault569's route plus the `# state: first-run` line that request.sh
  now requires.
- Spend: not readable from this session.

## Next

| candidate | P | win | cost |
|---|---|---|---|
| Render-pass cost on the tiler: per pass, GMEM vs sysmem, bin count, attachment load/store ops (draw.c render-pass begin and the render-pass create info; lane.rendermode474's area) | 0.35: X0 puts 97% of NG Black's GPU frame in render passes; TU_DEBUG=sysmem gave +8 gfps on DOA/AUF (flip474) | NG Black 3-6 ms off a 23 ms GPU frame (28.5+ in most windows); every GMEM-heavy title if T0/D0 agree | a per-pass census (telemetry), one NG Black run, then the fix lane |
| Forza/MC2 texture.c:2100 range scan | 0.35 | Forza 8-19 ms/frame PFIFO wait, MC2 8.0 | a counter, then the fix lane |
| (A) on Spider-Man 2 | 0.15 (gate refused all; the wait may move as on Forza) | up to 6 ms/frame, one title | a refusal counter, one run, maybe a GPU swizzle |
| Simpsons STALLED submit or lock | 0.05 (both halves refuted) | none expected | none |

## 2026-10-06 05:40 PDT (attempt 8): milestone (c); the GPU stamp double count found and fixed

- Attempt 7 ended on a WAITING for T0/D0. That is a finished wait. Both ran
  DONE, and hostops' restore ran after them. origin/master had not moved.
- **T0 (ToeJam & Earl III) and D0 (DOA3): the artifact holds.**
  - 94-98% of `gpu_nonrender_ms` is render-pass work that the in-pass stamps
    miss, as on NG Black X0.
  - The real GPU time between render passes is 0.26-0.52 ms a frame, and
    `download` (site 587) is its largest part on every title.
- **Milestone (c), the brief's decision rule:** judged "not". On NG Black,
  ToeJam and DOA3 the largest category is 2-5% of `nr`.
  - Otogi (Thor, fan), AUF and DOA Ultimate (no route) were not run. The rule
    could only flip if all three of them broke the driver mechanism that gave
    94-98% on the three measured titles.
- **Found and fixed, 5c35880d0a (draw.c, telemetry only): the GPU timestamp
  stats counted some command buffers twice.**
  - The mechanism: a non-deferred PFIFO finish reads its slot back
    (draw.c:4742). The render thread had marked the slot submitted
    (render_thread.c:153), so frame rotation read the same stamps again
    (draw.c:4803-4807).
  - The fix: a slot's stamps are read once per recording, and skipped
    readbacks are counted as `dup` on the `XFR rp` line.
  - **T1** (`1-1791289531-lane.gpunonrender-3548254`, ToeJam, same route and
    scene as T0): every leg of the known answer, written before the run,
    passes.
    - `dup` 1.00 per frame against 1.01 `sd` finishes.
    - 2.00 readbacks per frame for 2.09 finishes.
    - Tot fell from 48.5 to 25.5 ms. The drop (23.04 ms) equals the skipped
      span (23.01 ms).
  - **ToeJam is not GPU-bound on this scene.** Its GPU is busy 25.5 ms of a
    38.8 ms frame, at 401 MHz. belowbar1005's 52.3 Tot / 17.9 `nr` were about
    twice the real values.
  - **18 of belowbar1005's 33 survey titles carry this over-count** (any `sd`
    finish). These include Top Spin, Midtown Madness 3, Conker, Halo 2,
    Forza, Nightfire, Otogi and ToeJam; the full table is in NOTES.md.
  - NG Black, DOA3, AUF and DOA Ultimate do not carry it. Any "GPU-bound"
    judgement from `xemu-gpu` Tot on an affected title needs a re-read on a
    build with the fix.
  - Lanes reading `xemu-gpu` or the frametrace record's `gpu` field
    (frametrace, the fps chain) should know this.
- Nova runs this attempt: T1 (300 s) and a 60 s master restore after it (DONE).
- Spend: not readable from this session.

## Next

| candidate | P | win | cost |
|---|---|---|---|
| Render-pass load/store census, then the fix (brief in NOTES.md "Brief for the next lane"): LOAD of every initialised surface even when the pass starts with a full clear (draw.c:3567-3593); STORE of every depth/stencil attachment (draw.c:1774-1794) | 0.35 | NG Black 3-6 ms off a 23 ms GPU frame (GPU-bound at 680 MHz); DOA3's fight (GPU 84% busy at 680) | one draw.c telemetry commit, two Nova runs (NG Black, DOA3), then the fix lane |
| Re-read "GPU-bound" on the 18 affected survey titles with the fix (one perflog soak each, no code) | 0.6 that at least one more title, like ToeJam, turns out not GPU-bound | decides which titles a GPU-side fix can help at all | 18 soaks; a sweep-tier batch after a pilot of two |
| What paces ToeJam at 25 fps with the GPU 66% busy | unmeasured | one survey title | a frametrace capture |
| Forza/MC2 texture.c:2100 range scan | 0.35 | Forza 8-19 ms/frame PFIFO wait, MC2 8.0 | a counter, then the fix lane |

## 2026-10-06 06:35 PDT (attempt 8): PR ready

- A release build of the lane branch did not compile. texture.c declared the
  `xemu-xfr` bracket calls only inside its perflog block, and every device run
  so far was perflog. Fixed in ddfea13092. All four lane TUs now compile
  under the release NDK line, with and without `NV2A_PERF_LOG`.
- Jobs selftest: 3088 passed, 0 failed. preflight passed. PR.md is
  `State: ready`. The full release APK is forge-android's to build.
- Nothing of this lane is queued or running. The Nova is on master (the
  restore after T1 ran DONE).

## 2026-10-06 06:45 PDT (attempt 9): nothing left; ready for the fold

- Resumed 6 minutes after attempt 8 marked the PR ready. No new work:
  origin/master is still c3a0c70ace, the branch is pushed (8cb3cdf0e7 plus
  this note), and nothing of this lane is queued or running on either device.
- The PR stays `State: ready`. The next step is the fold, then the
  render-pass load/store census lane (NOTES.md "Brief for the next lane").
- Spend: not readable from this session.

## 2026-10-06 07:00 PDT (attempt 10): WAITING fold; nothing else

- Resumed at 06:55 PDT by the lanewaker keepalive pass. That pass resumes a
  keepalive-listed lane whose branch has no WAITING file, even when PR.md is
  `State: ready`. No new work. origin/master is still c3a0c70ace, and nothing
  of this lane is queued or running.
- Added `docs/lanes/gpunonrender/WAITING` with `fold gpunonrender`, so the
  keepalive pass leaves the lane stopped until the fold.
- For lane.local: a keepalive entry for a lane whose PR.md is `State: ready`
  resumes it every 15 min with nothing to do. lanewaker's keepalive pass could
  skip `State: ready` the way its stranded pass already does.
- Spend: not readable from this session.

## 2026-10-06 10:45 PDT (attempt 11): census done; no load/store A/B; PR ready

- Telemetry commit f4ffe285e7 (draw.c, surface.c, texture.c; `HAKUX_GPUXFR=1`,
  default off): the render-pass census, `xemu-xfr XFR rpc` lines.
- N0 NG Black `1-1791306758-lane.gpunonrender-630725` and D1 DOA3
  `1-1791306763-lane.gpunonrender-631156`, apk 281bf2515bb8 (dispatcher:
  `shader cache cleared: apk 6beaa5ac1cdd -> 281bf2515bb8`). Restore
  `1-1791306764-lane.gpunonrender-631498` ran DONE at 0342eba317 (apk
  ad6f37a2f087, empty env): the Nova is on master. Nothing of this lane is
  queued or running.
- Rule written before the runs: S (avoidable passes carry at least 30% of the
  outer span) and B (avoidable MiB x 0.043 ms at least 1.0 ms a frame). S holds
  (82%, 93%), **B fails on both** (0.39 ms NG Black, 0.38 ms DOA3 fight, over
  every pass). No load/store fix, no A/B.
- The cost is the GMEM scene passes outside their last tile: 11.7 ms a frame on
  NG Black, 19.3 ms on the DOA3 fight (one ~700-draw pass at in/out 0.50, DOA
  Ultimate's replay pattern).
- DOA3's fight window is 60 s, not 180: the route loses the fight in a minute
  (as in D0). Its structure matches D0's fight; the attract screens are read
  beside it.

| candidate (for lane.rendermode474's area) | P | win | cost |
|---|---|---|---|
| DOA3 `54430001` to sysmem in `kTitleRenderModes` after an A/B on `bb-doa3` | 0.55 | fight GPU 38.5 toward ~29 ms; 22 toward ~28 gfps | one A/B pair (default vs `TU_DEBUG=sysmem`, census on), then a table line |
| Per-pass mode in the Turnip fork's autotune (many draws, few bins: sysmem) | 0.3 | every replay-bound title, size unknown | a fork change plus a per-pass bin count |
| NG Black `5443000D` to sysmem after an A/B on `bb-ngb` | 0.3 | up to ~10 ms of a 24.6 ms GPU frame; 36 toward ~45 gfps | one A/B pair |

- Spend: not readable from this session.
- PR.md `State: ready` at c3dd710a53 (pushed). preflight: every gate ok but
  `coverage`, which fails on open issues #852-#857 having no board row
  (lane.local: those rows are board files). WAITING is `fold gpunonrender`.

## 2026-10-06 13:20 PDT (attempt 12): scope (D) P1 DOA3 read; sysmem halves the GPU frame on matched scenes

- Merged origin/master (fast-forward to bf85412b88); WAITING removed. The
  census is on master, so every arm runs master's perflog build with `--env`.
- Brief premise corrected: the table is `kTitleRenderModes` in
  xemu_android.cpp (there is no TitleDefaults.kt), and **DOA Ultimate is
  already `sysmem` there**. Its pair is `TU_DEBUG=gmem` vs the table.
- P1 DOA3 (`-1511368` sysmem, `-1511854` GMEM; apk 4028728fcc5a,
  `shader cache cleared: apk ad6f37a2f087 -> 4028728fcc5a`). Story mode drew
  a different stage per run, and the driver ran P1-G's snow fight sysmem by
  itself, so the fight comparison is void. The attract demo is deterministic
  (same draw-count sequence in D1, P1-G and P1-S):

| matched segment | GMEM gfps / Tot | sysmem gfps / Tot |
|---|---|---|
| ~430 draws/CB | 31-34 / 27.6 ms | 59 (vsync) / 13.7 ms |
| ~800 draws/CB | 21-22 / 35.8-44.7 ms | 52.5 / 16.3 ms |

  GMEM's last tile (13.5 ms) equals the whole sysmem pass (13.5 ms): two
  bins, and each bin replays the whole draw stream. Region check passes.
- **New top candidate**: gmem474 found that `TU_AUTOTUNE_ALGO=profiled`
  picks sysmem by itself on DOA Ultimate (15.6 -> 32.4 gfps) and AUF
  (19 -> 23). It keeps Kabuki at 59.9 with no stall, and matches Crimson's
  fps. An app default of `profiled` would reach every replay-bound title
  without a fork change. Added one profiled arm each on DOA3 and NG Black.
- Queued (Nova, study priority): P2-S `1-1791317653-lane.gpunonrender-1627450`
  (running), P2-G `-1627551`, P3-G `-1629224`, P3-S `-1629401`, restore
  `-1629543`, P1-P `-1634952`, P2-P `-1635052`, restore
  `1-1791317787-lane.gpunonrender-1635156` (last). Pilot verdict rewritten in
  `pilots/lane.gpunonrender.ok`.
- For lane.local to file (no tracker access from here): "GMEM scene passes
  replay the whole draw stream per bin on Turnip (DOA3: 2 bins, GPU frame 2x
  sysmem's); the `bandwidth` autotune sends the heaviest passes to GMEM".
  Evidence: NOTES.md "P1 read".
- Spend: not readable from this session.

## 2026-10-06 14:20 PDT (attempt 13): P2/P3/P1-P read; WAITING on the parked P2-P

- Merged origin/master (6cef37f426). P2 NG Black, P3 DOA Ultimate and P1-P
  DOA3 profiled are read in NOTES.md. Sysmem wins on all three titles with
  pixels intact:

| title | GMEM gfps / Tot | sysmem gfps / Tot | profiled |
|---|---|---|---|
| DOA3, matched attract A+B | 31-34 / 27.6 ms | 59 / 13.7 | 59 / 13.8 (sysmem chosen, cold cache) |
| NG Black, matched intro | 32.5 / 25.0 | 59 / 13.4 | parked |
| DOA Ultimate, fight | 20 / 44.3 | 42-43 / 21.5 (the shipped row) | (gmem474: 32.4 gfps) |

- **`profiled` matches the best mode on DOA3** (within 1-3% of sysmem's Tot,
  on the rule written before queueing). If P2-P matches on NG Black, the next
  step is an app default of `TU_AUTOTUNE_ALGO=profiled` with a guard list,
  then a fleet A/B. The brief is in NOTES.md ("Brief for the next lane"):
  P 0.45, a one-line change in xemu_android.cpp (a grant), ~4 h of Nova
  time. Fallbacks, which do not wait on it: a DOA3 sysmem table line (P 0.85,
  no occlusion queries) and an NG Black line (P 0.75; NG Black issues
  queries in both modes, so the line needs the #527 ruling hostops gave DOA
  Ultimate).
- Nova: nothing of this lane is queued or running. Restore
  `1-1791317787-lane.gpunonrender-1635156` ran DONE at 13:51 (apk
  ca290378e862). The dispatcher then cleared to 35ef582d81d5 for the next
  request.
- **For lane.local at 22:00**: P2-P (`1-1791317784-lane.gpunonrender-1635052`,
  env `TU_AUTOTUNE_ALGO=profiled`, `HAKUX_GPUXFR=1`) has no restore after
  it. The restore -1635156 was spent on P1-P. Please move a 60 s master
  restore with an empty env back with it, or I queue one when P2-P's DONE
  resumes me.
- For lane.local to file (tracker): "Turnip `bandwidth` autotune sends
  two-bin replay-bound passes to GMEM; each bin replays the whole draw
  stream (DOA3, NG Black, DOA Ultimate: GMEM GPU frame 2x sysmem's)". The
  evidence is in NOTES.md, the P1/P2/P3 reads.
- WAITING: `run 1-1791317784-lane.gpunonrender-1635052`.
- Spend: not readable from this session.
