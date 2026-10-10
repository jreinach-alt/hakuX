# lane.forzasurf1010 -- Forza's surfupd wait vs. default-on surfgpu (#433, 0.5)

Brief: does lane.surfgpudefault1009's shipped default (`HAKUX_SURFGPU=1`) remove the per-frame
`surfupd` wait lane.frametrace named on Forza (12.2 ms/frame, `vk/draw.c:4319` behind the render
thread's fence), given frametrace's own capture was invalid (car stalled against the wall, 8th of
8)? surfgpu targets `surfupd`/`reuse`; surfdl1008 found a different caller on Midnight Club 2
(`range`, `texture.c`'s `pgraph_vk_download_surfaces_in_range_if_dirty`), which surfgpu does not
touch. Measure, don't infer.

## 1. Setup

- Base: master @ `510dacff37` (this branch's root).
- Nova serial `ee317437`, root `/storage/E6C6-D7AA/Games/XBox` (docs/testing/devices.sh).
- **Forza's ISO is already on the Nova**, confirmed read-only (`adb -s ee317437 shell ls -la
  '/storage/E6C6-D7AA/Games/XBox/' | grep -i forza`): `4D53006E-Forza_Motorsport.xiso.iso`,
  3270705152 bytes, same size as the Thor's copy. `docs/testing/titles/targets.toml` only lists
  the Thor for this title -- that doc is stale, not mine to fix here (not in this lane's
  territory). No push needed; step 1 of the brief is done by reading, not by acting.
- The switch: `HAKUX_SURFGPU`, read once by `surfgpu_enabled()` in `hw/xbox/nv2a/pgraph/vk/surface.c`
  (line ~558). Default off at the native level; the app's Graphics toggle sets it on by default
  via `MainActivity.kt`'s `nativeSetenv`, but a queued request's `--env HAKUX_SURFGPU=0/1` is
  applied later by `xemu_android.cpp` from the `env_vars` pref and wins (confirmed by
  lane.surfgpudefault1009, NOTES section 4: `surfgpu: ON (#433)` then `env: HAKUX_SURFGPU=0`, 48 ms
  apart, same PID). So both arms here use `request.sh --env HAKUX_SURFGPU=1` / `=0` directly,
  independent of the app's Settings default, and the ON arm's log must show `[surfgpu] on`
  (it is logged once, from `surfgpu_enabled()`'s first call) while the OFF arm's must not.
- Route: `docs/testing/titles/routes/forza.drive.route` (`drive forza 420 find`), state `any`.
  This is lane.routedriver's screen-driven route (`drive.py`, RT held in the race, A only on
  menus, never START) -- proven on both handhelds to reach confirmed play (20 s of `find`), unlike
  the frametrace capture's blind route that left the car stalled. This is what the brief names in
  item 2 and is used unmodified (no local copy needed under routes/).
- Reader: `docs/lanes/surfgpu1009/sg_judge.py` is title-agnostic (`--expect`, `--a`, `--b`,
  optional `--floor`): it reads every `[sdcall]` caller's wait by name (not just `reuse`/`surfupd`)
  from post-mark logcat, `[surfgpu]` counters, and gfps/ph_* from
  `docs/lanes/near30/decompose.py`. Read-only, writes nothing -- used as-is rather than copied,
  per territory (this lane's territory is `docs/lanes/forzasurf1010/**` and its own prediction
  files; `sg_judge.py` is surfgpu1009's file, called, not edited).

## 2. Why attempt 1 did not finish

Attempt 1 did the setup above, built `docs/testing/titles/routes/forza-soak1010.route` (the
`mark`-variant of `forza.drive.route`, since the plain route's `find` stops at first confirmed
play and writes no `mark gameplay` line -- no window for any reader to key on), registered
`docs/testing/predictions/forzasurf1010-ab.json`, then queued an unscored verification run
(`1-1791644678-forzasurf1010-501671`, step 2 of the brief) to confirm the drive route still
reaches moving play before spending any scored device time. It ended its turn at ~08:09 "waiting
for the background task to notify me" instead of either polling the run in-foreground or writing
`docs/lanes/forzasurf1010/WAITING` and stopping. A headless session has nothing left running once
its turn ends, so nothing woke it; lane.local's addendum (10-10 08:51 PDT) is what actually
resumed this lane, after the run had already finished at 08:20 sitting unread for half an hour.
Lesson applied below: queue, write WAITING with the pending run id(s), commit+push, then stop --
never end a turn with a run outstanding and no WAITING line.

## 3. Verification run read (step 2)

`1-1791644678-forzasurf1010-501671` (`forza.drive.route`, 90 s, unscored, ref `ab1acc4154`):
`route-state.tsv` shows state `play` with sub-state `hud:hud-lap+motion` continuously from 79.7 s
to the end of the window (100.3 s+), LAP/RACE timers advancing (`00:08.633` -> `00:24.167` at
73-100s), minimap position advancing. Frame `081947-042-play.png`: 4 MPH, PLACE 8/8, lap timer
`00:00.000`. Frame `082005-051-play.png`, 18 s later: 13 MPH, lap timer `00:02.205`, car visibly
further down the track, position marker moved on the minimap. The car is moving, not stalled
against a wall as frametrace's capture was -- the route is good. Proceeding to step 3/4 unchanged
(the route and prediction from attempt 1 need no rework).

## 4. Scored runs, pilot chunk (first 2 of 4)

Per the board-request pilot rule (no `pilots/forzasurf1010.ok` on file yet, and the batch is 4
runs x (480+90)s = ~38 min, over the 30 min pilot ceiling), queued the first pair only this
session, A before B as `queue_order` specifies:

- A1 (`HAKUX_SURFGPU=0`, flag off): `1-1791647638-forzasurf1010-1663010`
- B1 (`HAKUX_SURFGPU=1`, flag on): `1-1791647642-forzasurf1010-1663501`

Both pinned to nova, ref `ab1acc4154`, route `forza-soak1010` (480 s, `drive forza 480 mark`),
`--perflog`, `--env HAKUX_FRAMETRACE=1`. Neither request.sh invocation was refused by the pilot
gate (prior device time this session was the 90 s verification run only). Written to
`docs/lanes/forzasurf1010/WAITING` and this session stops here per the addendum's instruction --
no background polling.

Next session: read both results' logs for `[surfgpu] on` (B) / its absence (A), run
`sg_judge.py` against the prediction, write the pilot verdict to `pilots/forzasurf1010.ok` (date,
result ids, what the per-caller table showed) per the pilot rule, then queue A2/B2.

## 5. Why attempt 2 did not finish

No attempt-2 NOTES section exists and no new commits appear between attempt 1's last commit
(`33479d7464`) and this session's start -- attempt 2 apparently made no progress worth a commit
(possibly another "waiting on a background task" turn-end, the same failure mode as attempt 1,
or a session that never ran). Nothing to carry forward beyond what attempt 1 already wrote.

## 6. Pilot pair read, `sg_judge.py`, and a judge-tool gap (attempt 3)

Both A1/B1 results were `DONE` on disk already at session start (`...-1663010`, `...-1663501`).
Confirmed valid: `[surfgpu] on` absent from A1's logcat (`grep -c` = 0), present exactly once in
B1's (`grep -c` = 1); `route-state.tsv` shows `hold mark gameplay` in both, with
`hud:hud-lap+motion` and the LAP timer advancing through the post-mark window in both (moving
car, not stalled).

`sg_judge.py --expect forzasurf1010-ab.json --a ...1663010 --b ...1663501`:

```
PASS V1.B_surfgpu_on            PASS V2.A_surfgpu_on         PASS V3.postmark_sdcall_windows_min
FAIL V4.thermal_pause (measured True, registered False)
PASS P0.A_surfupd_ms_per_frame_min (6.64 >= 4.0)
PASS P1.B_surfupd_ms_per_frame_max (0.14 <= 2.0)   PASS P1.B_detach_per_frame_min (1.00 >= 0.3)
FAIL P1.B_nodisp_per_frame_min (0.07 < 0.2)
FAIL P2.sdcall_wait_sum_ratio_max (0.77 > 0.6)
NO DATA P3.ph_Fin_drop_ms_min   NO DATA P4.gfps_gain_min
VERDICT: VOID (a V leg failed: identify why, do not rerun blind)
```

Per the judge's own rule, a V failure is not a number to report blind -- traced it instead of
re-queuing:

- **The V4 FAIL and both P3/P4 NO DATA share one root cause.** `sg_judge.py`'s `decompose()` shells
  out to `docs/lanes/near30/decompose.py <result dir>`, which reads `run.log` for a line matching
  `ROUTE (\d+):(\d+):([\d.]+) mark gameplay` (`decompose.py:59`) and returns early with `(None,
  'no mark')` if absent -- *before* it ever reaches the `THERMAL:` regex a few lines later. Our
  route (`forza-soak1010`, `drive forza 480 mark`) is driven by `docs/testing/titles/drive.py`'s
  screen-aware `mark` path (`drive.py:1051`, `self.dev.logcat("mark gameplay")`): that writes
  `mark gameplay` to the **device's** logcat (seen at `logcat.txt:8017`,
  `hakuX-route: mark gameplay`) and to `route-state.tsv`'s action column, but drive.py never
  prints a `ROUTE H:M:S mark gameplay` line to its own stdout (`run.log`) the way the older
  scripted-loop routes (e.g. `forza-nova-frametrace.route`, lane.gpuclock's LT-brake-then-RT
  pattern) evidently do. So `decompose.py` is VOID-with-no-mark on *every* drive.py `mark` route,
  not just this pair -- it never gets far enough to read the `THERMAL:` line, which is why
  `sg_judge.py` saw "(no line)" and `thermal_paused()` treats a missing line as paused (`not
  th.startswith("THERMAL: no thermal-pause device above 0")` is `True` when `th` is empty).
  **Both runs' own `run.log` carry the real line directly**: A --
  `THERMAL: no thermal-pause device above 0; ... hottest zone 95.1 C ...`; B -- the same. No
  thermal pause occurred in either arm; V4's FAIL is the judge-tool gap, not a real event.
- Confirmed by patching around it rather than editing `near30/decompose.py` (not this lane's
  territory, and the gap is systemic -- every lane pairing a drive.py `mark` route with this
  reader hits it, worth a shared fix outside this lane): built a scratch copy of each result dir
  under `/tmp/ffix/<rid>/` (symlinked `logcat.txt`, copied `run.log` with one appended line,
  `ROUTE <device-clock H:M:S.mmm from logcat.txt's own mark gameplay line> mark gameplay`) and ran
  `decompose.py` against the two copies directly. It then finds both `THERMAL:` lines (confirming
  "no thermal-pause device above 0" above) and the `all` row for each:

  | run | n (2s rows) | gfps (all) | ph_Fin (all, ms) |
  |---|---|---|---|
  | A (surfgpu=0) | 191 | 25.00 | 12.60 |
  | B (surfgpu=1) | 195 | 26.56 | 14.10 |

  P4 (gfps gain >= 1.0): **PASS**, +1.56. P3 (ph_Fin drop >= 3.0 ms): **FAIL** -- ph_Fin *rose*
  1.50 ms, it did not drop. This is not a contradiction: ph_Fin is the phase-profiler's finish-wait
  across the whole frame (every `[sdcall]` caller, not just `surfupd`), and the per-caller table
  below shows the wait moving to callers `ph_Fin` still counts.

- **Per-caller table** (`sg_judge.py`'s own read, unaffected by the decompose gap -- it reads
  `[sdcall]` lines from `logcat.txt` directly):

  | caller | A (off) ms/flip | B (on) ms/flip |
  |---|---|---|
  | surfupd | 6.64 | 0.14 |
  | range | 5.71 | 9.42 |
  | record | 4.70 | (absent) |
  | reuse | 0.15 | (absent) |
  | tobuf | (absent) | 3.41 |
  | expire | (absent) | 0.53 |
  | **all callers (sum)** | **17.59** | **13.48** |

  `[surfgpu]` counters on B: `detach 1.00/flip  nodisp 0.07/flip  dedup 2.98/flip  hold 0.88/flip`.

- **Reading the table**: surfgpu does exactly what it was built for -- `surfupd`'s wait is
  essentially gone (6.64 -> 0.14 ms/flip, P1's surfupd and detach legs both PASS). But the total
  `[sdcall]` wait per flip only falls 23% (17.59 -> 13.48, P2's ratio 0.77 vs. a 0.6 ceiling,
  FAIL), because `range` -- the same caller surfdl1008 named on Midnight Club 2, which surfgpu
  does not touch -- rises from 5.71 to 9.42 ms/flip and a new caller `tobuf` appears at 3.41. This
  is the brief's **outcome (b)**: the wait moved, it did not disappear. It also matches
  lane.local's NFS MW addendum (`range` the only caller with real wait once surfgpu is on) in
  kind, though Forza's `range` wait is larger in both arms and does not fall to the dominant-only
  position NFS MW showed. `nodisp` (0.07/flip) stayed below the registered 0.2 floor -- surfgpu's
  no-display-surface-needed path barely engaged here, unlike NBA Live's original mechanism
  (surfgpu1009), plausibly because Forza's surfaces are read back for reasons `nodisp` does not
  cover (feeding the HUD/minimap texture via `tobuf`?). gfps still rose a modest 1.56 fps --
  removing `surfupd` is a net win even though `range` absorbed most of the slack.
- Wrote the pilot verdict (`dispatch/pilots/forzasurf1010.ok`, via `python3` per the sandbox rule)
  summarizing the above and recommending the remaining batch: this pair is a real, scoreable,
  non-void signal on the brief's central question, not a cheap/noisy one -- worth completing to 2
  runs/arm as registered.
- Queued A2 (`1-1791649862-forzasurf1010-2253823`, `HAKUX_SURFGPU=0`) and B2
  (`1-1791649867-forzasurf1010-2254415`, `HAKUX_SURFGPU=1`), same route/ref/env as the pilot pair.
  Merged `origin/master` first (4 commits, lane.lanepath1009's PATH-shim fold -- no conflict,
  nothing in this lane's territory touched) before concluding anything further from this tree,
  per the lane contract; `ab1acc4154` (the registered `a_ref`/`b_ref`) is unaffected and still the
  commit both arms' `request.json` cite, so no re-registration is needed. Wrote
  `docs/lanes/forzasurf1010/WAITING` with both new run ids, committing this NOTES update in the
  same push, then stopping -- per the addendum's rule, never end a turn with runs outstanding and
  no WAITING line.

Next session: read A2/B2 once DONE, re-run `sg_judge.py` (still expect a V4 false-FAIL from the
same decompose.py gap -- confirm via the same `/tmp/ffix` patch, or just quote `run.log`'s own
THERMAL line directly, which is simpler), average the per-caller table across both runs per arm,
then write PR.md's decision: outcome (b), name `range`/`tobuf` as the callers that absorbed the
wait, and propose the texture.c GPU-side surface-to-texture follow-on (per brief step 5(c)) with
this lane's numbers as its P x win row, even though outcome is formally (b) not pure (c) --
`range` is present and growing in both arms, so the follow-on's rationale (the one caller surfgpu
structurally cannot reach) still applies.
