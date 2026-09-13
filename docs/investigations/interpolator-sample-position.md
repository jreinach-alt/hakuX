# Where silicon samples a colour: #38 mechanism 2, measured per axis

Written 2026-09-12 against the goldens and three capture arms, no build and no
device. Branch tip `0f708c8d33`. Arms: `1789268617-bytegrid-fix-1396332`
(APK `b2e2c45d833a`, ref `dca3c94b98` — the arm that landed #38's byte
quantisation, 405 captures, `progress_log_proof` true), and the full-corpus
sweep `z-sweep-*` (APK `fb4dfafc6d38`, ref `ce9c4eecf8`). Reproduce all of it
with `python3 docs/testing/interpolator_phase.py [CAPTUREDIR ...]`.

Issue #38 mechanism 2 is "the host rasteriser's colour interpolation differs
from the NV2A's", and it is the largest one-step class in the corpus — 70
one-step-lo and 201 one-step-sym captures against mechanism 1's 24. The
sharpest prior statement of it, from #57's `Alpha_func` work, was:

> hardware's **red ramp starts 0.8 high and its blue ramp starts 0.8 low** on
> identical geometry — the same direction in *x*, so a **phase offset of about
> 1 px**, not a value bias.

That reading is right about the sign, the axis and the magnitude. It is wrong
about the shape and wrong about the scope, and both matter more than the number
does: the shape is an even-aligned **2-pixel group** in x, not a shift, and the
scope is **two draws in the whole corpus**, not the interpolator. Our
interpolator's phase is already correct on both axes on every other capture we
hold, and `Lighting_normals` — which #38 names as this mechanism's carrier —
has no displacement of any size.

## 1. The measurement

Two ramps, both on axis-aligned screen-space quads with `w = 1` (passthrough
vertex shader, so perspective-correct and linear interpolation coincide), both
with endpoints that are exactly representable bytes under **every** rule #38
considered — so nothing below depends on the vertex quantiser, and the pre- and
post-`colorPrecision` arms give identical answers on them.

| axis | ramp | geometry | endpoints | ours | hardware |
|---|---|---|---|---|---|
| **x** | `Alpha_func` red band, diffuse alpha `0.0f -> 1.0f` | quad x 64 → 576, 512 px | **0 → 255** | pixel centre, **512/512** | **−1.0042 px** |
| **x** | `Alpha_func` blue band, diffuse alpha `1.0f -> 0.0f` | same quad | **255 → 0** | pixel centre, **512/512** | **−0.9958 px** |
| **y** | `Attrib_float/0_1`, grey diffuse `0.0f -> 1.0f` | quad y 144 → 432, 288 px | **0 → 255** | +0.0000 px | **+0.0332 px** |

The x measurement needs no fit. `Alpha_func`'s bands are blended
`SRC_ALPHA`/`ONE_MINUS_SRC_ALPHA` over a known clear colour from a known source
colour, and the inversion is unique: exactly one integer source alpha in 0..255
reproduces a given output RGBA, on **512 of 512 px** of both bands. So the
integer fragment alpha the pipeline used is readable per pixel, and a 255-step
staircase over 512 px locates each crossing to better than a pixel.

The y measurement is a direct read of the written bytes — no blend, no
inversion — over 1,185 unit steps across five columns.

**There is no y offset.** +0.033 px on a ramp whose steps are 1.13 px apart is
zero, and hardware's step positions show no even/odd preference at all (600
even, 585 odd; skew 0.506).

## 2. What the x offset actually is

It is not a phase. A constant phase φ puts every crossing in a window one pixel
wide; hardware's crossings spread over a window exactly **two** pixels wide
(sd 0.596 ≈ 2/√12, range −2.00..−0.01), and **254 of 254** of them land on an
even x. Ours land on both parities, 128 odd against 127 even.

Hardware holds the fragment alpha **constant across the even-aligned pixel
pair** `{2m, 2m+1}`, and its value is the exact vertex-attribute plane
evaluated at the pair's right-hand edge:

> **s = 2·floor(x/2) + 2**

Against the recovered hardware alpha, that is **0 wrong of 512** on the red
band and **0 wrong of 512** on the blue band, including the 127.5 tie at
x 318..321 where the run is four pixels long rather than two. Six other sample
positions were tried and every one of them misses by hundreds of pixels:

