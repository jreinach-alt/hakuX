# `Attrib_carryover`: carryover is REPRODUCED, and the floor is not dither

`Attrib_carryover` carries 2,923,650 differing channels over 96 captures — on
the face of it one of the largest residuals left, and the first lead in a while
whose code sits **in this lane**: the inline-attribute binding at
`gl/vertex.c:110/205/207/224` and `gl/draw.c:642-656`.

It is not a carryover defect. Attribute carryover is reproduced to the pixel.
Two in-lane mechanisms for what remains were tested and **both are dead**, one
of them by a falsified prediction.

Every number below is reproduced by
`docs/testing/attrib_carryover_floor.py <ours_dir> <goldens_root>`.

## What the suite actually measures

Each capture renders a fully-specified primitive, then a second primitive that
omits one attribute, and checks the omitted attribute carries over. Names are
`{L,T}-<attr><colour>-<mode>`: 12 attributes × 4 draw modes × 2 primitives = 96.

**The colour in the name is not an axis.** `kTestConfigs` in
`attribute_carryover_tests.cpp` assigns exactly one colour per draw mode, so
`col` and `mode` are perfectly confounded — the two pivots below are the same
pivot printed twice, and the colour carries no independent information.

| pivot | n | channels | per capture | mean \|d\| |
|---|---:|---:|---:|---:|
| `T` triangles | 48 | 2,896,815 | **60,350** | 1.16 |
| `L` lines | 48 | 26,835 | **559** | 1.00 |
| mode `da` | 24 | 809,742 | 33,739 | 1.20 |
| mode `ib` | 24 | 807,112 | 33,629 | 1.19 |
| mode `ia` | 24 | 799,537 | 33,314 | 1.19 |
| mode `ie` | 24 | 507,259 | 21,135 | 1.01 |

Triangles carry 99.1%. **Eleven of the twelve attributes produce byte-identical
difference maps** — `np.array_equal` true, zero differing pixels between the
maps — at 246,307 channels each. Only `d` (diffuse) differs, at 214,273.

## The control, and the headline

An identical aggregate can mean reproduced, not ignored. So: for each attribute,
how far does the image move from the `w` capture — **on our side and on
hardware's side, measured separately**?

| | ours-vs-ours(`w`) | GOLD-vs-GOLD(`w`) |
|---|---:|---:|
| T/da `t0` | 65,154 | 65,154 |
| T/da `bd` | 34,410 | 34,410 |
| T/ie `n` | 92,208 | 92,208 |
| T/ie `t3` | 96,090 | 96,090 |
| L/da `fc` | 3,720 | 3,720 |
| L/ib `bs` | 5,040 | 5,040 |

**80 of 88 comparisons are identical to the pixel.** The test discriminates —
the counts are large and differ per attribute, so this is not a blind
instrument — and our renderer moves by exactly the amount the hardware moves,
for every attribute and every draw mode.

**Attribute carryover is reproduced. The in-lane lead is dead:
`gl/vertex.c` and `gl/draw.c`'s inline-value binding is correct.**

The eight exceptions are all the `d` attribute, and all tiny: T/da +93, T/ib
+222, T/ia +234, T/ie +291, L/da +1, L/ib +1, L/ia +3, L/ie −1 — under 0.3% of
the movement in every case. On a residual that is entirely a ±1 floor, a 0.2%
difference in how many pixels moved is what floor pixels tipping either side of
a rounding boundary look like. **Not a separate defect on this evidence**, and
I am not going to promote it to one.

## What the residual is

- **|d| is capped at 2.** 83.77% at exactly 1, 16.23% at exactly 2, **nothing
  above**, across all 96 captures.
- **Solid, not thin** (P1, with a shuffled control C2):

| capture | diff px | bg-diff | mean nbrs | ≥3 nbrs | shuffled | shuffled ≥3 |
|---|---:|---:|---:|---:|---:|---:|
| `T-t0…-da` | 27,519 | **0** | 3.61 | 91.8% | 0.35 | 0.3% |
| `T-t0…-ib` | 27,519 | **0** | 3.61 | 91.8% | 0.37 | 0.3% |
| `T-t0…-ia` | 27,519 | **0** | 3.61 | 91.8% | 0.36 | 0.3% |
| `T-t0…-ie` | 20,869 | **0** | 3.06 | 77.9% | 0.27 | 0.1% |

  C1 holds: zero differing pixels where both sides are background.

- **It is exactly the interpolated region.** Of differing interior pixels,
  **0.0%** sit where the golden's colour is locally flat; of *matching* interior
  pixels, **90.8%** (da) and **75.4%** (ie) do. In 28,280 flat interior pixels
  there are **zero** differences. We are byte-exact wherever the colour is flat
  and differ only where a colour is being interpolated across the triangle.

## An instrument correction, because it inverted the answer

The gradient ratio (P3: mean golden gradient at differing vs matching interior
pixels) was registered with a ≥ 1.5× threshold. Measured naively it comes back
**0.53–0.92** — an apparent *anti*-correlation, two of three below the null band.

That was my instrument, not the data. The in-primitive mask includes the
primitive's boundary against the background, where the gradient is enormous and
where we happen to agree. Eroding three pixels off the mask:

