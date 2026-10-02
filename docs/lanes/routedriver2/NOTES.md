# routedriver2 (#433): the screen-aware driver past its two proof titles

Successor to lane.routedriver (folded 7efa13af89). Its record,
`docs/lanes/routedriver/NOTES.md`, is the base this file builds on and is
not repeated here.

## Session 1 (Opus 5.5), 2026-10-02

Brief items, in order: (1) Sonic Heroes past the Seaside Hill block with
the three untried ideas, (2) a Forza steering policy for a scored window,
(3) roll `drive` out to titleroutes' menu/intro-loop backlog, (4) spot-check
title_verdict's play_share gate against a frame review.

### 1. Sonic Heroes past the Seaside Hill block: DONE (Nova, 4 trials)

Nova ee317437, hold `routedriver2:s1` 02:21-03:02 PDT (taken while ibcache's
request ran; idle 02:25). AC, battery 80%. Each trial is a held replay of
this worktree's drive.py on a scratch copy of the profile that only adds
`slow_s = 1`, `keep_every_s = 0` and `escape_capture_s = 0.7` (every capture
kept, and frames from a thread during each escape), no `find`, so the run
goes past the block. Script: `scratch/replay.sh` (lane.routedriver's, calling
drive.py directly). Records: `docs/lanes/routedriver2/sonic/`.

**What the frames said before any new escape was tried.** At 0:07-0:09 the
team passes a formation gate (two posts) that switches it to Fly. The lower-
path block where every earlier replay wedged is what you meet in Fly when the
team does NOT fly up the checkered pillar just past the gate. All five
recorded escapes held forward through the flight, so the team sailed over the
block and into the sea.