| sample position | red band, wrong / 512 | blue band |
|---|---:|---:|
| pixel centre `x + 0.5` (ours) | 256 | 254 |
| pixel corner `x` | 383 | 382 |
| pair left `2·floor(x/2)` | 510 | 510 |
| pair centre `2·floor(x/2) + 1` | 256 | 254 |
| pair right-half `2·floor(x/2) + 1.5` | 128 | 126 |
| centre + 1, `x + 1.5` | 127 | 127 |
| **pair right `2·floor(x/2) + 2`** | **0** | **0** |

Relative to our pixel centre `x + 0.5` that is **+1.5 px on even x and +0.5 px
on odd x** — mean +1, which is the "about 1 px" #57 saw, arrived at by
averaging over a structure that is not a shift.

### It is the fragment's alpha, not the blend unit

The alpha test discards per fragment, before blending, so its coverage mask is
a direct read of the same quantity with the blend taken out of the question.
Across all sixteen `Alpha_func` goldens, every interior band boundary starts on
an **even** x (10 of 10) and ends on an **odd** x (22 of 22) — the exact
footprint of `{2m, 2m+1}`. Ours are mixed: 14 even ends against 8 odd.

### The out-of-sample check

The sample position was fixed on red and blue, whose ramp is 255 byte units
wide. The green band is a different instrument — `0.495f -> 0.505f`, **three**
byte units across the same 512 px — and nothing above was fitted to it.

#57 landed the byte-quantised endpoints (126 → 129, span 3) and got the slope
right, but left the `AlphaFuncEqual_Enabled` coverage on x **149..319** where
hardware has **148..317**, and recorded that 1–2 px displacement as this
mechanism's to finish. It is:

| | `a8 == 127` on |
|---|---|
| ours, pixel centre, byte endpoints | x 149..319 |
| **prediction, pair right, byte endpoints** | **x 148..317** |
| **hardware, measured** | **x 148..317** |

Both bounds, out of sample, from a model fitted to a different band with a
different span and a different direction. `AlphaFuncLessThan_Enabled`, which
holds the low crossing alone with no second edge to average against, is the
same story: predicted x 64..**147**, hardware x 64..**147**, ours 64..148.

## 3. Scope: some draws, not the interpolator

This is the part that changes what should be done about it, and it is also
where my first two readings of the rule died. Both deserve recording, because
each is what the `Alpha_func` evidence alone supports and each is wrong.

### The second instance, and what it kills

**`Context_switch/GRZero`** is a screen-space 7-vertex `PRIMITIVE_POLYGON`
(passthrough shader, `w = 1.0`, `z = 0.1f`) with per-vertex diffuse RGBA, and
**80 of its 192 measurable rows are paired**, reaching E = 1.000, O = 0.039.
Read a row of it straight out of the golden, y = 96, x = 100..119:

```
x : 100 101 102 103 104 105 106 107 108 109 110 111 112 113 114 115 116 117 118 119
G : 129 129 128 128 128 128 128 128 127 127 126 126 126 126 126 126 125 125 124 124
B :  39  39  40  40  40  40  41  41  41  41  42  42  42  42  43  43  43  43  44  44
```

Every step in both channels is on an even x. That kills both readings:

- **not alpha-specific** — this is R, G and B, and the polygon's alpha is not
  what is varying here;
- **not specific to a purely-x gradient** — this polygon's vertex colours
  differ top to bottom as well as left to right, so `dv/dy ≠ 0`.

It also strengthens the finding: the same even-aligned 2-pixel group, on a
different attribute, a different primitive type, a different gradient
orientation, and a suite fitted to nothing.

### But it is not universal, and the counter-example is clean

**`High_vertex_count`** draws 6×6-px screen-space Gouraud quads, passthrough
shader, `w = 1`, four differing vertex colours each — and is **not paired at
all**. Straight out of the golden, y = 200, x = 100..105:

```
R : 227 229 232 234  38  35
```

Every pixel differs. A pair-constant field cannot do that at any gradient
steepness, because within a pair the two pixels are equal by construction. Its
four submission variants (`arrays`, `inlinearrays`, `inlinebuffers`,
`inlineelements`) all read maxE = 0.000 over 432 measurable rows.

`3D_primitive`, `Shade_model`, `Attrib_carryover`, `Lighting_accumulation`,
`Material_alpha`, `Fog` and `Specular` are likewise unpaired, with 61 to 329
measurable rows each and not one paired row among them.

