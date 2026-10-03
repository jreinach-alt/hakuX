# lane.tcg424flip: the #424 range test measured on Arctic Thunder and pgraph; stays opt-in (#424)
State: ready

Lane: tcg424flip            Issue: #424
Base: master @ 9d1155f919 (merged into the branch 2026-10-03)
Files: docs/lanes/tcg424flip/NOTES.md, docs/lanes/tcg424flip/OUTBOX.md, docs/lanes/tcg424flip/PR.md, docs/lanes/tcg424flip/arctic-nova.out, docs/lanes/tcg424flip/arcticread.py, docs/lanes/tcg424flip/arcticread2.py, docs/lanes/tcg424flip/arcticread3.py, docs/lanes/tcg424flip/baseline.out, docs/lanes/tcg424flip/moverscan.py, docs/lanes/tcg424flip/pgraphnoise.py, docs/testing/predictions/tcg424flip-arctic.json, docs/testing/predictions/tcg424flip-arctic2.json, docs/testing/predictions/tcg424flip-arctic-nova.json, docs/testing/predictions/tcg424flip-pgraph.json
Prediction: docs/testing/predictions/tcg424flip-arctic-nova.json (judged: M1 FAIL) and docs/testing/predictions/tcg424flip-pgraph.json (judged by the arms job: FAIL, not attributable)
Needs device: no    Needs NDK: no

Release note (none): no behaviour change; the #424 range test stays opt-in (HAKUX_TCG424_RANGE=1)

The branch tested flipping `hakux_tcg424_range_on()` to default-on (62ef8bf0fe). Neither gate passed as registered, so this PR does not include the flip. `accel/tcg/tb-maint.c` and `tb-internal.h` match master's text, and the net diff is documentation, predictions and readers only.

- **Arctic Thunder, Nova, 2 pairs.** M0, M2a, M2b and M4' pass:
  - gfps A 40 vs B 39.5;
  - cpf 20.95 -> 19.0;
  - on% 83.75 -> 75.05;
  - di/s 72k -> 0.

  M1 fails its falsifier: A's churn is 2.5%, below the A >= 5.0 threshold. The registered decision (ship iff M0, M1 and M4' pass) therefore says no.
- **pgraph must-not-move, same-device Nova pair.** FAIL, 41 of 3379 captures, judged not attributable. All 41 of the fix arm's images are byte-identical to captures from builds without the flip (`pgraphnoise.py`). Nothing there points at the flip, but the leg did not pass.

The flip's measured value is 0 gfps on both titles (Blinx/Thor, Arctic/Nova). It saves about 9% of vCPU per frame on Arctic.

Next, ranked by P x win (NOTES.md, "Attempt 7"):
1. Arctic on the Thor under tcg424flip-arctic2.json, after the fan fix. P about 0.5, win about 0 gfps.
2. A `--runs 3` pgraph pair. P about 0.8, and useful only together with 1.

Recommended: leave the range test opt-in.

Local checks in place of CI: `git diff --stat origin/master...HEAD` lists only the files above, and nothing under accel/, hw/ or other emulator paths. Every prediction JSON parses with `python3 -m json.tool`. No harness file changed, so selftest.sh does not apply. preflight.sh: see NOTES.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
