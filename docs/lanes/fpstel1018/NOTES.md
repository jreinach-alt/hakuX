# fpstel1018: Forza and Buffy missed the bar -- decompose the frame, name the lever

Issue #433. Offline analysis only, no device time. Two finished perflog runs:

- Forza Motorsport (4D53006E), `forza-soak1010`:
  `/home/justin/hakux-work/dispatch/results/z-1792324127-lanelocal-1592789/`
  verdict 17.5% of gameplay >=30fps (bar 90%).
- Buffy the Vampire Slayer (45410012), `buffy.returning`:
  `/home/justin/hakux-work/dispatch/results/z-1792324128-lanelocal-1592854/`
  verdict 73.9% of gameplay >=30fps (bar 90%).

Both read-only; nothing under either result dir was edited.

## Step 0: Already-tried

| Title | Already tried | Source | Outcome | Do not re-propose |
|---|---|---|---|---|
| Forza | SURFACE_DOWN uncoalesced-finish coalescing (`surface_update_may_defer_downloads`, 94f002d309) | forza414 NOTES | shipped, fps-refuted | cutting sync-point *count* without pricing the wait left after the last one |
| Forza | Vulkan `cleared` flag after a full clear (`pgraph_vk_clear_surface`, vk/draw.c hunk 1, 51721e36aa) | forza414 NOTES | shipped, mechanically correct (evictions -> 0), fps flat on the registered window | the clear/swizzle round-trip fix alone |
| Forza | small-target full-clear forced-upload skip (`surface_drop_covered_upload`, hunk 5, b991fb4c21) | forza414 NOTES §"hunk 5" | shipped, PASS, "fps does not move: 9.0 vs 9.0" | hunk 5 as an fps lever |
| Forza | uniform-hash skip part (a) (79f0102478) | forza414 NOTES | shipped, pixel-safe, inert for fps on Blinx pilot | re-measuring part (a) alone |
| Forza | RenderCommandSnapshot copy removal (hunk 3, 72de98abd1) | forza414 NOTES | real win, but measured on Blinx, not confirmed as Forza's bound | claiming it as Forza's fix without a Forza measurement |
| Forza | flip pre-download / deferred-download-completion branch (hunk 4/O1, ee830484bb, 32657e9719; lane.flip474) | forza414 NOTES | shipped, real wins on DOA/AUF; Forza-specific effect unconfirmed | assuming it already fixed Forza |
| Forza | #488 NOTIFY handler (pgraph.c, methods.h.inc, nv2a_regs.h) | forza414 NOTES §23 (merge of 38e33bae67) | unrelated: touches neither vk/draw.c nor vk/surface.c, confirmed by forza414's own merge-arm (no line either hunk touches changed) | treating #488 as a performance change at all |
| Forza | the in-race fps decay (29fps -> 3fps standing still) | forza414 NOTES §42 (final section) | **never fixed; still the open item.** Original (non-perflog) measurement: a discrete regime step at ~race-time 48.5s where guest CPU time/frame rises ~5x and TB-invalidate/"slow stores" rise ~4x while GPU-side work rises only ~1.1-1.3x -- i.e. guest-CPU-driven, not a draw-count/GPU-load increase. Did not reproduce on a later perflog soak (ran clean). | -- (this is the one still-open lever to build on, not avoid) |
| Buffy | #804 fence wait (`pgraph_vk_process_pending_reports_internal`, hw/xbox/nv2a/pgraph/vk/reports.c) | belowbar1005 NOTES | refuted: proven inert/non-blocking for Buffy (also NG Black, DOA3) | re-raising #804 for Buffy |
| Buffy | #474 pgraph.lock wait (`[lock474]`) | belowbar1005 NOTES (next-step, never run) + this lane's `lockw` column | belowbar1005 left "split the sleep by register" as an open next step, never completed. This lane's own perflog pass shows `lockw` ~0.01-0.02ms across every group on both titles -- directly measured near-zero, not just unconfirmed. | proposing #474/lock474 as Buffy's or Forza's cause |
| both | surface-as-texture copy/bind path (gta3fps1017/1017b, `pgraph_vk_bind_textures`, `bind_surface_as_texture`, `copy_surface_to_texture`) | gta3fps1017b NOTES; this lane's own logcat grep | checked directly against both runs' own `hakuX-stall` `txw[...]` lines: `bt` (bind_textures wall time) is 0.03-0.4ms per ~2s window and `cp` (copy_surface_to_texture) is 0.00/0.00 throughout, on both Forza and Buffy -- the S2T copy path is not exercised by either title in these runs | proposing the S2T lever for either title; it is answered by their own telemetry, not absent evidence |
| cross-title | GPU non-render time (`gpu_nonrender_ms`/Xfr) cross-title ranking (`xfrsurvey.tsv`) | belowbar1005 NOTES | established as often ~50% of GPU time on *other* titles (NG Black, DOA3, AUF, Otogi, ...); not re-run here | treating that ranking as if it included Forza/Buffy -- it didn't |
| n/a | cloud-286 `decompose286.py` | cloud-286 NOTES | a decomposition method for 3D-primitive pixel accuracy (AA/smoothing), not fps | reusing it as an fps tool |

