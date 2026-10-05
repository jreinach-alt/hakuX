## #433 -- 2026-10-02 09:30 PDT

[lane.pathfind] pathfind.py is running unattended on real titles. First lot-drawn title:
**Star Wars Episode III (Nova): gameplay confirmed in 3.5 min, 17 model calls (16 Haiku, 1 Sonnet for the
confirmation), 18 steps.** Path: 3 logos/title skipped with START, the opening crawl and a long FMV (START
ignored, it waited them out), first gameplay frame "NEW OBJECTIVE: ESCAPE THE CRUISER HANGAR"; the stick
probe moved Obi-Wan (frames checked by eye too). Frame: `docs/lanes/pathfind/runs/star-wars-iii/strip.jpg`.
Side finding: this title's intro FMV renders as green blocks (a video decode/rendering defect).
Model step latency via `claude -p`: 8-10 s per Haiku call, ~$0.027. Next: the other 9 lot titles on the
Nova (running now), ESPN NFL 2K5 on the Thor (running now).

## #433 -- 2026-10-02 09:49 PDT

[lane.pathfind] Scoreboard 2/2 on the Nova lot so far. **Midnight Club 3 (Nova): gameplay confirmed in
6.2 min, 33 model calls** (Career -> buy a car -> Test Drive -> driving in the city; RT moved the car).
Frame: `docs/lanes/pathfind/runs/midnight-club-3/gameplay_frame.jpg`. Running now: Bruce Lee, then
Black Stone, Panzer Dragoon Orta, Amped 2, Counter-Strike, Top Spin, Ninja Gaiden Black, Spikeout.
Changes from what was learned: the d-pad is the hat axis (the d-pad buttons do nothing in hakuX), inline
images and Sonnet 5 per step (3.5-3.9 s vs Haiku's 6-9 s, measured), Opus 5.5 when stuck, a 2-screen cycle
detector. ESPN NFL 2K5 (Thor) reached the kickoff twice in 3.3 min but the Thor heat-stopped at 70 C both
times (52 -> 70 C in 3.6 min of menus); retrying from a cold start.

## #433 -- 2026-10-02 10:08 PDT

[lane.pathfind] Lot scoreboard: **5 confirmed of 6 run** (Nova, unattended, cold):

| title | min | model calls | gameplay frame |
|---|---|---|---|
| Star Wars Episode III | 3.5 | 17 | runs/star-wars-iii/gameplay_frame.jpg |
| Midnight Club 3 | 6.2 | 33 | runs/midnight-club-3/gameplay_frame.jpg |
| Black Stone: Magic & Steel | 2.4 | 12 | runs/black-stone/gameplay_frame.jpg |
| Panzer Dragoon Orta | 4.5 | 21 | runs/panzer-dragoon/gameplay_frame.jpg |
| Amped 2 | 9.0 | 34 | runs/amped-2/gameplay_frame.jpg |

(paths under docs/lanes/pathfind/). **One false pass, caught in my frame review:** Bruce Lee "reached
gameplay" in 0.9 min on its letterboxed intro cinematic (the model took the emulator's FPS overlay for a
HUD, and the cinematic's hero moves by himself). Fixed with a letterbox veto, a 30-s recheck that retracts a
claim when the frame 30 s later is no longer play, and a left/right steering test for scenes that move by
themselves. Bruce Lee will be rerun. Running now: Counter-Strike, Top Spin, Ninja Gaiden Black, Spikeout
(Nova); ESPN NBA 2K5 (Thor) as the cross-title baseline. ESPN NFL 2K5 reached the kick return but the Thor
heat-stops every attempt at ~4 min (football needs play-call menus before any live play).

## #433 -- 2026-10-02 10:17 PDT

[lane.pathfind] **7 confirmed of 8 lot titles run** (Nova, cold, unattended, each frame strip reviewed by
eye): + Counter-Strike (3.1 min, 14 calls: Single Player -> Beginner -> Airstrip -> Auto-Select -> walking
the map, bomb planted) and Top Spin (5.5 min, 24 calls: Exhibition -> Sampras vs Sampras -> serving, a point
played). The acceptance count (7) is met; Ninja Gaiden Black, Spikeout and the Bruce Lee rerun complete the
10. Thor: ESPN NBA 2K5 stopped on a SEGA "problem with the disc ... dirty or damaged" screen right after
team select (an emulator or ISO fault worth a look; frame `runs/espn-nba-2k5.discerror/last_frame.jpg`);
pathfind now ends a run on a fatal error screen. Cross-title proof next: DOA3 -> DOA Ultimate on the Nova
(no heat limit), and NHL 2K5 -> College Hoops 2K5 on the Thor when it is cool.

## #433 -- 2026-10-02 10:30 PDT

[lane.pathfind] **Acceptance met: 9 of the 10 lot titles reached confirmed gameplay on the first attempt**
(Nova, cold, unattended, all within 15 min, max 9.0; strips reviewed by eye). New since the last post:
Ninja Gaiden Black (7.0 min, 33 calls: intros, lore screens, weapon menu, Ryu walking by the waterfall) and
Spikeout (4.3 min, 22 calls: name entry, Story, a street fight with health bars). The miss is Bruce Lee's
false pass (caught in review, not counted); it is being rerun now with the fixed tool. Table:
docs/lanes/pathfind/NOTES.md. Rendering side-findings for whoever owns video: Star Wars III's intro FMV and
Spikeout's loading screen both render as green blocks. pathfind now reads lane.pathknow's hints and appends
one learned line per success to `pathknow/hints/learned-*.md`. Next: the cross-title proof (DOA3 -> DOA1
Ultimate on the Nova; College Hoops 2K5 on the Thor, guided by the NHL/NFL 2K5 paths, running now).

## #433 -- 2026-10-02 10:51 PDT

[lane.pathfind] Bruce Lee rerun (fixed tool): **gameplay in 4.9 min, 22 calls**, a fight with health bars;
all 10 lot titles have now reached confirmed gameplay (9 of them on the first attempt). Thor: **ESPN College
Hoops 2K5 reached confirmed gameplay in 2.0 min with 10 model calls** (live basketball, the user player
moved under the stick; app stopped 20 s later, xo stayed under 70 C), replaying 2 steps of its own path from
an earlier heat-stopped run. Its first run, guided by the NHL/NFL 2K5 paths, reached the tip-off in 2.0 min
and 11 calls but heat-stopped while probing. For comparison, unguided NHL 2K5 needed 3.3 min and 16 calls to
reach its faceoff. Running now: the controlled cross-title test (Blinx -> Blinx 2 on the Nova, and NHL 2K5
with and without its siblings' paths on the Thor). DOA3 reached a live fight at 5 min but no probe could be
confirmed in 15 min: the CPU knocks the player down or ends the round inside the ~25 s a probe takes.

## #433 -- 2026-10-02 11:26 PDT

[lane.pathfind] Cross-title results (table in NOTES.md, "Cross-title"). ESPN 2K5 family on the Thor: runs
guided by a sibling's recorded path reached live play in **7-9 model calls and 1.6-2.1 min, against 12-19
calls and 3.0-3.4 min unguided** (NFL, NHL baselines). Two confounds favour the guided runs (profiles
saved on the device by earlier runs; tool changes between runs), so this is evidence, not a controlled
measurement. Sibling knowledge travels through the model, not frame matching: the same ESPN menu in two
titles is too far apart in pixels to match, so the agent now lets the model plan the next menus from a
sibling's path and sends them with no call while each input visibly changes the screen. Rule-5
confirmation is the hard part for team sports: goals, fouls and camera cuts land inside the probe, and
two NHL runs played CPU vs CPU (controller icon left in the middle of Team Select; now a rule). Every Thor
ESPN run is cut by the 70 C stop about 4 min in.
**Finding for an emulator lane:** Blinx 2 (4D530065, Nova) reaches Challenge 1 with the HUD up, but the
character never moves under any stick, d-pad or button input (2 runs, 30+ probes each, idle animation only).
Frames: scratch run dirs, summary in docs/lanes/pathfind/runs/blinx-2.*. Next: the rest of the lot on the
Nova (Conker, Ghoulies, Tork, DOAX, JSRF, Halo 2, ...), Tiger Woods 2004 on the Thor.

## #433 -- 2026-10-03 06:58 PDT

[lane.pathfind] waiting: hold-play is built and selftested (`pathfind.py --hold-s 600`, Nova only: after the claim, a
model-free genre loop keeps the player in play, with frames every 30 s). On saved real frames the in-play check read
3 of 3 right (play, title splash, pause) and the genre read 4 of 4 right (Midnight Club 3 drive, Top Spin rally,
Panzer Dragoon Orta on-rails, Counter-Strike attack). Model: Sonnet only today; Opus is off.

No held run yet. Every held run starts from its golden profile (`titlestate.py prepare`), which arrives with the
savestate433 fold, and that is not on master at 06:58. Nothing is queued on the Nova. When it folds, I merge master and
run the pool in P order, Black Stone first, each for 600 s held: Black Stone, Panzer Dragoon Orta, Midnight Club 3, Top
Spin, Spikeout, Amped 2, Counter-Strike.

Also recorded from the 10-02 late session, which never reached this file: Ghoulies gameplay in 2.35 min (11 calls),
Tork gameplay in 4.41 min (19 calls), Conker gave up at 15 min (23 calls, black after a level load). See NOTES.md.

## #433 -- 2026-10-03 08:40 PDT

[lane.pathfind] Hold-play, first held run (Black Stone Magic Steel, Nova): **not held**. The run claimed gameplay at
step 97 after 13.3 min and 66 Sonnet calls. The hold ran 65 s of 600 s before the 15-min budget ended, and the hold
strip (frames 106 and 110, 30 s apart) shows a near-static corridor, so those 65 s are not counted as Playable.
Frames: docs/lanes/pathfind/runs/black-stone-hold/ (hold_strip.jpg, frames/096-gameplay.jpg). Nova released; titlestate
golden released.

Why it failed, in order of weight: the claim read gameplay on a HUD playfield from step 3 to step 95, while every stick,
D-pad and A probe measured control 0.000-0.005. That is a claim-rule failure or an input-path failure on this title, and
it is open. Next: a pad-to-game input check on Black Stone before any more device time on it, then the next pool title
(Panzer Dragoon Orta) with a budget that covers claim and hold together.

## #433 -- 2026-10-03 09:32 PDT

[lane.pathfind] Probe gate (ADDENDUM 4), before any more device time. **Cause:** the probe's change test was a fixed
16-level grey step. In Black Stone's dark dungeon a real sword, spell or step changes 0.3-1% of the pixels, so the probe
refused real control before the model was asked (stored triplets: 0.002-0.010 under the old step). **Fix shipped:**
the step scales with the frame's contrast (floor 4, cap 16), the floor 0.03 -> 0.004, and a claimed hold gets its own
clock (the claim keeps the budget). Selftest: all ok, including a new dark-scene case that fails on the old code.

**Gate (48 labelled stored probes, scored through the whole chain: the new motion rule, then the real confirm question
to the strong model):**

| | result |
|---|---|
| real control accepted | 14 of 18 |
| non-control accepted | 0 of 30 (menus 0/4, cutscenes 0/8, pauses 0/2, no-response 0/16) |
| agreement | 44 of 48 (92%) |

Caveats, in NOTES.md "Probe gate": it passes on the corrected labels only (43 of 48 = 89.6% before one relabel). That
relabel (Midnight Club 3, 034: real control, the car drives and steers) was made after the model's answer on the same
frames; the owner should judge it. Four real controls are refused, two of them self-moving College Hoops cases that the
real pipeline sends to the steering test (not replayed). The alternating 2-of-3 windows and the classifier are not in.
Table, labels and scripts: docs/lanes/pathfind/gate/.

Next: the first held run, Panzer Dragoon Orta on the Nova, 600 s of play, with the golden profile.

## #433 -- 2026-10-03 10:58 PDT

Panzer Dragoon Orta (4947002B, Nova), first held run (600 s of play asked, 740 s held). Result: claimed at 3.4 min on
the on-rails dragon (probe control 0.25-0.68 under input); held 740 s, **598 s of play = 81%**, so title_verdict FAILs on
its 90% play-share bar. The three deaths in the hold (game over at about 216, 430 and 645 s) each cost an episode-card
cutscene of about 35 s before control came back; the hold recovered all three. Frames: docs/lanes/pathfind/runs/
panzer-dragoon-hold/hold_strip.jpg and hold.jsonl. Not a Playable confirmation.

Fixes made after run 1 (selftest all ok): the cutscene's A and a game over's press repeat three times with no model
read before the next look (`holdrepeat`), which removes ~3 model looks per death. A second Panzer run with that code is
queued behind a lanelocal request and will be judged the same way.

NEW ISSUE: pathfind's held run on Panzer Dragoon Orta dies three times in 10 min and loses ~140 s to game over and
episode-card cutscenes (play 81%, below the 90% bar).
Evidence: runs/panzer-dragoon-hold (hold.jsonl, the game-over and cutscene looks at 216-254 s, 430-464 s, 645-678 s,
verdict FAIL "menu time: 80.8% of the scored window in play"). Blocks: the 600-s Panzer confirmation and the NBA Live family
pass, which needs the same long hold.

NEW ISSUE: hold verdict was silently wrong: pathfind's hold wrote logcat in threadtime format and request.json without
the ISO, so title_verdict reported "guest never appeared" for a run that played 740 s and resolved no title id.
Evidence: runs/panzer-dragoon-hold, first verdict "booted: the guest never appeared". Fixed on lane/pathfind (logcat
`-v time`, request.json carries the ISO, run.log gets the held line); pending the fold.

## #433 -- 2026-10-03 11:24 PDT

Panzer Dragoon Orta, held run 2 (repeat change in; 601 s of play held, 717 s scored). Verdict still FAILS the 90% play
share: **83.6%** (play 600, cutscene 74, menu 21, black 14). Up from 80.8% in run 1. The cutscene repeats worked (three
A/START presses per episode card, no model read); each death now costs about 23-30 s off play, down from 33-38 s. The bigger
cost in this run is at the start of the hold: a black screen at 82 s, then the game returned to the title screen and
the model steered NEW GAME and the difficulty menu, about 65 s of off play. Frames: runs/panzer-dragoon-hold2/hold_strip.jpg
and hold.jsonl. Panzer is not a Playable confirmation. Next, Black Stone (58490004), the title the probe fix was built for,
held run in progress.

## #433 -- 2026-10-03 11:55 PDT

Black Stone Magic Steel (58490004, Nova), held run. Claimed at 2.4 min (probe: idle 0.002, under input 0.088). Held 602 s.
Verdict line: `Black Stone Magic Steel ? PASS gameplay=601.9s fps_ok=1.0 hitches=0 play_share=0.9996`.
**My frame review does not confirm it as Playable.** The strip (runs/black-stone-hold2/hold_strip.jpg, 16 frames, 30 s apart)
shows the red-armoured player in the same spot of the same octagon for the whole 600 s, sword swinging, camera fixed. The
hold log has 46 model checks, all "in play", and 47 steps; per-frame change is 0.003-0.010, and it is the swing effects,
not travel. The genre loop (attack: STICK up, X, A, ...) was sent every cycle and did not move him. This is the same stance
the 10-03 attempt-4 notes describe (the sword raised on the spawn octagon, released by X). The verdict PASS comes from the
play-share and fps rules, which do not check position. Not counted. The owner should judge the strip.
Next: the hold needs a position-change test on the playfield before it can count a second of play (NOTES, attempt 3
findings, was the same request). Not started here.

Status for today (the owner's 0.5 bar, 600-s Playable confirmations): none accepted yet.
Panzer Dragoon Orta: 80.8% and 83.6% play share, FAIL. Black Stone: PASS by the verdict, not confirmed on the frames.

## #433 -- 2026-10-03 12:50 PDT

NEW ISSUE: golden saves harvested on the Thor are read as "damaged" on the Nova (different eeprom.bin); 55 of 84 goldens are Thor-made
Forza (4D53006E), memfast run 1-1791047880-lane.memfast-3557511 (Nova, 12:11): the route pressed A 25 times between "Player
profile 'Default' is damaged and cannot be used" and PROFILE SELECT ("This profile is damaged ... Press X to delete"); frames
route-frames/121040-043-cutscene.png and 121129-071-fail-profile.png. The disk carried golden a1baf745d557. That save's store
record (titlestate/saves/4D53006E/a1baf745d557/save.json) names its source as pull/thor-hdd.img (09-30). The two handhelds'
eeprom.bin differ (Thor f52cf53a..., Nova 7eb04a87..., lane.titlestate NOTES 09-27). A save signed with the console HDD key
(which comes from the EEPROM) does not load on the other device. saves.py's docstring predicts exactly this. 55 of the 84 goldens
come from a Thor image (list: lane/pathfind scratch/goldsrc.py), and the Nova now runs every soak. Each is at risk on the Nova if
its title signs with the HDD key. That is per title, and Forza is the first confirmed from frames. Castlevania's golden
20235e93867b is also Thor-made: lane.local's queued 1-1791056447-lanelocal-2267406 tests it directly.
Options (P x win): (1) one eeprom.bin on both handhelds. Every future save then moves both ways, but saves already signed by the
replaced EEPROM stop loading on that device. That is a device decision. (2) Per-device goldens: compose only a save made on the
target device, otherwise first-run. (3) Re-sign at compose time: per-title formats, low P.
Blocks: Forza (pool), and possibly any Nova run on a Thor-made golden that dies on a profile/"damaged" screen.
This lane's part: a first-run pathfind on the Nova for Forza makes a Nova profile; harvest and promote it.


## #433 -- 2026-10-03 13:25 PDT

Pool (pm/pathfind-pool.tsv), first two rows:
- **Castlevania: CoD (4B4E002D):** lane.local's returning run 1-1791056447-lanelocal-2267406, on the Thor-made golden
  20235e93867b, reached play on the Nova ("Abandoned Castle", HP bar; frames/f00020.png shows the player moved). So this
  title's save does load across the two handhelds. No first-run work is needed from pathfind while that golden works. The
  row is lane.local's to close on that run's verdict.
- **Forza (4D53006E):** held first-run on the Nova, runs/forza-firstrun. It made a NEW PROFILE in 2 steps and reached a
  live Arcade race at 2.6 min. Then the car was stuck nosed into the pit wall: the agent pressed RT and stick 40 times
  and never reversed. Gave up at 15 min, 76 model calls, $6.01. Not a pass. The release harvested the new Nova profile
  5725499d3c7f. Its CarIcons.sig, Garage.bin and Garage.dat are byte-identical to the 09-30 Nova save and differ from
  the Thor-made golden, which confirms the device-signing cause in the 12:50 issue. **Promoted 5725499d3c7f as
  Forza's golden** (it loads on the Nova; it will read as damaged on the Thor).
- Tool changes, selftested: (1) **position test in the hold**: a 30-s window whose kept frames barely change is
  state=still, not play. Black Stone's standing 600 s would now be credited about 30 s; Panzer is unaffected. (2) RT+/LT+
  tokens (trigger and stick together), a drive loop that steers on the gas, and a reverse-while-turning step when a drive
  window is still.
Next: Forza run 2 (returning, the new golden, hold 600 s), queued behind lane.local's Tron telemetry run on the Nova.

## #433 -- 2026-10-03 13:55 PDT

Forza (4D53006E), held run 2 on the Nova, returning on the new Nova-made golden 5725499d3c7f: **the profile loads**
(PROFILE SELECT, "Default" lit, no damaged message, A to the main menu). The pool's profile failure is fixed. The
admission gate releases it on the golden change. It reached a live race again at 2.6 min and gave up at 15 min (60
calls, $4.56), stuck on walls. Cause, found in the frames: the confirm probe's steering legs steered with the gas off
and turned the slow car into the pit pillar (both runs). Fixed in the tool (a throttle probe steers on the throttle).
The car is slow because the game runs at **0.59x speed** (race clock 24.5 s in 41.2 s of wall time, 16-21 fps). It is
not an input fault: the trigger sends its full range. Forza is a performance miss for the Playable bar, not a route
miss. No further pathfind runs on it today.
Other pool rows, identification (no rerun): Burnout Revenge (1790873999), D&D Heroes (1790878175) and BF2:MC
(1790877270) are classed did-not-reach-play, but all three reached play. Their routes took 4.7-6 min to the mark in an
840-s window, so play was 484-557 s, and the real miss is fps (72%, 46%, 66% at >= 30 fps). They are performance
rows, not routing. A longer window (seconds >= route time + 600 + margin) fixes the duration part only.
ToeJam & Earl III (1791003320, class menu): the route's play loop opened the Vinyl Albums jukebox after Player Stats
and stayed in it all window. A pathfind held run (returning, hold 600 s) is next on the Nova, after lane.xbox's
title push.

## #433 -- 2026-10-03 14:20 PDT

ToeJam & Earl III (5345000F), held run on the Nova (golden 71a91de8b905 as-is): pathfind reached confirmed gameplay in
1.7 min (11 steps, 23 model calls in all, $1.29) and held 605 s of play.
Verdict line: `ToeJam & Earl III: Mission to Earth ? FAIL(fps: 72.8% of gameplay at >= 30 fps (bar 90%)) gameplay=641.4s
fps_ok=0.7278 crash=False hang=False hitches=0/0.0pm play_share=0.9486`.
Frame strip: docs/lanes/pathfind/runs/toejam-earl-3-hold/hold_strip.jpg. The player travels: 19 frames in different
places, all 17 30-s windows moved. But 13 of the 19 frames show a "PRESENTS: You don't have any presents!" dialog that a
button in the generic input loop kept opening. Fixed in the tool: a loop button that opens a menu is dropped for the rest
of the hold. The pool row's cause (the old route stuck in the Vinyl Albums jukebox) does not occur on pathfind's path. The
title fails on **performance** (72.8% at >= 30 fps), so it is a telemetry case, not a retest. The dispatched route
still has the jukebox defect.
Today's spend: about $26 of the $35 (Sonnet). Pool status: Castlevania resolved (lane.local's run on the golden), Forza's
profile fixed (golden promoted; the title is at 0.59x speed), ToeJam's route fixed (fps miss), and 3 rows identified as
fps misses. No Playable confirmation accepted from this lane today: every title that held play failed on fps or
travel.

## #433 -- 2026-10-03 14:45 PDT

**Playable confirmation candidate (owner's frame review): Spikeout: Battle Street (53450029), Nova, held run.**
Verdict line: `Spikeout: Battle Street ? PASS gameplay=607.3s fps_ok=1.0 crash=False hang=False hitches=0/0.0pm play_share=0.9996`
Frame strip: docs/lanes/pathfind/runs/spikeout-hold/hold_strip.jpg (18 frames, 30 s apart). Claimed at 8.2 min (50 model
calls in all, $3.46; four probes were refused while enemies moved in the opening fight). Then 607 s of play with no
off-play step. My review: the player moves in every frame. The camera and position change across all 18 (wall, dock,
harbour), and the position test saw motion in all 17 windows. He circles in the starting dock area, though, with no
progress through the level and K.O. 0. That is movement, not progression. The owner decides whether it counts.
Golden: c714fbc41e16, Thor-made. It loads on the Nova, so Spikeout is another title whose save crosses devices.
Why not Top Spin, Counter-Strike or Midnight Club 3: their 10-02 gameplay frames read 20, 13 and 22 fps, so a 600-s hold would
fail the fps bar. Those are performance cases.
Spend today: about $29.5 of $35. The Nova is released. No NBA Live title is on the Nova yet (listing-nova.txt).

## #433 -- 2026-10-03 16:47 PDT

**NBA Live 2005 (45410050), Nova, held run: gameplay reached and held 609 s; FAILS the Playable bar on frame rate.**
Verdict line: `NBA Live 2005 ? FAIL(fps: 0.0% of gameplay at >= 30 fps (bar 90%)) gameplay=609.7s fps_ok=0.0 crash=False hang=False hitches=1/0.109pm worst_ms=119.1 play_share=0.9996`.
Frame strip: docs/lanes/pathfind/runs/nba-live-2005-hold/hold_strip.jpg (16 frames, 30 s apart). Claimed at 6.8 min
(43 model calls, all Sonnet, $2.92). The player moves in every frame, the position test saw motion in all windows,
and the game clock runs 10:17 -> 5:44 across the hold, so the quarter covered the 600 s. Frame 076 is the EA logo
card at a stoppage, not a menu. Median frame rate 19.97 fps (window min 17.8). That is the performance miss, the
same class as Top Spin, Counter-Strike and Midnight Club 3 (10-02). I will not re-queue it.

NEW ISSUE: NBA Live 2005 runs at about 20 fps on the Nova in gameplay (not the route)
Evidence: runs/nba-live-2005-hold/verdict.json (fps_window_median 19.97, fps_ok_share 0.0, 202 windows), hold_strip.jpg. Same class as Top Spin / Counter-Strike / Midnight Club 3 (10-02). Blocks NBA Live as a Playable title. lane.local: if an issue for the 20-fps class already exists, link this to it instead of filing a new one.

**Not run today: NBA Live 2004 (45410038), 06 (4541007A), 07 (454100A1).** Spend is about $32.4 of the $35 cap (the $29.5 at 14:45 plus this run's $2.92). A sibling costs about $3, so it would exceed the cap. The same engine should hit the same frame-rate wall. Next run, when the cap lifts: a sibling only after the fps cause is named. The recorded path is committed (pathknow/paths/45410050.json and the learned pub-4541 hint), so a sibling can replay the menu part.

Pool status: no pool row changed. NBA Live was not on the pool file.

## #433 -- 2026-10-03 17:58 PDT

**Halo 2 (4D530064), Nova, two held runs: neither confirmed gameplay. Blocked, not Playable.**

- Run 1 (`runs/halo-2-hold`): gave up at the 15-min budget, 85 calls. Cause found in the prompt: the navigation action list did not name `RSTICK`, so the model could not steer the Armory look test. Fixed in `92cf166279`.
- Run 2 (`runs/halo-2-hold2`, with the fix): gave up at the 15-min budget, 95 calls, claim never confirmed. The model used the right stick from step 32 on. The camera stayed pinned on the floor of a sealed octagonal room (the Armory), and the probe frames are identical under input (mean grey difference 0.0 between probes a and b), so the game is not responding in that room. The change measure is not the cause.
- Unsettled: whether the Armory tutorial locks the camera until a step the model has not found. The cold boot spent about 5 min in cutscenes before the HUD. A route past the cutscenes and the Armory is the next thing to check.
- Spend: about 180 model calls across both runs (about $9 at the usual rate; the cost sheet is the authority).
- Not queuing a third run until a frame shows the camera responding in the Armory, or a route exists past it.
- Halo 2 stays off the Playable list. The Halo pool row is not released.

## #433 -- 2026-10-03 20:45 PDT

**Black Stone: Magic & Steel (58490004), Nova, held run with the attack walk: FAIL (menu time). Not Playable.**
Verdict line: `Black Stone Magic Steel ? FAIL(menu time: 63.8% of the scored window in play (bar 90%); play 600 s, still 340 s) gameplay=940.3s fps_ok=1.0 crash=False hang=False hitches=0/0.0pm play_share=0.638`.
Frame strip: docs/lanes/pathfind/runs/black-stone-walk/hold_strip.jpg (68 kept frames over 942 s). Claimed in 2.4 min, 45 model calls (Sonnet), $2.40.

What the frames show:
- Frames 024-044 (about 0-175 s of hold): the player stands on the same spot in the octagon. The square walk (`STICK:right:2`, `up`, `left`, `down`, each 2 s with A) moved nothing; the position test read 0.005-0.015 per 30-s pair.
- From about frame 047 the team-style rotation (`Y`, `R1`, `B`, `X`) runs. Frames 059-089 show a magic/item panel open at the bottom left in most of them: the buttons opened menus. The verdict's menu share is right.
- The hold counter credited 600 s of play, but only about 46 s of that was real play before the rotation. The counter does not separate play from a menu (`play_s` runs while the look is "gameplay").

Verdict on the change: the attack square walk does not move the fighter in this arena, and the unlock rotation after it walks into menus. The fix as shipped is wrong. I am not queuing another Black Stone run until the attack hold can move the player without the unlock rotation.

NEW ISSUE: Black Stone hold: the attack walk does not move the fighter, and the rotation's buttons open the magic menu
Evidence: runs/black-stone-walk/verdict.json, hold.jsonl (window 0.005-0.015 for 175 s), hold_strip.jpg (menu panel in 059-089). Blocks Black Stone as a Playable title. Hold-play design issue, not performance.

Pool row: Black Stone stays on the list. Spend: this run $2.40. By the NOTES figures (about $33 at the start of this resume, plus about $9 for the two Halo runs) the day is about $44 of the $70 cap; the cost sheet is the authority.

## #433 -- 2026-10-03 21:45 PDT

**Dino Crisis 3 (43430003), Nova, held run: FAIL (menu time). Not Playable.**
Verdict line: `Dino Crisis 3 ? FAIL(menu time: 79.1% of the scored window in play (bar 90%; play 608 s, still 154 s, menu 6 s)) gameplay=769.4s fps_ok=0.3793 crash=False hang=False hitches=18/1.522pm worst_ms=481.7 play_share=0.7906`.
Frame strip: docs/lanes/pathfind/runs/dino-crisis-3-hold/hold_strip.jpg. Claimed at 3.55 min, 35 model calls (Sonnet), 24 steps. Held 607 s of play.
Claim: the Game Controls overlay was closed with A, then the first corridor at step 23 was confirmed. The probe read control 0.000 idle and 0.547 under STICK:up.

What the frames show:
- Frames 023-082: the player stays in the same corridor and the camera barely moves. Per-window change is 0.16-0.28 early and 0.0007 at the claim check. The player walks in place.
- Frames 085 and 089: the genre loop's L1 and X presses opened the Map ("Map review screen") and the Item/equipment screen. The verdict's menu share is right.
- fps share: 0.38 of gameplay windows at >= 30 fps (bar 90%). That is a frame-rate cost, the same class as NBA Live 2005 (10-03). I will not re-queue this run.

Verdict on the change: the shooter loop does not travel in this corridor, and its L1/X presses open menus after the first minute. Same design fault as Black Stone's walk run: a hold that does not move the player, plus an unlock button that opens menus.

NEW ISSUE: Dino Crisis 3 hold: the shooter loop does not move the player; L1/X open the Map and Item screens
Evidence: runs/dino-crisis-3-hold/verdict.json, hold.jsonl (changed 0.16-0.28 early, 0.55 once in menus), hold_strip.jpg (menu at 085/089). Blocks Dino Crisis 3 as a Playable title. Hold-play design issue, not performance. Also fps_ok 0.38: a separate frame-rate cost; link it to the 20-fps class if an issue exists.

Pool status: Dino Crisis 3 stays on the list. Model spend about 35 Sonnet calls (about $2; the cost sheet is the authority). Next: 007 Agent Under Fire only if the cap allows, and only after the hold moves the player.

## #433 -- 2026-10-03 22:25 PDT

**Black Stone: Magic & Steel (58490004), Nova, held run with the title hold (X alone, left-stick walk): FAIL. Not Playable.**
Verdict line: `Black Stone Magic Steel ? FAIL(menu time: 9.5% of the scored window in play (bar 90%; still 1104 s, play 116 s)) gameplay=1219.2s fps_ok=1.0 crash=False hang=False hitches=0/0.0pm play_share=0.0948`.
The verdict's "menu time" wording is its name for the non-play share. Here it is still time: the strip shows no menu.
Frame strip: docs/lanes/pathfind/runs/black-stone-hold3/hold_strip.jpg (40 kept frames over 1219 s). Claimed at 4.9 min, 67 model calls (Sonnet), about $3.4 by the call estimate.

What the frames show:
- The fighter stands on the same spot of the octagon in every kept frame, from 037 to 102, with the camera fixed. No menu, no cutscene.
- The hold did what the title hold says: X at 1.8 s, then the four-stroke left-stick walk. Two still windows later, X again. Y, R1, BACK, START and B were never sent in the walk.
- Per cycle, the walk changed 0.82 of the frame once after each X, then 0.0002-0.002 for the rest. The fighter did not travel.

## #433 -- 2026-10-04 20:02 PDT

[lane.pathfind] RetroTechDad list 1/9: **Tork: Prehistoric Punk (55530040, Nova, golden 6cb2e3c07c9e, `--state any`): PASS.**
Verdict line: `Tork: Prehistoric Punk ? PASS None gameplay=632.7s fps_ok=1.0 crash=False hang=False audio_short=0.0 hitches=0/0.0pm worst_ms=0.0 static_frac=0.0976 play_share=0.952 fps_excluded=32.0s`.
Claimed at 3.85 min, 28 model calls (26 steps, 3 replayed). The hold ran 601 s of play; fps median 29.0 (locked 30), share >= 30 1.0.
Frames: 55 under docs/lanes/pathfind/runs/retro-tork/frames/ (about one per 12 s, at least one per 30 s in the scored window); strip: runs/retro-tork/hold_strip.jpg; gameplay frame: runs/retro-tork/frames/025-gameplay.png.
The position test: static_frac 0.098 (the window changed on most samples). Frame review by lane.local is the remaining check; the owner's flicker check is separate.
Caveat: the run exited rc=1 after its result line: `titlestate: cannot read x1box_prefs.xml` in the post-run restore. The verdict and result were written before it.

NEW ISSUE: titlestate release cannot read x1box_prefs.xml after a held run, so pathfind exits rc=1 (Tork, 10-04 20:01 PDT)
Evidence: runs/retro-tork/heldrun.log line 41 (`titlestate: cannot read x1box_prefs.xml`, from set_hdd's `</map>` check in docs/testing/titles/titlestate.py:1059), then `pathfind rc=1`; the verdict and result.json were already written. It is not yet known whether hddPath was restored on the device, so the next run's prepare must read it back.
It blocks a clean exit code for every held run (the wrapper treats rc=1 as a failure), not the verdict.

## #433 -- 2026-10-04 20:20 PDT

[lane.pathfind] RetroTechDad list 2/9: **JSRF - Jet Set Radio Future (USA) (Nova, first-run, ISO name; no golden): PASS.**
Verdict line: `JSRF - Jet Set Radio Future (USA) ? PASS None gameplay=602.4s fps_ok=1.0 crash=False hang=False audio_short=0.0 hitches=0/0.0pm worst_ms=0.0 static_frac=0.0135 play_share=0.9997 fps_excluded=2.0s`.
Claimed at 2.39 min, 22 model calls (17 steps, none replayed). The hold ran 600 s of play; the exit was rc=0.
Frames: 44 under docs/lanes/pathfind/runs/retro-jsrf/frames/ (at least one per 30 s); strip: runs/retro-jsrf/hold_strip.jpg; gameplay frame: runs/retro-jsrf/frames/016-gameplay.jpg.
Static fraction 0.014: the scene changed through the window (the camera and the character moved). The title's Sega GT id is shared (4D53003D); the run used the ISO name, so it was JSRF.
Frame review by lane.local is still needed; the owner's flicker check is separate.

## #433 -- 2026-10-04 20:36 PDT

[lane.pathfind] RetroTechDad list 3/9: **Conker: Live & Reloaded (Nova, golden d18aa0a71b74, `--state any`): GAVE UP at the 15-min claim budget.** No gameplay confirmed; no hold run. 83 model calls, 88 steps, one replay.
Identified cause (runs/retro-conker/heldrun.log, steps 4-10 and 17-30):
- Steps 4-8 read a live multiplayer match (timer, kill feed, HUD) as gameplay, and the probes read control 0.39-0.85. That read was wrong; the screen was not a single-player play state.
- Step 9's probe (HOLD:A:3, STICK) opened a save-data error box (step 10). It offers only A to repair. After it the title returned to its bar hub (a main menu with 'Chapters' as the lit item).
- From step 17 to 88 the hub's Chapters entry did not change: A, UP, START, B, DOWN+A, RIGHT+A, LEFT, stick, Y/X, BACK all returned to the same screen, and Xbox Live sign-in and submenus came up. The 'Chapters' submenu was a dead end for the model.
- So: the golden's save disk raised a save-data error on the first probe; the claim then had nothing to go back to. The next attempt should be a first-run (no golden) claim, which the golden's save error does not touch. Not re-run today.
NEW ISSUE candidate (lane.pathfind to file): golden d18aa0a71b74 raises a save-data error when probed on the Nova; check the golden's save before any returning run.

## #433 -- 2026-10-04 21:01 PDT

[lane.pathfind] RetroTechDad list 4/9: **Dead or Alive 3 (54430001, Nova, first-run): FAIL.**
Verdict line: `Dead or Alive 3 ? FAIL(menu time: 70.1% of the scored window in play (bar 90%; play 600 s, cutscene 123 s, menu 88 s, game_over 22 s)) gameplay=855.9s fps_ok=0.4394 crash=False hang=False audio_short=5e-05 hitches=20/1.508pm worst_ms=653.2 static_frac=0.0 play_share=0.7014 fps_excluded=253`.
Claimed at 4.74 min, 58 model calls (26 steps, none replayed). Hold ran 602 s of play, then the window's breakdown above.
Cost, line by line:
- **Play share 70%.** About 210 s of the window was non-play: 123 s cutscene (the fight's intro/KO moments the attack hold ran into), 88 s menu, 22 s game over. The hold did not keep the fight going through round ends.
- **fps.** Median 35 at 191 s, then median 30 at 307 s (share >= 30 0.55 over 145 samples). It is not on course for the 90% bar on fps alone: fps_ok 0.44 on the scored play.
- **Hitches.** 20 in the window, worst 653 ms (the per-title slowdown of #413, judged on this hold).
Frames: 25+ under docs/lanes/pathfind/runs/retro-doa3/frames/ (at least one per 30 s); strip: runs/retro-doa3/hold_strip.jpg; gameplay frame: runs/retro-doa3/frames/025-gameplay.jpg.
Not re-run. Identified; the next DOA3 step is a menu-free hold (stop at game over, re-enter the round) and a perflog on the fps, if the owner wants it.
Frames: 73 under runs/retro-doa3/frames/ (about one per 8 s).

## #433 -- 2026-10-04 21:20 PDT

[lane.pathfind] RetroTechDad list 5/9: **Amped 2 (4D530041, Nova, first-run, ISO name): FAIL on fps.**
Verdict line: `Amped 2 ? FAIL(fps: 44.2% of gameplay at >= 30 fps (bar 90%)) gameplay=629.6s fps_ok=0.4423 crash=False hang=False audio_short=0.0 hitches=6/0.632pm worst_ms=177.9 static_frac=0.0003 play_share=0.9594 fps_excluded=26.4s`.
Claimed at 4.36 min, 29 model calls (26 steps, 7 replayed; "four probes refused" at the end of the claim). The hold ran the full 630 s of play. Play share 96%: the menu problem is not the cause here.
fps: median 28.5 at 185 s (share >= 30 0.50), median 27.0 at 310 s (share >= 30 0.44). At the 5-minute check it sits right at the screening's median-27 line, not on course for 90%.
Class by the screening rule: **close** (median >= 27 at 5 min) on fps; it fails the 90% bar. Cause not yet named: this is the same family as Amped's 10-03 perflog (guest busy 31.6 ms/frame, vCPU), so a perflog run is the next step, not a re-hold.
Frames: 82 under runs/retro-amped2/frames/ (about one per 8 s); strip: runs/retro-amped2/hold_strip.jpg; gameplay frame: runs/retro-amped2/frames/025-gameplay.jpg.

## #433 -- 2026-10-04 21:37 PDT

[lane.pathfind] RetroTechDad list 6/9: **Ninja Gaiden Black (Nova, first-run, ISO name): FAIL on fps.**
Verdict line: `Ninja Gaiden Black ? FAIL(fps: 24.9% of gameplay at >= 30 fps (bar 90%)) gameplay=610.6s fps_ok=0.2495 crash=False hang=False audio_short=0.000273 hitches=7/0.763pm worst_ms=311.6 static_frac=0.0153 play_share=0.9997 fps_excluded=0.0s`.
Claimed at 4.74 min, 30 model calls (35 steps, 9 replayed). Hold 611 s of play, play share 99.97%: the hold design held here.
fps: median 26.0 at 187 s (share >= 30 0.24), median 27.0 at 305 s (share >= 30 0.24). Below the 28.5 bar for the whole window.
**This is a regression, not a known ceiling**: the 10-02 Ninja Gaiden Black run read 55-75 fps (`docs/investigations/frame-pacing-and-parallelism.md`, the guest-visible vblank notes). Same title, same device; the difference is not named. Cause to find before any re-hold: the build (this run's build vs 10-02), the vCPU busy share (decompose.py), or the GPL/ubershader setting. Not re-run.
Class by the screening rule: median 27.0 at 5 min is the close line, but the share (24%) is far from 60%, so **fail (on fps)**.
Frames: 69 under runs/retro-ngb/frames/; strip: runs/retro-ngb/hold_strip.jpg; gameplay frame: runs/retro-ngb/frames/034-gameplay.jpg.

## #433 -- 2026-10-04 21:50 PDT

[lane.pathfind] RetroTechDad list 7/9: **Buffy the Vampire Slayer (USA) (Nova, first-run, ISO name): FAIL on fps (close by the screening rule).**
Verdict line: `Buffy the Vampire Slayer ? FAIL(fps: 55.2% of gameplay at >= 30 fps (bar 90%)) gameplay=608.1s fps_ok=0.5516 crash=False hang=False audio_short=0.0 hitches=0/0.0pm worst_ms=0.0 static_frac=0.3422 play_share=0.9997 fps_excluded=0.0s`.
Claimed at 1.9 min, 20 model calls (13 steps, none replayed). The #659 channel_valid abort and the #660 save-slot limit did not occur in this run.
fps: median 29.0 at 182 s (share >= 30 0.58), median 29.0 at 306 s (share >= 30 0.61). **By the screening rule this is close** (60-90% at >= 30 or median >= 27), not a clean fail on fps.
**Static: 34% of the window** (static_frac 0.342). The hold's position test passed it, but a third of the samples did not change: the player was still in part of the window. Frame review must check whether the player travelled (runs/retro-buffy/frames/, at least one per 30 s, 41 frames). The known ledge loop (#730) is the likely cause; not re-run.
Frames: 41 under runs/retro-buffy/frames/; gameplay frame: runs/retro-buffy/frames/012-gameplay.jpg.

## #433 -- 2026-10-04 22:10 PDT

[lane.pathfind] RetroTechDad list 8/9: **Tron 2.0 - Killer App (USA, Europe) (Nova, first-run, ISO name): PASS. Handed to lane.local for frame review.**
Verdict line: `Tron 2.0 - Killer App (USA, Europe) ? PASS None gameplay=612.5s fps_ok=0.9777 crash=False hang=False audio_short=0.0 hitches=0/0.0pm worst_ms=0.0 static_frac=0.0376 play_share=0.9994 fps_excluded=0.0s`.
Claimed at 9.79 min, 71 model calls (75 steps, none replayed; "four probes refused" at the end of the claim). The hang watch (#672) did not trip: no hang gap, no 744-ms stall in the window, worst_ms 0.
fps: median 36.0 at 183 s (share >= 30 0.89), median 37.0 at 311 s (share >= 30 0.94).
Static 3.8%: the scene changed through the window.
Frames: 109 under runs/retro-tron/frames/ (about one per 6 s, at least one per 30 s); strip: runs/retro-tron/hold_strip.jpg; gameplay frame: runs/retro-tron/frames/074-gameplay.jpg.
Frame review must list what the scene should contain (the player, the grid or the level's enemies, the HUD). Flicker is the owner's check.

Verdict on the change: the title hold does not move Black Stone's fighter. The stance rule from 10-03 ("one X lowers the sword, then the stick walks") is not confirmed by this run. The 10-02 probe moved him only after a mixed sequence. I am not queuing another 600-s Black Stone run until a stick-response probe shows what moves him.

**Note on the profile:** the run was started as first-run, not returning. Black Stone has a golden (86c8f6eada06), and the first-run route composes the disk without it, so the claim got through Name Entry on its own (about 4 min) and saved a new profile to the latest slot. That was a state mistake on my side; the next run uses returning.

NEW ISSUE: Black Stone: the left stick does not move the fighter in the hold (stance rule unconfirmed; 1104 s still in the run)
Evidence: runs/black-stone-hold3/verdict.json, hold.jsonl (the walk windows at 0.0002-0.002 for 1100 s), hold_strip.jpg (one spot in all 40 frames). Blocks Black Stone as a Playable title. A control question for the stick path first, then the hold design. Also: the 10-02 run (runs/black-stone-hold, steps 94-97) moved the fighter after a mixed X/stick/LEFT sequence, so the trigger is unknown.

Pool status: Black Stone stays on the list (the pool's hold is the design fault, not the fps). Dino Crisis 3 stays on the list. 007 Agent Under Fire is not started: our rule is that a hold must move the player first, and it does not yet on Black Stone. Today's spend by the call estimate: about $50 of the $70 cap. The Nova is released (hold.sh who: free). Nothing is in flight and no WAITING file is written.

## #433 -- 2026-10-04 08:50 PDT

[lane.pathfind] RalliSport Challenge (4D53000F) CLEAR: 98.9% of 649 s at >= 30 fps, median 59, full window; profile golden cc9b4ced4a0f (titlestate), path docs/testing/titles/pathknow/paths/4D53000F.json
- Verdict line (rescored): `VERDICT RalliSport Challenge ? PASS None gameplay=671.2s fps_ok=1.0 crash=False hang=False audio_short=0.0 hitches=2/0.196pm worst_ms=151.4 static_frac=0.0125 play_share=0.9026 fps_excluded=66.1s`
- Frame strip: docs/lanes/pathfind/runs/screen-ralli-challenge/hold-0816/hold_strip.jpg (20 kept frames, 08:19-08:30 PDT, the car driving the stage).
- Path: the first-run claim at 3.2 min (19 Sonnet calls); the measurement run replayed it to play in 2.05 min (18 calls, 8 steps replayed). 3/5-min checks: median 59, 100% at >= 30 at both. No native target in targets.toml for RalliSport 1 (RalliSport 2 is 60).
- The run first scored FAIL "window unmeasured": master's failgate (de4b991a6c) reads the scored window from HHMMSS-named route-frames, and the hold kept NNN-hold frames. pathfind now writes its kept hold frames to route-frames/ (b81b9086de); this run was rescored from its kept JPGs, same capture times.
- The 08:04 attempt (234 s, ended with the session) read 230 of 236 s at >= 30 and is not used.
- Spend so far today: about $4.3 (screening, Sonnet).

[lane.pathfind] Aliens Versus Predator: Extinction (56550022) CLEAR on fps: 100% of 856 s at the verdict's bar (30 x 0.95), median 29, full window; profile golden 50a35dcd33ed, path docs/testing/titles/pathknow/paths/56550022.json
- Verdict line: `VERDICT Aliens Versus Predator Extinction ? FAIL(menu time: 70.7% of the scored window in play (bar 90%; play 605 s, still 239 s, other 11 s)) gameplay=855.9s fps_ok=1.0 crash=False hang=False audio_short=0.0 hitches=0/0.0pm worst_ms=0.0 static_frac=0.0529 play_share=0.7073`
- fps: gfps reads 29 or 31 in every 2-s sample (29: 230, 31: 190, 30: 19, 28: 2), so the title is locked at 30 and holds it. Raw share at >= 30 is 47%; at the verdict's 28.5 it is 100%. No hitches.
- Not Playable yet: the verdict fails it on play share. It is an RTS, and the hold's shooter loop leaves the camera still in 7 windows (239 s). This is a hold-design miss for the genre, not a performance miss. A pan-the-camera RTS loop is the fix if it is promoted.
- Claim: first-run, 3.1 min, 17 Sonnet calls (the morning survey only reached menus). Measurement run: replayed to play in 2.7 min (36 calls in the run, including hold looks). Frame strip: docs/lanes/pathfind/runs/screen-avp-extinction/hold/hold_strip.jpg. No native target in targets.toml.

[lane.pathfind] Phantom Crash (504C0001) CAN'T-PATH: the 15-min first-run budget ended in the ClubWired story dialogue (last state cutscene, DAY-01 hub talk), 92 Sonnet calls ($6.7); no profile, no measurement run. No perflog run (can't-path).
- Route so far: logos -> title -> New Game -> Name Entry (step 77) -> the hub's tutorial dialogue. A advanced the dialogue every time (frames change 0.01-0.28 per press), but each line cost one model look, and the "same screen" guard then rotated through B/BACK/START. Last frame: docs/lanes/pathfind/runs/screen-phantom-crash/claim/frames/ (the 08x cutscene frames); strip: claim/strip.jpg.
- Fix in pathfind (0dcef33ed3): a cutscene press that advanced the same screen repeats unlooked up to 3 times before the next look. Per the owner's rule I am not spending a second session on Phantom Crash today.

[lane.pathfind] The Simpsons Road Rage (45410013) CAN'T-PATH: the race HUD was reached at 10.8 min, but gameplay was never confirmed. Ten throttle probes (RT) were refused: 0.02 idle vs 0.02 under input, so the car did not move. The race timer then ran out to results, the save prompt and the menu. 74 Sonnet calls ($5.5). No profile and no measurement run.
- Route: logos, Burns' intro dialogue, main menu Road Rage, driver Homer, location Evergreen Terrace, load, race HUD (frames 075-095 in docs/lanes/pathfind/runs/screen-simpsons-road-rage/claim/frames/).
- Likely cause: RT is not this title's accelerator (on PS2 the accelerator is X, which maps to the Xbox's A). The model chose RT every time, although each answer said the earlier throttle probes had failed.
- Fix in pathfind (5829691aac): a probe input refused twice is replaced by the next untried input from a ladder (HOLD:A:3, STICK:up, RT, HOLD:X, LT, ...). Per the owner's rule there is no second session today.
- Also: a 10:2x attempt died at step 2 on my own mid-run edit to pathfind.py (AttributeError). The run above is the clean retry, not a second session on a can't-path.
Spend so far today: about $19 of $60.

[lane.pathfind] The Simpsons Hit & Run (56550015) CLEAR: 100% of 606 s at the verdict's bar (98.2% of 388 gfps samples at >= 28.5), median 38, full window. Profile: golden bcc71e970cff (title data only; the game had saved no profile by gameplay, so the hold boots `--state any`). Path: docs/testing/titles/pathknow/paths/56550015.json
- Verdict line: `VERDICT The Simpsons Hit Run ? PASS None gameplay=605.7s fps_ok=1.0 crash=False hang=False audio_short=0.0 hitches=0/0.0pm worst_ms=0.0 static_frac=0.0251 play_share=0.9998 fps_excluded=1.4s`
- Frame strip: docs/lanes/pathfind/runs/screen-simpsons-hit-run/hold/hold_strip.jpg. Claim: first-run, 2.7 min, 18 Sonnet calls. Measurement run: replayed to play in 2.7 min (7 steps replayed). 3/5-min checks were on course. No native target in targets.toml.
Spend so far today: about $21 of $60.

[lane.pathfind] Guilty Gear XX #Reload (53410002) CLEAR on fps, PARTIAL window: fps_ok 1.0 over 193 s of gameplay (100.0% of 195 gfps samples at >= 28.5), median 59. The hold ended at 97 s of play, not at 600 s. Profile golden 6f0d8fc26eb7; path docs/testing/titles/pathknow/paths/53410002.json
- Verdict line: `VERDICT Guilty Gear XX Reload The Midnight Carnival ? FAIL(duration: 193 s of gameplay < 600 s confirmation) gameplay=192.6s fps_ok=1.0 crash=False hang=False audio_short=0.0 hitches=0/0.0pm worst_ms=0.0 static_frac=0.0 play_share=0.5187`
- Why the window is short: the CPU won the first match. The hold's steering pressed A four times on the CONTINUE countdown (A did not continue), then went to GAME OVER, the ranking and the title. At character select its START presses did not start a match before the 12-step limit. This is a hold-recovery miss for fighting games, not a performance miss: 59 fps the whole time.
- Claim: first-run, 1.9 min, 13 Sonnet calls. Strip: docs/lanes/pathfind/runs/screen-guilty-gear-xx/hold/hold_strip.jpg. No native target in targets.toml.
Spend so far today: about $25 of $60.

[lane.pathfind] LEGO Star Wars: The Video Game (4553001D) CLEAR on fps: fps_ok 1.0 over 733 s of gameplay (100.0% of 734 gfps samples at >= 28.5), median 59, full window; profile golden 5251f98730d1, path docs/testing/titles/pathknow/paths/4553001D.json
- Verdict line: `VERDICT LEGO Star Wars The Video Game ? FAIL(menu time: 68.5% of the scored window in `play` (bar 90%; play 502 s, cutscene 117 s, still 78 s, pause 17 s)) gameplay=732.9s fps_ok=1.0 crash=False hang=False audio_short=0.0 hitches=0/0.0pm worst_ms=100.0 static_frac=0.0008 play_share=0.6845 fps_excluded=232.9s`
- Not Playable as held: the verdict fails it on play share 68.5% (cutscenes 117 s, still 78 s, pause 17 s). The claim landed in the Dexter's Diner hub (the strip shows the Episode I/II doors), and the hold's loop stayed in the hub. From frame 081 the pause menu (Resume / Options / Extras / Quit) is open over it in 4 of the last 5 kept frames. The strip does not show what the verdict's 117 s of "cutscene" were. This is a hold miss, not a performance miss: 59 fps at both the 3- and 5-min checks, worst frame 100 ms.
- Claim: first-run, 1.21 min, 9 Sonnet calls. Frame strip: docs/lanes/pathfind/runs/screen-lego-star-wars/hold/hold_strip.jpg. No native target in targets.toml.
Spend so far today: about $27 of $60.

[lane.pathfind] Mashed: Drive to Survive (454D000A) CAN'T-PATH: the 15-min first-run budget ended with gameplay never confirmed (last state results), 83 Sonnet calls ($5.6); no profile, no measurement run. No perflog run (can't-path).
- The claim reached live races (a HUD with start lights and boost/damage meters) from about 2 min on. All 19 probes were refused. The camera and the cars move on their own (idle change 0.3-0.86 in most probes), so the frame-change test cannot separate input from the scene. The confirm model saw winner banners, race results and camera cuts between the probe frames: in this elimination racer an undriven car is knocked out within seconds, so each round ended almost at once.
- One probe did respond: HOLD:A:3 at 170 s (0.017 idle, 0.814 under input), the first input from the new probe ladder after two RT probes. The confirm model refused it on a results screen. A is probably the accelerator here, as in Road Rage; that is unverified.
- Evidence: docs/lanes/pathfind/runs/screen-mashed/claim/ (strip.jpg, steps.jsonl, calls.jsonl).
Spend so far today: about $33 of $60.

[lane.pathfind] Amped: Freestyle Snowboarding (4D530005) FAIL: fps_ok 0.35 over 305 s of gameplay, median 23, aborted at 5:04 (the 3-min check read median 27 and 45% on the bar, so the run went on; the 5-min check read median 23 and 30%). Perflog run: docs/lanes/pathfind/runs/screen-amped/perf (180 s, fps_ok 0.086, median 21). Profile golden a7d274372a00, path docs/testing/titles/pathknow/paths/4D530005.json
- Verdict (measurement, partial): `VERDICT Amped: Freestyle Snowboarding ? FAIL(duration: 305 s of gameplay < 600 s confirmation) gameplay=304.5s fps_ok=0.3504 crash=False hang=False audio_short=0.0 hitches=3/0.736pm worst_ms=588.5 static_frac=0.0013 play_share=0.7863`
- Verdict (perflog run): `VERDICT Amped: Freestyle Snowboarding ? FAIL(duration: 188 s of gameplay < 600 s confirmation) gameplay=187.6s fps_ok=0.0861 crash=False hang=False hitches=0/0.0pm worst_ms=101.3 play_share=0.9992`
- Telemetry (docs/lanes/near30/decompose.py on the perflog run, 93 two-second rows): 20.4 fps, a 49.0 ms frame. Guest busy (vCPU running guest code) is 31.6 ms, and guest idle is 16.4 ms, 12.9 ms of it timer-woken. Renderer idle (Ri) is 12.3 ms, so the renderer waits on the guest. The slowest 10% of rows: busy 35.1 ms, 18.6 fps. Reading: the guest's CPU work is about 32 ms per frame, just over the 33.3 ms budget for 30 fps, and the frame then waits for the next 60 Hz slot (50 ms = 20 fps). The vCPU is the cost, not the GPU. The hakuX-phase columns (ph_Fin, render) were not in this logcat, so the GPU side is shown only by Ri.
- Claim: first-run, 3.75 min, 24 Sonnet calls. Strip: docs/lanes/pathfind/runs/screen-amped/hold/hold_strip.jpg. No native target in targets.toml.
Spend so far today: about $39 of $60.

[lane.pathfind] Dark Summit (54510004) CLEAR: fps_ok 0.9318 over 606 s of gameplay (92.2% of 434 gfps samples at >= 28.5), median 46, full window; profile golden 430384745827, path docs/testing/titles/pathknow/paths/54510004.json
- Verdict line: `VERDICT Dark Summit ? PASS None gameplay=606.4s fps_ok=0.9318 crash=False hang=False audio_short=0.0 hitches=2/0.22pm worst_ms=127.7 static_frac=0.0 play_share=0.9998 fps_excluded=1.9s`
- A verdict PASS: 606 s of play, fps_ok 0.93, play share 0.9998, 2 hitches (worst 128 ms). The 3- and 5-minute checks read median 31 and 35. The claim took 9.1 min: four probes were refused before the hold (a snowboarder on a self-moving slope). The measurement run replayed it to play in 4.0 min.
- Claim: first-run, 9.08 min, 40 Sonnet calls. Frame strip: docs/lanes/pathfind/runs/screen-dark-summit/hold/hold_strip.jpg. No native target in targets.toml.
Spend so far today: about $44 of $60.

[lane.pathfind] Whiteout (4B4E0001) CAN'T-PATH: the 15-min first-run budget ended on one loading screen. Quick Race, the default driver and the default track were selected, and "LOADING / COMING UP NEXT ... TROJAN PARK" stayed up from 145 s to the end of the budget, about 12.5 min. 35 Sonnet calls ($2.4); no profile, no measurement run. No perflog run (can't-path).
- During the load the fps counter read 29 and only the scrolling ticker changed. pathfind sent no input there: the model answered `wait` each time, and the cheap static-load rule waited between its looks. So the frames cannot tell a hung load from a load that wants a press. Frames: docs/lanes/pathfind/runs/screen-whiteout/claim/frames/015-loading.jpg through 138-loading.jpg.

NEW ISSUE: Whiteout (4B4E0001): the first race's loading screen never finishes (12+ min on the Nova)
Evidence: docs/lanes/pathfind/runs/screen-whiteout/claim (steps.jsonl steps 15-138 are all `loading`; frames 015-138 show the same "LOADING ... TROJAN PARK" card at 29 fps), pathfind screening 2026-10-04 13:30-13:46 PDT on the Nova, first-run disk. Quick Race, default driver, default track. No input was sent during the load, so a hung load and a wait-for-press are not yet told apart. One A/START press on the card, plus a logcat of the load (disc reads, xemu-work), separates them. Blocks Whiteout from the screening.

Spend so far today: about $47 of $60.

[lane.pathfind] MTV Celebrity Deathmatch (5454000B) CLEAR on fps: fps_ok 0.9876 over 687 s of gameplay (98.5% of 604 gfps samples at >= 28.5), median 59, full window; profile golden b206649c8fff, path docs/testing/titles/pathknow/paths/5454000B.json
- Verdict line: `VERDICT MTV Celebrity Deathmatch ? FAIL(menu time: 87.8% of the scored window in `play` (bar 90%; play 603 s, cutscene 37 s, menu 34 s, other 8 s)) gameplay=686.8s fps_ok=0.9876 crash=False hang=False audio_short=0.0 hitches=12/1.149pm worst_ms=348.6 static_frac=0.0 play_share=0.8781 fps_excluded=85.4s`
- The verdict fails it on play share: 87.8% against the 90% bar (cutscene 37 s and menu 34 s between rounds; the hold held 601 s of play). fps: median 59 at both the 3- and 5-min checks. Hitches: 12 (1.15 per min, worst 349 ms). The verdict did not fail on them, but they are the one performance cost to look at here. The claim took 4.9 min: five probes were refused, then HOLD:A:3 confirmed the fight. The probe ladder had first put that input in at probe 19, after two refused STICK:left probes.
- Claim: first-run, 4.93 min, 29 Sonnet calls. Frame strip: docs/lanes/pathfind/runs/screen-mtv-celebrity-deathmatch/hold/hold_strip.jpg. No native target in targets.toml.
Spend so far today: about $53 of $60.

SCREENING DONE 12/12, clear 7, close 0, fail 1, can't-path 4
- clear (fps share >= 90% on the verdict's bar): RalliSport Challenge (PASS), The Simpsons Hit & Run (PASS), Dark Summit (PASS), AvP: Extinction (fps_ok 1.0, locked 30; play share 70.7%), LEGO Star Wars (fps_ok 1.0; play share 68.5%), MTV Celebrity Deathmatch (fps_ok 0.99; play share 87.8%), Guilty Gear XX #Reload (fps_ok 1.0 over a partial 193-s window).
- fail: Amped (fps_ok 0.35, aborted at 5:04; perflog run: guest busy 31.6 ms/frame, vCPU-bound).
- can't-path: Phantom Crash (story dialogue), The Simpsons Road Rage (the car never moved under RT), Mashed (self-moving race, rounds ended at once), Whiteout (load card never finished: NEW ISSUE above).
- The owner's target of 8 clear-or-close was not reached: 7 of 12. Three PASS verdicts are Playable candidates for lane.local's frame review (RalliSport, Hit & Run, Dark Summit). Four more cleared fps but missed on hold design (play share or the hold's recovery), not on performance: AvP (RTS camera), LEGO (Diner hub and pause menu), MTV (between-round screens), Guilty Gear (CONTINUE screen).
- Spend: about $53 of the $60 cap (Sonnet). The Nova is released.

TORK RERUN: STOOD STILL (not traversed). Run docs/lanes/pathfind/runs/tork-rerun2/ (600 s hold, 603 s of play, fps median 29, fps_ok 1.0 at the bar, no crash/hang; frames every ~30 s in frames/, hold_strip.jpg).
- First frame of the hold (031-gameplay.jpg): village with huts and fire, Tork on dirt in front of the huts.
- Frames 041-056 (about 73 s to 600 s into the hold): the same cliff-side stair with cacti and a fence, Tork at the same spot (046 and 056 are nearly the same frame). The hold sent the same genre walk (STICK:up:4, A, STICK:up:3, STICK:right/left) every step from 73 s on and never changed action, so the stand-still check did not fire.
- Reading: the player walked out of the village in the first minute, then stood on one stair for the rest of the window. This is the Tork lesson again: the walk loop is not enough, and there is no working stuck-detector yet. Not a Playable retest; the Playable already counts.
- The automatic verdict says FAIL (static window 64%), but its frames are the claim's route-frames (13 sampled), not the hold's frames. Treat that verdict as the harness reading the wrong frames; the frame review above is the real judgement.
- NEW ISSUE: Tork: the hold walk does not detect a stand-still (no action change for 500+ s)
  Evidence: runs/tork-rerun2 (hold.jsonl steps 42-68: the same genre walk, changed 0.19-0.25 each step; frames 046 vs 056 the same spot). The hold must try a different action after 60 s with no movement (the brief's rule), which it did not.
- Verdict run: 06:38-06:54 PDT. Spend this session: nothing new beyond the claim (4.3 min, 20 model calls, Sonnet). Stopped at 06:55 PDT, the 07:00 window.
- Next (not started, window closes at 07:00): Tier 1 Guilty Gear XX, LEGO Star Wars, AvP.

[lane.pathfind] TORK RERUN 2 (10-05 07:23, runs/tork-rerun3, 600 s hold on the walk with the stand-still move): STOOD STILL. Verdict says FAIL (still 100 s, play share 0.857, fps_ok 1.0 at 29 locked). Frames agree: 059 village with the fire; 062 to 088 the same stair, the fence at the same place, the "Press A to jump" prompt on screen, Tork in the same spot every frame from 62 on.
- Why the stand-still move did not fire: the window test (classify.motion) read 0.17-0.30 on every 30-s window that stood still, because the attack flash changes pixels in place. Two still windows in a row never happened, so no move was sent. My detector fixed the trigger, not the measure.
- Fix committed on lane/pathfind: title holds judge still by the scene's shift (phase correlation, scene_shift: 0 px on every standing pair, 36 px on the walk out of the village), and two still windows send the next move. Rerun next (tork-rerun4).
- Spend this session: claim 4.3 min, about 20 Sonnet calls for the claim, plus one hold. Running total against the $80 cap is in the next line.

[lane.pathfind] TORK RERUN 3 (10-05 08:00, runs/tork-rerun4, 600 s hold with the shift test and the stand-still moves): NOT TRAVERSED, stood on the stair. Hold ended on budget at 219 s of play (not held). Frames 044 to 096: the village, then the same stair with the fence from 047 on, Tork in the same place in every frame, Press A to jump on screen.
- The shift test fires: scene shift 0 to 2.8 px at 235-543 s, and the moves ran in order (hop with A, RSTICK sweep, back out and sidestep, then the walk). None of them moved Tork off the stair. The stand-still detector works; the walk does not climb this stair.
- Next for Tork (not run): a different approach to the stair, not more walk. Not a Playable confirmation tonight; the Playable already counts.

[lane.pathfind] Guilty Gear XX #Reload (53410002) 10-05 08:23, runs/gg-rerun5, 600 s hold on the attack loop with the 10-04 select/continue rules: HELD 603 s of play, FAIL on play share 68.4% (menu 122 s, game over 65 s, other 23 s), fps_ok 1.0 at 59 median. Frames: gg-rerun5/hold_strip.jpg. Not a Playable yet.
- Two causes in the hold's own log, not the fighter: (1) the continue screen (step 34, a countdown over a portrait) was answered as cutscene, so the CONTINUE rule (START, then A) never ran; continue was not a state the hold's look could name. (2) On character select the look answered START, not A, because the hold's look prompt did not carry the fighting menu rule that the claim's prompt has. Each game over then cost ~70-100 s of title walk-back (START x4, ARCADE, select, versus).
- Fix committed (next line): the hold's look names continue, and for a fighting hold (genre attack) it gets the select/continue rule. Selftest 66 ok. Rerun 6 follows, the same 600 s.

[lane.pathfind] Guilty Gear XX rerun 6 (10-05 09:06, runs/gg-rerun6, 600 s hold, the look names continue and takes A on select): HELD 607 s of play, FAIL on play share 80.9% (menu 90 s, game over 38 s, other 14 s), fps_ok 1.0 at 59 median. Frames: gg-rerun6/hold_strip.jpg.
- The continue fix did its job (no CONTINUE screen was missed; the game overs ran out before a continue was offered). Character select still answered START on a PRESS START over empty slots (looks at 40-41 and 73-74): the prompt rule was not enough. Each game over now costs ~35 s of walk-back.
- Next (rerun 7, running): a model-free rule in the fighting hold, a menu look whose reason names a select screen (not a title or attract) takes A, not START. Selftest 66 ok.
