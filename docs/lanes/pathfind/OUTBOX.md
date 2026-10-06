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

[lane.pathfind] Guilty Gear XX rerun 7 (10-05 09:37, runs/gg-rerun7): HELD 608 s of play, FAIL on play share 78.3% (menu 111 s, black 15 s, continue 12 s). fps_ok 1.0 at 59 median. CLASS: CLOSE (60-90%), not Playable. The select rule works (A on select, no START on the character screens). What is left is the fight itself: the loop loses a round two or three times in 10 min, and each game over returns through title, ARCADE, select, versus (5-7 looks, ~6 s each). Named cost: game-over walk-back, about 35 s per loss. A cheaper loop is the next lever, not another rerun of this hold. Frames: gg-rerun7/hold_strip.jpg.

[lane.pathfind] NFL Blitz 2002 (10-05 ~10:50-11:05, runs/nfl-blitz-2002): CLAIM FAIL, gave up at the 15-min budget after 80 steps, 84 model calls (Sonnet; spend not totalled here, see calls.jsonl). No gameplay confirmed, no hold, no verdict. Named causes, from steps.jsonl and frames 010/016:
1. The period was not set. Quickplay went main menu -> SELECT TEAMS (A FORWARD) -> loading -> kickoff with the first quarter's clock at 1ST 2:00 (frame 016). The model guessed the quarter setting came after team select; no such screen appeared. OPTIONS on the main menu was never opened. Next run's goal says OPTIONS first (unverified location).
2. Pre-snap formations with the HUD and no menu were read as gameplay four times (steps 16, 73, 76, 79); the stick probe moved nothing and the claim spent its budget there. Rule added: a formation before the snap is not play; A snaps.
Hint: docs/testing/titles/pathknow/hints/series-nfl-blitz.md. Sports rule committed (500dcaff1d, 1e8bd8d269): period_break state with START then A, sports look before a team hold, claim sets the longest period.

NEW ISSUE: NFL Blitz 2002 claim cannot set the quarter length (Quickplay has no period screen; the setting is not found) and reads pre-snap formations as gameplay
Evidence: docs/lanes/pathfind/runs/nfl-blitz-2002/hold/steps.jsonl (steps 8-16 period, 16/73/76/79 pre-snap), frames 010-016. Blocks the sports family's standing period rule (Blitz and its siblings).

