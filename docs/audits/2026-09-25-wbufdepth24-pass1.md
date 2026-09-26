# Audit pass 1 -- PR #268, lane/wbufdepth24 (#266)

Head audited: `8dfe303deb`. Diff against `origin/master`: `psh.c` (+7/-1, the
D24 case), `predictions/wbufdepth24-d24sat.json` (new), `nv2a_index.json`
(line moves only), `docs/lanes/wbufdepth24/{NOTES.md,classify.py}`.

**Result: no HIGH, no MEDIUM, four LOW.** The code change is correct and the
arm confirms the prose claim row by row. Next state: `needs-audit-2`.

## The change

`gl_FragDepth = min(zfloor, 16777215.0) / 2^24` (plus the unorm path's +1 ULP),
in `DEPTH_FORMAT_D24` only.

- **Float storage (Vulkan Z24S8 = D32_SFLOAT):** 16777215/2^24 is exact and
  bit-equal to the clear value the clear path stores, so a saturated fragment
  now passes LEQUAL against a cleared buffer. Before the change it carried up
  to CLIP_MAX/2^24 = 16.0 and failed.
- **Unorm storage:** (1 - 2^-24) + 1 ULP = 1.0 -> 0xFFFFFF. A value above 1.0
  was already clamped by the target there, so this path does not change.
- **D16, F24, F16:** these are other cases of the switch and emit the same
  text as before. F24 already had `min(..., 0xFFFFFFu)`.
- **Clip mode (`depth_clipping`), with CLIP_MAX > 0xFFFFFF:** fragments in
  (0xFFFFFF, CLIP_MAX] now saturate instead of failing against the clear. The
  saturation evidence in the goldens comes from CLAMP-mode rows. The ClipF/ClipW
  rows on this disc did not regress (0 worse over 530), so this is the
  expected behaviour and not a finding.

## Arm check (not only the PASS line)

`[job.arms]` PASS covered 530 checks, one run per arm, on the Thor
(`1790371358-arms-wbufdepth24-base-50897` / `-fix-50997`). I read the 18
target rows in the verdict file myself, because the must-move leg is prose
(see L1):

| rows | A -> B | worst B/A |
|---|---|---:|
| WBuf24D FloorQuad V0 ZB{0,1} ZS1 (blank -> ok) | 230,469 / 230,399 -> 219 / 216 | 0.1% |
| ZBuf24D FloorQuad V0 x4 | 73,980..81,809 -> 609..702 | 0.95% |
| ZBuf24D FloorQuad V1 x4 | 16,190..24,135 -> 37..153 | 0.63% |
| ZBuf24D RoofQuad V1 x4 | 29,167..37,442 -> 38..492 | 1.31% |
| ZBuf24D WallQuad V1 x4 | 32,121..39,935 -> 97..297 | 0.74% |

The 18 rows sum to 5,217 px against the registered bound of 113,000. Every row
is well below its 10% kill line. Tally: better 18, worse 0, same 512. The
18 better rows are exactly the predicted rows.

## Findings

**L1 (LOW) -- the must-move leg is not judged.** `expect` and
`expect_counts` are both `{}`. `ab_compare.judge()` therefore scored only
`must_not_move` and `must_not_regress`, and `same` satisfies
`must_not_regress`. Failure scenario: if b_ref had been inert, all 18 rows
would have been `same` and the verdict would still say "PASS -- all 530
registered checks hold". The prediction says that the leg is bound in prose,
and the rows did move (table above), so this arm is sound. The fix for next
time is `"expect_counts": {"worse": 0}`, plus a per-row ceiling if the judge
gains one. An exact `better` count was not available because the edge rows
were allowed to move.

**L2 (LOW) -- single-run arms.** Each arm ran once, so
`pixels_moved_attributable` cannot fire, and `must_not_move` on `*Buf16*` /
`*Buf24F*` checked scores, not bytes. Failure scenario: a leak that changed
pixels but not scores on those rows would pass. That leak cannot happen from
this diff, because those rows emit other switch cases whose text did not
change.

**L3 (LOW) -- NOTES carries a superseded plan without a pointer.** Session
1's "Candidate fix" and "Status" sections name 26 rows and put `_ZB` rows in
`must_not_move`. The registered prediction names 18 rows, and `_ZB` is under
`must_not_regress` through `*Buf24D*`. Session 2 corrects this, but nothing
marks the earlier text as superseded, and NOTES does not record the verdict.
Failure scenario: a reader who takes the kill condition from session 1
checks 26 rows and finds 8 "unmoved".

**L4 (LOW) -- the PR is CONFLICTING again.** GitHub reports
`mergeable: CONFLICTING`. Per `[job.board]` the conflict is only in the
derived `nv2a_index.json`. This is not a defect in the diff, but the fold
needs a merge of master plus an index rebuild (`nv2a_index.py build` over the
fold pins) before it can build the head.

## Not findings

- `classify.py` is a lane tool with no callers. Its Z16 `gsat` uses the
  golden's own maximum, and the file says so.
- The `nv2a_index.json` hunks are `loc` line shifts (+6) plus
  `emulator_commit`. No entry was added or dropped.
- The psh.c comment accurately states CLIP_MAX = 16 x 0xFFFFFF (268,435,440).

## For pass 2

There is no HIGH or MEDIUM to verify as fixed. Pass 2 should confirm that the
branch merges master cleanly, with the index rebuilt and `check` green (L4).
The LOWs can be left as they are.