### The census

Per row, over every golden in the corpus — **1,162 captures have x rows this
test can measure at all**, and the pairing appears in three places:

| capture | paired rows | of measurable rows | what it is |
|---|---:|---:|---|
| `Alpha_func/*` (14 captures) | 128 | 128 | interpolated diffuse alpha |
| `Context_switch/GRZero` | 80 | 192 | interpolated diffuse RGB |
| `Image_blit/BlitBeyondWidth` | 14 | 479 | a blit, not an interpolant — #59 |
| the other 1,145 captures | **0** | 61–479 each | — |

**The metric's blind spot, stated so a silence is not read as a negative.** It
counts only positions where neighbours are within 4 per channel, because
without that bound the `pb_print` overlay's 3-px white glyph stems on a flat
ground read as a pair — E = 1.00, O = 0.03 on `Depth_Clamp`'s text alone, and
E = 0.82 on `Specular`'s, which is what sent me chasing two false positives.
A gradient steeper than about 4 bytes/px therefore leaves too few qualifying
positions and the row is *dropped rather than judged*. `High_vertex_count` is
not one of those: its rows do qualify, and they read maxE = 0.000.

A companion scan — parity of the step positions in long monotone unit-step
runs — gives 208 of 208 `Alpha_func` rows and 0 of 6,528 rows in 25 other
suites, but it needs a 32-step monotone run and so never sees
`Context_switch` at all: the checkerboard under that polygon puts a 7-unit
jump every 20 px and breaks every run. Quote the row census above, not that
one.

### And there is no global displacement

If the interpolator sampled in the wrong place, some non-zero (dx, dy) would
beat (0,0) on capture after capture. Over every capture we hold on both sides:

| best shift | non-exact captures |
|---|---:|
| **(0, 0)** | **1,482** |
| (+1, 0) | 38 |
| (−1, 0) | 37 |
| (−1, +1) | 35 |
| (0, +1) | 30 |
| (−1, −1) | 28 |
| everything else | 24 |

The non-zero winners scatter in every direction, which is what a *different*
defect (edges, lines, texture decode) looks like, not a systematic phase.
`Alpha_func` is the only suite where one non-zero shift takes nearly all of it:
**14 of 16 captures at (dx = −1, dy = 0)**, and the residual it leaves is the
half-pixel the pair structure adds on top.

**So our interpolator's phase is already correct, on both axes, everywhere in
the corpus except `Alpha_func`.**

## 4. `Lighting_normals` is not this mechanism

#38 names `Lighting_normals` as mechanism 2's carrier — 12 captures, 114,164
channels, `ours = hardware + 1`, "endpoints provably exact while its ramp is
not, so the defect is strictly in interpolation".

The endpoints part is right and the interpolation part is not. Over all 28
captures the best shift is **(0,0) on every one of the 16 that are not already
exact**, and the shift surface is flat and symmetric about the origin in both
axes — `Nz_100` goes 8,130 → 15,970 at dy = ±1 and 10,428 at dx = ±1, with no
asymmetry to indicate a direction. The maximum per-channel difference is 1, and
the pair test reads E = O. There is no displacement in `Lighting_normals` of
any size, in either axis. Its ±1 is a value-level residual in the lit colour,
and it belongs with whatever produces the other 201 one-step-sym captures — not
with a sample position.

That matters because `Lighting_normals` is 114,164 channels and `Alpha_func` is
706,696: if mechanism 2 is "the interpolator samples in the wrong place", its
entire measured extent in this corpus is 15 captures. The other 70
one-step-lo and 201 one-step-sym captures the issue counts under this
mechanism are a value-level residual with no displacement in them, and looking
for a sample position in them will not find one.

## 5. Where a fix would have to live, and why I did not make one

**It cannot live in this stream's territory.** `glsl/vsh.c` and `glsl/vsh-ff.c`
run once per vertex and have no access to a fragment's position;
`glsl/geom.c` runs once per primitive and has neither. Reproducing "constant
across `{2m, 2m+1}`, evaluated at `2·floor(x/2)+2`" needs the fragment's own
`gl_FragCoord.x` parity and a screen-space derivative, and both exist only in
the fragment shader.

The change is one expression, and it belongs in
**`hw/xbox/nv2a/pgraph/glsl/psh.c`**, which is #52's:

