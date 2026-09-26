# lane.forza414 -- #414: Forza Motorsport races at 3-16 fps on the Thor, game clock at 26% of real time

Issue: #414. Base: origin/master @ dc38b745b8.
Files: docs/lanes/forza414/**, docs/testing/predictions/forza414-*.json. Code files are NOT granted yet: name the site in
       NOTES.md and on the issue and the board grants it if free.
Needs device: yes (Thor soak of the same route). Needs NDK: no. The Thor has a bad-cable history: explicit SERIAL, Intel port.
Read first: the issue body (run 0-0-y-1790433159-titleplay-p1-forza in $DISPATCH_DIR/results), docs/lanes/fps382/NOTES.md
and docs/lanes/blinx372c/NOTES.md for the method.

## What is settled
Arcade Race, Maple Valley Raceway Short, 1999 Civic Si, player in control, but the route sits at 0-6 mph (Forza accelerates
on the right trigger), so this is the LIGHTEST scene a race has. 16.7 fps median, 3.1 minimum over 174 s; hang gaps
14.8, 17.3, 17.4, 17.7, 17.1, 19.1, 19.3 s; audio callbacks short 67%. Race timer 00:17.967 -> 01:01.433 over 168 s wall:
43.5 s of race, 26% speed. fps per 30 s: `10 30 28 22 6 12 12 14 14 20 2 4 4 2`. The loading screens already run at 6-7 fps,
and the race falls from ~14 to 2-4 fps after about 90 s with the car standing still.

## The job
1. The decay is the lead: 14 -> 2-4 fps with nothing changing in the scene means a cost that grows with time (a leak, a
   cache that fills, a per-frame list that lengthens, surface or descriptor churn). Take the per-30-s counters from the run
   on disk (renderer busy, `Sub`/`Fen`, slow stores, pipeline/shader cache sizes, any memory line) and say which one grows.
2. The 15-19 s hang gaps recurring at ~20 s spacing look periodic: find the period and what fires on it (a queue drain, a
   GC-like cache trim, a shader compile burst, the audio path).
3. Then the loading-screen 6-7 fps: same counters, separate table.
4. Say whether the same scene on the Nova reads the same (Thor and Nova agree per capture only when prefs and selection
   match: match them). Price the fix offline before the arm.

## Falsifier and arm
Mover: fps at t = 150-174 s of the race window from 2-4 toward the t = 60 s value, on a same-session Thor A/B; and the game
clock ratio from 26% toward 100%. Must-not-move: Depth buffer fixed function, Color_zeta_overlap, Surface_format, PR #387's
arm. Name what would move each; check `status`. Do not touch vk/surface.c while PR #396 (lane.blinx372d) holds it.

## Done when
NOTES.md holds the growing counter named (or its absence stated), the period of the hangs, the priced hunk or why none
exists; a grant request on #414 if a code file is needed; prediction registered after the last rebase; before marking ready
merge master and re-run the arm.