Reading also done: near30/NOTES.md (decompose.py's own precedent lane: the
Tron "gbusy==F always, use v_run/Ri instead" rule, and the Blinx2 ocean-dip /
first-appearance-hitch structural analogs used below) and vcpuwait433/
decompose.py itself (the decomposer, read as reference, not modified).

Stop rule acknowledged: the same analysis failure twice for one cause means
stop and report. Did not trigger -- see "decomposer blocker" below, resolved
on the first attempt.

## Decomposer blocker: Forza's mark isn't in run.log

`decompose.py` requires a literal `ROUTE HH:MM:SS.sss mark gameplay` line in
`run.log`. Buffy's route (`buffy.returning`, a scripted press-based route)
writes that line directly (`run.log:49`, confirmed). Forza's route
(`forza-soak1010`, `route.txt`: `drive forza 480 mark`) uses the screen-aware
`drive` script, which per its own embedded comment "writes `mark gameplay`
itself once play is confirmed ... then keeps driving for the rest of the
hold" -- to **logcat**, tag `hakuX-route`, not to run.log:

    10-18 04:51:28.204 I/hakuX-route(26477): mark gameplay

Both logcats carry full perflog telemetry (confirmed by grepping
`hakuX-pace|hakuX-phase|rr425w|idlehalt|tlb68|rwait526|lock474|xemu-work`:
3112 matches for Forza, 3899 for Buffy) -- the only blocker was mark-time
discovery, not missing instrumentation.

