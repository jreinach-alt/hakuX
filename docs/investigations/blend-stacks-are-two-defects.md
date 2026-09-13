# Blend_tests is two defects in different regions, and #50's mechanism is not a reversal

Measured 2026-09-12 on all 1,568 captures of the recovered oracle
(`res_oldblend`) against the silicon goldens, region against region.
Reproduce with:

    docs/testing/blend_stack_regions.py --captures ~/hakux-work/res_oldblend

## The frame is three pictures, not one

`blend_tests.cpp` draws three swatch stacks, each into its own
render-to-texture, then composites them. Scoring the whole capture averages a
bit-exact region together with a broken one and reports something true of
neither.

| stack | function | cols | draw order, top to bottom |
|---|---|---|---|
| A | `DrawColorStack` | 16-79 | green, red, blue, white |
| B | `DrawAlphaStack` | - | green, red, blue, white |
| C | `DrawColorAndAlphaStack` | 560-623 | **white, blue, red, green** |

All at rows 112-368. Geometry is derived rather than guessed: the stack is
`kColorSwatchSize` = 64 wide and 256 tall, composited at `x = 16` and at
`x = framebufferWidth - (16 + 64)` = 560, `y = (480 - 256) / 2` = 112.

A and C draw the same four colours in **opposite** order. A band index is not
portable between them, and that is the trap in reading these captures.

## Result: the two regions fail for unrelated reasons

    equation     stack A       stack C
    ADD           0/224        223/224
    MAX           0/224        224/224
    MIN           0/224        224/224
    REVSUB        0/224        224/224
    SUB           0/224        224/224
    SADD        224/224        224/224
    SREVSUB     224/224        224/224
    TOTAL       448/1568      1567/1568

**Stack A is a clean oracle for the signed equations.** Bit-exact on all 1,120
unsigned captures, wrong on every one of the 448 signed ones, with perfect
separation by equation. Any residual there is the #43 signed-equation defect
alone -- no contamination from stack C, no fifth-quad strip, no revision
question. #43 should be fitted and validated on this region.

**Stack C fails on 1,567 of 1,568, including every unsigned equation**, so it
is dominated by something that is not blending. That is #50. The single
exception is `0_ADD_1`, exact in both regions.

## #50 is real, but "exact reverse vertical order" is not supported

Two hypotheses tested and **falsified**:

**Render-target aliasing** -- that stack C shows stack A's content, which
would elegantly explain why its apparent order is A's order. Compared our
stack C against both our own stack A and the golden's stack A on all 1,568
captures: **0 matches either way.** Dead.

**Exact band reversal** -- that our four bands are the golden's four bands in
reverse. On 1,567 of 1,568 captures **no band matches any golden band
bit-exactly**, in any position. So the bands differ in value, not only in
order, and the strong form of the claim is false.

As an ordering *tendency* it is real but mixed: reversal fits better on 949
captures, ties on 376, and fits **worse** on 243, with median band-mean L1
distance 121.1 reversed against 194.4 in order. A pure reversal would leave
the reversed distance near zero on nearly everything. It does not.

So #50's premise as filed -- four swatches "in exact reverse vertical order"
-- overstates what the captures show. Something is wrong in that region on
essentially every capture, and it has a reversal-shaped component, but neither
reversed placement nor reversed colour assignment accounts for bands whose
values match nothing.

## What is ruled out, and what the 376 ties mean

**A test-revision mismatch is ruled out.** The concern was that the oracle
disc (release `v2025-03-14`) might predate the goldens, making the comparison
invalid. Checked against upstream: `blend_tests.cpp` was touched by
`283e2971` (2025-02-24, the last revision before the release) and then not
again until `41f3b0fd` (2025-04-22) and `2cfe6073` (2026-01-23). Both
`DrawColorStack` and `DrawColorAndAlphaStack` are **byte-identical** in draw
order and in all four swatch colours across that whole span; only the
positional arguments were parameterised. The test did not change, so no
revision difference can explain any of this.

**The 376 ties are degenerate, not evidence.** A tie means reversing the
golden's bands changes the distance not at all, which happens when the bands
are already near-symmetric under the blend in question. Those captures cannot
distinguish the two readings and must not be counted toward either.

## Next

The discriminator is not in these captures. It is what the draw queue
receives: vertex positions and diffuse colours for the four stack-C draws.
Correct positions with swapped colours means colour assignment; mirrored
positions means placement; correct both means the defect is downstream of
submission, in the render-to-texture composite -- which the falsified
aliasing test does not rule out in its weaker forms, and which would
cross-reference #4.

One observation that does survive and favours a per-draw explanation: stack C
is the only stack whose four consecutive draws carry no state change between
them, and on the 1,120 unsigned captures it is the only stack that fails at
all. A y-flip in the vertex path would hit all three stacks.
