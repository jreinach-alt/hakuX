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

### 2. Forza: a steering policy for a scored window: TRIED, NOT SOLVED (steering off)

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

Built (drive.py `[steer]`, opt-in):
- A steering thread runs while the race HUD is up. It captures as fast as
  screencap allows, independent of the classifier's cadence, and sends LX
  plus the throttle in ONE `adb shell` sendevent call (`Device.axes`), with
  raw ranges from pad.sh's own cache (both handhelds: ABS_X ±32767,
  ABS_GAS/BRAKE 0..32767).
- LX = (line cx − 640) / 300, clamped. Throttle 0.7, eased by 40% at full
  lock. Under 40 line px the line is lost: hold the last steer 1.5 s at 0.3
  throttle, then centre at 0.3. `straight_s`: the wheel stays straight for
  the first N s after steering starts.
- The thread is paused while a stall escape plays, and every tick goes to
  `<out>/steer.tsv`. `[steer] enabled = false` keeps the table and its
  selftest but does not steer.
- Selftest on the rdfz1 fixtures: the bend reads full right (LX 1.0) and
  the straight 0.05. With the line lost, it holds right 1 s after the bend
  and centres at 3 s. 1 s after steering comes on it reads straight.

**Device results (Nova, hold `routedriver2:s2`, 2026-10-02 03:49-04:02 PDT):**

| run | profile | result | frames / steer.tsv |
|---|---|---|---|
| f1 | steering on | ROUTE FAIL stalled, 131 s | The loop ran at **~1.1 Hz** (a Nova screencap takes ~0.9 s). From the standing start it steered toward the line (110 px right, LX +0.37) and clipped the car alongside. Then the line swung to x 417 and 272, it went full left into the pit wall, and sat at 0 MPH with the line lost (`no entry` sign). `forza/f1-*` |
| f2 | + straight_s 5, a reverse-with-lock stall escape | window-done, 240 s | The car was sideways at the grandstand wall from ~20 s of race clock, **0 MPH for the rest of the window**. Four reverse escapes did not free it; line lost on 188 of 198 ticks. The classifier called some of those captures `play`: the animated crowd changes 0.054-0.097, over Forza's default 0.05 bar. `forza/f2-*` |
| f3 | steering **off**; HUD bars 0.12/0.10 | **reached-play**: title 10.6 s, play 54.0 s | The `--find` route still works, but the frame review is weak. In the 20 s stretch the car scrapes along the pit wall at 0-22 MPH, three of its ten captures at 0 MPH while it pivots. The race clock reads 29.8 s at the stretch's start. RT alone does not drive Forza's Nova grid start cleanly: the Thor run made 73 MPH. `forza/f3-find-stretch.jpg` |

What it means for a scored Forza window: **not ready.**
- At ~1 Hz the loop is too slow to follow the line, and it makes things
  worse from a grid start.
- What would change the probability is a faster signal. Options: a cropped
  or raw capture, an in-process signal, or reading the minimap's car
  position, which needs no line at all. A slower car alone would not.
  Priced by impact, a 3-5x faster capture is the precondition for any
  steering law. Until then `enabled = false`.

Kept from this item:
- The HUD bars (motion 0.12 / stall 0.10), so a parked car beside an
  animated crowd is `stalled`, not `play`. Fixture rdf2, counter-case to
  rdfz1's live race.
- The trigger-release fix, below.
- The 10 s progress check does NOT separate Forza: 0.154 on a live race
  10 s apart against 0.155 on the parked car over 41 s, so it is off for
  Forza.

Found on the way and fixed: every axis release in drive.py sent pad.sh
`mid`. On a 0..32767 trigger that is a HALF press, so Forza's RT was
half-pressed whenever the driver left play (menus, pause). Triggers now rest
at `min` (selftest: release sends RT min, LX mid).

### 3. Rolling `drive` out: Buffy reaches live play, but not 20 s of it

Backlog, read from lane.titleroutes' NOTES/OUTBOX on origin/lane/titleroutes
(5139f9556c; titleroutes is at attempt 4/4 and nobody is driving these):
- Buffy (Nova): wedges in play.
- Black Stone (Nova): blind A presses typed into name entry; the warrior
  never walks.
