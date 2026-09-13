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
about the shape, and wrong about the scope, and both matter more than the
number does.

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

## 3. Scope: it is one suite, not the interpolator

This is the part that changes what should be done about it.

**Corpus-wide parity scan.** Every golden, every 16th row and column, longest
monotone unit-step run per line: **6,736 long x-ramps across 26 suites**. The
even-parity signature appears in **208 of 208 `Alpha_func` rows and 0 of the
other 6,528.** On the y axis, 10,278 ramps and none.

**Corpus-wide pair test**, which does not need unit steps and so is not limited
to shallow ramps: E = P(v[x] == v[x+1]) for even x against O for odd x, over
gradient pixels. `Alpha_func` reads **E = 1.000, O = 0.009**. Under the
signature E > 0.85 with O < 0.30, **14 captures of 1,915 fire, and all 14 are
`Alpha_func`.** Zero fire on the y axis.

**Corpus-wide best-shift census.** If the interpolator sampled in the wrong
place, some non-zero (dx, dy) would beat (0,0) on capture after capture. Over
every capture we hold on both sides:

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
entire measured extent in this corpus is one suite.

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
// NV2A holds the fragment's diffuse alpha constant across the even-aligned
// pixel pair and evaluates it at the pair's right-hand edge, s = 2*floor(x/2)+2.
// Relative to the pixel centre x + 0.5 that is +1.5 px on even x, +0.5 on odd;
// both give the same value, which is what makes the pair constant.
float nv2aPairOffsetX() {
  return 1.5 - mod(floor(gl_FragCoord.x), 2.0);
}
// applied to the interpolated diffuse alpha before the combiners and the
// alpha test consume it:
float a = vtxD0.a + dFdx(vtxD0.a) * nv2aPairOffsetX();
```

`dFdx` is evaluated over the 2×1 half of the derivative quad, which is the same
pair, so the two pixels of a pair land on the same value by construction.

**Three things must be said to whoever takes it.**

1. **It must not be applied to RGB.** Every RGB gradient in the corpus is
   already per-pixel and phase-exact — 3D_primitive, Shade_model,
   Attrib_carryover, Lighting_*, Material_*, Fog, Texgen. Applying this to
   colour would displace all of them by a pixel to fix one suite.
2. **It must not be applied as a uniform 1-px shift.** A uniform shift is the
   mean of a structure that is not a shift; it reproduces neither the pair nor
   the green band's coverage, and it would move the 1,482 captures whose best
   shift is already (0,0).
3. **The blast radius is narrow but not empty, and is an A/B question.** Any
   capture whose visible output depends on an *interpolated* diffuse alpha
   moves. In this corpus that is `Alpha_func` (16 captures, 435,032 px) and
   `Attrib_setter` (2), and nothing else obviously — but "nothing else
   obviously" is a reading of the tests, not a measurement, and the measurement
   is an arm.

I have registered no prediction and queued no device work, because there is
nothing in my territory to A/B. The measurement is offline against the goldens
and stands without a device.

## 6. Must not move

The whole corpus is downstream of a colour interpolator, so anything claiming
to fix this must show these unchanged. They are the captures that pin the
*current, correct* phase, and a global shift breaks every one of them:

- `Point_size/*` — 21 captures, especially `PointSmoothOff_16_FF`
- `Surface_clip/*`, `Null_surface/*`, `SetVertexData/*`, `Stencil_func/*`
- `Antialiasing_tests/*` — `AAOnThenOffCPUWrite` and
  `FramebufferNotModifiedBySurfaceState` are bit-exact as of `dca3c94b98`
- `Lighting_normals/*` — 12 of 28 bit-exact, 16 at best shift (0,0)
- `3D_primitive/*`, `Shade_model/*`, `Attrib_float/*`, `Attrib_carryover/T-*`
  — every long x-ramp in them is unpaired and phase-exact
- `python3 docs/testing/vertex_colour_quantiser.py` must keep reporting
  `surviving rules = ['mantissa13_half_up']`. Checked at `0f708c8d33`: it does.

## 7. Least certain, and the capture that exposes it

**What makes `Alpha_func` different is not established.** The rule is measured
on the only probe in the corpus that can see it, and three properties of that
probe cannot be separated, because `Alpha_func` is the only capture that has
any of them:

  (a) the only varying interpolant is diffuse **alpha**;
  (b) the gradient is purely along x — `dv/dy` is exactly zero;
  (c) the quad is axis-aligned screen space, `w = 1`, exactly 512 px wide.

(b) is the one I could partly test. A corpus-wide hunt for ramps that run in x
across a region exactly constant in y found **91 such regions: 28 in
`Alpha_func`, all paired, and 63 in six other suites, none paired** — `Texgen`,
`Texgen_with_texture_matrix`, `Texture_Matrix`, `Texture_palette`,
`Texture_signed_component_tests`, `W_buffering`. But every one of those 63 is a
texture- or depth-driven ramp, not a diffuse-colour one, so they rule out "any
x-only ramp" without reaching "any x-only *diffuse* ramp".

`Attrib_setter/Setters-alpha` looks like a second blended-alpha probe and is
not one: its triangle ramps RGB and alpha together, so the output differs
across a pair whatever the alpha does, and its E = O = 0.000 is uninformative
rather than contradictory. **No second probe exists.**

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

**Second**, the 2-pixel group is established in x only. Whether silicon's group
is 2×1 or 2×2 cannot be read here: `Alpha_func`'s bands are constant in y, so
they carry no y information, and `Attrib_float`'s y ramp — which shows no y
pairing at all — is an RGB ramp, which by (a) may not be governed by the same
rule. A test that ramped diffuse alpha vertically would settle it in one
capture. None exists.

## Falsifier

`python3 docs/testing/interpolator_phase.py` must print, over the goldens
alone:

```
PAIR RIGHT      2*fl(x/2)+2      wrong    0 / 512   <== hardware
hardware step phase  -1.0042 px            (red band)
hardware step phase  -0.9958 px            (blue band)
prediction pair right    a8 == 127 on x 148..317
hardware   measured   a8 == 127 on x 148..317
hardware  1185 steps  phase +0.0332 px  parity skew 0.506     (y)
hardware  starts 10 even / 0 odd,  ends 0 even / 22 odd
Alpha_func  AlphaFuncAlways_Disabled  E=1.000 O=0.009  PAIRED
```

and exit 0, with all twelve witness captures classified as recorded. If any
capture directory is supplied it must also report our own ramp as the exact
pixel-centre ramp, 512/512 on both bands.

If hardware's bands stop matching `2·floor(x/2)+2`, or the green prediction
stops landing on 148..317, or any suite other than `Alpha_func` starts showing
the pair, the goldens changed and this document is void. If *our* bands start
matching `2·floor(x/2)+2`, section 5 has landed in `psh.c`.