| trial | profile change | result | what the frames show |
|---|---|---|---|
| t1 02:26 | three escapes per run (`stall_cycles`): climb-then-drift, long A presses, Y + X | killed at 247 s by a focus read that came back empty (adb hiccup; screencap failed in the same second) | **never met the block**: an 8 s A tap landed in Fly at the pillar's foot, the team flew up it (+1000 at 0:09), took a Power gate (0:11), 49 rings at 0:26. New obstacles: robots at 0:26, then a white block under a POWER sign at 0:52 in Power formation. Escape 3 pressed Y and so left Power for Speed. From 1:43 the team struggled in a corner behind the block for 100 s, and **~40% of those captures read `play`** (2 s motion 0.35-0.50): a false play. `t1-path.jpg`, `t1-corner-false-play.jpg` |
| t2 02:36 | escapes by formation (`[[mode]]` from the leader circle's colour), no-progress check | window-done, 400 s | **The lower-path block is cleared by Fly's climb-in-place.** The stick is released, 12 A taps fly Tails up the face, then 1.2 s of forward lands the team on top (0:12 wedge, 0:17 on top, then a spring pedestal and 30 s of play; budget reset). The POWER block ("Can you break this rock, Knuckles?") fell to the third Power escape (1:52, +200). After a fall into the sea and the checkpoint respawn, the block was back. Speed's Y-and-climb there put the team in Fly, and Fly could not punch it: 100 s stuck, ~45% read `play`. `t2-block-cleared.jpg`, `t2-power-block-stuck.jpg` |
| t3 02:48 | each mode's list ends in another formation; `stall_clear_s` 10 | ROUTE FAIL stalled at 235 s | Lower block cleared again (0:12). **POWER block cleared by Power's third escape, B into Fly and climb**: on top of it at 2:03, then on past it. A third obstacle at ~2:27 (a pink block by a pillar) came after the budget (6) was spent; 40 s still, ROUTE FAIL. The stall watch now ends it honestly. `t3-power-block-cleared.jpg` |
| t4 02:54 | a stall at a NEW place (scene) gets a fresh budget | window-done, 450 s, no ROUTE FAIL | Three obstacles, the lower block (Fly), the POWER block (Power), and robots, then a fall into the sea, a respawn, the POWER block again, and a Game Over at ~390 s. The driver took the menus back into the stage. Captures after the first HUD: play 70, recovering 44, stalled 14, menu/load 6. `t4-mid.jpg`, `t4-late.jpg` |

The brief's three untried ideas, as they came out:
- **Formation change**: this is the answer, but in the direction the gates
  set rather than against them. Each formation gets its own escape, read
  from the HUD.
- **Hold the jump longer** (`A/600` presses, Fly's second escape): it ran
  in t2-t4 and never cleared anything the first escape had not.
- **Go around the side**: not needed. Replay 2's side route was the path
  that missed the pillar.

**Driver changes** (all in drive.py, all opt-in per profile, with selftest
pass and counter cases, and each mutant caught):
- `stall_cycles`: escape n plays cycle (n-1) mod len; `BTN/ms` long presses;
  `escape_capture_s` frames from a thread (no gap in the press cadence).
- `[[mode]]`: a region's mean RGB picks a mode, which may override
  `play_tap`/`play_hold`/`play_cycle`/`stall_cycles`. Read only on frames
  with the play HUD up. Sonic's main menu is the same blue as Speed (the
  counter-case). Leader circle: Speed (50,82,157), Power (170,60,37),
  Fly (160,137,49); Nova and Thor frames agree.
- `progress_bar`: a `play` frame whose 32x24 scene layout (HUD masked)
  changed less than the bar against the HUD frame ~10 s earlier is
  `stalled` (`hud+no-progress`). Running reads 0.46-0.71, the t1 corner
  0.07-0.29; Sonic's bar is 0.30. Off by default: a title whose play stays
  in one place must not opt in.
- `stall_clear_s`: once stalled, play has to hold this long before it counts.
  Until then frames log as `stalled` with `+recovering`; play's inputs still
  go out, but no escape fires. This understates play_share by up to 10 s per
  stall and never inflates it.
- A stall at a new place gets a fresh escape budget (scene against the last
  escape's start).
- `escape_reset_s` (30 s of play after an escape) also resets the budget.

**What the classifier got wrong, honestly:**
- t1 and t2: the corner and hover wedges read `play` 40-45% of the time.
  This is fixed by progress_bar and stall_clear_s, and the t2 stuck stretch
  re-simulates with no `play`. t4's 44 recovering captures include real play
  after each escape, logged as stalled. That is the price of the rule.
- t4 025910-108: a dark close-up of the team balls matched `profile-nodata`
  at 19.7 against threshold 20, and an A went out in play (harmless).
  Threshold is now 8 (the prompt itself scores 0.1-0.6), with a counter-case
  fixture.
- **A fixture was wrong:** the selftest's "sonic: find play in a live run"
  (1790910096) passed as reached-play because its last frames, the team
  wedged at the POWER block (1:21-1:41, score frozen at 3080), read `play`.
  It now expects play and then a stall. A new sim, trial 1's boot to 28 s of
  running, is the Sonic reached-play case.

**Not solved:** Seaside Hill end to end. A scored 600 s Sonic window would
still fail play_share (roughly half its HUD time is stalled or recovering).
The next obstacles are the pink block by the pillar (~2:27) and the falls
into the sea after the FLY sign (~2:04). The `--find` route is unchanged
and still ends before the block.

### 2. Forza: a steering policy for a scored window (built, not yet driven)

What the frames give (lane.routedriver's Thor run rdfz1, 040-050): the
Arcade assists draw the suggested line as **green chevrons on the asphalt**.
In a 1280x200 band ahead of the car (y 400-600) it is 330-1290 px of
saturated green (hue 85-160) in the full PNGs. Its centroid sits at x
650-760 on the straight and swings to 951-1054 at the right-hand bend where
the car ran wide onto the dirt (049). In the frame after (050), the car is
on the dirt and no line is visible. There are no yellow or red (braking)
segments anywhere in that run. The grey-road centroid was tried as a second
signal and is noise: sky and barriers are grey too (road cx 460-650 with no
relation to the bend).

Built (drive.py `[steer]`, opt-in; Forza's profile has it):
- A steering thread runs while the race HUD is up. It captures as fast as
  screencap allows, independent of the classifier's cadence, and sends LX
  plus the throttle in ONE `adb shell` sendevent call (`Device.axes`), with
  raw ranges from pad.sh's own cache. Both handhelds read ABS_X ±32767 and
  ABS_GAS/BRAKE 0..32767.
- LX = (line cx − 640) / 300, clamped. Throttle 0.7, eased by 40% at full
  lock. Below 40 line px the line is lost: hold the last steer 1.5 s at
  0.3 throttle, then centre at 0.3.
- It owns LX/RT/LT while on; play_hold's RT is dropped then. It stops on
  any non-play state (pause, menu) and releases to 0. Every tick goes to
  `<out>/steer.tsv`.
- Selftest on the rdfz1 fixtures: the bend reads full right (LX 1.0), the
  straight 0.05, line lost 1 s after the bend holds right, and at 3 s it
  centres.

Found on the way and fixed: every axis release in drive.py sent pad.sh
`mid`. On a 0..32767 trigger that is a HALF press, so Forza's RT was
half-pressed whenever the driver left play (menus, pause). Triggers now rest
at `min` (selftest: release sends RT min, LX mid).

**Not yet shown on a device:** whether a 1-3 Hz loop clears the first two
turns. That is the next held run (Forza is on the Nova per onhand.py).

### 3. Rolling `drive` out: Buffy the Vampire Slayer (profile written)

Backlog, read from lane.titleroutes' NOTES/OUTBOX on origin/lane/titleroutes
(5139f9556c; titleroutes is at attempt 4/4 and nobody is driving these):
Buffy (Nova, wedges in play), Black Stone (Nova; blind A presses typed into
name entry, the warrior never walks), Crash: Wrath of Cortex (Nova; mark on
LOAD/SAVE), 187 (needs a re-queue only), plus Thor titles (closed while the
fan is dead). Super Monkey Ball's Stage Select ignores everything but START.
titleroutes calls that an input-layer issue, not a route; it is not
ours. Buffy goes first: fps 29.97 against a 30 target, ok_share 0.93
(targets.toml), and its only problem is a play loop that cannot see.

Buffy's two blind replays both froze in play. Replay 1 (1790931264) moved for a
minute and then sat 4 min on the sky. Replay 2 (1790932722, B jumps added)
showed the same sky from 030531 to 030859, five minutes. The frame is not
literally still: the camera sways, 0.17-0.21 changed 21 s apart, against
0.49-0.52 for real running. The 32x24 scene settles it: stuck 0.00-0.06,
running 0.31-0.35. The camera is tilted at the sky with Buffy out of frame,
and the game's tip says "Pull the L trigger to reset".

`drive-profiles/buffy.toml`:
- Crops cut from 1790932722 and scored over every frame of all three runs
  on disk: title, main menu, Start Game, Difficulty, Summoning, PAUSE, and
  a masked HUD learned over seven play frames in five places.
- Play is a run cycle with LT pulled at its start, B every 4 s, A every 7 s.
- Stall escapes: LT, back off and turn, then run and jump (both ways), and
  a straight run with two jumps.
- HUD bars 0.25/0.22, progress_bar 0.15, stall_clear_s 10.
- Selftest:
  - Each screen.
  - Counter-cases: the frozen sky is `stalled`, not play. The in-engine
    opening (030406), which draws its own HUD, is not play (it scores 24.3
    against the HUD crop). A dark canyon frame is not Summoning.
  - Summoning itself is under the black luma bar, so it is `black`, which
    is waited on exactly like `loading`.

Its `--find` is the next held Nova run.

### 4. play_share gate: BLOCKED for dispatched runs (harness gap)

**No dispatched run can use `drive` today.** The dispatcher snapshots a
fixed file list (dispatcher.sh `SCRIPT_DEPS` and `snapshot_scripts`, lines
89-92 and 117-121): titles/route.sh is in it, but titles/drive.py,
titles/classify.py, titles/waitfor_match.py (classify's import) and
titles/drive-profiles/ (the .toml files and their reference PNGs) are not.
On the live snapshot:
`bash $DISPATCH_DIR/bin/titles/route.sh --check routes/sonic-heroes.drive.route`
gives `drive 'sonic-heroes': no profile .../bin/titles/drive-profiles/sonic-heroes.toml`,
and `bin/titles/` holds only route.sh, saves.py and titlestate.py. So no
confirmation run has a drive timeline, and the gate has nothing real to be
spot-checked against. The fix belongs in dispatcher.sh, which is outside this
lane's territory:
- add the three .py files to both lists;
- copy `drive-profiles/*.toml` and `drive-profiles/<name>/*.png` (not
  `selftest/`, which is fixtures);
- extend selftest.d/97's closure check, since classify imports waitfor_match.

Until then, every `drive` route is a held replay.

What can be checked meanwhile is the gate's READER, on a held run's own
logcat. Every held replay so far, lane.routedriver's included, recorded only
the first 30 s of logcat: the replay script ran `adb logcat` through a
wrapper with a 30 s timeout (trial 4 has 7 `state=` lines against 35 changes
in its tsv). The script is fixed (scratch/replay.sh), and the next held runs
carry a full logcat for title_verdict's `play_timeline`.