| capture | uneroded | **eroded** |
|---|---:|---:|
| `T-t0…-da` | 0.92 | **10.24** |
| `T-t0…-ie` | 0.69 | **4.23** |
| `Polygon` | 0.53 | 1.16 |
| `TriStrip` | 0.62 | 1.49 |

**P3 holds for `Attrib_carryover`, decisively.** The uneroded figure was
measuring "edges have big gradients", which is a different question.

## The dither hypothesis, falsified

Every property above fits one thing: an ordered dither, which perturbs a
fragment by at most one count, only where the value is not exactly
representable, on a position-dependent pattern. And the switch is **in this
lane** — `gl/draw.c:212` and `:378` enable `GL_DITHER` from
`NV_PGRAPH_CONTROL_0_DITHERENABLE`, while Vulkan has the same line **commented
out** at `vk/draw.c:1591`. Nothing in `nxdk_pgraph_tests` or `pbkitplusplus`
touches `SET_DITHER_ENABLE`, so the bit sits at its default.

Registered in `predictions/2026-09-15-the-filled-floor-is-gl-dither.md` before
measuring. Both predictions fail.

**P4 — periodicity.** `P(differ at p+L | differ at p)` over density, for dither
lags 2/4/8 **and non-dither controls 3/5**:

| capture | axis | L2 | **L3** | L4 | **L5** | L8 |
|---|---|---:|---:|---:|---:|---:|
| `T-t0…-da` | x | 2.051 | **2.209** | 2.052 | 2.044 | 2.037 |
| `T-t0…-da` | y | 1.992 | 1.995 | 2.009 | **2.217** | 1.998 |
| `T-t0…-ie` | x | 2.436 | **2.926** | 2.435 | 2.412 | 2.389 |
| `T-t0…-ie` | y | 2.001 | 2.019 | 2.134 | **2.905** | 2.001 |

The kill condition was "no lag in {2,4,8} beats density by 1.25×, **or lag 3/5
matches the best of them**". Lags 3 and 5 don't match — they **win**, on every
capture and both axes. The mask is periodic at the *ramp step spacing*, which is
what interpolation rounding looks like, not at a power of two.

**P5 — phase.** Occupancy over the 16 cells of (x mod 4, y mod 4), restricted to
interior pixels with non-zero gradient: max/min ratio **1.02, 1.09, 1.02, 1.03**
against a kill floor of 1.2 and a threshold of 1.5. The 4×4 map is flat to three
decimal places. **There is no dither matrix.**

**`gl/draw.c:212` is correct as written.** H2 is dead, and C7 — the emulator run
that would have measured a `glDisable(GL_DITHER)` probe — is not spent, which is
the point of putting the cheap spatial test first.

## The other in-lane knob was already dead

`glsl/common.c`'s interpolation qualifier is this lane's only other control over
interpolation, and it cannot be the mechanism here:
`src/shaders/attribute_carryover_tests.vsh` ends `mov oPos, iPos` — a pure
passthrough — and every vertex is submitted at a constant `z = 3.0f` with w = 1.
**Constant w makes perspective-correct and screen-linear interpolation
identical.** Checked in the test's own source rather than assumed.

## This floor is NOT `3D_primitive`'s filled floor

P1 and P2 both passed, and both pointed at one mechanism: same solid-area shape,
same magnitude cap (`3D_primitive` filled 96.34% at |d| ≤ 2, `Attrib_carryover`
100%). Two spatial tests then separate them cleanly:

| | `Attrib_carryover` | `3D_primitive` filled |
|---|---|---|
| differing on FLAT interior | **0 of 28,280 (0.000%)** | **302 of 910 (33.2%)** |
| P4 elevation over density | **2.0–2.9×** | **0.99–1.16×** |
| eroded gradient ratio | **4.23–10.24** | 1.16–1.49 |

`Attrib_carryover`'s floor is confined to interpolated colour and is strongly
structured. `3D_primitive`'s filled floor differs on flat colour too and has
essentially no spatial structure. **They are two populations.**

So P1 and P2 — a shape statistic and a magnitude statistic — matched across two
mechanisms that the spatial tests separate. That is the fourth time an aggregate
has pointed the wrong way in this work, and the first time it did so while
*passing* its registered predictions. **A prediction can be met by the wrong
mechanism; what discriminates is the measurement that could tell them apart.**

For `3D_primitive`'s filled floor this adds a fourth exclusion — not one
rounding convention, not triangulation seams, not the AA surface, **and not GL
dither**.

## Where this leaves the suite

`Attrib_carryover` is **characterised and not actionable from this lane**:

- The defect the suite is named for does not exist in our renderer.
- What remains is colour-interpolation rounding: we interpolate in float and
  round at the framebuffer; the hardware interpolates already-quantised colour.
  The magnitude cap, the flat-colour exactness and the ramp-period structure all
  say the same thing.
- Both in-lane knobs are excluded **by measurement, not by judgement**: the
  interpolation qualifier (constant w) and `GL_DITHER` (P4/P5 falsified).
- A fix would have to quantise fragment-side, in `glsl/psh.c` — `[free]`, not
  this lane, and already the blocked grant wanted by three other leads. **Four
  now.**

I am not reaching for a fifth framing of a ±1 floor. Four have been tried.
