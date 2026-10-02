# lane.pathfind -- NOTES

## Scoreboard (10-02)

Lot: the brief's 35 never-routed Nova titles, shuffled with
`random.Random('pathfind-2026-10-02')`; the first 10 in that order are the acceptance set, run in order,
none swapped out. Order: Star Wars III, Midnight Club 3, Bruce Lee, Black Stone, Panzer Dragoon Orta,
Amped 2, Counter-Strike, Top Spin, Ninja Gaiden Black, Spikeout (spares after: Conker, Ghoulies, Tork,
DOAX, DOA3, JSRF, ...). pathfind never reads the retired `.route` files some of these have.

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

Cross-title (Thor, sibling after a recorded path):

| title | path guide | result | min | model calls | steps |
|---|---|---|---|---|---|

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
