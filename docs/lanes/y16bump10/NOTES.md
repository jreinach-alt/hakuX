# lane y16bump10 (#10, the Y16 bump source)

## The change

`hw/xbox/nv2a/pgraph/glsl/psh.c`, `append_bump_channel`: when the bump input
is SZ_Y16 or LU_IMAGE_Y16 (new `PshState.tex_y16`, set next to
`tex_comp0_const`), component 2 (the horizontal offset, the one m00 scales)
reads the low byte of the filtered 16-bit value as two's complement:

    bump_signed(float(uint(round(t.b * 65535.0)) & 255u) / 255.0)

Component 1 (the vertical offset) is unchanged. It still reads the full
16-bit value, rounded to a byte by `bump_signed` as before. The luminance
(component 0) is unchanged too. It is the literal ONE for Y16.

- **Vertical source: the full value, not the high byte.** The brief allowed
  either. PR #363's vertical axis has no seam sweep: 770 px on hakuX with the
  full value (classified NONE), 2,088 px on silicon. A third of silicon's
  2,088 px sit on vertical checker edges and 658 are in the seam band, so the
  full value and the high byte are not separated there. The full value is the
  reading already measured to give NONE on the dry run, and keeping it means
  this arm tests only the horizontal low-byte model.
- **Sign flags are ignored for component 2.** Signing each texel's low byte
  (0x52 or 0x53, both positive) before the filter would remove the sweep in
  the flagged quads. Silicon's four flag-combination quads differ on every
  Y16 capture only by the positional floor that A8 shows (0/586/312/612), so
  the sweep is present in all four.
- **Only Y16 changes.** R16B16, A8, Y8/AY8/A8Y8 and the YUV formats have
  `tex_y16` false and emit byte-identical shaders.

## Bump env lum Y16 cannot show this, whatever the brief assumed

The brief listed `BumpEnvLum_Y16` as must-move at ~28,132 px. That figure
predates the luminance-literal fix (93196d2d05). Since then it has been at the
1,576 px floor (`nv2a_issues.toml`, the full6743 scores). PR #350 also showed
that its m11 = 5.0 image is horizontal stripes (150 of 168 seam-band rows are
one colour), so a horizontal offset change cannot show there. PR #187's use of
it to refute the low-byte model is void for the same reason. The prediction
therefore guards it as **must-not-regress** rather than must-move.

## The arm

`docs/testing/predictions/y16bump10-y16.json`:

- a_ref = the master tip I merged
- b_ref = the branch head after the merge and the index regeneration. The
  only `hw/` difference between the two is the fix.

The file is committed, so the arms job queues it. I did not queue arms by hand.

## Do not repeat

- Do not use `BumpEnvLum_Y16` as evidence either way about a horizontal
  offset. It is stripes.
- Do not tune the low-byte expression to the arm's number if the Y16 leg
  lands elsewhere. Report it, and treat the model as refuted.

## State at session end (2026-09-25)

Waiting on two signals:

- the arms job verdict for `y16bump10-y16.json` (a 081dcf4a38, b 50b46b0495),
  which will arrive as a `[job.arms]` comment on PR #367;
- CI on the head.

Once the verdict is in, cite it in the PR and mark the PR ready. On a FAIL,
name each refuted leg with its figure and take its hunk out.

## Why attempt 1 did not finish

It ended waiting, correctly, but on a head GitHub could not build: the PR
had gone CONFLICTING with master (`docs/testing/nv2a_index.json`, the
generated index), so no CI run existed and none ever would. A `waiting:`
on CI needs a mergeability check first.

## Verdict (2026-09-26, `[job.arms]` on PR #367): PASS

a 081dcf4a38 → b 50b46b0495, one run per arm, 141 captures, disc
identical in both arms, prediction bound before the run
(sha256 e992390a…613b5c).

| capture | A | B |
|---|---:|---:|
| BumpMap_Y16 | 22,374 | 3,490 |
| BumpMap_Y16_L | 22,374 | 3,490 |

better 2, worse 0, same 139, exact 57 → 57. BumpEnvLum_Y16/_Y16_L did not
move, as registered. Only the two Y16 Bump_map captures differ byte for byte.

The residual is 3,490 px, 1,914 above the 1,576 floor. It is under the
6,000 bound, and it fits the vertical source being the open leg. PR #363's
m11-only run moved silicon 2,088 px, where hakuX with the full value moved
770. A next lane can test the high-byte vertical reading against this
residual. It should do that as its own arm, not by tuning this one.

## Attempt 2

Merged origin/master in, which conflicted only in the generated index.
I rebuilt the index from the fold-pins trees (`--tests
fold-pins/nxdk_pgraph_tests --support fold-pins/pbkitplusplus`, tests commit
6743b6ab, the same as master's provenance), and `check` passes. Building
against `~/nxdk_pgraph_tests` without `--support` loses the resolved table,
so do not use it. The prediction's refs are still ancestors of the head;
nothing was rebased.
