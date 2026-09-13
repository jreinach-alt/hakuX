# #57 is #38 mechanism 2, and what still blocks the fix

Written 2026-09-13 against the goldens and the `z-tip-003-Alpha_func` /
`z-tip-018-Context_switch` sweep arms (APK `88452c539d64`, ref `0026f00534`).
No build, no device, no queued arm. Branch tip `225e100025`.

Reproduce with:

```bash
python3 docs/testing/alpha_func_pair_boundary.py    # the identity, section 1
python3 docs/testing/interpolator_phase.py          # the pair rule itself
```

**Capture provenance, because a capture older than the fix reads exactly like a
live defect.** `0026f00534` is a descendant of `dca3c94b98` (#38 mechanism 1,
`colorPrecision`) and an ancestor of the tip, and **neither `glsl/psh.c` nor
`glsl/vsh.c` changed between that ref and the tip** — so this arm still
describes the shader the tip generates. Checked with
`git log 0026f00534..HEAD -- glsl/psh.c glsl/vsh.c`, which is empty.

## 0. The recovered tooling

`docs/testing/interpolator_phase.py` and
`docs/investigations/interpolator-sample-position.md` were not ancestors of the
integration branch — they existed only on `worktree-agent-a461720f7c39f5548`
(`bf90a00c44`, `fe1fdae25f`, `e41b66aad1`), so the census #38 tells the reader
to reproduce from could not be re-run at the tip. Cherry-picked in as the first
act of this lane; all three commits applied clean and the census reproduces at
the tip, exit 0, every recorded number unchanged.

The corpus census reproduces exactly: **5,608 captures scanned, 1,162 with
measurable x rows, 16 with at least one paired row** — fourteen `Alpha_func`,
`Context_switch/GRZero`, and `Image_blit/BlitBeyondWidth`.

## 1. The identity: one mechanism, established on the mask

