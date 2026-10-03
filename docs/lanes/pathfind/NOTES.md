# lane.pathfind -- NOTES

## Scoreboard (10-03, hold-play)

Today's bar (addendum 2): hold-play for >= 600 s of judged play, on the Nova, from the lot's routed pool in P order.
Sonnet only, <= $25. Model reads are counted per title.

| title | device | genre | play held (s) | model reads | frames | result | frame strip |
|---|---|---|---|---|---|---|---|
| (none yet: waiting on the savestate433 fold, see "Attempt 2") | | | | | | | |

Offline checks, run on saved frames with the real prompts (Sonnet 5, scratch/holdcheck):

| check | frames | answers | verdict |
|---|---|---|---|
| hold_look (in play?) | Black Stone play | in_play true | right |
| hold_look | Dead or Alive 3 title splash | in_play false, action A | right |
| hold_look | Blinx 2 GAME PAUSED | in_play false, action A | right |
| hold_genre | Midnight Club 3 | drive | right |
| hold_genre | Top Spin | rally | right |
| hold_genre | Panzer Dragoon Orta | onrails | right |
| hold_genre | Counter-Strike | attack | right |

## Attempt 3 (10-03): why attempt 2 did not finish

- **Attempt 2 built hold-play and stopped before any device run.** Its only blocker was the golden profile:
  `titlestate.py prepare` was not on master, and addendum 2 says held runs start from it. It went to a
  `waiting:` comment at 06:58 PDT and ended there with nothing queued on the Nova.
- **That blocker has cleared.** savestate433 folded to master (`cfa37a359e`, the Tron device proof). Attempt 3
  merged origin/master. The one conflict was `pathfind.py`'s argument block: both sides added arguments, so
  `--hold-s` and `--state`/`--hdd-img` are both kept. Selftest all ok after the merge.
- **Nothing else from attempt 2 carries over as a result.** Its hold-play work is selftested only; no held run has
  been made on a device yet. Today's bar stays addendum 2: 600 s held on a Nova title from the pool, judged.

## Attempt 2 (10-03): why attempt 1 did not finish

- **Attempt 1 finished its acceptance, not today's bar.** The 10-02 lot acceptance (9 of 10, Bruce Lee rerun) was
  met and folded to master (6b0c4a131f). Its last work stopped at the owner's 11:55 hold on navigation (token burn),
  before hold-play existed. No title was ever held for 600 s, which is the bar for today.
- **Its last commits were not written up.** At 11:50 it reached gameplay on Ghoulies (2.35 min, 11 calls) and Tork
  (4.41 min, 19 calls, four probes refused) and gave up on Conker (15 min, 23 calls, black after a level load). Their
  results are in `runs/<title>/result.json` and `pathknow/paths/`, but the scoreboard above and OUTBOX did not get them.
  They are recorded here, not re-run. Conker's black-after-level-load is still open.
- **Attempt 2 (10-03 06:47 PDT):** merged origin/master (63 commits: the pathfind fold, uberdefault569, buildstamp).
  Before the merge, 39 untracked pathknow hint files were removed; each was byte-identical to its master copy.
- **Not done in attempt 2 yet:** the held device runs. Addendum 2 says every held run starts from its golden profile
  (`titlestate.py prepare`), and that lands with savestate433's fold. savestate433 is PR-ready on
  `origin/lane/savestate433` and is not on master at 07:00 PDT, so `titlestate.py` on master has no `prepare`.
  The Nova stays unheld and no run is queued until it folds.

## Hold-play (10-03)

After the confirmed claim, `pathfind.py --hold-s 600` keeps the player in play. Design, as built:

- **A genre loop of inputs, model-free.** The genre (drive, attack, rally, onrails, other) is named once by Sonnet from
  the confirm frame. Each genre is a fixed list of inputs sent every cycle (`HOLD_GENRES`). The right stick is a new
  token, `RSTICK:<dir>:<s>`, at full deflection.
- **The model reads the screen only when play may have ended:** a black frame, a frame identical to the previous one
  (one static look; the previous draft waited for two), every 90 s, and after each step while off play.
- **Off play, the model steers back**, one look per step, with its own action, up to 12 steps in one episode. Past
  that the hold gives up, and the claim still stands (`hold.ok` false, the reason says so).
