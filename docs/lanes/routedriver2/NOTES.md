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
