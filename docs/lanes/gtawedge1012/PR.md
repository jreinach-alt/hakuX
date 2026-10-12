State: ready

Lane: gtawedge1012            Issue: none (#433 umbrella)
Base: master @ 00fde8afb3
Files: docs/testing/titles/routes/gta-3.route, docs/testing/titles/routes/gta-vc.route,
       docs/testing/titles/routes/refs/gta-3/fist-hud.png, docs/lanes/gtawedge1012/NOTES.md,
       docs/lanes/gtawedge1012/PR.md
Prediction: none: no device run (this lane edits route files only; lane.local queues the next
            confirmation after the fold, and that confirmation's frame review is the proof)
Needs device: no    Needs NDK: no

## What changed

**Both routes**: added a wedge escape to the play loop. Vice City's confirmation
(`1-1791785130-lane.local-2108844`) passed on frame rate but Tommy spent the run's last 189 s (23:41:54 to
23:45:03) wedged face-first into a recessed garage door -- the old loop's only net heading change was
0.5 s of `RX max` per cycle, which the frames show does not reliably turn far enough to clear a tight
recess no matter how many cycles run. Moving play was ~484 s of the required 600.

Escape (both routes, identical): nested the existing per-cycle body in `repeat 4 { ... }` inside the outer
`repeat forever { ... }`, followed by a back-off (`axis LY max` 2 s -- camera-relative, so it runs the
player toward the camera and away from whatever he's stuck on) then a hard camera turn (`axis RX max`
1.5 s, 3x the old per-cycle drift), then every axis back to `mid`. Runs at most every ~44.8 s of loop time
(measured ~10.1 s/cycle from a live run's logcat timestamps), so a wedge now costs at most about that much
play, and he's never stopped for longer than the one escape block.

**GTA III only** (Addendum 1 from lane.local, landed mid-session): the GTA III confirmation
(`1-1791785131-lane.local-2109239`) came back -- not a wedge, a menu trap. Its boot was faster than the
route assumed: the first 4 scripted A-presses already reached the street, so the route's next scripted
step, a blind `press START`, opened the in-game pause menu instead of the title screen, and the following
A-trains just kept answering "start a new game? / Cancel" on the resulting confirm dialog. `mark gameplay`
fired into that dialog; real play didn't start for ~480 s into the scored window.

Fix: dropped `press START` entirely (the same run proves A alone both skips every non-interactive screen
and starts a new game at the title), replaced the fixed-timer cutscene trains with one longer uniform
A-train (16 presses, 5 s apart), and gated `mark gameplay` behind a `waitfor` on the in-play HUD's
weapon/fist icon (`docs/testing/titles/routes/refs/gta-3/fist-hud.png`, region `1020,88,140,130`,
threshold `20`) instead of a fixed wait. Scored that region against every frame on disk from the failed
run: every non-gameplay state (loading, pause menu, confirm dialog) scored >= 65; every real-gameplay
frame scored <= 10 (full table in NOTES.md). The crop is cut from `frames/f00012.png` rather than
`route-frames/` as the addendum asked, because this run's `route-frames/` never captured real gameplay
(all 5 shots are pre-mark) -- checked `route.sh`'s `shot()`/`capture_tmp()` first and confirmed they issue
the literal same `adb exec-out screencap -p` as `dispatcher.sh`'s `frames/` capture (same device, same
session, both 1280x960), so the two are capture-path and size equivalent in this result dir; reasoning is
in NOTES.md.

"Byte-identical above the mark" stays true for `gta-vc.route` (confirmed by diff against `origin/master`)
and is lifted for `gta-3.route` only, per the addendum.

## Checks

```
bash docs/testing/titles/route.sh --check docs/testing/titles/routes/gta-vc.route   # exit 0
bash docs/testing/titles/route.sh --check docs/testing/titles/routes/gta-3.route    # exit 0 (also validates fist-hud.png exists)

SERIAL=dry ROUTE_DRY=1 timeout 150 bash docs/testing/titles/route.sh .../gta-vc.route   # exit 124 (timeout, expected); log
  shows 4 inner iterations then one full escape before the kill
SERIAL=dry ROUTE_DRY=1 timeout 200 bash docs/testing/titles/route.sh .../gta-3.route    # exit 124 (timeout, expected); needed
  200s not 150s because this title's pre-mark boot sequence alone takes ~140s of dry-run wall clock; waitfor
  passes instantly under ROUTE_DRY ("assumed matched") and does not exercise waitfor_match.py -- that only
  runs on-device
```

Full detail, the Vice City wedge-frame reading, the GTA III finding, and the fist-hud scoring table are in
`docs/lanes/gtawedge1012/NOTES.md`. `targets.toml` untouched.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