- **Frames every 30 s**, kept; the rest are deleted after the next look has been measured. `hold_strip.jpg` is the
  kept frames. `hold.jsonl` has a line per look (play seconds, change, whether the model was asked and what it said).
- **Nova only.** `--hold-s` is refused on the Thor, whose fan is dead and whose rule is to stop within 30 s of a claim.
- **Opus is off today.** `STRONG` defaults to Sonnet 5 (addendum 2). Restore `claude-opus-5-5` when Opus returns.

Selftest: `hold` (200 s of play on a fake clock: a pause read and cleared by START, 3 model reads, 7 frames kept, the
others deleted) and `holdstuck` (the pause never clears: the hold gives up at the nav cap). `actions` also covers
`RSTICK`. Full selftest: all ok.

## What the next lane should not repeat (10-03)

- **A frame the next look measures against cannot be deleted at the end of its own look.** The first version deleted
  every non-kept frame at once; the next look then failed to open it. The fix deletes the previous look's frame after
  the current one is measured.
- **Escalation is by model name, not by a source label.** With Sonnet as both tiers, the escalation case in the selftest
  stopped meaning anything. The selftest now pins Opus, so those cases still test escalation.
- **The fake clock.** The hold selftest patches `pathfind.now` and `time.sleep`, so 200 s of play takes no real time.
  The selftest must restore both (it does, before `actions`).

## Scoreboard (10-02, attempt 1)

Lot: the brief's 35 never-routed Nova titles, shuffled with
`random.Random('pathfind-2026-10-02')`; the first 10 in that order are the acceptance set, run in order,
none swapped out. Order: Star Wars III, Midnight Club 3, Bruce Lee, Black Stone, Panzer Dragoon Orta,
Amped 2, Counter-Strike, Top Spin, Ninja Gaiden Black, Spikeout (spares after: Conker, Ghoulies, Tork,
DOAX, DOA3, JSRF, ...). pathfind never reads the retired `.route` files some of these have.

**Acceptance: 9 of the 10 lot titles reached confirmed gameplay on their first attempt, each within 15 min
(max 9.0), cold, unattended, every strip reviewed by eye.** The miss is Bruce Lee: a false pass on its
letterboxed intro cinematic, caught in review (not counted), fixed in the tool, rerun below. Midnight Club 3's
counted run is its second: the first was stopped at 8 min on a tool bug (d-pad buttons; see below), before
any result was written.

| lot # | title | first attempt | min | model calls | frame |
|---|---|---|---|---|---|
| 1 | Star Wars Episode III | gameplay | 3.5 | 17 | runs/star-wars-iii/gameplay_frame.jpg |
| 2 | Midnight Club 3 | gameplay (run 2, tool bug in run 1) | 6.2 | 33 | runs/midnight-club-3/gameplay_frame.jpg |
| 3 | Bruce Lee | **false pass** (review); rerun with the fixed tool: gameplay in 4.9 min, 22 calls | 0.9 | 4 | runs/bruce-lee.falsepass/strip.jpg, runs/bruce-lee.rerun/gameplay_frame.jpg |
| 4 | Black Stone | gameplay | 2.4 | 12 | runs/black-stone/gameplay_frame.jpg |
| 5 | Panzer Dragoon Orta | gameplay | 4.5 | 21 | runs/panzer-dragoon/gameplay_frame.jpg |
| 6 | Amped 2 | gameplay | 9.0 | 34 | runs/amped-2/gameplay_frame.jpg |
| 7 | Counter-Strike | gameplay | 3.1 | 14 | runs/counter-strike/gameplay_frame.jpg |
| 8 | Top Spin | gameplay | 5.5 | 24 | runs/top-spin/gameplay_frame.jpg |
| 9 | Ninja Gaiden Black | gameplay | 7.0 | 33 | runs/ninja-gaiden/gameplay_frame.jpg |
| 10 | Spikeout | gameplay | 4.3 | 22 | runs/spikeout/gameplay_frame.jpg |

Every run, including the Thor ones (generated by `scoreboard.py`):

