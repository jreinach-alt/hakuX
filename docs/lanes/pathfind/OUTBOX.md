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

Verdict on the change: the title hold does not move Black Stone's fighter. The stance rule from 10-03 ("one X lowers the sword, then the stick walks") is not confirmed by this run. The 10-02 probe moved him only after a mixed sequence. I am not queuing another 600-s Black Stone run until a stick-response probe shows what moves him.

**Note on the profile:** the run was started as first-run, not returning. Black Stone has a golden (86c8f6eada06), and the first-run route composes the disk without it, so the claim got through Name Entry on its own (about 4 min) and saved a new profile to the latest slot. That was a state mistake on my side; the next run uses returning.

NEW ISSUE: Black Stone: the left stick does not move the fighter in the hold (stance rule unconfirmed; 1104 s still in the run)
Evidence: runs/black-stone-hold3/verdict.json, hold.jsonl (the walk windows at 0.0002-0.002 for 1100 s), hold_strip.jpg (one spot in all 40 frames). Blocks Black Stone as a Playable title. A control question for the stick path first, then the hold design. Also: the 10-02 run (runs/black-stone-hold, steps 94-97) moved the fighter after a mixed X/stick/LEFT sequence, so the trigger is unknown.

Pool status: Black Stone stays on the list (the pool's hold is the design fault, not the fps). Dino Crisis 3 stays on the list. 007 Agent Under Fire is not started: our rule is that a hold must move the player first, and it does not yet on Black Stone. Today's spend by the call estimate: about $50 of the $70 cap. The Nova is released (hold.sh who: free). Nothing is in flight and no WAITING file is written.