Fix, entirely inside this lane's own files, no edit to the result dir or to
decompose.py: `docs/lanes/fpstel1018/forza-run/` holds a copy of Forza's
`run.log` with one appended line (`ROUTE 04:51:28.204 mark gameplay`, the
literal wall-clock timestamp of the app's own logcat mark event) and a
symlink `logcat.txt` -> the original result dir's `logcat.txt` (read, not
copied -- it's 9 MB). Running `decompose.py` against that directory produces
419 rows of 2 s each = 838 s, which equals `verdict.json`'s own
`timeline.scored_s: 838.1` for this run -- strong independent confirmation
the mark time is the one the scorer itself used, not a guess.

## What ran

    python3 docs/lanes/vcpuwait433/decompose.py docs/lanes/fpstel1018/forza-run --bar 28.5 --tsv docs/lanes/fpstel1018/forza-decompose.tsv
    python3 docs/lanes/vcpuwait433/decompose.py <Buffy result dir> --bar 28.5 --tsv docs/lanes/fpstel1018/buffy-decompose.tsv

Per-row TSVs kept alongside this file for anyone who wants to re-bin them;
the tables in FINDINGS.md are derived from those two files plus the frames/
route-state.tsv/verdict.json already in each read-only result dir.

## Scene classification method

- Buffy has no `route-state.tsv` (scripted route, not the screen-aware
  driver); classified instead from `route-frames/` filenames (menu-start,
  menu-a, pre-mark, gameplay, play) and `frames/` (30 s screenshots).
- Forza has `route-state.tsv` through route-time 474.9 s (the drive script's
  own 480 s budget; it stops logging at window-done) plus `frames/`
  (`index.tsv`, screenshots every ~32 s for the whole 952 s capture,
  independent of the driver script). Cross-referencing the two: the drive
  script's own comments (`time_to_title_s=18.4`, `time_to_play_s=73.6`)
  match route-state row timestamps; a block of `stalled`/"stall escape N"
  rows from route-time 67-109 s show the driver fighting to get moving, then
  continuous `play` (hud:hud-lap+motion) through route-time 474.9 s.
- Critically, `frames/f00014.png`..`f00016.png` (wall-clock 04:56:06,
  04:56:37, 04:57:09) still show live racing (Lap 2/2, Place 8/8, car
  scrubbing a guardrail at 31-48 mph) but `frames/f00017.png` (04:57:41,
  just past the drive script's 480 s budget) already shows the **RESULTS**
  screen, and every frame after it through the end of the capture
  (f00018..f00031, wall-clock through 05:05:03) is the same results screen
  with a slowly-rotating parked car behind it. In decompose time (t = wall -
  04:51:28.204) the race ends and the results screen appears between
  t~341-373 s. FINDINGS.md splits Forza's decomposition at t=355 s on this
  evidence: "race" (t<355) vs "post-race results screen, idle" (t>=355).
  This is a route/harness fact (`forza-soak1010`'s 480 s drive budget ends
  mid-race-finish and nothing dismisses the results screen afterward, so a
  large share of the scored window -- 465.5 of 838.1 s per
  `verdict.json`'s `timeline.by_state.end` -- is not racing at all) worth
  flagging to lane.local/board separately from the fps lever below; it is
  not itself a renderer code lever and this lane does not propose one for
  it.

## Headline per-title numbers (see FINDINGS.md for full tables)

- Forza: fps is essentially unchanged between the race segment (t<355,
  median 24.1 fps) and the idle results-screen segment (t>=355, median
  23.6 fps) -- a near-static menu with a parked car renders at the same
  speed as live racing. GPU clock (`THERMAL` line in `run.log`) is pinned at
  its floor the *entire* run, 401 of 680 MHz, never once stepping up; Buffy's
  GPU clock on the same device model ranges 401-680 (reaches max). Render
  idle (Ri) is ~0 throughout Forza's run in both segments; the vCPU/guest
  thread (`v_run`) occupies ~92% of frame time (F) throughout. This matches
  forza414's own unresolved conclusion (§42: "Forza's lever is still the
  decay... guest-CPU-driven, not a drawing/GPU-load increase") and extends
  it: the guest/vCPU cost here is not proportional to scene complexity
  either (same fps whether racing or looking at a static results table), so
  it is a close-to-fixed per-frame cost on the guest/vCPU side, not a
  draw-count-scaling one.
- Buffy: the first ~90-100 s after mark (the opening of the "returning"
  mission, right after the loading screen) runs distinctly worse (27-28 fps,
  `BE` ~1500 draws/frame, a 14-15 ms gap between `F` and the sum of the four
  measured phases `ph_GPU+ph_Draw+ph_Fin+ph_Idle`) than the rest of the run
  (t>=120s: 29.2-29.6 fps steady state, `BE` ~1100-1200, gap 7-9 ms). Even at
  steady state the gap (time inside `F` that none of the four phase counters
  account for) persists at 7-9 ms and grows to ~19 ms in the slowest decile,
  while `lockw` (#474/pgraph.lock) and `ph_Fin` (the vk-finish/fence-wait
  phase) both stay ~0 throughout -- ruling both out directly, confirming
  belowbar1005's #804 refutation extends to this run, and sharpening
  belowbar1005's still-open "unattributed sleep" finding: it sits entirely
  outside GPU/Draw/Finish/Idle phase instrumentation, not inside vCPU's
  `v_blk` (which stays small, 0.8-1.1 ms, in this perflog pass).

## Caveat carried from the brief

Both runs capture a screenshot every 30 s (`frames/`), which the brief notes
costs some frame rate. Neither title's fps numbers here should be read as
the title's true device-default ceiling; they are this run's numbers, used
comparatively (good window vs bad window, phase vs phase) rather than as an
absolute bar-pass/fail re-litigation.
