# pathknow: screen-reading model eval and cross-title navigation hints for pathfind
State: draft

Lane: pathknow            Issue: #433
Base: master @ 66bce0c222
Files: docs/lanes/pathknow/NOTES.md, docs/lanes/pathknow/OUTBOX.md, docs/lanes/pathknow/PR.md, docs/testing/titles/pathknow/eval/answers/claude-haiku-4-5.jsonl, docs/testing/titles/pathknow/eval/answers/claude-haiku-4-5.prompt-v2-subset.jsonl, docs/testing/titles/pathknow/eval/answers/claude-sonnet-5.jsonl, docs/testing/titles/pathknow/eval/eval_set.tsv, docs/testing/titles/pathknow/eval/make_frames.py, docs/testing/titles/pathknow/eval/prompt.md, docs/testing/titles/pathknow/eval/prompt_v1.md, docs/testing/titles/pathknow/eval/score.py, docs/testing/titles/pathknow/families.md, docs/testing/titles/pathknow/hints/global.md, docs/testing/titles/pathknow/hints/pub-4143.md, docs/testing/titles/pathknow/hints/pub-4154.md, docs/testing/titles/pathknow/hints/pub-4156.md, docs/testing/titles/pathknow/hints/pub-4343.md, docs/testing/titles/pathknow/hints/pub-4541.md, docs/testing/titles/pathknow/hints/pub-4947.md, docs/testing/titles/pathknow/hints/pub-4C41.md, docs/testing/titles/pathknow/hints/pub-4D4A.md, docs/testing/titles/pathknow/hints/pub-4D53.md, docs/testing/titles/pathknow/hints/pub-4D57.md, docs/testing/titles/pathknow/hints/pub-5345.md, docs/testing/titles/pathknow/hints/pub-5443.md, docs/testing/titles/pathknow/hints/pub-5454.md, docs/testing/titles/pathknow/hints/pub-5553.md, docs/testing/titles/pathknow/hints/pub-5655.md, docs/testing/titles/pathknow/hints/series-007.md, docs/testing/titles/pathknow/hints/series-baldur-gate.md, docs/testing/titles/pathknow/hints/series-blinx.md, docs/testing/titles/pathknow/hints/series-buffy.md, docs/testing/titles/pathknow/hints/series-burnout.md, docs/testing/titles/pathknow/hints/series-castlevania.md, docs/testing/titles/pathknow/hints/series-crash.md, docs/testing/titles/pathknow/hints/series-dead-or-alive.md, docs/testing/titles/pathknow/hints/series-espn-2k5.md, docs/testing/titles/pathknow/hints/series-fifa.md, docs/testing/titles/pathknow/hints/series-goldeneye.md, docs/testing/titles/pathknow/hints/series-gotham.md, docs/testing/titles/pathknow/hints/series-grand-theft-auto.md, docs/testing/titles/pathknow/hints/series-halo.md, docs/testing/titles/pathknow/hints/series-kof.md, docs/testing/titles/pathknow/hints/series-mechassault.md, docs/testing/titles/pathknow/hints/series-midnight-club.md, docs/testing/titles/pathknow/hints/series-ninja-gaiden.md, docs/testing/titles/pathknow/hints/series-rallisport.md, docs/testing/titles/pathknow/hints/series-raw.md, docs/testing/titles/pathknow/hints/series-sonic.md, docs/testing/titles/pathknow/hints/series-tiger-woods.md, docs/testing/titles/pathknow/hints/series-tony-hawk.md
Prediction: none: no arm (no emulator code, no device time)
Needs device: no    Needs NDK: no

**Part 1: which model names pathfind's screen states.** I hand-labelled 120 frames from 639 dispatch
result dirs (about 70 titles). Each of pathfind's 17 states has up to 8 frames, gameplay has 16, and all 19
known false passes are included. Each frame was judged alone, with pathfind's JSON prompt.

| | Haiku 4.5 | Sonnet 5 |
|---|---|---|
| states right (117 scored) | 112 (96%) | 114 (97%) |
| known false passes right | 18/19 | 19/19 |
| gameplay called something else | 0/16 | 0/16 |
| non-gameplay called gameplay | 5 | 2 |
| name entry / save prompt: steered instead of A | 0/8, 0/8 | 3/8, 3/8 |

Both models confuse attract demos with play. Rule 5 (an input visibly changes the scene) is the
separator. The `claude -p` call was refused in this lane's session, so the models ran as subagents.
pathfind's own `calls.jsonl` gives the real `claude -p` latency: Haiku median 7.6 s per step.

**Part 2: hints.** `hints/global.md`, 15 `pub-<id prefix>.md` files and 23 `series-<slug>.md` files,
mined from 66 routes and 5 lanes' NOTES. Every line names its source title; each file is under 40 lines.
They are fitted to pathfind.py's action names and its `series_files()` slug rule, which I checked
against both owner listings. `families.md` lists about 70 title families with ids and devices.
ESPN 2K5, FIFA and Tiger Woods have no route evidence, so their series files are marked unverified.

Local checks in place of CI:
- `python3 -m py_compile` on `eval/score.py` and `eval/make_frames.py`: OK.
- `eval/score.py` reproduces the table above. `eval/make_frames.py` rebuilds byte-identical frames.
- `docs/testing/jobs/selftest.sh` on this head: running.

Release note (none): navigation knowledge and evaluation data for the test harness; no emulator change.
