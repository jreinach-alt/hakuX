## #433 -- 2026-10-02 09:35 PDT

[lane.pathfind] pathfind.py is running unattended on real titles. First lot-drawn title:
**Star Wars Episode III (Nova): gameplay confirmed in 3.5 min, 17 model calls (16 Haiku, 1 Sonnet for the
confirmation), 18 steps.** Path: 3 logos/title skipped with START, the opening crawl and a long FMV (START
ignored, it waited them out), first gameplay frame "NEW OBJECTIVE: ESCAPE THE CRUISER HANGAR"; the stick
probe moved Obi-Wan (frames checked by eye too). Frame: `docs/lanes/pathfind/runs/star-wars-iii/strip.jpg`.
Side finding: this title's intro FMV renders as green blocks (a video decode/rendering defect).
Model step latency via `claude -p`: 8-10 s per Haiku call, ~$0.027. Next: the other 9 lot titles on the
Nova (running now), ESPN NFL 2K5 on the Thor (running now).

## #433 -- 2026-10-02 09:55 PDT

[lane.pathfind] Scoreboard 2/2 on the Nova lot so far. **Midnight Club 3 (Nova): gameplay confirmed in
6.2 min, 33 model calls** (Career -> buy a car -> Test Drive -> driving in the city; RT moved the car).
Frame: `docs/lanes/pathfind/runs/midnight-club-3/gameplay_frame.jpg`. Running now: Bruce Lee, then
Black Stone, Panzer Dragoon Orta, Amped 2, Counter-Strike, Top Spin, Ninja Gaiden Black, Spikeout.
Changes from what was learned: the d-pad is the hat axis (the d-pad buttons do nothing in hakuX), inline
images and Sonnet 5 per step (3.5-3.9 s vs Haiku's 6-9 s, measured), Opus 5.5 when stuck, a 2-screen cycle
detector. ESPN NFL 2K5 (Thor) reached the kickoff twice in 3.3 min but the Thor heat-stopped at 70 C both
times (52 -> 70 C in 3.6 min of menus); retrying from a cold start.

## #433 -- 2026-10-02 10:12 PDT

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