| run | title | device | result | min | model calls | steps | replayed | cost | reason | frame |
|---|---|---|---|---|---|---|---|---|---|---|
| star-wars-iii | Star Wars Episode III Revenge of the Sith | nova | **gameplay** | 3.52 | 17 (haiku 16/sonnet 1) | 18 | 0 | $0.50 |  | runs/star-wars-iii/gameplay_frame.jpg |
| espn-nfl-2k5.try1 | ESPN NFL 2K5 | thor | heat-stop | 6.2 | 20 (haiku 18/sonnet 2) | 21 | 0 | $0.65 | Thor xo 71.033 C | runs/espn-nfl-2k5.try1/strip.jpg |
| espn-nfl-2k5.try2 | ESPN NFL 2K5 | thor | heat-stop | 3.6 | 20 (opus 1/sonnet 19) | 20 | 0 | $0.99 | Thor xo 70.757 C | runs/espn-nfl-2k5.try2/strip.jpg |
| midnight-club-3 | Midnight Club 3: DUB Edition | nova | **gameplay** | 6.23 | 33 (opus 3/sonnet 30) | 34 | 0 | $1.76 |  | runs/midnight-club-3/gameplay_frame.jpg |
| bruce-lee.falsepass | Bruce Lee: Quest of the Dragon | nova | gameplay -> REVIEW: false-pass | 0.93 | 4 (opus 1/sonnet 3) | 4 | 0 | $0.24 |  | runs/bruce-lee.falsepass/strip.jpg |
| black-stone | Black Stone Magic Steel | nova | **gameplay** | 2.41 | 12 (opus 3/sonnet 9) | 12 | 0 | $0.73 |  | runs/black-stone/gameplay_frame.jpg |
| panzer-dragoon | Panzer Dragoon Orta | nova | **gameplay** | 4.48 | 21 (opus 2/sonnet 19) | 25 | 0 | $1.08 | four probes refused | runs/panzer-dragoon/gameplay_frame.jpg |
| espn-nfl-2k5.try3 | ESPN NFL 2K5 | thor | heat-stop | 4.4 | 18 (opus 1/sonnet 17) | 18 | 0 | $0.91 | Thor xo 70.292 C | runs/espn-nfl-2k5.try3/strip.jpg |
| amped-2 | Amped 2 | nova | **gameplay** | 9.02 | 34 (opus 4/sonnet 30) | 48 | 0 | $1.83 | four probes refused | runs/amped-2/gameplay_frame.jpg |
| counter-strike | Counter Strike | nova | **gameplay** | 3.12 | 14 (opus 3/sonnet 11) | 14 | 0 | $0.80 |  | runs/counter-strike/gameplay_frame.jpg |
| espn-nba-2k5.discerror | ESPN NBA 2K5 | thor | title-error | 3.6 | 15 (opus 4/sonnet 10) | 15 | 0 | $0.87 | SEGA "problem with the disc ... dirty or damaged" after team select (stopped by hand at 3.6 min; fatal_error state added after) | runs/espn-nba-2k5.discerror/strip.jpg |
| top-spin | Top Spin | nova | **gameplay** | 5.48 | 24 (opus 3/sonnet 21) | 26 | 0 | $1.28 |  | runs/top-spin/gameplay_frame.jpg |
| espn-nhl-2k5.baseline-try1 | ESPN NHL 2K5 | thor | heat-stop | 3.7 | 16 (opus 1/sonnet 15) | 18 | 0 | $0.82 | Thor xo 70.418 C | runs/espn-nhl-2k5.baseline-try1/strip.jpg |
| ninja-gaiden | Ninja Gaiden Black | nova | **gameplay** | 6.99 | 33 (opus 3/sonnet 30) | 40 | 0 | $1.72 |  | runs/ninja-gaiden/gameplay_frame.jpg |
| spikeout | Spikeout: Battle Street | nova | **gameplay** | 4.27 | 22 (opus 3/sonnet 19) | 21 | 0 | $1.20 |  | runs/spikeout/gameplay_frame.jpg |
| espn-college-hoops-2k5.guided | ESPN College Hoops 2K5 | thor | heat-stop | 3.8 | 14 (opus 3/sonnet 11) | 16 | 0 | $1.07 | Thor xo 71.865 C | runs/espn-college-hoops-2k5.guided/strip.jpg |
| bruce-lee.rerun | Bruce Lee: Quest of the Dragon | nova | **gameplay** | 4.87 | 22 (opus 3/sonnet 19) | 22 | 0 | $1.49 |  | runs/bruce-lee.rerun/gameplay_frame.jpg |
| espn-college-hoops-2k5.replay | ESPN College Hoops 2K5 | thor | **gameplay** | 2.04 | 10 (opus 2/sonnet 8) | 11 | 2 | $0.73 |  | runs/espn-college-hoops-2k5.replay/gameplay_frame.jpg |
| dead-or-alive-3.baseline | Dead or Alive 3 | nova | gave-up | 15.1 | 62 (opus 9/sonnet 53) | 72 | 0 | $4.41 | budget 15 min | runs/dead-or-alive-3.baseline/strip.jpg |
| blinx-the-time.baseline | Blinx: The Time Sweeper | nova | **gameplay** | 4.35 | 19 (opus 2/sonnet 17) | 23 | 0 | $1.37 |  | runs/blinx-the-time.baseline/gameplay_frame.jpg |
| espn-nhl-2k5.sibguided | ESPN NHL 2K5 | thor | heat-stop | 3.9 | 16 (opus 3/sonnet 13) | 18 | 0 | $1.31 | Thor xo 70.903 C | runs/espn-nhl-2k5.sibguided/strip.jpg |
| blinx-2.guided | Blinx 2: Battle of Time & Space ~ Blinx 2: Masters of Time & Space | nova | gave-up | 15.2 | 61 (opus 17/sonnet 44) | 89 | 0 | $5.83 | budget 15 min | runs/blinx-2.guided/strip.jpg |
| espn-nhl-2k5.sibguided2 | ESPN NHL 2K5 | thor | heat-stop | 3.8 | 14 (opus 4/sonnet 10) | 16 | 0 | $1.14 | Thor xo 70.236 C | runs/espn-nhl-2k5.sibguided2/strip.jpg |
| blinx-2.unguided | Blinx 2: Battle of Time & Space ~ Blinx 2: Masters of Time & Space | nova | gave-up | 15.2 | 41 (sonnet 41) | 74 | 0 | $3.12 | budget 15 min | runs/blinx-2.unguided/strip.jpg |
| tiger-woods-pga-tour-2004.baseline | Tiger Woods PGA Tour 2004 | thor | **gameplay** | 3.07 | 14 (opus 3/sonnet 11) | 13 | 0 | $1.08 |  | runs/tiger-woods-pga-tour-2004.baseline/gameplay_frame.jpg |

