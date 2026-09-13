# `Alpha_func`, measured: the alpha test is right, its input is not (#57)

Written 2026-09-12 against the goldens and the `z-sweep-002-Alpha_func`
captures (APK `fb4dfafc6d38`, `progress_log_proof` true, 16/16 goldens
scored). No build, no device.

Reproduce the whole of section 1 with
`python3 docs/testing/alpha_func_ramp.py`, which is also the falsifier.

## 0. The number, and what it is made of

The issue opens on 435,032 differing pixels from the `pre-fixes-fb4dfafc`
scoreboard column and asks for a re-measure, because that column sits 31
`hw/` commits behind the tip. The re-measure is below. **The split matters
more than the total**, and it was never taken:

| | pixels | share |
|---|---:|---:|
| differing | 435,032 | 100% |
| **every channel one step out** | **425,816** | **97.9%** |
| **more than one step out** | **9,216** | **2.1%** |

`classify_residuals.py` says the same thing in the house vocabulary: 1 exact,
**9 `one-step-sym`**, 6 `structural`, 706,696 differing channels of which 51%
lie on a one-pixel boundary. `one-step-sym` is explicitly *not* a rounding
rule — neither sign dominates — so 97.9% of this suite is #38's mechanism 2,
interpolator precision, and is a floor rather than a defect.

That leaves 9,216 px to explain, and they are not spread about:

| band | what it ramps | structural px | share of structural |
|---|---|---:|---:|
| green | alpha 0.495f → 0.505f | **8,064** | **87.5%** |
| red | alpha 0.0 → 1.0 | 1,008 | 10.9% |
| blue | alpha 1.0 → 0.0 | 128 | 1.4% |
| white | alpha ≡ 0x7F | **0** | 0% |
| band edges | — | 16 | 0.2% |

## 1. The one exact capture, and what it proves

`AlphaFuncNever_Enabled` is bit-exact, 0 differing pixels. It is the only
capture in the suite that **draws nothing at all**: every fragment is
discarded, so the framebuffer keeps the clear colour and the `pb_print`
overlay, and both are exact.

Its partner is as informative. `AlphaFuncAlways_Enabled` is byte-identical to
`AlphaFuncAlways_Disabled` — the same 35,826 px, all one step. So both
degenerate ends of the comparison are right: NEVER rejects everything, ALWAYS
rejects nothing, and neither disturbs a pixel the disabled path would not.

Together they say the alpha test's *plumbing* is correct — the enable bit, the
function decode, `alphaRef` reaching the shader, the discard itself — and put
the entire residual in **the alpha value being compared**. The white rectangle
agrees from the other direction: it is drawn at diffuse alpha exactly `0x7F`,
the reference itself, and has **zero** structural error in all sixteen
captures. Equality against the reference decides correctly on 20,480 px per
capture. Only *interpolated* alpha is wrong.

`glsl/psh.c` emits

```
int fragAlpha = int(round(fragColor.a * 255.0));
if (!(fragAlpha <op> alphaRef)) discard;
```

which is the right shape and is not the problem.

## 2. The measurement: read the alpha back out of the blend

The three ramp bands are drawn with `SRC_ALPHA`/`ONE_MINUS_SRC_ALPHA` over a
known clear colour, from a known source colour. That makes the blend
invertible: for each band exactly one integer source alpha in 0..255
reproduces a given output RGBA, so **the fragment alpha the pipeline actually
used can be recovered per pixel**, from a golden as easily as from a capture.
On the red and blue bands all 512 px of a row recover uniquely with zero
residual.

| band | submitted | ×255 | **hardware ramp** | **ours** |
|---|---|---|---|---|
| red | 0.0 → 1.0 | 0.000 → 255.000 | 0.797 → 255.201 | 0.075 → 254.925 |
| blue | 1.0 → 0.0 | 255.000 → 0.000 | 254.207 → −0.196 | 254.925 → 0.075 |

Read the red and blue rows together. Hardware's ramp is pulled *inward* at the
left vertex in **both** bands — red starts 0.8 high, blue starts 0.8 low — and
overshoots at the right in both. A value bias would push both the same way in
value; this pushes both the same way in *x*. It is a phase offset of ≈1 px
between hardware's colour interpolator and ours, on identical geometry (both
cover exactly x 64..575 in every capture). That is #38 mechanism 2, it is the
whole of the 425,816 one-step pixels and 1,136 of the structural ones, and
nothing in the vertex stage can reach it — #38 says so and this measurement
does not contradict it.

### The green band is a different animal

The green band ramps `0.495f → 0.505f`: in byte units **126.225 → 128.775**, a
span of 2.55. Quantising those endpoints to bytes first gives **126 → 129**, a
span of 3 — an 18% slope change. Every other gradient in the corpus has
endpoints within 0.25 of a byte across a span of tens of units, where the two
rules differ by under half a percent. **This band is the only probe in the
corpus that can tell them apart**, which is why #38 could not decide it.

A fit will not read it: over the band the recovered alpha takes only the
values 126..129, and the alpha channel's blend is stationary there
(d/da of a² + (1−a) is zero at a = 0.5), so hardware and ours fit to the same
ill-conditioned numbers. The alpha test is the precise instrument.
`AlphaFuncEqual_Enabled` draws exactly the pixels whose a8 == 127, so its
**coverage mask** gives both crossings, 126.5 and 127.5, and the one unit
between them bounds the slope with no model of the blend at all:

