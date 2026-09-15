# Prediction: the ±1 floor is `GL_DITHER`, enabled in `gl/draw.c` — and that line is mine

Registered 2026-09-15, BEFORE the measurements. Not edited afterwards.

## Why this hypothesis, and why now

From `2026-09-15-attrib-carryover-is-the-filled-floor.md`, already measured:

- `Attrib_carryover`'s residual is **|d| <= 2, always** (83.77% at 1, 16.23% at
  2, nothing above).
- It is **byte-exact wherever the golden's colour is locally flat**: 0.0% of
  differing interior pixels sit at gradient 0, against 75.4-90.8% of matching
  interior pixels. Gradient ratio 4.23-10.24x after eroding boundary pixels.
- It is **independent of which attribute is exercised** -- eleven of twelve
  attributes give byte-identical difference maps -- and carryover itself is
  reproduced to the pixel.

The one in-lane knob on interpolation, the `noperspective` qualifier in
`glsl/common.c`, is **provably irrelevant here**: `attribute_carryover_tests.vsh`
ends `mov oPos, iPos`, a pure passthrough, and every vertex is set at a constant
`z = 3.0f` with w = 1. Constant w makes perspective-correct and screen-linear
interpolation identical. So that is not it, and I am not guessing that it is.

What is left fits one thing exactly:

```c
/* hw/xbox/nv2a/pgraph/gl/draw.c:212 and :378 -- MY LANE */
if (pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0) & NV_PGRAPH_CONTROL_0_DITHERENABLE) {
    glEnable(GL_DITHER);
} else {
    glDisable(GL_DITHER);
}
```

**Vulkan has the same line commented out** (`vk/draw.c:1591`), so the two
backends already disagree about dithering. The tests never touch
`SET_DITHER_ENABLE` -- nothing in `nxdk_pgraph_tests` or `pbkitplusplus`
mentions dither -- so the bit sits at its default, and `pgraph.c:69/304` shows
`DITHERENABLE` is live state.

GL dithering perturbs a fragment by at most one count, only where the value is
not already exactly representable in the target format, and by a **position-
dependent** pattern. That is every property of the floor, including why flat
colour is byte-exact.

## Hypothesis

**H2:** the floor is an ordered dither the desktop GL driver applies because we
enable `GL_DITHER`, and which the hardware does not apply to this target.

## Predictions, with numeric kill conditions

- **P4 -- the mask is PERIODIC.** For the best lag L in {2, 4, 8}, measured
  separately in x and y, `P(differ at p+L | differ at p)` exceeds the mask's
  overall density by **>= 1.25x**, and lags 3 and 5 do **not** do as well.
  **KILL:** no lag in {2,4,8} beats density by 1.25x, or lag 3/5 matches the
  best of them -> this is not an ordered dither.

- **P5 -- the phase is non-uniform.** Over the 16 cells of (x mod 4, y mod 4),
  restricted to interior pixels where the golden's gradient is non-zero, the
  occupancy is non-uniform with **max/min cell ratio >= 1.5**.
  **KILL:** max/min < 1.2 -> no dither matrix; the floor is plain
  round-to-nearest and the `gl/draw.c` line is correct.

- **C5 (control).** The same phase test on a capture region where the golden is
  FLAT must be empty or uniform -- there is nothing for a dither to do there.
  If flat regions show the same phase structure, P5 is measuring something else.

- **C6 (control).** `3D_primitive`'s filled arm must show the same periodicity
  if it is the same mechanism. If it does not, these are two populations and
  the cross-suite claim from the previous prediction weakens.

- **C7 (confirmatory arm, expensive).** If P4 and P5 hold, a probe that forces
  `glDisable(GL_DITHER)` must reduce the residual on these captures. Registered
  targets, to be written down before that run and not after: `Attrib_carryover`
  2,923,650 channels and `3D_primitive`'s filled arm 6,988,936 channels should
  both fall substantially; suites with no interpolated colour must not move.

## The uncomfortable outcome, named in advance

**P4 and P5 both fail.** Then the floor is ordinary round-to-nearest divergence
with no dither structure, `gl/draw.c:212` is correct as written, and this suite
joins the not-actionable pile with any fix sitting in `glsl/psh.c` -- `[free]`,
not my lane, and already the blocked grant. I report that and stop, rather than
reaching for a fifth framing. Four framings of this floor have now been tried.

The second uncomfortable outcome: **P4/P5 hold but C7 shows no improvement.**
That would mean the pattern is real but the driver applies it regardless of the
`GL_DITHER` switch, which would make it a driver property I cannot fix from the
lane either. C7 is the one that decides actionability, and it is the one that
costs an emulator run -- so P4 and P5 must both pass before I spend it.
