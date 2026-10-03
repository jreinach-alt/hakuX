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
