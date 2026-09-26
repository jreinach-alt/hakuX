# lane.titleplay: gameplay frame rate under scripted input

Issue #397. Brief: drive each title into real gameplay, confirm it from the
frames, measure it (the owner, 2026-09-26). Base `a5b5b628f2`. PR #399.

## Pass 1 (queued 2026-09-26 07:32 PDT)

29 requests `0-0-y-1790433159-titleplay-p1-<label>`, ref `a5b5b628f2`
(master, includes the #382 fix), 420 s each, pinned to the device that holds
each ISO. The ids are listed in the #397 comment of 07:33 PDT and can be
regenerated with `tools/plan_p1.py`.

- Population 1, all 20 titles, run on `survey.route`.
- Population 2, the titles whose file names on a device are already proven
  by a past `done` result (`tools/isoseen.py`):
  - Nova: Ghoulies, RalliSport 2 (PAL), Tork, Fuzion Frenzy (own route).
  - Thor: Galleon, DOA3, JSRF, Spikeout (PAL), Crimson Skies (own route).
- Not queued:
  - **Conker**: a dispatcher soak of `Conker Live & Reloaded.iso` has never
    started the app (#265), and the suspect is the `&` in the name. That is
    a harness defect, not a game result.
  - **The other 13 titles of population 2** (ToeJam III, THPS2x, NG, NGB,
    Deathrow, Dino Crisis 3, Halo, Halo 2, MechAssault, Psychonauts, PDO,
    Phantom Dust, Amped 2): their exact ISO names are unknown. Guesses have
    missed before (Psychonauts, PDO and JSRF, 2026-09-12). The listing
    (`devices.sh titles`) needs adb, so it was asked for on #397.

### Why a survey route and not generic

`generic.route` takes no frame between boot and `mark play`, so a run that
stalls in a menu shows nothing of where it stalled. `survey.route` sends the
same input and takes a frame at 20/40/60 s, after every START and every A of
the 14 menu rounds, and every ~23 s of play. It never writes
`mark gameplay`: a reviewer decides from the frames.

**The scored window of a survey run starts at `mark play` (~200 s).** Only
answer `--reviewed-gameplay yes` when the frames from `mark play` onward all
show gameplay. If gameplay began later, the menu time would be counted in the
share. That title gets a pass-2 route with its own `mark gameplay` instead.

## Tools

- `tools/isoseen.py [substr]`: every soak title a past dispatch result ran,
  per device, and whether the worker found the ISO. It reads results only.
- `tools/plan_p1.py [route]`: the pass-1 plan for population 1.
- `tools/queue.py --ref R --seconds S --tag T plan.tsv`: puts each line
  through `request.sh` into a private staging queue, re-keys it
  `0-0-y-<ts>-titleplay-<tag>-<label>`, and renames it into the real queue.
  The dispatcher takes a request's id from its file name (`serve_one`).
- `tools/review.py ids [--reviewed label=yes|no]`: copies each finished run
  to `scratch/runs/`, judges the copy, and prints the marks, the fps median
  and share, and a 30 s fps timeline over the whole run.
- `tools/targets_p1.py`: the `targets.toml` entries for population 1, from
  the compat CSV and the batch TSV.

## Attempt 1 ended waiting, and pass 1 was then stopped

The first session ended (07:42 PDT) waiting on the 29 pass-1 requests,
which ran outside the session. That was a correct stop, not a failure. The Nova
then went down (host outage 08:22-10:14 PDT, then off and charging), its
Nova-only titles were re-pinned to the Thor, and at 12:02 PDT **the owner
stopped pass 1** after reviewing the first 15. Their reasons: the generic
START/A input reached clean gameplay in about half the titles, and the batch
held the only live handheld. The 12 requests still queued are parked in
`dispatch/parked/titleplay-p1-20260926/` and must not be moved back. The owner
also set a new rule: **any device batch longer than 30 minutes runs a short
pilot first, and the pilot is reviewed before the rest is queued.** How titles
reach gameplay next (an agent-driven interactive route recorder has been
proposed) is the owner's decision on #397. This lane queues nothing more.

## Pass 1 results (17 runs, ref `a5b5b628f2`, apk `25abcaccbf45`, 1x)

I looked at every frame of every contact sheet. "Reached" means a
player-controlled scene. The fps figures cover the scored window, which runs
from `mark play` (or `mark gameplay` for a title's own route) to the end. A
title is judged only when every frame in that window is gameplay.
`tools/review.py` was rerun with `--reviewed-gameplay yes` for those titles.
No run reached the 600 s screening length; the brief asked for 2+ min.

| title | device | reached | play s | fps median | share 30+ | verdict | what the frames show |
|---|---|---|---|---|---|---|---|
| 25 to Life | thor | review | 91 | 35.7 | 0.54 | below the bar | profile created, chapter 1 Warehouse, third-person shooting; the menu rounds toggle pause over play |
| 007: Agent Under Fire | nova | review | 90 | 16.2 | 0.00 | below the bar, under 20: **#412** | first mission, first-person with the decryptor |
| Blinx | thor | review | 160 | 14.8 | 0.00 | below the bar, under 20: **#372** (comment) | New Game, first stage, Blinx under control |
| Blinx 2 | thor | review | 169 | 21.7 | 0.00 | below the bar | Story mode, locker room, Challenge 1 ("Locate the 3 balloons") under control |
| DOA Ultimate (DOA2U) | nova | review | 191 | 12.6 | 0.00 | below the bar, under 20, hangs of 11/76/44 s: **#413** | Story fight; after a ring-out the lower stage runs at 0-2 fps |
| Forza Motorsport | thor | review | 174 | 16.7 | 0.00 | below the bar, under 20: **#414** | Arcade race, on the grid; car never accelerates (right trigger), game clock at 26% of real time |
| Crimson Skies | thor | route | 306 | 23.4 | 0.09 | below the bar | flying from `mark gameplay`; the last ~2 min fall to 2-8 fps with 7 hangs of 10-25 s |
| Call of Duty 3 | nova | late | - | (~29 over the last ~60 s) | - | not measured | typed a profile name to the 13-char limit, New Game, intro FMV; gameplay ("Walk over to the M1 Garand") only in the last 2 frames |
| 50 Cent: Bulletproof | nova | no | - | - | - | not reached | profile keyboard: A types "a" forever |
| Black | thor | no | - | - | - | not reached | credits FMV, then the profile-name keyboard |
| Bruce Lee | thor | no | - | - | - | not reached | New Game lands on the Player Info status screen, which A never leaves |
| Burnout Revenge | nova | no | - | - | - | not reached | profile loop: A picks Load Profile, "no profiles", OK, again (Create Profile is one down) |
| Burnout 3 | thor | no | - | - | - | not reached | driver-details YES/NO loop, then Crash Nav and Race Training video panels |
| DOA3 | thor | no | - | - | - | not reached | the copyright warning scrolls at 3-14 fps for ~3 min, then the title screen |
| DOA Xtreme | nova | no | - | - | - | not reached | Vacation 1, intro dialogue, then the accessory shop menu |
| Galleon | thor | no | - | - | - | not reached | ~3 min of "Loading..." at 0 fps, attract demo, title menu, then a ship-deck scene I cannot tell from a cutscene |
| Fuzion Frenzy | - | - | - | - | - | not run | ERROR `title not on device`: re-pinned to the Thor, but the request still named the Nova card path |

Not run: 7 of population 1 (Nightfire, GoldenEye: Rogue Agent, WWE Raw 2,
Midnight Club 3, PGR, PGR2, Crash Twinsanity) and the rest of population 2 are
among the 12 parked requests, or were never queued (see above).

### What pass 2 routes would need (for whoever writes them)

- Profile keyboards (50 Cent, Black, CoD3): after the first letter, move to
  `Done` / press START, not A. CoD3 got through only because its keyboard
  stops at 13 characters.
- Burnout Revenge: D-pad down to `Create Profile`. Burnout 3: choose YES on
  "save your profile", then back out of the Crash Nav videos.
- Bruce Lee: B out of Player Info, then `Continue`.
- DOAX: B out of the shop, then the island map to a volleyball match.
- Forza: hold the right trigger. The route language has `axis`, so check it
  covers the triggers before writing this.
- Every generic run pauses and unpauses the game with START during the menu
  rounds. That wastes play time, and it puts pause-menu frames into the
  pre-mark timeline.

### Do not repeat

- Do not score a generic/survey run with `--reviewed-gameplay yes` unless
  every frame from `mark play` onward is gameplay. CoD3 and Galleon reach it
  only partway, and their medians would count FMV and loading.
- Do not queue a batch over 30 min without a reviewed pilot (owner, 09-26).
- Do not move the parked pass-1 requests back.