| | a8 == 127 on | ⇒ slope |
|---|---|---|
| **hardware** | x **148..317** | **(2.9942, 3.0296)** |
| **ours** | x **120..321** | **(2.5222, 2.5473)** |
| float endpoints, as `colorPrecision()` leaves them | — | 2.5369 ✓ ours |
| byte-quantised endpoints | — | 3.0000 ✓ hardware |

The hardware bracket contains 3.0000 and excludes 2.5369 by twenty times its
own width. Solving the intercept the same way pins hardware's left endpoint to
**126.005 ≤ A ≤ 126.011**, which rules out the 9-bit (126.5) and 10-bit
(126.75) carriers as well: the endpoints are the bytes 126 and 129, exactly.

**The rule: silicon quantises the vertex colour to its byte *before* the
interpolator. We interpolate the float and quantise at the fragment.**

Note what our own bracket dates. 2.5369 is the slope after `vsh.c`
`colorPrecision()` drops ten mantissa bits; the naive float slope is 2.5500,
and our bracket excludes it. The capture carries #38's committed rule, so it
postdates `5c2b26db2f` — behaviourally, not by metadata.

## 3. This refines #38, it does not contradict it

#38 closed today on nineteen component values read off **flat** golden
regions, and concluded "truncate the float's low mantissa bits, then round
255·x to nearest". On a flat region the candidate here gives the identical
byte — `round(255·x)/255` through a UNORM8 attachment is `round(255·x)` — so
**all nineteen probes still pass**, and `vertex_colour_quantiser.py` still
holds. The two rules are distinguishable only along a gradient, and flat
regions were all #38 had.

The naive form of the candidate would break #38, and the combined form does
not. `round(255 · 0.1f)` is 26 and hardware says 25; the truncation has to
come first and then the byte:

```
vec4 colorPrecision(vec4 c) {
  vec4 t = uintBitsToFloat(floatBitsToUint(c) & 0xFFFFFC00u);   // as now
  return floor(t * 255.0 + 0.5) / 255.0;                        // new
}
```

`floor(x + 0.5)` rather than `round()` because the 0.5f tie must go **up**
(#38 measured 128) while `acc(7)`'s 178.5 must go **down** — and it does,
because the truncation has already pushed it below 178.5. GLSL `round()` is
free to break that tie either way.

## 4. What this is worth, and why it is not committed here

Modelled offline against the goldens, over the 64 rows and 512 columns of the
green band, with the model first validated against our own capture (it
reproduces it to within one step on 3 of 512 px per row):

| green band, all 16 captures | differing px | structural px |
|---|---:|---:|
| measured now | 51,456 | 8,192 |
| modelled, byte-quantised endpoints | **2,176** | **768** |

Red and blue do not move: their endpoints are 0.0 and 1.0, already exactly 0
and 255 under either rule. So the change is **inert on 97% of this suite** and
the suite would not become exact — the ≈1 px interpolator phase is untouched
and is the floor.

**It is not committed because the patch site is `hw/xbox/nv2a/pgraph/glsl/vsh.c`,
which is not this stream's territory.** The defect is shown to live there: the
alpha test in `psh.c` is correct, `vk/draw.c` and `gl/draw.c` carry no alpha
state that could produce a slope, and `ALPHAREF` is correctly kept out of the
pipeline cache key because it is a shader uniform. Nothing in the assigned
territory can move this number. The prediction is registered as
`docs/testing/predictions/alpha-func-vertex-byte-quantisation.json` so the arm
can be queued the moment the territory is granted.

The blast radius is the reason to ask rather than commit: `colorPrecision()`
runs on all four colour outputs of every vertex shader, so every Gouraud
gradient in the corpus moves — Lighting's 195 goldens, `3D_primitive`,
`Attrib_carryover`, `Attrib_float`, `Shade_model`. That is a measurement to
buy with an A/B, not a change to land on one suite's evidence at the end of a
day.

## 5. Least certain, and the capture that exposes it

**One probe.** The byte-quantisation rule rests on a single band in a single
suite. I searched the corpus for a second gradient that could discriminate and
found none: `3D_primitive`'s 0.25f→0.65f ramp and its 0.75f→1.0f grey both
have endpoints within 0.25 of a byte over spans of 64 and 102 units, where the
two rules differ by under 0.4%. The bracket is tight and the arithmetic is
clean, but it is one measurement, and "measured once" is not "measured".

The capture that would expose a wrong choice first is
**`Alpha_func/AlphaFuncLessThan_Enabled`**. Its green coverage is the narrow
left segment — golden x 64..147, ours x 64..119 — so it holds the low crossing
alone, with no second boundary to average against and no clamping. If the rule
is right that segment becomes 84 px wide; if the endpoint is 126.5 or 126.75
rather than 126 it lands visibly short, and the modelled residual there is the
smallest in the suite (148 px), so nothing else can hide a miss.

**Second, the red band's 1,008 structural pixels.** They are a 2-px coverage
shift at the 127 crossing, and a pure 1-px attribute phase offset predicts a
1-px shift, not 2. So the interpolator characterisation in section 2 is
approximate — it is the right shape and the right sign, and it is not a
complete model. It is #38 mechanism 2's to finish, not this issue's.

## Falsifier

`python3 docs/testing/alpha_func_ramp.py` must print

```
HARDWARE  a8 == 127 on x 148..317  =>  slope in (2.9942, 3.0296)
OURS      a8 == 127 on x 120..321  =>  slope in (2.5222, 2.5473)
```

and exit 0. If the hardware bracket stops containing 3.0000, or starts
containing the float slope, the goldens changed and this document is void. If
*our* bracket starts containing 3.0000, the vertex stage was changed to
quantise to bytes and section 4 has landed.
