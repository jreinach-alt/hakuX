# Prediction: the hardware sweeps a square pen, GL sweeps a perpendicular segment

Registered 2026-09-15 on `3321d69e`, before measuring any diagonal.

## What forces this hypothesis

`line-width-first-gl-baseline.md` established, by direct measurement on two
independent vertical edges, that **the rendered width of a VERTICAL line is
exactly the requested width in both ours and the hardware**, at every integer
from 1 to 48. Yet the whole frame is still ~0.9x. So the deficit is entirely on
the non-axis-aligned lines.

That rules out most candidates at a stroke. Any rule that scales width globally
would have shown on the verticals. Whatever differs must be **exactly 1 at
0 and 90 degrees** and greater than 1 in between.

## The hypothesis

**GL** rasterises a wide line as a rectangle of width W measured **perpendicular
to the line** -- this is what the spec says and what `glLineWidth` means.

**The hardware** sweeps an **axis-aligned square pen of side W** along the line,
which is the classic Bresenham-with-a-square-brush construction.

For a line at angle theta, sweeping a WxW axis-aligned square gives a
perpendicular thickness of

    W * (|cos theta| + |sin theta|)

against GL's W. The ratio is therefore **|cos theta| + |sin theta|**:

| theta | ratio |
|---:|---:|
| 0 (horizontal) | 1.000 |
| 90 (vertical) | 1.000 |
| 26.6 | 1.342 |
| 45 | **1.414** |
| 63.4 | 1.342 |

It is exactly 1 on both axes -- which is the vertical-edge result -- and peaks
at sqrt(2) on the diagonal.

## The prediction, in falsifiable form

For each segment of the `LINE_LOOP` (16 known vertices in
`line_width_tests.cpp`), measure the perpendicular thickness of the golden and
of ours at the segment midpoint, at a width low enough that neighbours do not
merge.

**P1.** Our thickness is W for every segment, independent of angle.

**P2.** The golden's thickness divided by ours is `|cos theta| + |sin theta|`
for that segment's angle, within one pixel of quantisation.

**P3.** The ratio is 1.000 at the axis-aligned segments and peaks near 1.414 at
45 degrees.

## What kills it

Any of: our thickness varying with angle (P1 fails, and the shape is something
else entirely); the golden's ratio not tracking `|cos| + |sin|`; or the ratio
exceeding sqrt(2) or falling below 1 anywhere. A ratio that is constant across
angles would also kill it and would resurrect the global-scale reading that
`3321d69e` argued against.

## Stated in advance so a pass cannot be over-read

Confirming this identifies the RULE. It does not say the fix belongs in
`gl/draw.c`, and it probably does not: `glLineWidth` cannot express a square
pen, so matching the hardware would mean drawing wide lines as geometry rather
than as GL lines. That is a rasteriser-level change, `roundScreenCoords` in
`glsl/vsh.c` is rasteriser-wide and needs the owner, and nothing here licenses
it. The deliverable of this measurement is the rule and its evidence, not a
patch.

---

## Outcome: FALSIFIED. Thickness is correct at every angle that can be measured cleanly.

### The first instrument was unsound, and its own control said so

Measuring the `LINE_LOOP`'s 16 segments gave "our thickness" ranging from 2.50
to 27.50 for a requested width of 4. GL draws width-4 lines by construction, so
a reading of 27.5 is the normal walk crossing neighbouring segments -- the
LINE_LOOP is a dense tangle in a small region. **P1's own control failed, so
nothing from that pass is reportable in either direction.** It is recorded here
because the temptation was to read the noisy ratios as a falsification, and a
broken instrument cannot falsify anything.

### The second instrument has a control that passes

The `TRIANGLES` primitive is two triangles in a sparse region. Marking each
segment CONTAMINATED when our own thickness is not within 1px of the requested
width leaves the clean ones:

| requested | angle | ours | golden | ratio | square-pen predicts |
|---:|---:|---:|---:|---:|---:|
| 4 | 3.3 | 3.75 | 3.75 | **1.000** | 1.057 |
| 4 | 10.1 | 3.75 | 3.75 | **1.000** | 1.159 |
| 4 | 19.6 | 4.00 | 4.00 | **1.000** | 1.278 |
| 4 | 77.7 | 4.00 | 4.00 | **1.000** | 1.190 |
| 8 | 10.1 | 7.75 | 7.75 | **1.000** | 1.159 |
| 8 | 77.7 | 8.00 | 8.00 | **1.000** | 1.190 |

**Every clean measurement gives exactly 1.000.** The square pen predicts 1.057
to 1.278 over these angles and would have been visible at 19.6 and 77.7 degrees
even allowing a pixel of quantisation. P2 and P3 are dead, and with them the
hypothesis.

### Which generalises the vertical-edge result rather than complicating it

`3321d69e` showed thickness exact at 90 degrees. This shows it exact at 3.3,
10.1, 19.6 and 77.7 degrees as well, at two widths. **Line thickness appears
correct at every angle that can be measured cleanly.** There is no angle
dependence in the thickness at all, so `3321d69e`'s "the angle dependence is
back" is itself now doubtful -- it was an inference from a frame-wide total, and
this is a direct measurement.

### Where the CONTAMINATED rows point

The contaminated rows are not random. They cluster where segments MEET, and
there the golden is much larger than ours -- 17.00 against our 7.75 at one
W=8 corner, 8.50 against 5.50 at another. Our own thickness reads BELOW the
requested width at those corners (5.50 and 2.50), which is what a notch looks
like.

So the candidate that survives this measurement is **line joins**: the hardware
appears to fill the wedge where two wide segments meet, and we leave a gap. That
would give correct thickness along every segment, extra golden pixels at every
corner, and a deficit that grows with width -- which is the shape of the
original observation.

**That is a candidate, not a finding.** It rests on four contaminated readings
whose whole point is that they cannot be trusted as measurements. Testing it
needs an instrument aimed at corners specifically, with its own control, and a
prediction registered before the measurement.