- Crash: Wrath of Cortex (Nova): its mark lands on LOAD/SAVE.
- 187: needs a re-queue only.
- Thor titles: closed while the fan is dead.
- Super Monkey Ball's Stage Select ignores everything but START. titleroutes
  calls that an input-layer issue, not a route, so it is not ours.

Buffy goes first: fps 29.97 against a 30 target, ok_share 0.93
(targets.toml), and its only known problem is a play loop that cannot see.

Both blind replays froze in play. Replay 1 (1790931264) moved for a minute,
then sat 4 min on the sky. Replay 2 (1790932722, B jumps added) showed the
same sky from 030531 to 030859, five minutes, with the camera swaying.

`drive-profiles/buffy.toml`:
- Crops cut from 1790932722 and scored over every frame on disk: title,
  main menu, Start Game, Difficulty, Summoning and PAUSE.
- The HUD is masked, learned at LEARN_STD 10 over twelve play frames from
  three runs: play ≤ 6.2, everything else ≥ 18.8.
- Play: a run cycle with turns, B every 4 s, A every 7 s.
- Escapes: LT (the camera reset), back off and turn, run and jump.

Held `--find` runs, Nova, 03:21-03:48 PDT:

| run | change | result | what the frames show |
|---|---|---|---|
| b1 | first profile | 420 s, no play | The first HUD crop (std 14, 81% of the region kept) had learned scenery: the bright canyon scored 14-18 against threshold 12 and was named `cutscene`. The cutscene ladder's START paused the game, A resumed, over and over. Then a dark corner with the HUD in plain view (luma 5.8) was `black` for 300 s. |
| b2 | HUD relearned (std 10, 12 frames); `black_luma` 3.0; header thresholds | ROUTE FAIL stalled, 134 s | **The menu path is clean**: title 14.6 s, Start Game, Difficulty, Summoning, the mission card, canyon at 35 s. In play the 2 s motion read 0.07-0.14 while she ran. In a night scene few pixels move 16 grey levels, so play was never confirmed. |
| b3 | every capture kept (`keep_all`), 240 s | ROUTE FAIL stalled | The measurement run (below). |
| b4 | -- | killed at 28 s | **The emulator aborted** during the intro FMV (below). The driver's next A then launched Calendar from the launcher. |
| b5 | `motion_pixel` 8, HUD bars 0.12/0.08, progress 0.07 | ROUTE FAIL stalled | **Play confirmed** (37-47 s), then no progress at 49 s. |
| b6 | LT out of the play cycle | ROUTE FAIL stalled | Same. The frames: she runs (023-025), climbs a low ledge (026), and reaches the "Run and press B to jump between ledges" gap (027). There she stops, and no escape (back off and turn, run and jump, two jumps) clears it. |

So Buffy reaches **real, frame-checked play ~35 s after boot**, against
titleroutes' 5 START/A cycles (~70 s). `--find` does not complete: it gets
10-12 s of play before the ledge gap, under the driver's 20 s bar. I did not
lower the bar to make it pass. Next: what the gap needs. Likely run + B at
the right moment and facing; a `--keep_all` run with `escape_capture_s` on
the gap would show it.

b3's measurement (every capture kept, 2 s apart), in grey-level changed
fraction at a pixel step of 16 / 8:
- Buffy running in the dark canyon: 0.04-0.28 / 0.14-0.43.
- The dark dead end: 0.006-0.035 / 0.003-0.076.
- The sky sway in titleroutes' replay 2, 21 s apart: 0.17-0.19 / 0.31-0.37.
  Per-capture motion cannot separate it from running.
- The 10 s 32x24 scene can: dark running 0.077-0.185, the dead end 0.000,
  the sky sway 0.036-0.061, bright running 0.31-0.35. The sway margin is
  small, and that is recorded in the profile.

**Classifier and driver changes from Buffy** (with fixtures and counter-cases):
- `motion_pixel` and `black_luma`, per profile.
- `keep_all` and `--set KEY=VALUE` in drive.py (a trial no longer needs a
  scratch profile).