#57 filed the residual as "the enabled comparison boundary is misplaced", on the
signature that **complementary alpha functions carry identical structural
counts** — three pairs of them. At the tip those pairs are 448/448, 192/192 and
256/256, total **1,792** structural px (down from 9,216 when filed, the
reduction being #38 mechanism 1's ramp fix; the named defect was untouched).

The question is whether that is a second defect or #38 mechanism 2 seen through
a different instrument. A pixel count cannot answer it — residual classes
overlap, and **two masks of equal cardinality can be disjoint**. So the test is
the mask, and `intersection == union`:

| capture | structural | predicted | inter | union |
|---|---:|---:|---:|---:|
| `AlphaFuncNever_Enabled` | 0 | 0 | 0 | 0 |
| `AlphaFuncLessThan_Enabled` | 192 | 192 | 192 | 192 |
| `AlphaFuncEqual_Enabled` | 448 | 448 | 448 | 448 |
| `AlphaFuncLessThanOrEqual_Enabled` | 256 | 256 | 256 | 256 |
| `AlphaFuncGreaterThan_Enabled` | 256 | 256 | 256 | 256 |
| `AlphaFuncNotEqual_Enabled` | 448 | 448 | 448 | 448 |
| `AlphaFuncGreaterThanOrEqual_Enabled` | 192 | 192 | 192 | 192 |
| `AlphaFuncAlways_Enabled` | 0 | 0 | 0 | 0 |
| **total** | **1,792** | **1,792** | **1,792** | **1,792** |

**Every structural pixel in the suite, and no other pixel, is where the pair
rule says hardware's coverage and ours disagree.**

### What is fitted, what is not, and what is merely assumed

- **Fitted elsewhere.** `s = 2·floor(x/2) + 2` was fixed on the red and blue
  bands, whose alpha ramps 0→255 and 255→0. Those are blended
  `SRC_ALPHA`/`ONE_MINUS_SRC_ALPHA` over a known clear colour, so the blend
  inverts uniquely and the integer fragment alpha is a **direct read**, not a
  fit: 512 of 512 on both bands, hardware at the pair right edge and ours at the
  pixel centre. Section 1 of the tool re-derives this rather than citing it.
- **Not fitted.** The green band is `0.495f → 0.505f`, **three** byte units over
  the same 512 px, and it is where `Equal` and `NotEqual` — the two 448s, half
  the total — put their boundaries. Nothing about green enters the fit. Nor does
  the alpha test: the rule is a claim about the fragment's alpha, and coverage is
  a second instrument reading the same quantity with the blend removed.
- **Assumed, and named as assumed.** That the byte-quantised endpoints
  interpolate *linearly* between 126 and 129. The endpoints themselves are
  measured (#38 mechanism 1, confirmed by #57's slope going 2.5369 → 3.0118
  against hardware's 3.0000). This is the only assumption in the prediction, and
  it is the one to attack if the identity ever stops holding.

### The rivals, and why the check had to be a mask

| hardware sample position | predicted | inter | union | verdict |
|---|---:|---:|---:|---|
| pixel centre `x+0.5` (= ours, i.e. no defect) | 0 | 0 | 1,792 | explains nothing |
| pixel corner `x` | 768 | **0** | 2,560 | **disjoint** |
| pair left `2·floor(x/2)` | 1,280 | **0** | 3,072 | **disjoint** |
| pair centre `2·floor(x/2)+1` | 256 | **0** | 2,048 | **disjoint** |
| pair right-half `2·floor(x/2)+1.5` | 256 | 256 | 1,792 | mask differs |
| centre + 1, `x+1.5` | 1,536 | 1,024 | 2,304 | mask differs |
| **pair right `2·floor(x/2)+2`** | **1,792** | **1,792** | **1,792** | **identical** |

Three rivals produce a non-empty mask **disjoint** from the measured one. A
cardinality comparison would have ranked `pair centre`'s 256 as a partial
explanation of a defect it does not touch in a single pixel — this project's
`Bump_map` lesson reproducing itself inside the rival table of the script that
was written to respect it.

And the rival family #57's own filing proposed — that our *comparison* is wrong
rather than our sample position — fails badly: a reference of 126 predicts
67,584 px and a reference of 128 predicts 89,600, against 1,792 measured.

### Consequence

**Our alpha comparison is correct.** `psh.c` emits
`int fragAlpha = int(round(fragColor.a * 255.0)); if (!(fragAlpha <op> alphaRef)) discard;`
and every operator in it is right. What is wrong is the alpha arriving at it,
because the interpolated diffuse feeding the combiner is sampled at the pixel
centre where silicon samples at the pair's right edge.

So **#57 has no defect of its own.** It should be closed into #38 mechanism 2,
and a mechanism 2 fix closes it by construction — which also means #57 must not
be counted as a second win when that fix lands.

## 2. Two corrections to the recovered scope claim

Both matter because they weaken the evidence for the *selection* rule, which is
the thing still blocking a fix.

### `Context_switch/GRZero` is a partial positive, not an equal one

The recovered note reads `GRZero` as a full second confirmation — "the same
even-aligned 2-pixel group, on a different attribute, a different primitive
type, a different gradient orientation". Measured as **exact pair-constancy**
rather than as step parity, the polygon's two fan triangles are not alike:

| fan triangle | rows | pairs | broken | pair-exact | rows with any break |
|---|---:|---:|---:|---:|---:|
| `v0-v1-v2` (x < the v0–v2 diagonal) | 177 | 24,308 | 1,246 | **94.9%** | 28 of 177 |
| `v0-v2-v3` (x > the diagonal) | 176 | 23,995 | 16,000 | **33.3%** | **176 of 176** |

The earlier reading (90.1% / 75.1% even-x on step positions, "both triangles
have it") is true and understates the gap: on the second triangle two pairs in
three are broken and **not one row is clean**.

The row structure is also not what the census's `80 of 192 paired` suggests. The
paired rows are `y = 48..61`, then a short run, then **exactly `y ≡ 1 (mod 3)`
from y=79 to y=238** — and on those rows E = 1.000 on all three channels while
the others sit at E ≈ 0.90–0.95 with O ≈ 0.25–0.79. So it is not an on/off
within-draw selection (which would have been a clean refutation of any per-draw
rule); it is a period-3 partial breakdown, with every break at x ≥ 432, i.e. in
the second triangle. **I do not have an explanation for the period 3 and am not
offering one** — see section 5.

### The census cannot tell an interpolated colour from a texture

The row metric qualifies any position whose neighbours are within 4 per channel.
A **textured background** supplies those in bulk, and at least one recorded
negative is entirely that:

`Smoothing_control` reads 365 measurable rows and 0 paired, maxE = 0.010, which
looks like a hard negative. Its measurable rows are a **tiled background
texture** — the row repeats with period 320 px, 24,296 distinct colours in the
frame, and rows y=203 and y=443 are byte-identical. Masking the background out
by its own 320-px periodicity leaves **9,980 shape pixels and not one row with
20 gradient positions per parity**. Its smoothed-shape content is far too small to
measure.

So `Smoothing_control` is **unmeasured, not unpaired** — the same trap the
recovered note caught on `GRZero`'s lower half, one level further in. It is
neither a positive nor a negative and must not be cited as either.

This does **not** dissolve the negatives that matter. `High_vertex_count` reads
maxE = 0.000 over 1,728 rows on 6×6 screen-space Gouraud quads that are its own
draw (`R : 227 229 232 234 38 35` — every pixel differs, which a pair-constant
field cannot do at any steepness), and `Shade_model`'s untextured `Fixed_*`
variants are genuine Gouraud content. Those stand. But "1,145 captures with
measurable rows and zero paired rows" is not 1,145 independent negatives about
*interpolated vertex colour*, and should not be quoted as if it were.

## 3. The selection rule: what died, and why the corpus cannot finish it

The rule is established. **What selects the draws it applies to is not**, and
an unconditional version is wrong: it would displace every Gouraud gradient in
the corpus to fix two draws.

Candidates and their fate. The first two were already dead; the rest is this
lane's:

| candidate | fate |
|---|---|
| screen space, `w = 1`, no perspective divide | **dead** — `High_vertex_count` is `w = 1` passthrough and genuinely unpaired |
| immediate-mode vertices rather than arrays | **dead alone** — `Shade_model` is immediate mode and unpaired |
| immediate mode **and** `w = 1` | **unfalsifiable on this corpus** — see below |
| `SET_VERTEX4F` rather than `SET_VERTEX3F` | **unfalsifiable on this corpus**, and not separable from the row above |
| one large primitive (≥ 500 px wide) | not contradicted, still not really tested |
| per-triangle / triangle setup | **dead** — both of `GRZero`'s fan triangles carry it (94.9% / 33.3%), neither is clean-off |
| a within-draw row selection | **dead** — `GRZero`'s 80/192 is a period-3 partial breakdown, not an on/off |

### The class is exhaustively enumerable, and it has two members

Membership needs all three, per draw: **(A)** screen space with no perspective
divide (a `PassthroughVertexShader`), **(B)** immediate-mode vertices, **(C)** a
per-vertex diffuse *gradient* — at least two distinct `SetDiffuse` inside one
`Begin`/`End`. Enumerated over all 100 test sources:

| source | in class? | why |
|---|---|---|
| `alpha_func_tests.cpp` | **yes** | 4 gradient vertices, all `SET_VERTEX4F` w = 1.0 |
| `context_switch_tests.cpp` | **yes** | 14 gradient vertices, all `SET_VERTEX4F` w = 1.0 |
| `texture_perspective_tests.cpp` | no | gradient block runs under `SetVertexShaderProgram(nullptr)` with w = 0.3 |
| `texture_perspective_enable_tests.cpp` | no | no gradient vertex at w = 1.0 |
| `w_param_tests.cpp` | no | gradient block is fixed-function with a w = 0.0 vertex |
| `swath_width_tests.cpp` | no | gradient blocks are `SET_VERTEX3F` |
| `vertex_shader_rounding_tests.cpp` | no | gradient blocks are `SET_VERTEX3F` |
| the other 93 | no | no per-vertex diffuse gradient in an immediate-mode block |

**The corpus contains exactly two members of the class and both pair.** That is
the blocker, and it is a different statement from "two positives is thin": there
is **no capture in the corpus that could come back unpaired** and refute the
conjunction. More fitting cannot help, because the complement of the class is
empty.

`SET_VERTEX4F`-vs-`3F` is the one new candidate this lane can offer and it is no
better off: both positives use the 4-arg form, every `SET_VERTEX3F` gradient
suite (`Smoothing_control`, `Stipple_tests`, `Swath_width`,
`Vertex_shader_rounding`) is either textured-background-only or too small to
measure, so it too has an empty complement. It is also not separable from
"immediate mode" — no corpus capture varies one while holding the other.

### The blocker as a measurement that would refute it

Per "a blocker is a claim, and it needs the same evidence as a fix":

> **If the class had a third member, `interpolator_phase.py`'s per-row census
> would report paired rows for it.** It reports paired rows for exactly 16
> captures out of 5,608, and 14 of them are `Alpha_func`. If a reader finds a
> suite that satisfies A ∧ B ∧ C and the census calls it unpaired **on its own
> draw's pixels rather than on a background**, the conjunction is refuted and
> this section is void.

That is cheap to run and it is the check to run before trusting this.

### The four captures that decide it

Unchanged from the recovered note, and this lane's work is a reason to trust it
more rather than less: **the same screen-space quad with a shallow colour ramp,
drawn four ways — immediate vs arrays × `w = 1` vs `w ≠ 1`.** Concretely, and
sized so the census can actually measure it (which `Smoothing_control` could
not):

- a quad **x 64 → 576** (512 px, so ≥ 100 qualifying positions per row per
  parity) and **≥ 64 rows tall**, untextured, on a **flat** background;
- per-vertex diffuse ramping **0 → 255 in one channel across x** (≈ 0.5 byte/px,
  which is the slope `Alpha_func` pairs at and is well inside the metric's
  ≤ 4 byte/px window);
- four cases: `SET_VERTEX4F` w = 1.0; vertex arrays w = 1.0;
  `SET_VERTEX4F` w = 2.0 with the ramp pre-divided so the screen-space result
  is identical; vertex arrays w = 2.0 likewise.
- a fifth, nearly free, that separates this lane's new candidate: the same quad
  via **`SET_VERTEX3F`**.

That is `tests/**` — the remote lane's territory — and it needs no accuracy
oracle beyond the goldens it would produce, so it is a disc build and one run,
not an A/B.

## 4. Why no shader change landed

The fix is one expression and its location is not in doubt. In
`hw/xbox/nv2a/pgraph/glsl/psh.c`, where `pD0`/`pD1`/`pB0`/`pB1` are bound:

```glsl
// NV2A holds the interpolated vertex colour constant across the even-aligned
// pixel pair and evaluates it at the pair's right-hand edge, 2*floor(x/2)+2.
// Relative to the pixel centre x+0.5 that is +1.5 px on even x and +0.5 on odd;
// both give one value, which is what makes the pair constant.
float nv2aPairOffsetX() { return 1.5 - mod(floor(gl_FragCoord.x), 2.0); }
vec4 pD0 = vtxD0 + dFdx(vtxD0) * nv2aPairOffsetX();
```

It is not landed, for one reason: **applied unconditionally it is known-wrong,
and the condition is not established.** `High_vertex_count`'s 1,728 rows at
E = 0.000 and `Shade_model`'s untextured Gouraud are measured negatives about
interpolated vertex colour, and 1,482 of 1,674 non-exact captures already have
best shift (0, 0).

Two narrower things were considered and rejected, and both rejections are worth
recording because each looked attractive:

1. **Apply the pair sample to the alpha test's input only**, leaving the written
   colour alone. It would fix all 1,792 px of #57 and move nothing else in the
   corpus, because `Alpha_func` is the only suite that pairs *and* uses the
   alpha test. It is a **curve fit**: the mechanism is that the interpolated
   colour is pair-constant, and that colour reaches the blend as well as the
   test — `GRZero` shows the pair on written RGB with no alpha test in sight.
   Splitting the two so that only the cleanest instrument is satisfied is one
   rationalisation per data point, and the falsifier it would pass is one this
   change forces true. It would also have made #57 read as closed while #38
   mechanism 2 stayed open, which is the opposite of what section 1 establishes.
2. **Condition on immediate-mode submission.** Not refutable on this corpus
   (section 3), "the vertex submission path changes the fragment interpolator's
   spatial granularity" is not a sensible statement about silicon, and the
   plumbing needs a new `PshState` field fed from `pgraph.c` or the Vulkan draw
   path — both other lanes' files at wave 9. Even granted those files, the
   condition would be a two-point fit with an empty complement.

## 5. Least certain

**The period-3 breakdown on `GRZero`'s second fan triangle.** Exact
pair-constancy holds on `y ≡ 1 (mod 3)` and fails on two rows in three, and a
field that is genuinely constant across `{2m, 2m+1}` cannot do that — within a
pair the pre-rounding value is identical, so the rounded byte must be too. So
either the rule is an approximation to something finer (a sub-LSB per-pixel term
— an ordered dither, or a fixed-point x accumulator whose low bit survives),
or the second triangle's attribute plane is not what a fan split from v0
implies, or `GRZero` is contaminated by whatever else makes it differ from our
render by 172,824 px with a max channel error of 150.

I did not resolve it, and I flag it because it bears on the rule this lane is
certifying: **`Alpha_func` is the only clean instrument for the pair rule in the
corpus**, and it is constant in y. A y-dependent term would be invisible in it
by construction. If the four captures of section 3 get built, giving them **two
different y-gradients** costs nothing and would settle this at the same time.

The identity in section 1 does not depend on any of that: it is measured on
`Alpha_func` alone, where the rule is exact on 512 of 512 px on both fitted
bands and predicts the unfitted band's coverage to the column.
