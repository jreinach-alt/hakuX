# lane.gtawedge1012

## Vice City wedge (confirmation 1-1791785130-lane.local-2108844)

`frames/index.tsv` pairs by the device clock, one frame about every 31 s. The run's last 27 frames:
- 23:33:34 - ~23:41:40: Tommy runs through the city, FPS 29, one hospital respawn at 23:35:35 (matches brief).
- 23:41:54 (f00021) through 23:45:03 (f00027), the run's last 189 s / 7 frames: Tommy is jammed into a
  recessed garage-door alcove, running in place against the door. The game clock in the HUD keeps advancing
  (17:32 -> 21:10) across those frames; his screen position and the camera framing barely change at all.

That last point is the useful measurement for sizing the escape. 189 s covers about 22 loop iterations of
the old body (`~8.5 s` nominal, `~10.1 s` measured from a live run's logcat timestamps -- see below), each
contributing 0.5 s of `RX max`, i.e. roughly 11 s of cumulative stick-right input. The view at f00027 is
essentially the same as at f00021: still facing into the same door, same wall corner at the same screen
position. So 0.5 s of `RX max` per cycle does not reliably turn the camera far enough, even over many
cycles, to walk Tommy out of a recess once the forward-run leg (`LY min`, 1.5 s) has him replanted against
the same geometry faster than the drift can turn him away from it. I can't put a degrees-per-0.5s number on
it from 31s-spaced frames (too coarse), but the qualitative finding -- the existing turn alone does not
empty out a wedge no matter how long you leave it running -- is solid and is why the escape adds a much
bigger, unambiguous turn (`RX max` for 1.5 s, 3x the per-cycle drift) after a deliberate back-off.

Cycle timing used to size the escape: `run.log`'s `ROUTE HH:MM:SS.mmm` lines for one full loop iteration
(axis RX max -> next axis RX max) measured 10.142 s on a live device run, vs. ~7.4 s of declared `wait`/
`press` time -- the gap is per-instruction overhead (adb round trips). Used the measured 10.1 s, not the
declared 7.4 s, when picking how many iterations fit in the "at least every ~45 s" budget.

## GTA III: not a wedge -- a menu trap (confirmation 1-1791785131-lane.local-2109239)

Addendum 1 from lane.local (2026-10-12) landed while this lane was still on step 1-3, with the actual
finding: GTA III's confirmation never wedged in the play loop at all. It is the *boot* sequence that broke:

- `route-frames/234745-introskip.png`: after only the first 4 scripted `press A 300` / `wait 5` steps
  (meant to skip the intro video), Claude is already on foot in the street next to a car -- the boot was
  faster than the route assumed, and the A-train alone had already skipped the video, the title screen,
  and both opening cutscenes.
- `route-frames/234754-title.png`: the route's next scripted step, a blind `press START`, landed in-game
  and opened the **pause** menu (Load Game tab: New Game / Load Game), not a title screen.
- `route-frames/234826-cut1.png`, `234849-cut2.png`, `234855-gameplay.png`: all three are the identical
  "Are you sure you want to start a new game? ... OK / Cancel" confirm dialog, Cancel highlighted. The
  route's remaining scripted A-trains (meant to skip two more cutscenes) just kept re-opening/cancelling
  that dialog.
- `mark gameplay` fired at 23:48:55 (`frames/f00006`-ish) with that dialog still up. Real play only began
  once the *regular play loop's own* `LX`/`A` presses happened to land on OK (new-game cutscene at
  23:51:25 in `frames/f00011`, controlled play from `frames/f00012` at 23:51:56). Moving play was ~480 s
  of the scored window, which is why lane.local did not accept this run either -- not a wedge, a bad gate.

Fix in `gta-3.route` (addendum explicitly lifts "byte-identical above the mark" for this file only):
- Dropped `press START 300` entirely. The evidence above already proves A alone both skips every
  non-interactive screen *and* starts a new game at the title (the actual run reached controlled play
  using only A presses, before the route ever sent a START).
- Replaced the fixed `wait 8`/`wait 8` + two more 4-press cutscene trains with one longer, uniform A-train
  (4 + 12 = 16 presses, 5 s apart, ~85 s) long enough to cover a much slower boot than this run's, then
  gated `mark gameplay` behind a `waitfor` on the in-play HUD instead of a fixed timer.
- The `waitfor` reference crop is the weapon/fist icon box (top right of the HUD, away from the clock and
  money readout the brief said to avoid): `docs/testing/titles/routes/refs/gta-3/fist-hud.png`, region
  `1020,88,140,130`, threshold `20`.

### Why the fist-icon crop, and why threshold 20

Checked `route.sh` per the addendum's instruction before picking a source: `shot()` (line ~242) and
`capture_tmp()` (line ~291, what `waitfor`/`press-until` poll with) both run the literal same
`timeout 30 adb -s "$SERIAL" exec-out screencap -p > "$f"` that `dispatcher.sh`'s background frame
capture uses for `frames/`. Same device, same session, same command -- `frames/` and `route-frames/` in
this result dir are capture-path and size identical (both confirmed 1280x960 RGBA). Confirmation
1-1791785131-lane.local-2109239's own `route-frames/` never captured a real in-play HUD (all 5 of its
shots are pre-mark: the street-with-no-HUD intro frame, the pause menu, and three copies of the
new-game-confirm dialog), and the earlier pathfind session (`pathknow/paths/5454000E.json`) stored only
numeric histogram signatures, not images. So the crop is cut from `frames/f00012.png` (23:51:56, the first
frame of real controlled play in this same result dir) -- the one source in this run that is genuinely
"the screen waitfor needs to recognise" and is capture-equivalent to what `capture_tmp()` will poll.