- **No press while hakuX is not the focused app** (`Device.foreground`,
  `dumpsys window` cached 3 s, checked in `Device.pad` for presses and
  holds). Run b4's A went into the launcher and opened Calendar. Selftest:
  with hakuX not in front, a press fails and sends nothing.

**Emulator crash, Buffy run b4** (2026-10-02 03:40:27 PDT, Nova, debug APK
of the dispatcher's build-tree). The xemu process aborted on
`pgraph.c:2163: int pgraph_method(...): assertion "channel_valid" failed`,
from `pfifo_thread`, about 10 s into the intro FMV, right after the skip
ladder's A/START presses. Runs b1-b3, b5 and b6 passed the same intro, so it
is intermittent. Record: `buffy/b4-emulator-abort.txt` (the logcat
excerpt). Not chased here (emulator code is not this lane's).
Reported in OUTBOX for a tracker row.

### 4. play_share gate: the reader checks out; dispatched runs BLOCKED (harness gap)

**No dispatched run can use `drive` today.** The dispatcher snapshots a
fixed file list (dispatcher.sh `SCRIPT_DEPS` and `snapshot_scripts`, lines
89-92 and 117-121). titles/route.sh is in it. titles/drive.py,
titles/classify.py, titles/waitfor_match.py (classify's import) and
titles/drive-profiles/ (the .toml files and their reference PNGs) are not.
On the live snapshot, `bash $DISPATCH_DIR/bin/titles/route.sh --check
routes/sonic-heroes.drive.route` gives `drive 'sonic-heroes': no profile
.../bin/titles/drive-profiles/sonic-heroes.toml`, and `bin/titles/` holds
only route.sh, saves.py and titlestate.py. So no confirmation run has a
drive timeline.

The fix belongs in dispatcher.sh, outside this lane's territory:
- add the three .py files to both lists;
- copy `drive-profiles/*.toml` and `drive-profiles/<name>/*.png` (not
  `selftest/`, which is fixtures);
- extend selftest.d/97's closure check, since classify imports
  waitfor_match.

**The gate's reader, on a held run's full logcat** (Forza f3): title_verdict's
`parse_logcat` + `play_timeline` from the first `play` to `state=end` read
play 27.0 s, stalled 21.8 s, unknown 4.1 s, so **play_share 0.51**. That
matches the tsv's spans. Against the frames, the gate would FAIL that window,
correctly: the car spent most of it stuck on the pit wall. The over-count it
cannot see: three 0-MPH captures (≈6 s) inside the 27 s of `play`, where the
car pivots against the wall and the scene still changes. A real
confirmation's spot check waits on the snapshot fix.

Every held replay before this, lane.routedriver's included, recorded only
the first 30 s of logcat. The replay script ran `adb logcat` through a
wrapper with a 30 s timeout (Sonic trial 4: 7 `state=` lines against 35
changes in its tsv). scratch/replay.sh is fixed; b5, b6 and f1-f3 have full
logcats.

## For the next session (do not repeat)

- **Sonic:** do not retry straight-line jumps at the lower-path block; the
  climb-in-place Fly escape clears it. The open obstacles are the pink
  block by a pillar (~2:27) and the falls into the sea after the FLY sign
  (~2:04).
- **Buffy:** the menu path and play detection work. The open problem is the
  ledge gap ~12 s into the canyon. Do not raise play bars or shorten
  `find_play_s` to pass `--find`. Do not put LT back into the play cycle:
  it made no difference, and the raised fists are her running pose.
- **Forza:**
  - Do not turn `[steer]` back on at ~1 Hz; f1 and f2 are the evidence.
    The next step is a faster capture, not a different steering law.
  - The 10 s progress check does not separate a stuck Forza car.
- **The dispatcher snapshot** must carry drive.py, classify.py,
  waitfor_match.py and drive-profiles/ before any dispatched `drive` route
  or confirmation can run.

## Hand-off state (2026-10-02 04:15 PDT)

- Branch merged with origin/master @ 333711ac66 (merge, no rebase).
- `preflight.sh` passed. Its coverage gate DID NOT RUN (gh account
  suspended, HTTP 403): that check is unverified, not passed.
- `classify_selftest.py`: 0 failures.
- PR.md `State: ready`, and its `Files:` line equals
  `git diff --name-only origin/master...HEAD` (137 paths).
- The Nova hold `routedriver2:s2` is released.
- No confirmation was queued.


## Session 2 (Opus 5.5), 2026-10-02 (attempt 2 of 4)

**Why attempt 1 "did not finish":** it did. Session 1 ended normally with
PR.md `State: ready` and folded offline as `b71f92a12a` (05:01 PDT). This
attempt is the resume of a continuous pipeline lane, not a recovery. The
branch fast-forwarded onto that fold (0 ahead at start).

**Order chosen (probability x win):**
- Buffy first. It is the strongest Playable candidate in this lane's hands
  (29.97 fps against a 30 target, ok_share 0.93), its menu path and play
  detection already work, and one obstacle stands between it and a `--find`
  pass.
- Black Stone (titleroutes' "needs closed-loop input") is NOT taken: its
  draft route (`routes/black-stone.draft.route`, nav.py, session 37) already
  reaches the first room. The block is that the warrior never walks, with
  the stick or the hat. A screen driver cannot fix that, so the expected
  value of a profile is low until someone finds why he does not walk.
- Crash: Wrath of Cortex is already routed and confirmed (titleroutes
  session 37). titleroutes2 is working Gunvalkyrie, Bloody Roar, Star Wars
  Ep. III, Halo CE, Conker and NGB, so those are not duplicated here.

### Buffy: what the b5/b6 frames actually say about the "ledge gap"

b5 and b6 have identical timelines to the decisecond (play at 37.0 s, the
first stall at 49.2 s): under the same inputs the game is deterministic.
The frame kept on the first stall row (`028`) is written AFTER the escape
runs (drive.py `keep()` follows `act()`). But it holds the 49.1 s capture,
and in that capture **she is already in the stream bed below the gap**, with
a splash at her feet. The play cycle's B tap at 46.7 s, at the edge
(frame `027`), was the last input before it. So all six escapes in b5 and
b6, and every earlier variant, played from inside the stream bed, and none
of them was designed for it. The "ledge gap" problem is really two
problems:
1. getting out of the stream bed;
2. making the jump. A B tap every 4 s lands at a random distance from the
   edge.

Run b7 measures (1) first: four escapes, each exploring one direction
(forward, back, left, right) with B pressed through the push, every escape
filmed at 0.5 s (`escape_capture_s`), every capture kept.

Held runs, Nova ee317437, hold `routedriver2:s2` 05:35-05:59 PDT, AC, 80%,
each 240 s or less with `--find` (records: `docs/lanes/routedriver2/buffy/`):

| run | change | result | what the frames show |
|---|---|---|---|
| b7 | four exploring escapes (forward, back, left, right, B through each), every capture kept, escapes filmed at 0.5 s | ROUTE FAIL stalled | The timeline diverged from b5/b6. She climbed the low ledge (027), then **the camera swung to the sky** (028-036, 20 s). That is titleroutes replay 2's "frozen sky": the camera, not a wall. Escape 1 (forward + B) left it on the sky. Escape 2 starts with LT, and **LT (the camera reset) brought her back into view**. At 92 s she splashed into the stream bed (042). Then 8 escapes, each direction twice with B through the push, filmed every 0.5 s: **she never left the water**. The stream bed is a closed pit for every input tried. |
| b8 | B every capture, as a burst of 3 presses 0.4 s apart (new `play_tap` burst form); every escape starts with LT | ROUTE FAIL stalled | In the stream bed by 45 s, earlier than before. Escape frames: B presses with forward held, in the water, show no airborne frame. |
| b9 | probe: HUD bars at 1.01, so every HUD frame is `stalled` and escape 1 (LT, forward + B x4) fires at the spawn, on dry ground | (probe) | Running forward on dry ground with B pressed 4x in 0.9 s: never airborne at 0.4 s sampling. Escape 2: she ran forward toward the gap with B x4 at the phase start, then went off the edge 1-2 s later with no B in that window and splashed in (021). |
| b10 | B presses held 150 ms (the gap's frames read FPS 14-20, 50-70 ms a frame; pad.sh's default press is 60 ms), a burst of 8 every capture | ROUTE FAIL stalled | In the stream bed by 45 s. |
| b11 | probe: standing still on flat ground, stick released: B/150, B/300, A, X, Y, 1.5 s apart, filmed at 0.3 s | (probe) | **B and A each draw an attack trail (a kick, a punch), not a jump.** At the second site, on the ledge top under the "Run and press B" tip, the **Y** press (phase 5) moved her off the ledge with no stick: 022 standing, 023 blur, 024 splash in the stream bed. |
| b12 | Y bursts in place of B | ROUTE FAIL stuck, main_menu | **Never reached the canyon: the save limit.** Each Start Game makes a save ("BUFFY n"), the game keeps 10, and the Nova's disk is kept between runs. Dispatched runs keep it too: hdd.plan "keep", "the disk carries the store's saves". With 10 saves, Start Game shows "Buffy The Vampire Slayer only allows 10 saved games on your Xbox Hard Disk ... Press A to continue", and A goes back to the main menu. The driver looped there (it read the dimmed dialog as `cutscene` and pressed A). |

What this settles:
- The stream bed has no exit the driver can find. Falling in ends the run,
  so escapes cannot fix the gap; the jump has to be made.
- B pressed while running, at any density tried (one per ~2 s, a burst of
  3, a burst of 8 held 150 ms), never produced a frame of her in the air.
  Standing B is a kick. Y is the one button seen to move her off a ledge
  without the stick. **Open:** whether Y is the jump. b12 was meant to
  answer it and hit the save limit first.
- LT clears the sky-camera stall. Every escape now starts with LT.

Fixes from this:
- `play_tap` takes a burst, `[btn, every, n, gap]`, and `BTN/ms` presses.
  Selftest: a burst sends n presses and sleeps (n-1) x gap. The counter-case:
  `[btn, every]` sends one, and a burst is not due again inside `every`.
  `B/150` is sent held 150 ms. START is refused in a burst and as
  `START/150`. Mutant: a burst collapsed to one press is caught.
- Buffy's main menu takes **Load Game** (`LY:max`, then A). A `save-limit`
  crop (main_menu, press A) catches the dialog. Its scores: the dialog
  0.3-9.8, all 572 other Buffy frames on disk >= 23.3. Fixture: the b12
  dialog reads main_menu. Its counter-cases are the PAUSE, Start Game and
  canyon cases, since the crop is first in profile order. Mutant: without
  the crop the dialog reads `cutscene`, caught. The Load Game screen itself
  has not been seen yet: the next run films it.

Second hold, `routedriver2:s2b`, 06:28-06:34 PDT (taken after titleroutes2's
queue had run three requests):

| run | change | result | what the frames show |
|---|---|---|---|
| b13 | Load Game path; Y bursts (8 x Y/150 every capture) | **`reached-play` by the driver, REJECTED by the frame review** | The Load Game path works: Load Game, then "Buffy 1", then the checkpoint "Spanish Mission, Canyon", then the canyon. Title 14.3 s, play 39.1 s, one save loaded, nothing created. **Y is DELETE on the Load Game screen.** But all three play captures (025-027) show the camera on the sky or a rock face, with Buffy out of frame. The classifier counted the swaying camera as play: 2 s motion 0.55, and 10 s progress 0.125 against the 0.07 bar. Session 1 recorded the sway at 0.036-0.061 and called the margin small; here it was exceeded. The 8-press bursts spaced captures ~7 s apart, so only three frames stand behind the "20 s". `b13-false-play.jpg` |
| b14 | LT for 0.5 s at the start of each play cycle; Y bursts of 4 | ROUTE FAIL stalled | The camera was on the sky from the first play capture (37 s). Escape 1's LT brought it back (026), she climbed the low ledge (027), and at 65.9 s she was in the pit (028) with Y bursts running. **Y is not the jump either.** |

**Buffy, where it stands after session 2:**
- Driver path: title, main menu, Load Game, save, checkpoint, canyon,
  unattended and frame-checked, ~39 s from launch.
- The gap: NOT solved. B (four densities, two press lengths) and Y (two
  densities) were each pressed while running at it; she always ends in the
  stream bed, which has no exit.
- Next, not more driver variants: find out what the jump is. Options:
  - The game's Options screen may show the button map (a held nav.py look,
    or one more drive run that takes Options instead of Load Game).
  - A person with a controller makes the jump once, and the frames show
    what it takes.
  - The tip shows the B glyph, and B reaches games on this pad (Sonic
    trial 3's formation change), so an emulation question (a jump that never
    fires) is possible but unproven. Nothing here separates it from timing.
- **Classifier hole, found by the frame review:** with the camera swinging
  on the sky, Buffy's motion and progress both read as play. Its own frames
  rejected b13's `reached-play`. Until something tells "Buffy on screen"
  from "sky", a Buffy `--find` pass needs the frame review as the gate, not
  the driver's exit code. One candidate is the upper-centre region's mean
  colour as a `[[mode]]`, steering into an LT. Not built: the gap blocks
  Buffy before it would matter.
- **The profile as committed:**
  - Load Game, and the save-limit crop.
  - Every escape starts with LT, then forward with six B/150.
  - Play inputs as in session 1 (B every 4 s, A every 7 s). No Y anywhere.

Driver changes that stay regardless: `play_tap` bursts and `BTN/ms`, with
selftest cases.

## For the next session (session 2 additions; do not repeat)

- **Buffy:** do not try more B or Y timings at the gap; b7-b14 are the
  record. Do not try escapes from the stream bed: it is a pit. Find the jump
  first (above). Do not choose Start Game: 10 saves are on the Nova's disk,
  and Start Game loops on the limit dialog.
- **Black Stone:** not a driver problem until the warrior walks (titleroutes
  session 37: the stick and the hat only turn him).

### Buffy's main menu: the cursor moves one row or two (b15-b18)

Two Options probes, b15 and b16 (scratch profile, holds `routedriver2:s2c`
06:36-06:39), were meant to read the controller map. Neither reached Options:
- b15: the first LY flick moved one row (Start Game to Load Game), the
  second moved two (to Extras).
- b16: one hat pulse moved two rows (Start Game to Options), and the next
  went on to Extras.

So the committed Load Game path (`LY:max`, `A`, b13) works only when the
flick happens to move one row.

The first fix was one reference crop per lit row. It failed on the device
(b17, hold `s2d`): the glow pulses. Options lit at 018 and 021, and Extras
at 022-029, scored over their thresholds. Down at Extras, the bottom row,
did nothing for 8 presses: ROUTE FAIL stuck. Over 25 labelled frames
(b13-b17), Extras lit scored up to 33 against its own reference while unlit
rows scored from 21. No threshold separates them.

What works: **the lit row is the brightest row.** The measure is each
row's 99th-percentile grey. It was right on all 25 frames, by 89-126 grey
levels.

New, `[[cursor]]` (drive.py `cursor_press`, classify.py `cursor_row`): on a
screen named by `crop`, the brightest of `rows` (if it beats the next by
`min_margin`) picks that row's `press`. Buffy:
- Load Game lit: A.
- Start Game lit: down.
- Options or Extras lit: up.

Selftest (`CURSOR_WANT`):
- Each lit row reads right, including b17's two frames the crops missed and
  b15's dim-glow Load Game.
- Counter-cases: the 10-saves dialog (its own crop, margin 6) and the Load
  Game screen (margin 10) read no lit row.
- `cursor_press` returns nothing for the same frame under another crop.
- A `[[cursor]]` naming a missing crop is refused.
- Mutants caught: dimmest instead of brightest (7 failures), and the crop
  gate removed (1).
- Also fixed: `check_profile()` ran before `self.crops` was set.

**b18 (committed profile, `--find`, 06:52-06:55): the path works through
the very jitter it was built for.**
- The rows went Start, then (down moved two) Options, then (up moved two)
  Start, then down to Load Game, then A, the checkpoint, the canyon.
- Play at 41.4 s, then the known stall at the gap (52 s), ROUTE FAIL
  stalled. `b18-cursor-path.jpg`.

**Still open for Buffy: the jump.** The Options screen (and whether it shows
a controller map) is a ~70 s held run now: a scratch copy of the profile
whose `options` row presses A. It was not run because two priority requests
(lane.bf2stall433) and a titleroutes2 request were queued on the Nova.