```glsl
// NV2A holds the interpolated vertex colour constant across the even-aligned
// pixel pair and evaluates it at the pair's right-hand edge, s = 2*floor(x/2)+2.
// Relative to the pixel centre x + 0.5 that is +1.5 px on even x, +0.5 on odd;
// both give the same value, which is what makes the pair constant.
float nv2aPairOffsetX() {
  return 1.5 - mod(floor(gl_FragCoord.x), 2.0);
}
// applied to an interpolated colour before the combiners, the alpha test and
// the blend consume it:
vec4 d0 = vtxD0 + dFdx(vtxD0) * nv2aPairOffsetX();
```

`dFdx` is taken over the 2×1 half of the derivative quad, which is the same
pair, so the two pixels of a pair land on the same value by construction, and
`floor(gl_FragCoord.x)` is the integer pixel x because the fractional part is
the 0.5 of the pixel centre.

**Three things must be said to whoever takes it, and the first is the one that
stops this being shippable today.**

1. **What selects the paired draws is not established, and an unconditional
   version of this is wrong.** Two draws in the corpus pair and 1,145 captures
   do not. Applied unconditionally it would displace every gradient in the
   corpus by a pixel — including the 1,482 non-exact captures whose best shift
   is already (0,0) — to fix two. Section 7 lists the candidate conditions and
   what each of them survives; none is established, and `High_vertex_count` is
   a clean negative against the most attractive of them.
2. **It must not be applied as a uniform 1-px shift either.** A uniform shift
   is the mean of a structure that is not a shift: it reproduces neither the
   pair nor the green band's coverage, and it gets `AlphaFuncLessThan_Enabled`
   wrong (a uniform +1 px puts the low crossing at 147 by luck but the pair is
   what makes both bounds land).
3. **The blast radius is the whole corpus, and settling it is an A/B, not a
   reading.** Every Gouraud gradient is downstream of this expression. The
   must-not-move list in section 6 is the flat- and gradient-region evidence
   that pins the current, correct phase.

I have registered no prediction and queued no device work, because there is
nothing in my territory to A/B: neither `vsh.c`, `vsh-ff.c`, `vsh-prog.c` nor
`geom.c` can express a per-fragment sample rule, and a change to any of them
would be inert on this by construction. The measurement is offline against the
goldens and stands without a device.

## 6. Must not move

The whole corpus is downstream of a colour interpolator, so anything claiming
to fix this must show these unchanged. They are the captures that pin the
*current, correct* phase, and a global shift breaks every one of them:

- `Point_size/*` — 21 captures, especially `PointSmoothOff_16_FF`
- `Surface_clip/*`, `Null_surface/*`, `SetVertexData/*`, `Stencil_func/*`
- `Antialiasing_tests/*` — `AAOnThenOffCPUWrite` and
  `FramebufferNotModifiedBySurfaceState` are bit-exact as of `dca3c94b98`
- `Lighting_normals/*` — 12 of 28 bit-exact, 16 at best shift (0,0)
- `3D_primitive/*`, `Shade_model/*`, `Attrib_float/*`, `Attrib_carryover/T-*`,
  `High_vertex_count/*`, `Material_alpha/*`, `Lighting_accumulation/*`,
  `Specular/*`, `Fog/*` — measurably unpaired and phase-exact, 61 to 479
  measurable rows each and zero paired rows
- `python3 docs/testing/vertex_colour_quantiser.py` must keep reporting
  `surviving rules = ['mantissa13_half_up']`. Checked at `0f708c8d33`: it does.
- `python3 docs/testing/alpha_func_ramp.py` must keep exiting 0. Checked at
  `0f708c8d33`: it does. (Note that it still defaults to the pre-fix arm; #57
  recorded that re-pointing its assertions is owed, and this note does not do
  it — `interpolator_phase.py` supersedes its green-band framing rather than
  replacing the tool.)

## 7. Least certain, and the capture that exposes it

**What selects the paired draws is not established, and this is the thing to
attack next.** Two positives is very thin, and I have already had two readings
of them die (section 3): alpha-specific, killed by `Context_switch`'s RGB, and
purely-x-gradient, killed by the same capture's 2-D gradient. What the two
positives share, and what each candidate survives:

