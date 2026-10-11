# lane.pathknow -- NOTES

Brief: `~/hakux-work/briefs/pathknow.md` (#433). Two parts: (1) which model names pathfind's screen states
correctly, offline, on frames already on disk; (2) seed `docs/testing/titles/pathknow/hints/` and
`families.md` from 9 days of route history. No device time.

## Part 1: the labelled frame set

- Pool: 413 frames from 639 `dispatch/results/*/route-frames/` dirs, up to 5 per title across ~80 titles
  (`scratch/pool.py`, not committed), plus the review.tsv false passes by name.
- Labelled by eye from 26 contact sheets: 245 frames given a primary state and the other states that are
  also defensible (an attract demo is `intro_video` but `cutscene` is not wrong). Ambiguous frames were
  dropped, not guessed.
- Eval set: 120 frames, stratified (8 per state, 16 gameplay, every known false pass kept), downscaled to
  640 px JPEG. `eval/eval_set.tsv` names each frame's source result dir and file, its labels and why.
- Prompt: `eval/prompt.md`, the JSON prompt pathfind uses (state, why, action, wait_s) with one line per
  state saying where its edge is.

## The `claude -p` call was refused in this session

`claude -p --model ... --output-format json` (and `claude --version`) are refused by the lane session's
permission mode ("requires approval", non-interactive). I did not route around that with a wrapper. The
accuracy measurement ran the same prompt through Claude Code subagents pinned to the haiku and sonnet
model aliases (claude-haiku-4-5 and claude-sonnet-5), 12 frames per subagent, each frame judged alone.
What this cannot give: the per-call latency of `claude -p` (cold start vs a stream-json session).
pathfind measures that on its first steps (its brief logs every call to `calls.jsonl`).

## Part 1 result (posted to OUTBOX 09:45)

| | Haiku 4.5 | Sonnet 5 |
|---|---|---|
| states right (117 scored) | 112 (96%) | 114 (97%) |
| known false passes right | 18/19 | 19/19 |
| gameplay called something else | 0/16 | 0/16 |
| non-gameplay called gameplay | 5 | 2 |
| median s/frame, fresh context (subagent) | ~12 (n=28) | ~12.6 (n=9) |
| median s/frame, 12 frames in one context | 3.3 | 4.4 |

Do not repeat:
- **12 images in one context cross-talk.** Haiku's batch b06 gave f080-f082 each other's answers, and
  Sonnet's b09 described a racing frame for the f112 profile screen. Every batch miss was re-run as a
  single-frame call, and the single answer is the one scored (`answers/*.jsonl` is the merge). Score a
  model one frame per context, and check the `why` against the frame before you believe a miss.
- **Attract demos are the residual error for both models**, and the cause is the frame, not the prompt.
  Sonic Heroes, Bloody Roar, Forza and PGR attract loops come before any menu, have a HUD-like overlay,
  and show nobody steering. The v2 prompt line (the `FPS: NN` overlay is not a HUD) fixed 1 of 5. pathfind's
  rule 5 (input changes the scene) is the separator.
- **Actions are where the models differ.** Haiku answered A on 8/8 name entries and 8/8 save prompts.
  Sonnet navigated to the right option on 3/8 of each.
- Three frames were ambiguous on a second look and are marked `AMBIG:`: f021 (Black, dark ledge), f095
  (Alias casino walk, no HUD) and f105 (Azurik relief, no HUD).

## Part 2: hints and families (posted to OUTBOX 09:50)

- A subagent read every source and drafted 35 files plus `families.md`; I reviewed them. Spot checks
  against the sources held: BloodRayne's DIM highlight is in `bloodrayne.route:12` and titleroutes NOTES
  :834; the GoldenEye and Kabuki D-pad finding is in titleroutes NOTES :158-162.
- The hints are fitted to `pathfind.py` on origin/lane/pathfind @ 9a87999ca9:
  - its action names: `UP/DOWN/LEFT/RIGHT` (the D-pad, sent as hat pulses), `STICK:<dir>:<s>`, `RT:/LT:`;
    there is no right stick;
  - its `series_files()` rule: every slug word must appear in the normalised title name. Five slugs were
    renamed to satisfy it, and GoldenEye was split out of 007. A one-off copy of that rule, run over both owner
    listings, found that only `series-crash` over-matches (Crash 'n Burn, Phantom Crash), and its header says
    so.
- ESPN 2K5, FIFA and Tiger Woods have no route on this emulator. Their series files are short, marked
  unverified, and built around the sports controller-assignment trap (controller left in the middle
  means CPU against CPU).

Do not repeat:
- **Write hints in the consumer's vocabulary.** The first draft used pad.sh axis names (`LY min`,
  `HATY max`); the eval prompt used `DPAD_*` and `LSTICK_*`; pathfind uses `UP` and `STICK:up:1.5`. A
  model given two vocabularies in one prompt has to translate, and may echo the wrong one back as an
  action.
- **A slug is a matching rule, not a label.** `series-pgr` would never have loaded for "Project Gotham
  Racing". Check slugs against the consumer's matcher and the real listings.

## Local checks in place of CI

`docs/testing/titles/pathknow/**` counts as harness for offline_fold.py, so the fold runs
`docs/testing/jobs/selftest.sh`. Run here on 22d8ae61fb, 10:00-11:20 PDT: 2905 passed, 0 failed, all
120 fragments. After that I merged master 0426a98181, which touches none of this lane's files, and set
PR.md `State: ready`.