## Cross-title (10-02)

Metric: model calls and minutes from cold boot to the first screen of live play (kickoff, faceoff, tip-off,
the level), and the final result. The Thor rows are all cut by its 70 C stop (fan dead) about 4 min in.

| run | guide | calls to live play | min | result (total calls) |
|---|---|---|---|---|
| ESPN NFL 2K5 try1 | none (Haiku per step) | 12 | 3.0 | heat-stop (20) |
| ESPN NFL 2K5 try2 | none | 19 | 3.4 | heat-stop (20) |
| ESPN NHL 2K5 baseline | none (`--no-guide`) | 15 | 3.3 | heat-stop (16): CPU vs CPU, see below |
| ESPN College Hoops 2K5 | NFL + NHL paths (partial) | 9 | 2.1 | heat-stop (14) while probing |
| ESPN College Hoops 2K5 | its own path, replayed (2 steps) + siblings | 8 | 1.8 | **gameplay** (10) |
| ESPN NHL 2K5 | siblings only (`--no-replay`): Hoops + NFL | 13 | 2.7 | heat-stop (16): CPU vs CPU |
| ESPN NHL 2K5 | siblings only, with plans | 7 | 1.6 | heat-stop (14): probes refused |
| Blinx | none (`--no-guide`) | 17 | 4.1 | **gameplay** (19) |
| Blinx 2 | Blinx's path | 27 | 5.2 | gave up (61): 30 probes, the character never moved |
| Dead or Alive 3 | none | 20 | 5.1 | gave up (62): every probe lost to a knockdown/KO replay |

