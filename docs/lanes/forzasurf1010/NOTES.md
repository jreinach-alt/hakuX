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