Scored the candidate region (`1020,88,140,130`, downscaled 64x48 grayscale mean-abs-diff, matching
`waitfor_match.py`) against every frame available from that run:

| frame | state | score |
|---|---|---|
| f00001-f00003 | black loading screen | 83.7 |
| f00004 | loading | 69.5 |
| f00005 | loading | 105.4 |
| f00006 | loading | 65.2 |
| route-frames/234745-introskip | on foot, no HUD yet | 69.6 |
| route-frames/234754-title | pause menu | 105.4 |
| route-frames/234826-cut1, 234849-cut2, 234855-gameplay | new-game confirm dialog | 65.2 (all three identical) |
| f00012 | real gameplay (the reference itself) | 0.0 |
| f00013, f00014 | real gameplay, seconds later | 3.2, 4.1 |
| f00020, f00025, f00027 | real gameplay, minutes later | 9.9, 4.0, 5.6 |

Every non-gameplay state scores >= 65; every real-gameplay frame, including ones minutes apart and in
different parts of the city, scores <= 10. Picked threshold **20**: comfortably above the worst gameplay
sample (9.9) and comfortably below the best non-gameplay sample (65.2), so neither a slow boot (still
polling the loading/menu states) nor a lit-up HUD miles into the run can cross it by accident.

## Escape design (both routes)

Per the brief's suggested shape: nest the existing per-cycle body in `repeat 4 { ... }` inside the outer
`repeat forever { ... }`, then:
- `axis LY max` for 2 s -- camera-relative, so it runs the player *toward the camera*, i.e. backward out
  of whatever he just ran face-first into;
- `axis RX max` for 1.5 s -- a turn 3x the old per-cycle drift (0.5 s), picked because the Vice City
  wedge frames show the old 0.5 s/cycle drift does not reliably clear a tight recess even after many
  cycles (see above);
- every axis back to `mid` before the block closes.

Used `repeat 4` (not the brief's suggested 5) to keep the escape period under the "~45 s" budget using the
measured 10.1 s/cycle timing: 4 x 10.1 s + ~4.4 s of escape (declared 3.5 s of waits plus per-instruction
overhead) = ~44.8 s between escapes, vs. 5 x 10.1 s + 4.4 s = ~54.9 s, which would have been over. He is
never stopped for more than the one escape block, and still runs (not stands) through all of it.

Everything above `mark gameplay` in `gta-vc.route` is untouched (confirmed with a diff against
`origin/master` restricted to the lines before `mark gameplay`); `gta-3.route`'s pre-mark section changed
per Addendum 1 above, with "byte-identical above the mark" explicitly lifted for that file only.

## Checks run (worktree copies)

```
$ bash docs/testing/titles/route.sh --check docs/testing/titles/routes/gta-vc.route
route ok: .../gta-vc.route (82 lines)                    # exit 0
$ bash docs/testing/titles/route.sh --check docs/testing/titles/routes/gta-3.route
route ok: .../gta-3.route (82 lines)                     # exit 0   (also validates the fist-hud.png ref exists)

$ SERIAL=dry ROUTE_DRY=1 timeout 150 bash docs/testing/titles/route.sh docs/testing/titles/routes/gta-vc.route
# exit 124 (timeout, expected -- loop is `forever`). Log shows 4 inner iterations then one full escape
# (axis LY max -> axis RX max -> all axes reset) before the kill.

$ SERIAL=dry ROUTE_DRY=1 timeout 200 bash docs/testing/titles/route.sh docs/testing/titles/routes/gta-3.route
# exit 124 (timeout, expected). Needed 200s not 150s here: this title's pre-mark boot sequence alone
# (wait 55 + 16 A presses 5s apart) takes ~140s of the dry run's wall-clock budget before `mark gameplay`,
# leaving too little of a 150s window to reach even one escape. `waitfor` logs
# "waitfor fist-hud (dry, assumed matched)" and passes instantly under ROUTE_DRY (route.sh short-circuits
# it, never calls waitfor_match.py), so the dry pass does not exercise the real image comparison -- that
# only happens on-device.
```

`SERIAL` had to be set (even to a dummy value) for `ROUTE_DRY=1` runs: `route.sh` requires it
unconditionally (`: "${SERIAL:?route.sh: SERIAL is required}"`) before checking `ROUTE_DRY`.

## Next

- lane.local queues the next confirmation after the fold. This lane's proof is the frame review above,
  not a device run.
- If GTA III still doesn't clear the bar after this fix, the next thing to check is `fist-hud.png`/threshold
  20 against *that* run's own route-frames (same box, same scoring method as above) before touching the
  escape again -- the escape and the boot gate are two independent fixes and a next failure could be
  either one.