What this shows, and what it does not:
- In the ESPN 2K5 family, guided runs reached live play with **7-9 calls in 1.6-2.1 min against 12-19 calls
  in 3.0-3.4 min unguided**. The guide is the sibling's recorded path given to the model as text, plus
  (last row) a plan of the next menus that is sent without a call. Two confounds favour the later, guided
  runs: profiles saved on the device by earlier runs (CAPA T2), and tool changes between runs (the no-call
  loading check came after the NHL baseline). It is evidence, not a controlled measurement.
- Frame replay does not carry across siblings: the same ESPN menu in two titles is 10-23 grey levels apart in
  pathfind's 16x12 signature (match threshold 9 for a title's own path, 5.4 for siblings). Measured with
  `docs/lanes/pathfind/sigcmp.py` on the Hoops and NHL frames (it reads the run dirs under scratch/runs, which are not committed). That is why the plan mechanism exists.
- Blinx -> Blinx 2 did not help: the sequel's front end differs and the run lost 10 minutes on one stuck
  scene. Not a cross-title gain.
- Team sports are hard to CONFIRM even after reaching play: a goal, foul or out-of-bounds lands inside the
  ~25 s probe, and the hockey camera auto-switches players. The confirm model refused each time and was
  right to by the frames. The NHL baseline and the first sibling-guided NHL run also played CPU vs CPU: the
  controller icon sat in the middle of Team Select (pathknow's hint said so; the model pressed A anyway).
  That rule is now in pathfind's own rules.

## Measurements

- Model latency through `claude -p` (10-02, same ESPN NFL 2K5 menu frame, image INLINE via
  `--input-format stream-json`, one turn): **Sonnet 5 3.5-3.9 s** (70-80 output tokens), Haiku 4.5
  6.4-9.1 s (430-500 output tokens, mostly thinking; `--effort low` and MAX_THINKING_TOKENS=0 did not
  help). With the image read through the Read tool (two turns) Haiku averaged 13.6 s/step, max 52 s.
  So pathfind uses inline images and **Sonnet 5 per step, Opus 5.5 when stuck and for the gameplay
  confirmation**; a step is ~9 s end to end (screencap ~1-2 s, model ~4-5 s, input + wait).
  This departs from the brief's Haiku-first start on measurement: Sonnet is both faster and stronger
  here. Cost ~$0.05/call.
- Thor heat in MENUS alone: 38.8 -> 71.0 C in 6.2 min (try1), 52.3 -> 70.8 C in 3.6 min (try2).
  The ESPN NFL 2K5 path to the kickoff takes ~3.3 min, so a Thor title needs a cold start.

## What the next lane should not repeat

- **Put the image AFTER the prompt text, and make the model describe it first.** With the frame first and
  pathfind's long prompt after it, Sonnet 5 called Tiger Woods 2005's bright title logo "a black frame with
  only the FPS overlay" 12 steps running, anchored on its own history, and burned 3 of the Thor's 4 minutes
  (10-02 11:43). Same frame, same prompt: image-first wrong 2/2, image-last plus a leading "see" field right
  4/4. Every run started before 11:50 used image-first. (`scratch/blacktest2.py` in the lane worktree.)
- **The d-pad buttons (evdev 544-547) do nothing in hakuX.** The d-pad is the hat: pulse
  `axis HATY min|max` then `mid`. Midnight Club 3 try 1 looped 8 times on a Yes/No dialog because
  UP never moved the cursor (stopped at 8 min, not scored; the old route's notes already said this).
- A 2-screen cycle (dialog -> input -> menu -> input -> same dialog) changes the screen every step, so a
  "same unchanged screen" guard never fires. pathfind counts inputs per matching screen over the last
  12 steps (`seen_here`).
- "Gameplay" on a sports play-call screen: the stick only flips the play menu. The confirm call caught
  it (ESPN try2); the model's own action (A to kick off) now goes before the probe.
- Star Wars III's opening crawl and FMV ignore START/A; the agent pressed through 9 cutscene steps
  harmlessly. Its FMV renders as green blocks (a rendering defect, not a pathfind problem).
- Midnight Club 3: the agent took Career (garage tutorial: buy a car, Test Drive) where Arcade might be
  shorter; it still reached driving in 6.2 min. The disk keeps saved profiles between runs (CAPA T2).
