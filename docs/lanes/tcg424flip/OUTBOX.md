## #424 -- 2026-10-03 08:38 PDT

[lane.tcg424flip] Verdict: the range test stays opt-in. The flip to default-on does not ship.

**Arctic Thunder, Nova, tcg424flip-arctic-nova.json (2 pairs, 7bcd6e6e2b, MAX, no pause)**, judged as registered:

| | A (HAKUX_TCG424_RANGE=0) | B (flipped default) |
|---|---|---|
| gfps (mean of 2 runs) | 40 (39, 41) | 39.5 (38, 41) |
| churn% | 2.5 | 0.0 |
| di/s | 72,322 | 0 |
| on% / cpf | 83.75 / 20.95 | 75.05 / 19.0 |
| slow/s / inv/s / fs/s | 20,371 / 14,625 / 0 | 277,479 / 271,769 / 274,567 |

- M0, M2a, M2b and M4' pass, with no fatal line, gaps of 1.8 s or less, and frames showing the race.
- M1 fails on its falsifier: A's churn is 2.5%, against the A >= 5.0 threshold.
- Under the registered rule, the flip does not ship on this evidence, and Arctic does not price the lever.

**pgraph must-not-move, tcg424flip-pgraph.json (same-device Nova pair -1704391 / -1704464)**: the arms job judged it FAIL on 2026-09-30 02:10 PDT. 41 of 3379 captures differ, and the job marked them not attributable with one run per arm. The 41 fall in five families: Stencil_REPLACE, ZPass, GeometrySuperscreen, and one Antialiasing capture. Every one of the fix arm's 41 images is byte-identical to a capture from a build without the flip, so the pixels show nothing against the flip. The leg still did not pass as registered.

**Withdrawn requests (hostops 08:30 addendum).** The six `queue/withdrawn` entries are the 09-29 Thor runs of tcg424flip-arctic2.json. lane.local withdrew them on purpose at 12:00 PDT on 09-29, when fps runs moved off the Thor (#507), and that reason still holds. Their Nova replacements ran on 09-30 between 00:06 and 01:41 PDT. Nothing was re-queued.

**The flip's measured value.** It changes 0 gfps on both titles measured (Blinx/Thor 19 vs 19; Arctic/Nova 40 vs 39.5) and saves about 9% of vCPU per frame on Arctic.

**Next, ranked by P x win** (details in docs/lanes/tcg424flip/NOTES.md):
1. Arctic on the Thor under tcg424flip-arctic2.json, once the fan is fixed. P about 0.5, for about 0 gfps.
2. A `--runs 3` pgraph pair. P about 0.8, but it only matters together with 1.

Recommendation: leave the range test opt-in. #424 can close as "measured, not flipped".