| candidate condition | `Alpha_func` | `Context_switch` | survives? |
|---|---|---|---|
| screen space, `w = 1`, no perspective divide | yes | yes | **no** — `High_vertex_count` is `w = 1` passthrough and unpaired |
| immediate-mode vertices (`SET_VERTEX*`) rather than arrays | yes | yes | **no on its own** — `Shade_model` is immediate mode and unpaired |
| immediate mode **and** `w = 1` together | yes | yes | not contradicted: `High_vertex_count` is arrays, `Shade_model` is perspective |
| a single large primitive (≥ 500 px wide) | yes | yes | not contradicted, but `3D_primitive`'s ~200 px and `Shade_model`'s ~300 px are not a real test of it |

The third row is the one that fits every data point I have, and I do not
believe it. It is a two-positive fit to a conjunction, "the vertex submission
path changes the fragment interpolator's spatial granularity" is not a
sensible statement about silicon, and a conjunction fitted to two points is
exactly the shape of an artefact. Recorded as a lead, not a finding.

What would settle it is new test geometry, not more fitting: the same
screen-space quad with a shallow colour ramp, drawn four ways — immediate and
arrays, `w = 1` and `w ≠ 1` — which is four captures and decides the table
outright. Only goldens are available here, so this is recorded rather than
measured.

One near-probe that is not one: `Attrib_setter/Setters-alpha` looks like a
second blended-alpha instrument and has only **3** measurable rows, far too
few to call either way. Do not read its E = 0.000 as a negative.

The capture that would expose a wrong choice first is
**`Alpha_func/AlphaFuncLessThan_Enabled`**. Its green coverage is the narrow
left segment alone — hardware x 64..147, ours x 64..148 — so it holds the low
crossing with no second boundary to average against and no clamping, and it is
the capture where the pair signature is cleanest in the corpus (E = 1.000,
O = 0.003 over 30,908 gradient px). If the rule is right that segment ends at
**147**; the pixel centre ends it at 148, and the pixel corner, the pair left
edge and the pair centre all end it at 149.

Be careful with it, though, and this is the honest limit of that capture: three
candidates — pair right, pair right-half and plain `x + 1.5` — all predict 147,
so the green band **cannot separate them on its own**. What separates them is
the red and blue bands, where `x + 1.5` is wrong on 127 of 512 px and the pair
right-half on 126–128. The green band confirms; it does not decide.

**Second**, the group is established in x only. Whether silicon's group is 2×1
or 2×2 is not settled by the two positives: `Alpha_func`'s bands are constant
in y and carry no y information at all, and `Context_switch`'s polygon does
vary in y — its rows are not y-paired, which points at 2×1, but that capture
differs from ours by 172,824 px with a maximum channel difference of 150 for
reasons unrelated to this, so I would not hang the 2×1 conclusion on it. The
clean y statement is `Attrib_float`'s: no y pairing, phase +0.033 px. It is an
RGB ramp on an unpaired draw, so it bounds our own y phase and says nothing
about a paired draw's.

## Falsifier

`python3 docs/testing/interpolator_phase.py` must print, over the goldens
alone:

```
PAIR RIGHT      2*fl(x/2)+2      wrong    0 / 512   <== hardware
hardware step phase  -1.0042 px            (red band)
hardware step phase  -0.9958 px            (blue band)
prediction pair right    a8 == 127 on x 148..317
hardware   measured   a8 == 127 on x 148..317
LessThan_Enabled green: predicted x 64..147, hardware x 64..147
hardware  1185 steps  phase +0.0332 px  parity skew 0.506     (y)
hardware  starts 10 even / 0 odd,  ends 0 even / 22 odd
Alpha_func      AlphaFuncAlways_Disabled  rows=128 paired=128
Context_switch  GRZero                    rows=192 paired= 80
3D_primitive    Polygon-inlinearrays      rows=218 paired=  0
```

and exit 0, with all eleven witness captures classified as recorded — two
`Alpha_func` and `Context_switch/GRZero` paired, the other eight with zero
paired rows. If any capture directory is supplied it must also report our own
ramp as the exact pixel-centre ramp, 512/512 on both bands, and its best-shift
tally.

If hardware's bands stop matching `2·floor(x/2)+2`, or either green prediction
stops landing, or a suite other than `Alpha_func`, `Context_switch` and
`Image_blit` starts showing paired rows, the goldens changed and this document
is void. If *our* bands start matching `2·floor(x/2)+2`, section 5 has landed
in `psh.c`.