[lane.pathfind] NFL Blitz 2002 CLEAR (fps) -- flicker unchecked (10-05 11:57, runs/nfl-blitz-2002/hold2): full window, 600 s hold after a 13.2-min claim. Harness verdict PASS: play_share 0.990 of 606.9 s gameplay, fps_ok 0.996 at the bar 28.5, window median 45.1 (min 25.2). Period length used: QUARTER LENGTH 5 MINUTES (OPTIONS, then PLAY OPTIONS: the longest offered). Aborted at: full window (no 3/5-min abort). Perflog: not taken (the fps gate was not tripped).
SCENE SHOULD CONTAIN: a live Arizona vs Arizona game, both teams on the field, the human-controlled player marked by the yellow/blue arrow, the scorebug with the score and quarter clock, the field moving between plays (position first-to-last 0.86 of the bar).
FRAME REVIEW CAVEAT (my read of the strip): the scene matches, but 5 of the 16 kept frames (097, 115, 118, 124, 130) show a PLAY-CALL overlay between plays. The loop pressed through those with A (the genre loop's A picks the play), and the model read them as play. So the harness play share is generous: the real play share is below 0.99 by an amount I did not measure. Please check the strip (hold2/hold_strip.jpg) before counting it.
Claim: 76 steps and 93 model calls to gameplay (`result.json`, 13.2 min); the period was set on the OPTIONS path the first run never tried. The sports look read 1st 4:35, human controlled. Model use: claim Sonnet, sports look and 6 hold checks Sonnet; spend not totalled here (see calls.jsonl).
Not done: no `paths/<id>.json` was written, because the ISO has no title id and paths are keyed by id, so a replay does not set the period by itself. The route is in the hint (series-nfl-blitz.md, verified this run).
Frames: docs/lanes/pathfind/runs/nfl-blitz-2002/hold2/frames (hold kept frames 094-139 every 30 s) and hold_strip.jpg. Log: runs/nfl-blitz-2002/heldrun2.log.

NEW ISSUE: a play-call overlay between football plays reads as play in the hold (the play share counts it)
Evidence: hold2 frames 097, 115, 118, 124, 130 (5 of 16 kept frames); the hold's model checks read in_play on those looks. The verdict's play_share 0.990 is the harness figure. Blocks an honest play share for every football title (the NFL Blitz family and the EA/2K football titles).

[lane.pathfind] NFL Blitz Pro (10-05 12:31, runs/nfl-blitz-pro): STOPPED at claim step 2, not a fail. Stopped on lane.local's 12:35 order (football last); the hold was released at once and the Nova went to AMF Bowling 2004. No verdict, no hold.

[lane.pathfind] AMF Bowling 2004 FAIL on hold design, not fps (10-05 12:43, runs/amf-bowling-2004/hold): claim 15 min to gameplay (controller 1 set Human; game length set to 10 frames, the longest offered). Hold ended at 283 of 600 s of play, "off play for 13 steps" (period_break, frame scorecard with REPLAY AVAILABLE). fps: median 59.0, 100% at the bar over 301 s, so fps is clear. Named causes, from hold.jsonl:
1. The hold used the team-sports loop (RT, X, B, Y, A, sticks). It never throws the ball: the bowler stood at the foul line for the whole play window, and its B and Y opened the pause menu (states "pause" at 197 s and 301 s). A bowling hold needs its own loop: aim with the stick, throw with A.
2. Each frame's scorecard is a period_break, and the START/A continue budget (4 presses, shared with CONTINUE) ran out on the first scorecards. After that the model's own START/A answers repeated on the same scorecard until HOLD_NAV_MAX (12) ended the hold.
Not re-run. Next: a bowling loop in the hold (per-title hint in the bowling family) with a per-frame scorecard rule, then one re-hold.

NEW ISSUE: bowling hold loop throws nothing and a frame scorecard ends the hold (team loop used for bowling; continue budget exhausted on frame scorecards)
Evidence: docs/lanes/pathfind/runs/amf-bowling-2004/hold/hold.jsonl (hold_s 197-386: pause and period_break looks), frames of the run. Blocks the bowling family (AMF Bowling 2004, Strike Force Bowling, AMF Xtreme).

[lane.pathfind] NBA 2K2 PASS (harness; flicker unchecked; 10-05 13:07, runs/nba-2k2/hold): full 600-s hold after a 12.6-min claim (76-80 steps, 89 model calls). play_share 0.9996 of 606.8 s, fps_ok 0.995 at the bar 28.5, window median 57.0. Position first-to-last 0.61, no still window by the position test. Aborted at: full window. Perflog: not taken.
Period: the claim goal set the quarter length to the longest offered, but the setting was not read back from the frames. The hold opened at 1st quarter 4:52 (sports look: human-controlled player "Wells" marked, LAL vs POR). Treat the period length as UNVERIFIED until the claim's steps show the value.
SCENE SHOULD CONTAIN: a live LAL vs POR game, both teams and their players on the court, the human-controlled player marked, the scorebug with the score and quarter clock, the crowd and courtside.
FRAME REVIEW CAVEAT (my read of hold_strip.jpg, 16 kept frames): 101 is an ACTION REPLAY card and 122 is the NBA logo, so the harness play share counts two non-play frames. 13 frames are live court view. The true play share is below 0.9996 by an amount not measured. Frames: runs/nba-2k2/hold/frames and hold_strip.jpg.
Model spend: claim and hold, Sonnet, 89 claim calls; spend not totalled here (calls.jsonl).
Claim: the team select had no controller assigned for ~20 steps (steps 40-55: A, stick+A, X, Y, HOLD:A, R1+A, L1 all failed in the team list before controller 1 was set). The claim was slow, but it reached play.

[lane.pathfind] NBA 2K2 claim note (10-05 13:07): team select with the controller not assigned took ~20 steps, and a pre-game intro with START toggled pause twice. Named, not a new issue (the claim reached play).

[lane.pathfind] AMF Bowling 2004 CLOSE (10-05 13:24, runs/amf-bowling-2004/hold2): the bowling loop works. Held 603 s; verdict FAIL on play share 89.2 percent (bar 90: play 601 s, menu 66 s, results 6 s). fps_ok 1.0 at the bar, window median 59.9. Position first-to-last 0.52, no still window. The loop threw and the scorecards no longer end the hold (the 12:43 failure was the team loop and the shared CONTINUE budget). CLASS: CLOSE (play share 60-90 band, not a hold failure).
Named cost: the game is 10 frames (the longest offered, set in the claim), so it ends at 271 s with Game Over, Press START. The walk back through title, Start New Game, Open Bowling, Controller Port Select (START x3), Regular Game and Bowl cost 66 s. One game over is the whole miss. Candidate next lever: a rematch or play-again entry at the game-over screen, if the game has one (not verified).
SCENE SHOULD CONTAIN: a live bowling lane with the bowler at the foul line, the pins set and the aim and power meter, the ball rolling down the lane between throws.
Frames: runs/amf-bowling-2004/hold2 (frames and hold_strip.jpg). Spend: claim 35 model calls (Sonnet).

[lane.pathfind] MLB SlugFest 2003 CLOSE (10-05 13:45, runs/mlb-slugfest-2003/hold): claim to gameplay, then a 606-s hold. Verdict FAIL on play share 88.3 percent (bar 90): play 607 s, still 74 s, other 7 s. fps_ok 1.0 at the bar, window median 59.9. Position first-to-last 0.74, 2 still windows out of 17 pairs. Innings: set to the longest offered by the claim goal (not read back; the sports look read 1ST inning, no clock in baseball). CLASS: CLOSE (play share band, not a hold failure).
Named cost: 74 s still. The held scene stops between pitches (the pitch and batter reset, not a menu), so the position test counts it as still. The hold sent its genre loop there; the still time is the game's own pitch cycle. Candidate lever: count a pitch-cycle still as play (a baseball scene check), not a hold change.
SCENE SHOULD CONTAIN: a live ANA game, the pitcher on the mound, the batter and the PLAYER 1 batting prompt, the scorebug with the inning and score, the fielders.
Frames: runs/mlb-slugfest-2003/hold (frames and hold_strip.jpg). Spend: claim and hold Sonnet, not totalled here (calls.jsonl).

[lane.pathfind] NHL Hitz Pro CLOSE (10-05 14:01, runs/nhl-hitz-pro/hold): claim 3.3 min, 20 steps; hold 603 s. Verdict FAIL on fps: 75.0 percent of gameplay at 30 (the verdict's own bar was 30, not 28.5; the 28.5-bar share is not computed in the verdict, so I have not guessed it). Window median 37.4, min 15.8, play share 0.936 of 646.5 s, fps excluded 40.2 s. Three hitches after warmup (worst 108 ms, unexplained). CLASS: CLOSE (fps: 60-90 band at 30; median above 27).
Named cost: 25 percent of play below 30 fps, which a 28.5 bar would mostly clear. Re-check the share at the 28.5 harness bar from the logcat before counting it.
Human control: UNVERIFIED. The claim put controller 1 under the Islanders and the sports look read no controller icon or marked player; the hold ran the team loop. A CPU-vs-CPU match would fail play share, and this one passed at 0.936, so the controlled player was probably moving, but the frames should be checked for a marked player.
SCENE SHOULD CONTAIN: a live Hitz game, skaters on the ice, the human-controlled player marked, the 3:00 or quarter clock and the score.
Frames: runs/nhl-hitz-pro/hold (frames and hold_strip.jpg). Spend: Sonnet, not totalled here.

[lane.pathfind] NHL 2K3 CAN'T-PATH on the claim (10-05 14:16, runs/nhl-2k3): gave up at the 15-min claim budget after 70 steps and 84 model calls. The HUD and a running period clock were live from step 32, and every stick probe was refused: the stick did not move the controlled skater (control 0.2-0.3 against input 0.1-0.4, and the camera cuts to a stoppage or line-change panel between probes). Likely cause, NOT verified: controller 1 was never assigned to a team on team select, so the stick drives nobody. The claim goal asked for it, but no frame of the team select was checked. Identification needed, not a re-run: read the team select frame in runs/nhl-2k3/hold/frames and look for a controller icon under a team.

NEW ISSUE: NHL 2K3 claim cannot confirm a controlled skater: stick probes never move the player (controller not assigned on team select, likely)
Evidence: docs/lanes/pathfind/runs/nhl-2k3/hold/steps.jsonl, steps 32-70 (probe refusals, the stick did not move the controlled skater). Blocks NHL 2K3 and the other hockey titles on this engine.

[lane.pathfind] Strike Force Bowling FAIL on hold design, not fps (10-05 14:27, runs/strike-force-bowling/hold): claim to bowling aim in about 3.5 min, hold ran 266 of 600 s of play. fps: median 59.0, 100% at the bar over 281 s, so fps is clear. The hold ended at 266 s: "off play for 13 steps" in a high-score Name Entry screen (name AAAAA, Strength/Accuracy/Curve bars, Done).
Named causes, from hold.jsonl:
1. At 266 s the play looked still for two windows, so the hold's still rotation replaced the bowl loop with the unlock ladder: X, then RT and the stick. The X opened the high-score name entry at the end of the game.
2. The name entry was answered with A, which types a letter on that keyboard (the 10-03 RULES warning), 12 times in a row. Nothing pressed START (which jumps to Done on some keyboards) or B to close it on the screen the model named. HOLD_NAV_MAX (12) then ended the hold.
Not re-run. Identification is done. Next lever: a name_entry rule in the hold (START to Done, then A to confirm) and the still rotation not sending X on a bowling hold. Both are generic, so they go with the bowling-family fix, not a Strike-Force one-off.
Frames: runs/strike-force-bowling/hold.

[lane.pathfind] Strike Force Bowling FAIL (10-05 14:56, runs/strike-force-bowling/hold3; re-hold after the 14:27 fix): held 276 of 600 s. fps clear (median 59.0, 100% at the bar over 284 s). The bowl loop threw and scored (frame scorecard, aim, Player 1's turn). It ended on a high-score NAME ENTRY at 276 s: "off play for 13 steps", and the name_entry label now fires (reason rule and START, A per 10-05). The entry did not close in 13 presses (START, A, B cycled), so the cause is the name-entry keyboard's confirm, not the loop.
Cause (not verified on the keyboard): the entry's Done/confirm is a cursor button the presses did not reach; the claim never saw a name entry. Named cost: about 60 s of game-over and entry per game, and a game is 10 frames. Stopped for today per lane.local (14:50); no further runs on this title today.
Frames: runs/strike-force-bowling/hold3.

[lane.pathfind] MLB SlugFest 2004 PASS (harness; flicker unchecked; 10-05 15:16, runs/mlb-slugfest-2004/hold): claim to a human-assigned batter, then a full 600-s hold. Verdict PASS: 603.9 s gameplay, fps_ok 1.0 at the bar, window median 44.4, position first-to-last 0.63, no still window. Aborted at: full window. Perflog: not taken.
Period: the claim goal set innings to the longest offered (not read back from the frames). The sports look read 1ST inning, PLAYER 1 batting command menu, human-controlled batter (NYM vs ANA).
SCENE SHOULD CONTAIN: a live game, a pitcher on the mound, a batter in the box with the PLAYER 1 command menu on a pitch, fielders on the infield, the scorebug with the inning and score, pitch speed (MPH) readouts.
FRAME REVIEW (my read of hold_strip.jpg, 16 kept frames): the scene matches. The batter-intro "career avg" cards in 060, 080 and 086 are in-game and count as play. 056 shows a fielder down on the grass (a play in progress). No menu frame in the strip.
Frames: runs/mlb-slugfest-2004/hold (frames, hold_strip.jpg). Spend: Sonnet, not totalled here (calls.jsonl).

[lane.pathfind] MLB SlugFest Loaded PASS (harness; flicker unchecked; 10-05 15:30, runs/mlb-slugfest-loaded/hold): claim to a human-assigned batter, then a full 600-s hold. Verdict PASS: 600.8 s gameplay, play_share 0.9995, fps_ok 1.0 at the bar, window median 58.9, position first-to-last 0.62, no still window. Aborted at: full window. Perflog: not taken.
Period: innings set to the longest offered by the claim goal (not read back). The strip reaches the 2nd inning, so the innings ran through the hold.
SCENE SHOULD CONTAIN: a live game, a pitcher and batter with the PLAYER 1 batting prompt (Contact, Power, Bunt, Dodge), fielders, the scorebug with the inning, outs and score, batter intro cards and STRIKEOUT banners.
FRAME REVIEW (my read of hold_strip.jpg, 16 kept frames): the scene matches. The batter intro cards (044, 059) and the STRIKEOUT banner (038) are in-game, not menus. No menu frame in the strip.
Frames: runs/mlb-slugfest-loaded/hold (frames, hold_strip.jpg). Spend: Sonnet, not totalled here (calls.jsonl).

[lane.pathfind] NBA 2K3 CAN'T-PATH on the claim (10-05 15:46, runs/nba-2k3): gave up at the 15-min claim budget after 79 steps and 77 model calls. The team select never gave controller 1 a team: the controller icons stayed in the middle column, so the CPU would have played both sides. No gameplay was reached, so no hold ran.

IDENTIFICATION, team select (ESPN / Sega Sports, the same screen as NBA 2K2 and NHL 2K3). Frame: runs/nba-2k3/hold/frames/021-main_menu.jpg. What it shows: AWAY NETS on the left, HOME LAKERS on the right, STAPLES CENTER between. In the middle column four controller icons stack vertically. The top one is green with a "User Name" bar above it. The other three are dark. Two small side arrows sit at mid-height, left and right of the column. The footer reads X help, B back, START start game, Y options. What the models tried, from the steps: A, D-pad LEFT/RIGHT and A, STICK+A, L1, R1, L3, RT, X, Y and HOLD:A. None put the green icon under a team, and the controller count never changed.
What is NOT verified: which input moves a controller icon under a team. The side arrows are the likely target (press the D-pad toward the side arrow while the green icon is selected, then A), but no run has shown it. Next run's identification: one frame sequence of LEFT then A, then a frame, on NBA 2K3's team select, to see which press moves the green icon. No re-run today.

Applies to: NBA 2K2 (lost ~20 steps to this, then reached play), NBA 2K3 (this run, no play), NHL 2K3 (the 14:16 can't-path: the stick probes never moved a skater, consistent with an unassigned controller).

NEW ISSUE: ESPN team select (NBA 2K2, NBA 2K3, NHL 2K3): no controller icon moves under a team, so the CPU plays both sides and the claim cannot confirm a human player
Evidence: runs/nba-2k3/hold/frames/021-main_menu.jpg; steps 19-79 of runs/nba-2k3/hold/steps.jsonl; NHL 2K3 steps 32-70. Blocks the 2K family's human-controlled team and the NBA 2K/NHL 2K siblings.

[lane.pathfind] DAY SUMMARY 10-05 (for lane.local, spend not totalled here; claim and hold model calls are in each run's calls.jsonl):
- Harness PASSes, full 600-s windows: NFL Blitz 2002 (play 0.990, fps 0.996, 5-min quarter via OPTIONS; frame review: 2 of 16 kept frames are play-call overlays, the play share is generous), NBA 2K2 (play 0.9996, fps 0.995; 2 of 16 frames are a replay card and the NBA logo, so the play share is generous), MLB SlugFest 2004 (fps 1.0, 604 s), MLB SlugFest Loaded (play 0.9995, fps 1.0).
- CLOSE: AMF Bowling 2004 re-hold (play 0.892, a 10-frame game's game-over walk-back of 66 s; the bowling loop works), MLB SlugFest 2003 (play 0.883, 74 s between pitches), NHL Hitz Pro (fps 75% at 30, window median 37.4; play 0.936; human control unverified).
- FAIL: Strike Force Bowling (both holds ended on a high-score name entry; the fps was clear).
- Can't-path: NHL 2K3 (stick never moved a skater; the team select, see the NEW ISSUE), NBA 2K3 (team select never assigned controller 1), Phantom Crash and the earlier screening list as in NOTES.
- Not run today: NFL Blitz Pro (stopped at step 2 on the 12:35 football-last order), AMF Xtreme, NBA 2K3 retry, Tork (deferred by the owner), the football titles (last in the order).
- Code committed on lane/pathfind today: the sports period rule (period_break, the claim period goal, the sports look), the claim's live grace window, a bowl hold loop with its own period budget, the name-entry rule (START then A) and the reason-based name_entry label, and the bowl still move (no X). Selftest all ok (last run: scratch/selftest-attempt3h.log).
- Model use: Sonnet throughout (FAST = claude-sonnet-5).

## #433 -- 2026-10-05 16:05 PDT
[lane.pathfind] ESPN team select IDENTIFIED from stored frames (no device time): the input works and the claim misread it. runs/nba-2k3/hold/frames 019 -> 020: one RIGHT moved controller 1 (the top, yellow one) a single notch into the side column next to HOME, a "User Name" plate appeared above it and its outer arrow went away. That is the assigned state; the controller never travels under the team logo. The model expected it under the logo, called it unassigned, and the next 60 presses (LEFT, RIGHT, sticks) undid and redid it. The help overlay (frame 030) confirms: left stick or D-pad selects team, L/R scroll teams, START advances. Fix committed: the claim rule and global.md's Sports section now say one RIGHT/LEFT, read the plate, then START. NBA 2K3 and NHL 2K3 can re-path with it (answers the ESPN team-select NEW ISSUE, pending a run).
Next on the Nova: AMF Xtreme Bowling (waiting on lane.gpuclock's running request 1-1791221184).

[lane.pathfind] CORRECTION to 16:05 (NHL 2K3): its team select was NOT the cause. runs/nhl-2k3/hold/frames/010-submenu.jpg (Choose Uniforms) shows controller 1 (red) already moved next to HOME Boston after steps 8-9 (RIGHT, A), and the play frames (034) show a red-ringed Boston skater. NHL 2K3 failed on the claim probe: the hockey broadcast camera moves by itself (no-input change 0.26-0.49, over the 0.15 self-moving line), so the probe asked the model whether the player steered LEFT then RIGHT, and it refused every time. The ESPN team-select fix applies to NBA 2K3 (and the 20 steps NBA 2K2 lost), not to NHL 2K3. NHL 2K3 needs a team-sports confirm (the marked skater, not the whole scene), not a re-path.

[lane.pathfind] AMF Xtreme Bowling CLOSE (10-05 16:11, runs/amf-xtreme-bowling/hold): claim 2.5 min, 16 steps, 43 model calls; hold 606 s of play in a 730-s scored window. Verdict FAIL on play share 83.2 percent (bar 90): play 607 s, menu 68 s, still 37 s, loading 10 s. fps_ok 1.0 at the bar, window median 59.1, min 35.0, 3 hitches (worst 239 ms). Aborted at: full window. Perflog: not taken. CLASS: CLOSE (fps clear; play share 60-90 band).
Named cost, from hold.jsonl: (1) the claim picked PRACTICE, which ended at about hold_s 160; the loop's A presses then walked from its end screen into Profiles > Profile Stats, and the hold look took 90 s of menus (Profiles, Pin Challenge difficulty, venue, oil pattern, loading, intro card) to get back into a game. (2) The first 74 s of the hold were still (change 0.002-0.004): the bowl loop's A taps did not throw, and the throws began only when the still move added STICK:up to the loop (change 0.63 from then). Pin Challenge then ran from 256 s to the end with every look reading gameplay (change 0.65-0.88).
Lever: claim Pin Challenge or a full game, not Practice (the goal line), so one mode outlasts the hold; the loop already carries the STICK:up that throws. A re-hold is queued after NBA 2K3 (one try).
SCENE SHOULD CONTAIN: a bowler at the foul line with the power/aim meter, the ball rolling down the lane, pins falling and resetting, neighbouring lanes with other bowlers.
Frames: runs/amf-xtreme-bowling/hold (frames, hold_strip.jpg). Spend: Sonnet, 43 claim calls plus 9 hold looks.

[lane.pathfind] NBA 2K3 CAN'T-PATH again, on the probe this time (10-05 16:26, runs/nba-2k3/hold2): the team-select fix WORKED (step 30 one RIGHT, step 31 the User Name plate read and START; quarter length set to 10 min, the longest). Live play from about step 40, then 15 stick probes over 9 min, all refused: the broadcast camera, the foul / out-of-bounds / goaltending banners and the replays move the whole frame by themselves (no-input change 0.18-0.62), so the steer-left-then-right question was unanswerable. Same cause as NHL 2K3. Gave up at the claim budget; no hold ran.
Fix committed (selftest all ok, 76 checks, scratch/selftest-attempt4c.log): for a team sport (a period or team-select goal, or an NBA/NHL/NFL/NCAA/FIFA name), the self-moving confirm judges ONLY the marked human-controlled player (ring, arrow, name label) and accepts a move LEFT under the left hold or RIGHT under the right hold, against the court markings; a camera cut alone is not a response. Bowling, baseball and racing keep the both-ways test. NBA 2K3 and NHL 2K3 go again with it after the AMF Xtreme re-hold now running.

[lane.pathfind] Strike Force Bowling name entry IDENTIFIED from stored frames (no device time; no run today per lane.local 14:50): runs/strike-force-bowling/hold2/frames/092-hold.jpg. The Name Entry is a letter WHEEL across the top with the footer "D-pad Change Letter, A Select, B Cancel"; END and DEL sit just LEFT of A on the wheel. START does nothing and A only types (the hold typed FFAAFFAA). Likely close: LEFT until END is under the ring, A, then DOWN to Done in the panel, A. Not verified. Written to hints/series-strike-force-bowling.md so the next run's model reads it; the hold's unlooked START/A name rule does not apply to this keyboard.

[lane.pathfind] AMF Xtreme Bowling re-hold (10-05 16:38, runs/amf-xtreme-bowling/hold2): the first boot HUNG on the brushed-metal backdrop before the title (FPS overlay 1, every input ignored, 05:00 to 07:10 of the claim). The 16:11 run passed the same screen in about 10 s. hangwatch tripped (vCPU pinned: 98% of a 2-s window at r:800151ed, frame change 0.0) and then logged "probe-cleared" with frame_change 0.0, so the claim did not stop. I force-stopped the app on the held Nova at 7:10; pathfind relaunched it once (its "not in front" rule), and the second boot went straight through to the title and Pin Challenge. Evidence: hold2/hang.jsonl, hold2/hang/probe-before.png and probe-after.png, hold2/hang-logcat.txt (logcat -t 4000 taken during the hang), frames 004-028.

NEW ISSUE: AMF Xtreme Bowling hangs at boot 1 time in 2 on the Nova: guest vCPU pinned at r:800151ed on the brushed-metal backdrop, FPS 1
Evidence: docs/lanes/pathfind/runs/amf-xtreme-bowling/hold2/hang.jsonl (probe event: share 0.9838, top r:800151ed, idle_us 0), hang-logcat.txt, frames 004-028 (static grey backdrop for 2+ min); the 16:11 run (hold) passed the same screen in 10 s. Also for lane.hangwatch: a probe with frame_change 0.0 was logged probe-cleared, so a pinned, still screen did not end the claim. Blocks a clean first boot of the title.

[lane.pathfind] AMF Xtreme Bowling re-hold FAIL on a CRASH (10-05 16:55, runs/amf-xtreme-bowling/hold2): after the boot hang and one relaunch, the claim went straight to Pin Challenge (the goal line worked: DOWN x4 past Practice, Easy, venue, oil pattern) and confirmed on HOLD:A:3 (change 0.82 under input vs 0.04 idle). The hold then ran 426 s of play at fps 1.0 (median 59.0, 100% at 30) and hakuX died with SIGSEGV at 16:53:46; the hold found the Game Library and stopped. Verdict FAIL (crash), play share 0.747, gameplay 574 s, 7 hitches (worst 211 ms). Aborted at: crash at 7:06 of play. Perflog: the run's logcat carries the perf lines. CLASS: FAIL (crash), fps clear. Spend: Sonnet, about 45 claim calls plus hold looks.
Crash: Caught signal 11 in tid 5355 (pfifo thread) fault_pc in /data/data/com.jreinach.hakux.debug/files/gpu_driver/vulkan.purple.so+0xa21264, si_addr 0x80; backtrace #00 vulkan.purple.so+0xb0ad74, #01-#03 libxemu.so+0x520cb0/0x51e63c/0x51f1d8, #04 pgraph_vk_draw_end, #06 pgraph_method, #07 pfifo_thread. This is the pushed GPU driver, not the system one.

NEW ISSUE: AMF Xtreme Bowling: SIGSEGV in the pushed GPU driver (vulkan.purple.so+0xa21264, si_addr 0x80) under pgraph_vk_draw_end after 7 min of Pin Challenge on the Nova
Evidence: docs/lanes/pathfind/runs/amf-xtreme-bowling/hold2/logcat.txt lines 5719-5738 (backtrace), verdict.json (crash_detail), hold frames; fps was 1.0 at 59 up to the crash. The 16:11 run of the same title held 606 s with no crash (Practice then Pin Challenge). Blocks AMF Xtreme Bowling's Playable.

[lane.pathfind] PARKED for the perf queue (owner priority, lane.local 16:55): Nova released 16:55:30; no Nova title is claimed until the queued perf requests have run (frametrace 1-1791225335 running; gpuclock 1-1791241711, -436985, -437094, -437210; gpunonrender 1-1791243663, 1-1791243666). WAITING lists them.
NEXT SCREENING ORDER when the perf queue drains (P x win; fps is already clear on every one):
1. NBA 2K3 hold3 (scratch/nba2k3c.sh): the team select is fixed and proven on the device (16:2x); only the confirm failed, and the team-sport marked-player confirm is new in b2f6838b03. P about 0.5, and it unblocks the 2K basketball and hockey family.
2. NHL 2K3 hold2 (scratch/nhl2k3b.sh): same confirm fix; its play ran at FPS 29 on the overlay, so the fps bar is at risk. P about 0.35.
3. LEGO Star Wars re-hold (scratch/lego2.sh, golden 5251f98730d1): fps 1.0, the join-prompt START cause is fixed in the hold look (2c2ce35a19). P about 0.5.
4. AvP: Extinction re-hold: fps locked 30, the new title hold (3b1cb99dd3) selects the squad and scrolls the map. P about 0.3 (controls unverified).
5. Football last, per the 12:35 order (NFL Blitz Pro, NFL 2K2, then the rest).
Not again today: AMF Xtreme (crash, for identification), Strike Force Bowling (name-entry wheel identified, untested), Guilty Gear XX, Tork.

## #433 -- 2026-10-05 18:50 PDT

[lane.pathfind] NHL 2K3 FAIL (replay counted as play; harness verdict is wrong): hold2 (runs/nhl-2k3/hold2, 622 s held, 11.2 min claim, 73 model calls) reported PASS on play share 0.973 and fps_ok 1.0 (median 29, locked 30). The frames do not show live play for the back half: frames 070-115 are the instant-replay viewer, with its footer across the bottom reading L Rewind, R Forward, A Play/Pause, X Zoom In, B Zoom Out, Y Hide, START Back (frame 091 is the clearest). The hold's looks read those frames as "gameplay" ("the game world is live", "could be a replay"), so the hold never pressed START and the verdict counted about 300 s of replay as play. The sports look at the start also read no controlled skater (human_controlled false, a goalie close-up), so the controlled-player check did not hold either. SCENE SHOULD CONTAIN (for the re-hold): a human-controlled skater with the marker, the puck moving, the scoreboard and period clock, the crowd, and no replay footer.

NEW ISSUE: the hold verdict counts an instant-replay viewer as play: NHL 2K3 hold2 scored 0.973 play share over about 300 s of replay (footer "L Rewind R Forward A Play/Pause X Zoom In B Zoom Out Y Hide START Back", frames 070-115 of runs/nhl-2k3/hold2/frames). Blocks any sports Playable whose replays run in the hold (the same looks would pass NBA 2K3 replays too). Fix in progress: the hold look now names the footer as period_break with input START (HOLD_REPLAY in pathfind.py; selftest "replay" ok, 77 ok).

Fix committed, one re-hold queued (NHL 2K3 hold3, same recipe). Spend: about 73 model calls on hold2 plus hold looks, Sonnet.

## #433 -- 2026-10-05 19:20 PDT

[lane.pathfind] NHL 2K3 re-hold FAIL (fps; the replay fix worked): hold3 (runs/nhl-2k3/hold3, 612 s held, 6.2 min claim, 46 model calls, Sonnet). Play share 0.989 of 612 s (fps excluded 9.4 s). The frames are live play through both periods (1st 12:27 to 2nd 12:23; PWR PLAY, ICING, PUCK FROZEN, no replay footer: the HOLD_REPLAY rule held). Harness verdict FAIL: 69.4% of gameplay at or above the 28.5 bar (the verdict's text says "30", but the threshold is 30 x 0.95), median 35.0, window min 17.3. Hold2 (the replay run) had median 30.1 at the same title, so the frame rate is not stable between runs. Aborted at: full window. Perflog: taken from the hold's logcat (the hold carries the perf lines; no separate run).

Named cost (decompose.py on the hold's own logcat; the mark copied into a scratch run.log, see NOTES): 305 two-second windows, 422 s at or above the bar, 188 s below (share 0.69). Below-bar windows: fps 24.2 against 36.2 at the bar; guest busy 26.6 ms per frame against 13.3 at the bar; guest idle 14.9 against 13.0; renderer idle (Ri) 40.7 against 27.2; timer interrupts about 12 ms in both groups. A slow frame here is guest code on the vCPU (busy time doubles, idle does not fall, Ri rises as the renderer waits for the guest), not the renderer or a shader stall. The slowest 10% of windows (fps 22.0) are the same pattern (guest busy 24.5 ms).

NEW ISSUE: NHL 2K3 frame rate drops to ~24 fps in 31% of play (vCPU guest busy doubles, 13 to 27 ms per frame in the slow windows): runs/nhl-2k3/hold3 logcat.txt, decompose.py output above. Blocks the NHL 2K3 Playable: play share 0.99 and the replay fix are fine, fps is the only failing gate. Not queued again today (owner rule: a miss gets telemetry and a named cost, not a re-run).

SCENE SHOULD CONTAIN (for the next reviewer): the hockey broadcast camera on a live rink, a human-controlled skater with the marker, the puck in play, the scoreboard HUD with a running clock; the replay footer must not appear.

Spend: NHL 2K3 hold2 (73 model calls) and hold3 (46 calls) in Sonnet, about $6 for the two claims and looks together.

## #433 -- 2026-10-05 19:40 PDT

[lane.pathfind] Strike Force Bowling FAIL (play share, game end): hold4 (runs/strike-force-bowling/hold4) and hold5 (runs/strike-force-bowling/hold5). Claim 3.1 min, 17 steps, 34 model calls: the name entry at the start (DOWN x4, A, the default name) worked on the bowler's creation, and the claim reached the bowling aim screen at about 2.5 min. fps clear: median 59.0, 100% at the bar, window min not below 28.5. Play share 0.80 (hold4) and 0.73 (hold5) of about 380 s; the hold ended off play at 276-279 s both times, after 13 off-play steps.

Named cost, from hold.jsonl and frame 085 (hold5): (1) the first game ends at about 4.6 min of play (the loop's A presses walk through the game-over prompts); (2) the game then opens the high-score NAME ENTRY for the bowler ("Name field, Strength/Accuracy/Curve bars, Done"), and then Name Entry for Player 2, 3, 4, 5; (3) the title's DOWN x4 then A (the claim's default-name sequence) did NOT leave that high-score entry in hold5 (six presses, same screen); the recovery's B and A then reached PlayerSelect (frame 085: Mary Anne highlighted, Change / Select / Cancel footer), where no lanes are in play. The hold ends there. The game-length setting in the claim was not confirmed to be the longest offered (one game of about 4.6 min); if the first game is the longest, a rematch or Add-another-game entry on the game-over screen is the input to find.

NEW ISSUE: Strike Force Bowling hold ends at the first game's end: the high-score name entry is not left by the title's default-name sequence, and PlayerSelect is the only way back (runs/strike-force-bowling/hold5/frames/085-hold.jpg). Blocks the bowling Playable (fps clear, play share 0.73-0.80). Input for the high-score entry and the rematch screen not yet identified; needs the game-over frames (hold4 frames 040-080) read before the next run.

SCENE SHOULD CONTAIN: a bowler at the foul line with the aim meter, the ball rolling down the lane, pins falling and resetting, the frame sheet, neighbouring lanes with bowlers.

Parked: no third run today (rule: identify, do not re-run). Next: LEGO Star Wars re-hold (one try), then AvP re-hold (one try), football last.

## #433 -- 2026-10-05 20:00 PDT

[lane.pathfind] LEGO Star Wars CLOSE (play share 84%, fps clear): re-hold (runs/lego-star-wars/hold2), 607 s held, scored window 727 s. Verdict FAIL on play share 0.84 (bar 0.90): play 611 s, still 74 s, cutscene 42 s. fps_ok 0.976 at the bar, median 59.0, 3 hitches (worst 157 ms). The join-prompt fix worked: the hub did not go to the pause menu (the previous run's 68.5% share had 117 s of cutscene and 17 s of pause). Claim and hold: 9 claim steps, the golden 5251f98730d1 with `--state any`. Aborted at: full window. Perflog: not taken. Spend: a few model calls (Sonnet).

Named cost, from frames (hold_strip.jpg): (1) about 60 s of title and story cards at the start of the window: the "Episode 1 The Phantom Menace" card (frame 024), the level's "Chapter 1 NEGOTIATIONS" card (043-051, about 20 s of no-control card), the Star Wars crawl (055), then a cutscene of battle droids (058): these are the cutscene and loading share. (2) From about 540 s the two characters stand in one room, attacking the droids with the saber while the camera stays put (frames 080-098): the scene is live but the characters do not travel, so the still test counted about 74 s of still. That is the stand-still case (the 60-s rule), and the hold did not rotate its inputs. Not re-run: CLOSE, one try per title.

SCENE SHOULD CONTAIN: a LEGO minifigure hero (Anakin or Obi-Wan) with the health hearts and stud counter in the corner, moving through a level, droids and enemies in the room, the camera following the hero, no card, no crawl.

Next: AvP re-hold (one try, title hold 56550022), football last.

[lane.pathfind] AvP Extinction FAIL (play share 0.06, scene still; re-hold 2): runs/avp-extinction/hold2, budget 23 min, play 67 s, still 1146 s (static_frac 0.99), fps_ok 1.0 (median 31, locked 30). The title hold (TITLE_HOLD 56550022: select the squad, long cursor strokes, A to order) never moved the scene: the strip is a near-black RTS map with a small panel and a cursor that moves a few pixels. Aborted at: budget (23 min); no crash, no hang. Perflog: not taken.

Named cost: the squad orders do not register on this screen. The hold reads the screen as dark and static, and the look never names a control that changes the view. Not re-run (a failed run is identified first, not repeated). Next step for AvP: read the claim frames (runs/avp-extinction claim) for the order mode's footer before another hold.

NEW ISSUE: AvP Extinction: the squad-order input does not move the RTS scene (99% static over 20 min; the map is almost black); needs the order-mode footer read from frames before a hold. Blocks AvP's Playable.

## #433 -- 2026-10-05 20:22 PDT

[lane.pathfind] Mortal Kombat Shaolin Monks PASS (harness, full window): play share 0.936 of 645 s, fps_ok 1.0 at the bar, hitches 1 (worst 116 ms), no crash or hang. Claim 3.5 min, 30 steps, 27 model calls (Sonnet, about $1.5). Run: runs/sweep-4D570029 (frames/, hold_strip.jpg, verdict.json). Aborted at: full window. Perflog: not taken. Flicker: unchecked (owner's check).

SCENE SHOULD CONTAIN: Liu Kang (or the fighter the claim picked) walking and fighting through the dungeon rooms, the health bar and EXP bar in the top-left, enemies in the room, the room changing across the window (frames 042 to 088 show three rooms).

Frames for the owner: runs/sweep-4D570029/frames (about one frame per 3 s in the strip; the kept frames are every 15-30 s). Frame review: the strip shows the scene moving and the player walking, not a title card.

## #433 -- 2026-10-05 20:40 PDT

[lane.pathfind] Mortal Kombat: Armageddon PASS (harness, full window): play share 0.955 of 636 s, fps_ok 1.0 at the bar, hitches 0, no crash or hang. Claim and hold in one run (runs/sweep-4D570034, 13 min). Run dir: frames/, hold_strip.jpg, verdict.json. Aborted at: full window. Perflog: not taken. Flicker: unchecked (owner's check).

SCENE SHOULD CONTAIN: two fighters in a live round (Scorpion against Jax, Havoc, Sektor or Kenpo in the frames), the health bars, round timer, wins counter, a stage with blood and background movement. The hold also passed two menu frames (the ARCADE / VERSUS / PRACTICE menu at 056 and a roster select at 060) between rounds, and then returned to the fight; the reviewer should expect those within the 4.5% non-play.

Frames for the owner: runs/sweep-4D570034/frames (strip every 3 s, kept frames every 15-30 s).

## #433 -- 2026-10-05 21:00 PDT

[lane.pathfind] Mortal Kombat Deadly Alliance PASS (harness, full window): play share 0.915 of 657 s, fps_ok 0.996 at the bar, hitches 2 (worst 156 ms), no crash or hang. Claim and hold in one run, 16 min (runs/sweep-4D57000C). Run dir: frames/, hold_strip.jpg, verdict.json. Aborted at: full window. Perflog: not taken. Flicker: unchecked (owner's check).

SCENE SHOULD CONTAIN: Shang Tsung against Kung Lao (or the claim's fighter pair) on the Shaolin temple stage, two fighters in a live round with the health bars and the round wins, blood and snow on the stage. The window also held a CONTINUE? countdown (frame 041: the hold pressed through it, START then A) and a loading screen (045), then the fight resumed; the reviewer should expect them within the 8.5% non-play.

Frames for the owner: runs/sweep-4D57000C/frames.

## #433 -- 2026-10-05 21:20 PDT

[lane.pathfind] Spider-Man 2 FAIL (fps; play share fine): runs/sweep-4156002B, 608 s held, claim 1 run (about 9 min). Play share 0.9995 (gameplay 607 s, no menu). fps: window median 25.8, min 17.9, 28.9% of play at the 28.5 harness bar (the 3- and 5-minute gates read median 29.0 and 29.0, so they did not stop it: the rule is below 22 at 3 min or below 27 at 5 min). Aborted at: full window. Perflog: the hold's own logcat, with the mark copied into a scratch run.log (no separate run; no re-run queued).

Named cost (decompose.py on the hold's logcat, 302 two-second windows, 158 s at or above the bar, 446 s below, share 0.26 at the bar): in the below-bar windows the frame rate is 23.6 against 29.7 at the bar, and the RENDERER is the busy side: renderer idle (Ri) falls from 18.1 ms per frame to 7.1 ms, while the guest sits idle (27.4 ms per frame on average, timer-woken). Guest busy is about the same (12.5 against 10.4 ms). So the slow frames are the renderer's (host GPU or draw path), not the vCPU's: the opposite of NHL 2K3's pattern.

NEW ISSUE: Spider-Man 2 frame rate drops to ~24 fps in 60% of play with the renderer busy (Ri 7 ms against 18 at bar; guest busy unchanged): runs/sweep-4156002B logcat, decompose.py output above. Blocks Spider-Man 2's Playable (play share 0.9995; fps is the only failing gate).

SCENE SHOULD CONTAIN: Spider-Man in New York streets or interiors, moving, traffic and pedestrians, the health bar and the web meter, the camera following him.

## #433 -- 2026-10-05 21:30 PDT

[lane.pathfind] Batman Begins CAN'T-PATH (claim budget 15 min, 100 steps, 75 model calls, about $3): gameplay looks reached 21 times and the probe ran 21 times. The probe refusals were in a combat tutorial with enemy thugs in view and the prompts changing (X, Y, B finisher): the control and under-input values read 0.35 to 0.88 against 0.30 to 0.70 under input, so no probe settled as control. The mission failed six times (game_over: Restart Level, Continue Last Checkpoint dimmed), and the last 8 steps were cutscenes (START) with black frames between. Last named state: cutscene (step 100, runs/sweep-45410389, steps.jsonl). No hold ran; not re-run in this session (can't-path rule: move on).

NEW ISSUE (for identification): Batman Begins: the confirm probe cannot settle the combat tutorial (thugs moving under input, prompts for X/Y/B), and the mission-failed loop restarts the claim. Blocks Batman Begins' path. The tutorial's prompts should be taken as the input (X, then Y, then B finisher), not probed.

## #433 -- 2026-10-05 21:45 PDT

[lane.pathfind] Need for Speed Most Wanted FAIL (fps; aborted at 5:06 by the fps gate): runs/sweep-4541007B. Play 306 s (share 0.999 of the window), fps_ok 0.19 at the 28.5 bar. The gate read median 26 at 5:06 (below 27, 20% of 127 samples at the bar) and stopped the hold, as the rule says. Claim about 14 min, 53 model calls. Aborted at: 5:06 (fps gate). Perflog: the hold's own logcat (mark 21:23:12.8 copied into a scratch run.log; no separate 3-min run was queued, since the perf lines are already in the record).

Named cost (decompose.py, 152 two-second windows, 56 s at or above the bar, 248 s below): guest busy is about 25 ms per frame in both the fast and the slow windows (24.1 at the bar, 25.5 below), and renderer idle is the same (11.2 against 10.7 ms). The slow windows add timer-woken idle (13.9 ms against 9.1 per frame) and the frame rate falls to 24 fps. So the cost is the vCPU's: the guest code costs about 25 ms per frame throughout (a ceiling near 40 fps by itself), and the slow windows are pacing on top of it. Not a renderer cost.

NEW ISSUE: Need for Speed Most Wanted: the guest code (vCPU) costs about 25 ms per frame throughout play, so the title runs at ~24-26 fps (median 26 at 5 min): runs/sweep-4541007B logcat, decompose.py output above. Blocks NFS Most Wanted's Playable (play share fine; fps is the only gate).

SCENE SHOULD CONTAIN (for the next reviewer, if it ever clears): a car on a Rockport or city road, traffic and police cars, the HUD speedometer and the heat bar, the camera behind the car.

## #433 -- 2026-10-05 22:00 PDT

[lane.pathfind] Midnight Club II FAIL (fps; aborted at 5:03 by the fps gate): runs/sweep-54540008, claim about 14 min. Gate at 5:03: median 23, 0% of 117 samples at the bar, stopped as the rule says (below 27 at 5 min). Gameplay 303 s; verdict play share 0.635 (still 0.53 of the window: the camera and car wait at a few points); fps_ok 0.00. Aborted at: 5:03 (fps gate). Perflog: the hold's own logcat (mark 21:37:04.5 copied into a scratch run.log, no separate run).

Named cost (decompose.py, 151 two-second windows, all below the bar, median 23.1): the RENDERER is saturated: renderer idle (Ri) is 0.0 ms per frame, so the render thread never waits for the guest, while the guest is idle 30 ms of a 43-ms frame (timer-woken 22 ms, other 7 ms) and busy 13 ms. This is a renderer-bound title: the frame time is the render thread's own work, and the guest is waiting on it.

NEW ISSUE: Midnight Club II: the renderer is saturated (Ri 0 ms per frame) at a median of 23 fps: runs/sweep-54540008 logcat, decompose.py output above. Blocks Midnight Club II's Playable (fps is the only failing gate; play is 0.64 with the stalls at the camera).

SCENE SHOULD CONTAIN (for the next reviewer, if it clears): a street race in a city, the car moving, traffic, the speedometer and the race position, the camera behind the car.

## #433 -- 2026-10-05 22:08 PDT

[lane.pathfind] The Lord of the Rings: The Return of the King FAIL (fps; play full window): runs/sweep-4541003E, 607 s held, claim about 10 min. Play share 0.9997 of 607 s, no crash, no hang, 0 hitches. fps: window median 27.7, min 20.3, 33.3% of play at the 28.5 bar; the 3- and 5-minute gates read median 27.0 and 27.0 (on the rule's line, so the hold went on). Aborted at: full window. Perflog: the hold's own logcat (mark 21:49:12.3 copied into a scratch run.log, no separate run).

Named cost (decompose.py, 302 two-second windows, 190 s at or above the bar, 414 s below, share 0.31): guest busy is the cost: 27.9 ms per frame below the bar against 24.1 at it, and the vCPU runs 0.70 of the time. Renderer idle is 22.7 ms, so the renderer is waiting, not saturated. This is the vCPU's guest code (the same pattern as NHL 2K3 and NFS MW), not the renderer.

NEW ISSUE: LOTR Return of the King: the guest code (vCPU) costs 24-28 ms per frame, so play runs at ~27 fps median and 33% of play at the bar: runs/sweep-4541003E logcat, decompose.py output above. Blocks LOTR's Playable (play share 0.9997; fps the only failing gate).

SCENE SHOULD CONTAIN: Aragorn or another hero in a battle with orcs, a wide camera on the battlefield with many enemies, the health bar, the camera moving with the hero.

## #433 -- 2026-10-05 22:22 PDT

[lane.pathfind] The Incredible Hulk: Ultimate Destruction FAIL (fps; play full window): runs/sweep-56550039, 604 s held (claim about 10 min). Play share 0.9996, no crash, no hang, 3 hitches (worst 148 ms). fps_ok 0.64 at the 28.5 bar (the verdict's text says "30"; its threshold is 28.5). Aborted at: full window. Perflog: the hold's own logcat (mark 22:02:06.4 copied into a scratch run.log, no separate run).

Named cost (decompose.py, 302 two-second windows, 368 s at or above the bar, 236 s below, share 0.61): the slow windows are guest code: guest busy 30.5 ms per frame against 16.4 at the bar (the guest idle falls from 17.2 to 7.4 ms), and the vCPU runs at 0.74 against 0.91 at the bar. The renderer is not the limit (Ri 14.7 against 19.7). So this title's slow scenes are heavy guest work (the open-city destruction scenes), the vCPU's.

NEW ISSUE: The Incredible Hulk: Ultimate Destruction: the slow scenes are vCPU guest work (guest busy 30 ms per frame against 16 at bar): runs/sweep-56550039 logcat, decompose.py output above. Blocks Hulk's Playable (play share 0.9996; fps 0.64 of play at the bar).

SCENE SHOULD CONTAIN (if it clears): the Hulk in a city street or a destruction scene, buildings and vehicles breaking, the health bar, the camera behind him.

## #433 -- 2026-10-05 22:33 PDT

[lane.pathfind] Fight Club CAN'T-PATH (claim budget 15 min, 72 steps, 77 model calls, about $3): the claim reached a live fight 22 times and probed each (22 probes). The probes were read against the hit reactions of the fight: most refused, and the closest read was control 0.51 against 0.41 under input, which was not enough to confirm. The claim then ran into the post-fight rematch prompt (YES highlighted, A accepted it) and a cinematic close-up (step 72). No hold ran. Last named state: cutscene (step 72, runs/sweep-5655002F, steps.jsonl). Not re-run (can't-path: move on).

NEW ISSUE (for identification): Fight Club: the fight confirm probe (STICK probes during a fight) refuses on hit reactions; the attack-genre loop would confirm on the fight's own action (X presses change the fighters' stances), and the rematch prompt is an A press. Blocks Fight Club's path; the fighting probe needs the same treatment as the Guilty Gear fight hold.

## #433 -- 2026-10-05 22:50 PDT

[lane.pathfind] Marvel Nemesis: Rise of the Imperfects FAIL (menu loop at the end-of-match panel; fps fine): runs/sweep-4541038A. Claim about 13 min, 73 steps, 77 model calls; the claim's "four probes refused" reason is not the hold's. Hold: 251 s of play (verdict play share 0.62; fps_ok 1.0, no hitches), then the hold stopped at 155 s of play on the END OF MATCH panel after 13 off-play steps.

Named cost (hold.jsonl, looks 155-247 s): a two-screen cycle. The panel (REMATCH / RETURN TO CHARACTER SELECT / QUIT TO MAIN MENU) and the "Are you sure you want to REMATCH?" dialog (NO/YES, NO highlighted) turned into each other six times: the loop pressed STICK:down and A, which lands on NO and returns to the panel. The working input is not verified: from the confirm dialog, YES then A (the cursor is on NO by default), or B to cancel and A on REMATCH. Not re-run (identify first).

NEW ISSUE: Marvel Nemesis: the end-of-match REMATCH confirm defaults to NO, and the hold's recovery cycles panel to confirm to panel (6 times in 90 s). Blocks Marvel Nemesis' Playable (fps clear; play 0.62).

SESSION SUMMARY (lane.pathfind, 10-05 17:50 to 22:50, Sonnet; spend about 2,500 model calls for the day, estimated near $125 at the lane's $0.05 a call -- the owner's cap is the number to check):
- Full-window harness PASS, for lane.local frame review: NBA 2K3 (play 0.988, 615 s, fps 0.92); Mortal Kombat Shaolin Monks (0.936, 645 s); Mortal Kombat: Armageddon (0.955, 636 s); Mortal Kombat Deadly Alliance (0.915, 657 s).
- FAIL on fps (named cost, telemetry from the hold's own logcat): NHL 2K3 hold3 (guest busy in slow windows; NEW ISSUE, replay-free); Spider-Man 2 (renderer busy, Ri 7 vs 18 ms; NEW ISSUE); NFS Most Wanted (guest 25 ms per frame; aborted at 5:06; NEW ISSUE); Midnight Club II (renderer saturated, Ri 0; aborted at 5:03; NEW ISSUE); LOTR Return of the King (vCPU guest busy; NEW ISSUE); Hulk Ultimate Destruction (vCPU guest in slow scenes; NEW ISSUE).
- FAIL, other: NHL 2K3 hold2 (replay read as play, fixed; NEW ISSUE filed); Strike Force Bowling (game-end high-score entry; NEW ISSUE); AvP re-hold (scene still; NEW ISSUE); Marvel Nemesis (REMATCH confirm loop; NEW ISSUE).
- CLOSE: LEGO Star Wars (play 0.84, fps 0.98: cards and a still room; one try used).
- CAN'T-PATH: Batman Begins (combat tutorial probes; NEW ISSUE); Fight Club (fight probes on hit reactions; NEW ISSUE).
- Not run (deadline 22:40 for starts): Rogue Trooper, Ratatouille, Winning Eleven 9, Blowout, Tecmo Classic Arcade. Football (NFL Blitz Pro, NFL 2K2 etc.) not started, per the 12:35 order.

What the next lane should not repeat: the verdict's fps text says "at >= 30" but its threshold is 28.5 (30 x 0.95): read the share, not the text. A hold that stops at a menu after 13 steps is a recovery miss, not a play share; name the input from the frames before a re-run.

Telemetry: decompose.py needs a run.log with the mark line; runs without --perflog carry the perf lines in logcat.txt, and the mark is copied into a scratch run.log (scratch/telemetry-*/).

## #433 -- 2026-10-05 22:55 PDT

[lane.pathfind] Session status (attempt 2 of the resume): no device run tonight. The 10-05 sports and sweep order stops here: the five unrun sweep titles (Rogue Trooper, Ratatouille, Winning Eleven 9, Blowout, Tecmo Classic Arcade) and the football family (NFL Blitz Pro, NFL 2K2, NFL Blitz 2003, NCAA College Football 2K3, NFL 2K3) are not started. The Nova's screening-only window ended at 22:00. Spend: not measured by this attempt; the lane's estimate is about $125 of the $220 cap (owner's figure is the authority).

Committed for frame review (the harness PASSes from today, unchanged): NBA 2K3, NBA 2K2, MK Shaolin Monks, MK Armageddon, MK Deadly Alliance, MLB SlugFest 2004, MLB SlugFest Loaded. LEGO Star Wars and AvP path files re-recorded by their re-holds are committed with this status.

Resume: time-gated WAITING (2026-10-06 07:10 PDT). Next item: the five sweep titles, then football last, each to a verdict before the next.

## #433 -- 2026-10-06 01:28 PDT

[lane.pathfind] Marvel Nemesis: Rise of the Imperfects FAIL on play share (menu time), fps clear: 85.6% of the scored window in play (567 s play, 45 s menu, 35 s results, 15 s pause; bar 90%), fps_ok 0.991, median 29, no crash or hang. Run: runs/sweep-4541038A (claim 12.9 min, 74 model calls, replayed 6 steps; hold 664 s). Spend: this session's model calls (claim 74 + hold looks); not priced.

Named cost, from hold.jsonl (n134-n146): the run used the first rule (one STICK:up:0.5, then A). The stick push did not move the panel cursor: the A that followed opened QUIT TO MAIN MENU (n134-135), then the hold cycled QUIT, RETURN and the panel for ~90 s, with B and STICK-down-A on each dialog, before the stop at 562 s. The REMATCH confirm was reached only once, at n102 of the earlier run. Frames 101 and 106 show the panel opens on REMATCH and the confirm on NO.

Fix in the tree (cf10c3a95c and the next commit): the panel now takes UP, UP, A (two taps reach the top row from any of its three rows); the confirm takes DOWN, A (to YES); a RETURN confirm takes B back to the panel. Selftest 79 ok. Not yet run on the device; a re-hold (runs/sweep-4541038A-r2) is queued behind the sweep queue, after Rogue Trooper and the other unrun titles.

SCENE SHOULD CONTAIN (if it clears): Marvel Nemesis in an arena fight, both fighters' health bars and portraits, the camera following the fighters, a live round (not an END OF MATCH panel).

## #433 -- 2026-10-06 01:41 PDT

[lane.pathfind] Rogue Trooper PASS (harness, Nova, first-run claim): 6.1 min to gameplay, 31 model calls, 27 steps; hold 609.8 s of play, play share 0.9997, fps_ok 1.0 (bar 28.5), no crash or hang. Run dir: runs/sweep-5343000E (frames/036-hold.jpg, frames/083-hold.jpg, strip.jpg, verdict.json). Excluded time 1.1 s. Spend: this session's model calls (31 claim, hold looks), not priced.

SCENE SHOULD CONTAIN: Rogue Trooper in third person on an alien crystal landscape, the HUD (radar bottom left, ammo and health bottom right), the player moving through canyons and past crystal formations, the camera behind him. Caveat for the frame review: the 'Press to enter the digipad' prompt is on frames 036 and 083 (about 45 s apart) with the scene changed between them, so check that the walk covered ground and did not circle one terminal.

Flicker: owner's check (frames above).

## #433 -- 2026-10-06 03:26 PDT

[lane.pathfind] Marvel Nemesis r3 FAIL on ONE HITCH (play share and fps clear): runs/sweep-4541038A-r3, claim 7.6 min (48 model calls, 46 steps), hold 603 s, play share 0.9998, fps_ok 0.992, static 0.0015, no crash or hang. The REMATCH rule did not fire in this run (the match did not end in 600 s), so the fix is still unexercised on the device. The only miss is a 1014 ms stall at 167 s into the window against the 500 ms hitch bar (verdict: `unexplained`, not shader or texture).

Named cost (decompose.py on the run's logcat; 300 two-second windows, 594 s at the bar, 6 s below): the three slow windows (one at 12 fps) have the guest busy 10.9 ms and the vCPU idle 41.6 ms, of which 38.6 ms is timer-woken (the guest waits on time), and the renderer idle (Ri) 25 ms. Neither the guest's work nor the renderer's is the cost: both are idle at once. That points at a host stall outside the emulated work (the capture or the host), not at Marvel's scene.

NEW ISSUE: the hitch bar counts an all-idle host stall as a title hitch: Marvel Nemesis r3 fails on one 1.01 s stall at 167 s where guest and renderer are both idle (timer-woken, Ri 25 ms; decompose on runs/sweep-4541038A-r3). Blocks Marvel's Playable (play 0.9998, fps_ok 0.992; the only fail is the hitch). Not re-run: the cause is named but not fixed (a host stall is not a title cost, so the fix is in the verdict or the capture).

## #433 -- 2026-10-06 03:00 PDT

[lane.pathfind] Marvel Nemesis re-hold FAIL (duration: 284 s of gameplay, the REMATCH loop again): run runs/sweep-4541038A-r2, claim 10.8 min, 71 model calls, hold stopped at 186 s of play (off play 13 steps on the END OF MATCH panel and its confirms). fps_ok 0.988, median fine, no crash. Spend: model calls, not priced.

Named cost (hold.jsonl, looks 101-111): the panel reads REMATCH highlighted, and UP UP A still opened RETURN TO CHARACTER SELECT's confirm, then the cycle ran panel, RETURN confirm, panel, QUIT. The menu wraps: UP from the top row goes to QUIT, so two UPs from REMATCH land on RETURN. The 13-step cap then stopped the hold, so the REMATCH confirm (which the rule would have answered: DOWN, A) was never reached.

Fix (2b851dd27f): the panel takes A only when the look reads REMATCH highlighted, else one UP and read again; the REMATCH confirm takes DOWN, A (to YES); a RETURN confirm takes A (its NO default cancels back to the panel). Selftest 79 ok. Re-hold queued as runs/sweep-4541038A-r3 (log scratch/queue1006c.log), the third and last Marvel run unless it clears.

## #433 -- 2026-10-06 02:44 PDT

[lane.pathfind] Tecmo Classic Arcade GAVE UP at the 15-min claim budget (no hold, no verdict): 70 steps, 76 model calls. The claim reached a live Tecmo Cup match at about 14.5 min (step 67: HUD, a counting clock, players moving), the probe was refused (control 0.014 under input 0.100), a GOAL banner followed, and the budget ran out at step 70. Last named state: cutscene (GOAL banner), runs/sweep-5443000E (steps.jsonl, frames).

Named cost (steps 61-64): a GAME OVER screen (match ended, TIME 00:00) cycled START, A, B, DOWN+A, UP+A and X RIGHT A for ~60 s, none of which left it; the attract screen (PUSH ONE PLAYER BUTTON, step 65) then took START. The claim spent about 150 s of the budget on game-over and attract screens before it reached a live match. Not re-run: identify first. Next step for a re-claim: the arcade collection's game-over exit (START from the match-end card) is the input to test, and the claim's budget should not stop once play is live (ADDENDUM 10-04 rule).

## #433 -- 2026-10-06 02:29 PDT

[lane.pathfind] Blowout FAIL (play share, still walls; fps clear): 1.8 min to gameplay, 25 model calls, 8 steps; hold 780 s, play share 0.776 (bar 0.90), fps_ok 1.0, no crash or hang. Run dir: runs/sweep-4D4A0008 (frames/024-hold.jpg, frames/062-hold.jpg, verdict.json). The model read gameplay in every check; the hold's own motion readings show 3 still stretches (windows at 78-112 s, 447 s and 717 s, change 0.005 to 0.02, against 0.13 to 0.28 in the moving windows), about 175 s in all. Frames 024 and 062 are different corridors, so the player moved between them; the still stretches are where the genre walk pressed into a dark corridor wall. The stand-still unstick fired two windows late each time (the first still window at 78 s; play resumed only at 153 s).

NEW ISSUE: Blowout: the generic hold's stand-still recovery is slow in dark corridors (two still windows before the first unstick, and the walk returns to the same wall); blocks Blowout's Playable at 77.6% play share (fps clear, 1.0). Not re-run: next step is a Blowout walk (or an earlier unstick for the generic genre) identified from these frames.

SCENE SHOULD CONTAIN (if it clears): Blowout's dark industrial corridors with the first-person weapon and HUD (ammo, health bars), a moving view down the corridors, enemies or doorways changing across the window.

## #433 -- 2026-10-06 02:13 PDT

[lane.pathfind] World Soccer Winning Eleven 9 PASS on the harness, WITH A CONTROL CAVEAT: 6.3 min to gameplay, 39 model calls, 30 steps; hold 629.7 s, play share 0.9731 (static 0.113), fps_ok 1.0 (bar 28.5), no crash or hang. Run dir: runs/sweep-4B4E002F (frames/039-hold.jpg, frames/084-hold.jpg, strip.jpg, verdict.json). Setup done in the claim: Match Time set to 20 min (the longest offered), so the first half ran 24:21 of clock with no half-time in the window. Spend: this session's model calls, not priced.

The control check is NOT confirmed. The sports look in the hold said human_controlled: False (no controller icon under either name bar), so the hold ran its generic team loop. Frames 039 and 084 show a blue control marker (an arrow and a ring on the radar) on a player, which is what a human-controlled player looks like here, but no frame pair shows the marked player moving under the hold's input. Lane.local should confirm control before it counts this as a Playable; a CPU-only match would be a FAIL.

SCENE SHOULD CONTAIN: the Konami WE9 pitch with both teams (Austria in red and white, the other side in white and black), the HUD (half and clock top left, score top right, the radar at the bottom middle with the blue control ring on your player), players moving across the pitch, the score moving in a live half.

## #433 -- 2026-10-06 01:55 PDT

[lane.pathfind] Ratatouille PASS (harness, Nova, first-run claim): 3.4 min to gameplay, 26 model calls, 21 steps; hold 605.3 s of play, play share 0.9998, fps_ok 1.0 (bar 28.5), static fraction 0.002, no crash or hang. Run dir: runs/sweep-54510109 (frames/030-hold.jpg, frames/091-hold.jpg, strip.jpg, verdict.json). Excluded time 1.4 s. Spend: this session's model calls (26 claim, hold looks), not priced.

SCENE SHOULD CONTAIN: Remy the rat in third person in the Ratatouille village (a stone cottage, gardens, a stone wall, grass, collectible mushrooms), the HUD counter top left (mushrooms collected, x/35) rising through the window (1/35 at frame 030, 6/35 at frame 091: real collection progress), the camera behind the rat.

Flicker: owner's check (frames above).

## #433 -- 2026-10-06 06:46 PDT

[lane.pathfind] Mortal Kombat: Armageddon (4D570034) FAIL on play share (fps clear): re-hold, first-run claim (no golden loaded), 600-s hold, run dir runs/rehold-4D570034 (frames/013-gameplay.jpg, hold_strip.jpg, verdict.json). Scored 588.6 s from the gameplay mark: play share 0.798 (bar 0.90): play 469.8 s, menu 93.7 s, still 16.9 s, black 8.1 s. fps_ok 1.0 at the 28.5 bar, median 59.9, min 30.2, no crash, no hang. Claim to the first live round at 2.0 min.

Ref and env: I could not read this run's device record (pathfind.py passes no ref, and no dispatch result carries its request id). The pre-hold gate read the last clean Nova result before the take: ref c3a0c70ace (origin/master), apk 6beaa5ac1cdd, env []. Read that as the build, not as a per-run receipt.

Named cost (hold.jsonl): most of the menu time is the Character Select grid with Scorpion highlighted, read as not a live round on about 15 looks in a row. The recovery answered each look with A on the highlighted fighter, and the round never restarted from that screen. This is the fighting-game hold recovery (the same family as the Guilty Gear CONTINUE/select problem), not performance.

NEW ISSUE: fighting-game hold stalls on Character Select after a round, so the play share falls to 0.80 on Mortal Kombat Armageddon. The recovery needs a rule for returning from the grid to a live round, not one A per look. Blocks Armageddon's Playable (fps clear; play share 0.80 against 0.90). Not re-run: identify the input from the frames first.

SCENE SHOULD CONTAIN: MK Armageddon live rounds, two fighters in a 3D arena, a HUD with health bars and a round timer, the fighters moving and trading hits between rounds; no character-select grid during the window.

Spend: model calls for this run, not priced (claim and hold looks). Queue continues: MK Shaolin Monks is next.

## #433 -- 2026-10-06 07:01 PDT

[lane.pathfind] Mortal Kombat: Shaolin Monks (4D570029) FAIL on play share, a near miss (fps clear): re-hold, first-run claim, 600-s hold, run dir runs/rehold-4D570029 (frames/028-gameplay.jpg, verdict.json, hold.jsonl). Claim to gameplay 3.15 min. Scored 686.5 s from the gameplay mark, 84.7 s excluded: play share 0.880 (bar 0.90): play 603.8 s, still 82.6 s. fps_ok 1.0 at the 28.5 bar, median 50.9, min 38.6, no crash, no hang.

Ref and env: as for Armageddon, this run's device record could not be read (pathfind.py passes no ref). The pre-hold gate read ref c3a0c70ace (origin/master), apk 6beaa5ac1cdd, env [] from the last clean Nova result. Read that as the build, not as a per-run receipt.

Named cost (hold.jsonl, steps 39-60): the scene goes still from about 130 s to 230 s (window change falls from 0.55 to 0.003) while the genre walk keeps pressing STICK:up, X and A. The stand-still check fires and the unstick comes only at 229 s (STICK:right:2 and A), so the still stretch costs about 100 s. The other still stretches (about 60 s in all, 466-520 s and 634 s) show the same recovery lag. Frames not yet read for the still stretch; that is the next step for identification.

NEW ISSUE: the generic hold's stand-still recovery is slow on Mortal Kombat Shaolin Monks: two windows of still scene pass before the unstick, and the walk repeats the same press (the same finding as Blowout). Blocks Shaolin Monks' Playable (fps clear; play share 0.88 against 0.90). Not re-run: identify the still stretch from the frames first.

SCENE SHOULD CONTAIN: MK Shaolin Monks gameplay, a 3D arena with two fighters, the HUD (health bars, round timer), the fighters moving and trading hits through the window; no still camera on one wall.

Spend: model calls for this run, not priced. Queue continues: MK Deadly Alliance is running now.

## #433 -- 2026-10-06 07:16 PDT

[lane.pathfind] Mortal Kombat Deadly Alliance (4D57000C) GAVE UP at the 15-min claim budget (no hold, no verdict): 80 steps, 71 model calls, run runs/rehold-4D57000C (run.log, steps). Live rounds were read as gameplay from about step 88 (14.0 min) on, with a HUD and a counting timer, but each fighter probe was refused (control 0.10 to 0.90 under input 0.12 to 0.58), and the budget ended the claim during the probes. Claim budget spent: 15 min.

Ref and env: as for Armageddon, the pre-hold gate read ref c3a0c70ace (origin/master), apk 6beaa5ac1cdd, env [] from the last clean Nova result. Read that as the build, not as a per-run receipt.

Named cost (run.log steps 86 to 95): a CONTINUE countdown at step 87 (START, then A), a 'PLAYER 2 PRESS START' join prompt read as gameplay at step 88 (A pressed on it), and four probe-and-read pairs in which the screen was live but the stick probe measured control at 0.10 to 0.47 under input. The probe reads the fighter's stick response, and a fighting game's fighter does not move under a stick push in every state (block stance, hit reaction, a round just started). So the confirm refused live rounds and the claim spent its last 2 min on probes.

NEW ISSUE: fighting-game claim confirm refuses live rounds: the stick probe measures control at 0.1 to 0.5 in a live Mortal Kombat Deadly Alliance round, so the claim gives up at its budget with play on screen (step 94, 15 min budget). Blocks Deadly Alliance's Playable and needs the same fighting-game confirm fix as Armageddon and Guilty Gear. Not re-run: the claim needs its probe rule identified from these frames first.

Spend: model calls for this run (71), not priced.

## #433 -- 2026-10-06 07:32 PDT

[lane.pathfind] NBA 2K3 (NBA_2K3.xiso.iso) GAVE UP at the 15-min claim budget (no hold, no verdict): 81 steps, 82 model calls, run runs/rehold-NBA_2K3 (run.log, steps). Live court with the HUD and players read as gameplay from about step 80 (14.5 min); the stick probe at step 81 read control 0.70 under input 0.46, and the budget ended the claim there. The validity rule did not run: it lives in the hold, and this run never reached one.

Ref and env: as for the other re-holds, the pre-hold gate read ref c3a0c70ace (origin/master), apk 6beaa5ac1cdd, env [] from the last clean Nova result. This run's own device record was not readable. Read that as the build, not as a per-run receipt.

Named cost: the claim spent most of its 15 min in team select and the probe ladder before the live court. Team select was not reached before about 12 min (the sports setup and team pick came late), and the first live read came at 14.5 min with no confirm time left. The team-sport setup needs its own claim time, not the shared 15 min.

NEW ISSUE: NBA 2K3 claim budget (15 min) runs out in team select before the live court on a re-hold: the first live read came at 14.5 min with the probe still open. hold3 (10-05) passed from the same title with a longer route; the claim budget is the blocker here. Not re-run: identify the time split from these steps first.

Spend: model calls for this run (82), not priced.

## #433 -- 2026-10-06 07:47 PDT

[lane.pathfind] Marvel Nemesis (4541038A) GAVE UP at the 15-min claim budget (no hold, no verdict): 87 steps, 77 model calls, 7 replayed, run runs/rehold-4541038A (run.log, steps). Live fight with the HUD and both health bars read as gameplay from about step 63 (10.7 min); the claim ended at 15 min in the fight probes, the same shape as Deadly Alliance and NBA 2K3.

Ref and env: as for the other re-holds, the pre-hold gate read ref c3a0c70ace (origin/master), apk 6beaa5ac1cdd, env [] from the last clean Nova result. This run's own device record was not readable. Read that as the build, not as a per-run receipt.

Named cost: the claim reached a live fight at 10.7 min, then spent about 4 min in probe and continue cycles with the budget running out. The REMATCH fix (2b851dd27f) was not reached, since the match did not end in the claim. Its earlier r3 hold (10-06 03:26) ran the hold and was judged on play share, so this claim give-up is a different failure: the claim's own budget, not the hold.

NEW ISSUE: fighting titles give up at the 15-min claim budget with live fight on screen (Marvel Nemesis at step 63, 10.7 min; Deadly Alliance and NBA 2K3 the same shape). The shared claim budget runs out in probe and continue cycles after play is live, so no fighter hold runs. Blocks Marvel's Playable and the fighter family (Armageddon, Deadly Alliance, Guilty Gear, Marvel). Not re-run: the claim budget and the probe rule for fights need identifying together.

Spend: model calls for this run (77), not priced.

## #433 -- 2026-10-06 08:10 PDT

[lane.pathfind] Replay divergence, offline (owner order 08:00): first pass from this morning's steps.jsonl, no device time. Per title, the first step where a recorded-path replay stops matching the screen, and what is written:

- Shaolin Monks (4D570029, run rehold-4D570029): replay ran 13 steps in sync to the cutscene section. The first non-replay step is a Character Select read at step 7 that the path did not expect, so the model took A on Liu Kang; then a black stretch and a loading screen at step 12 that the path did not hold. The replay resynced at step 13 and reached gameplay at step 28 (3.15 min claim, the same as the recorded time). So the path reached play; the failure was the hold's still stretch (82.6 s), not the replay. Path file: NOT changed (no step to fix); the recovery the hold needs is the still-scene unstick (the same as Blowout).
- Deadly Alliance (4D57000C): replay ran 8 steps, then a black frame at step 8 with no recorded step matching it; the claim budget then ended on live play (the 07:16 result). The divergence is at recorded step 8. Path file: NOT changed yet. The fix (what the path expects after the black frame) needs the frame at step 8 read before writing it.
- NBA 2K3 (no paths/ file for this title): 0 replay steps; it ran from the hint alone. No divergence to name; there is nothing to write. The team-select recovery is the claim time (the +10 min team allowance is in).
- Marvel Nemesis (4541038A): replay ran 7 steps; the first non-replay step is a publisher logo at step 3 (a mid-animation card the path did not record). Path file: NOT changed; the recovery is a skip (A, re-read), which the model already does; the claim then ended in the fight probes.
- Armageddon (4D570034, the retry rehold2b): replay ran 4 steps, the first non-replay is a Sofdec logo at step 3. Path recorded at 07:57 by its own claim. Path file: NOT changed; its hold is still running.

Nothing in this pass met step 3's bar (a named divergence step and the input that recovers it, confirmed on frames). So no path file was written and no per-title run is queued by it. The one-run-each list in step 4 is therefore empty until a path changes: Shaolin's still-scene hold is a hold change, which is a separate run only after its fix.

The replay abort rule (step 2) is in `pathfind.py` with its own pure leg (`replay_diverged`: Deadly Alliance aborts past 7.5 min on a non-matching screen, not before). The integration of the abort into the claim loop is NOT yet exercised on a device; it is the first thing a later replay run tests.

Spend: no device time and no model calls for this pass.

## #433 -- 2026-10-06 08:12 PDT

[lane.pathfind] Mortal Kombat: Armageddon (4D570034) retry FAIL on play share, fps clear (run runs/rehold2b-4D570034, verdict.json, hold.jsonl, hold_strip.jpg). The validity check ran as designed: the hold played 603 s, the verdict counted 604 s of play in a 795.3 s scored window, play share 0.760 (bar 0.90), menu 140 s, black 25 s, other 15 s. fps_ok 1.0, median 59.9, no crash, no hang. The check asked for 1117 s more play to reach 90 %, and the budget was gone, so the hold ended not held ('share short by 1117 s with no budget left'). Excluded time as the verdict counts it.

Ref and env: as for the other re-holds, this run's device record was not readable (pathfind.py passes no ref). The pre-hold gate read ref c3a0c70ace (origin/master), apk 6beaa5ac1cdd, env [] from the last clean Nova result. Read that as the build, not a per-run receipt.

Named cost (hold.jsonl, the ladder): the off-play cap tripped once, at 12 menu steps, and started ladder round 1. The menu time that followed was the Character Select grid again, and the ladder's A, START, A, A, B, START did not clear it in the rest of the window (one round in about 800 s, so the cap did not trip again while the grid was up). The validity rule did what the owner asked (no stop at the cap; the check named the shortfall). What is still missing is a Character Select exit that works: the ladder's A on a highlighted fighter did not start a round.

NEW ISSUE: Armageddon's Character Select is not exited by the hold's ladder (A, START, A, A, B, START): menu time 140 s and the share falls to 0.76 with fps clear. Blocks Armageddon's Playable. Not re-run: the select screen's working input needs identifying from these frames (the 'PRESS START' join prompt in the claim's step 88 of Deadly Alliance is the same family).

Spend: model calls for this run, not priced.

## #433 -- 2026-10-06 11:30 PDT

[lane.pathfind] NFL Blitz Pro (NFL_Blitz_Pro.xiso.iso, no title id) claim FAIL: gave-up at the 25-min claim budget (15 + 10 team), 134 steps, 154 model calls, $12.25. No hold, so no benchmark window. Run runs/nfl-blitz-pro/hold2 (frames/, steps.jsonl, calls.jsonl). Nova 10:58-11:23 PDT. Build: ref 0342eba317 (master restore, the last Nova result before the hold), apk ad6f37a2f087, env []; tools 8d7af64998 from a clean checkout.

Identified, two causes:
1. The claim-live rule (07:50 order: the budget ending on live play enters the hold) was NOT in committed 8d7af64998. It was only in the uncommitted worktree, although 853ee7da6a's message names it. This run reached live football from ~656 s (snaps, tackles, clock running) and ended on a live look (#133) and then a refused probe (#134). On the rule it would have entered the hold. The rule is now committed in ab8788c38b, and its selftest leg (claimlive) passes; the full selftest is 89 ok.
2. The quarter length was never set: Blitz Pro's MAIN MENU tabs (GAME MODES, with L/R arrows) change with the triggers. The model pressed R1/L1 and the d-pad for 13 steps (~10 min) and went to QUICKPLAY at the default 2:00 quarter.

Next, started 11:28: one run on ab8788c38b (runs/nfl-blitz-pro/hold3) with a goal naming RT/LT for the tabs. This is not a blind retry: both causes above are fixed.

Spend: $12.25 this run.
