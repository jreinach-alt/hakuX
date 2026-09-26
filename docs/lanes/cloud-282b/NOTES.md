# cloud-282b: an attribute-plane setup model for the texel-tie direction (#282)

Follow-up to `docs/lanes/cloud-282/` (PR #314). Desktop only: no device, no
build, no `hw/` edit.

## Outcome

**The plane-setup model is falsified by its pre-registered test.** No plane
arrangement predicts the discriminating region it was not fitted on. That covers
every snap of the four vertices, every reference vertex, exact, float32 or
p-bit arithmetic, and fused or unfused evaluation. The best ones reproduce #314's
95.25% and get the up band 0.4% right. What the goldens do show, exactly, is that the
tie direction is keyed on the **binades of the barycentric weights**: a
two-line rule on those binades predicts **99.88%** of the v <= 128 tie pixels
(#314's fit: 95.2%; today: 44.8%). No arithmetic I tried reproduces that rule
from first principles, so it is a fit, not a model. **Recommendation: no code
lane.** #286's question (which half-column the AA resolve's u tie selects) is
answered from the u-tie data: 2x+1, the right one, which is what we already select.

## Data, dated

| set | where | date |
|---|---|---|
| goldens (silicon) | `/home/justin/goldens/results`, abaire `6e159f1` | 2026-08-11 |
| console (silicon, V1.1) | `hardware/runs/2026-09-19-calib/full/out/run1` | 2026-09-19 |
| test list (which captures carry a checkerboard) | `1790361615-arms-shadetie224b-base`, `1790347539-xbox-region200-dryrun`, `z-sweep-079-Texture_border_color` | 09-25, 09-25, 09-13 |

The model is scored against silicon only; our captures just name the tests.
`extract.py` reads 145 tests and **1,189,655 tie pixels**, #314's total to the
pixel.

**The console run is not a second sample.** On all 145 tests the console PNG
is byte-identical to the golden (0 differing px). #286 found a console capture
that differs from its golden, so this is real silicon agreeing with itself,
not a copied set. Silicon's tie direction is deterministic across the golden unit and
our V1.1 console. As a held-out set, though, it adds nothing.

**Held-out design.** The brief asked for a fit on the checkerboard and a score
on the lighting and bump suites. Every tie pixel on disk *is* a checkerboard
pixel of the lighting, material, combiner and border suites. They all draw the same four
vertices through `SetXDKDefaultViewportAndFixedFunctionMatrices`, so
splitting by suite would score the same pixels twice. The bump suites draw
through a passthrough VS and are not a tie class (#314 sec. (b)). The
held-out set here is spatial instead, as pre-registered in `e3ff4fcf06`: fit
on rows 15-105, T2 and rows >= 255; hold out the up band (T1, x 320-479, rows
135-240) and the cut between rows 240 and 255, 25,513 px.

## Reproduce

```
R=/home/justin/hakux-work/dispatch/results
D="$R/1790361615-arms-shadetie224b-base-3530164 $R/1790347539-xbox-region200-dryrun-3236568 $R/z-sweep-079-Texture_border_color"
python3 docs/lanes/cloud-282b/extract.py gold.npz $D
python3 docs/lanes/cloud-282b/extract.py console.npz --flat \
    --gold /home/justin/hakux-work/hardware/runs/2026-09-19-calib/full/out/run1 $D
python3 docs/lanes/cloud-282b/plane_model.py gold.npz --scan      # 256 snaps x refs x arithmetic
python3 docs/lanes/cloud-282b/model_p.py gold.npz --scan          # p-bit mantissa, ~25 min
python3 docs/lanes/cloud-282b/align_model.py gold.npz --scan      # guard-bit-free adders
python3 docs/lanes/cloud-282b/binades.py gold.npz                 # the binade table
python3 docs/lanes/cloud-282b/binades.py gold.npz --rule          # the rule's score
python3 docs/lanes/cloud-282b/plane_model.py gold.npz --map golden
```

## Geometry, from source

- Camera at z = -7, unproject onto world z = 1: **w = 8 exactly** at all four
  vertices (the lookAt basis and the projection's w column are exact in
  float). 1/w is a constant plane, and scaling by 1/8 is exact, so
  perspective correction can contribute no error here.
- With the vertices on the 1/16 grid (every snap offset 0), both triangles
  have **dv/dx = 0 exactly**: T1's v0 and v1 share v = 0 and y, and T2's
  v2 and v3 share v = 1 and y. So **no plane, in any precision, can make a v
  tie depend on x.** The golden map's band does depend on x (U at 320-479,
  D on either side, same row), so a plane evaluator is excluded before any
  scan. The scans below only confirm it.
- The XDK viewport offset, 0.53125 = 8.5/16, puts every corner exactly on a
  midpoint of the 1/16 grid. A truncating snap is immune to the unproject's
  float error. A round-to-nearest snap would move each coordinate by 0 or
  1/16 according to the error's sign. The scan tries all 256 combinations.

## Models tried (all in this directory)

| family | what varies | best v <= 128 | held-out right (band, or band + cut for `model_p`) | verdict |
|---|---|---:|---:|---|
| plane, `plane_model.py --scan` | 256 snap combinations x ref vertex per triangle x exact / f32 / fused | 95.25% | 0.4% | reproduces #314's diag rule (T1 referenced at v2, T2 at v0), band wrong |
| plane, `model_p.py --scan` | mantissa p = 8..24, round-nearest or truncate, reciprocal or divide, term order | 89.15% (best on the fit region) | 64.2% | no |
| barycentric, normalised (sum t_i l_i / sum l_i) | same, 6 summation orders per triangle | 44.8% (all-up: the weights on a tie row are dyadic, the sums round to 1) | - | no |
| barycentric from a reference vertex (t_r + dt_b l_b + dt_c l_c) | same, f32 and p-bit | 69.3% | 47% | no |
| barycentric, guard-bit-free adders, `align_model.py --scan` | p = 10..24, reciprocal truncated / rounded / divide, 36 orders | 95.25% | 0.2% | no: the diag rule again (T1 referenced at v2) |

`plane_model.py --show 00000000:exact:00:0` reproduces today's 44.78%, and
`model_p.py` at p = 24 reproduces `plane_model.py`'s float32 numbers config
for config, so the p-bit evaluator is checked against the float32 one.

## What the goldens do show: the weights' binades (`binades.py`)

In T1 = (v0 v1 v2) the texcoord is v = l2 exactly (v0 and v1 carry v = 0), with
l0 = (640 - x)/640 and l2 = y/480. In T2 = (v0 v2 v3), v = 1 - l0. Tabulate
the golden direction of every FF v-tie pixel by floor(log2) of each weight:

| cell | golden down / tie px |
|---|---:|
| T1, l2 < 1/4 (rows <= 105), every binade of l0 and l1 (60 cells) | **99,484 / 99,484** |
| T1, l2 in [1/4, 1/2), l0 not in [1/4, 1/2) | **52,453 / 52,565** (99.8%) |
| T1, l2 and l0 both in [1/4, 1/2): x 320-479, **the band** | **738 / 13,491** (5.5%; mostly row 120, where l2 = 1/4 exactly) |
| T1, l2 in [1/2, 1) (rows >= 255) | 4,304 / 74,250 (5.8%) |
| T2, every cell (156) | 322 / 254,145 (0.13%) |

l1's binade never separates anything.

At the exact powers of two, the weights behave as if computed a hair below
them. Row 240 (l2 = 1/2) follows the band's binade, row 120 (l2 = 1/4)
follows the lower one, and x = 320 (l0 = 1/2) is in the band. So the intervals
are (1/4, 1/2]. As a rule:

    T1 v tie goes down  iff  l2 <= 1/2  and not (l0 in (1/4,1/2] and l2 in (1/4,1/2])
    everything else (T2, every u tie, every VS draw) goes up

| | v <= 128 tie px | u ties | v >= 136 | band |
|---|---:|---:|---:|---:|
| today (always up) | 44.78% | 99.80% | 99.96% | 99.62% |
| #314 diag+FF | 95.2% | 99.8% | 99.99% | ~0% |
| **binade rule** (`binades.py --rule`) | **99.88%** | 99.80% | 99.96% | 99.62% |

This rule is read off the whole map, band included, so it is **a fit and not
held out**. What it establishes is structural: the v coordinate on silicon is
computed from quantities that vary with x even where dv/dx = 0. The
direction then follows the exponents of the normalised barycentric weights,
which are powers of two in l, not in the edge functions. The edge
functions' binade boundaries (2^16/307200 = 0.213, 2^17/307200 = 0.427)
fall nowhere near the observed 1/4 and 1/2. That is a barycentric
evaluator with float weights, not a plane equation and not a DDA. The DDA
in the `psh.c` comment ("u along the scanline, v between scanlines") also
steps v by dv/dx = 0 along a row, so it cannot make the band either.

## Against the pre-registered falsifier

"Plane setup explains the tie direction" is falsified. No plane
configuration predicts the held-out band, and the configurations at 95.25%
are the #314 fit re-expressed. The barycentric-binade structure passes the
map at 99.88%, but only as a fit, so it does not meet the pre-registered bar
of predicting the held-out region from the fit region either. What would
settle it is a second geometry with exact ties whose weights cross a
different set of binades (below).

## The hunk, and whether it is implementable

- **Named hunk:** `hw/xbox/nv2a/pgraph/glsl/psh.c:2018-2019` (`texelTieBias`;
  the v half), applied at `psh.c:1103-1107, 1454, 3000`. Holder:
  **lane.wbufdepth24** (#266) per `origin/board:territory.toml` wave 217.
- `vsh.c:562` (`roundScreenCoords`, holder **lane.nanfix281**) and `vsh-ff.c`
  (holder **lane.wparamcode223**) are **not** the place: the snap is already
  right (no snap offset scores above all-zero), and the effect is not in vertex positions.
- **Not implementable without the triangle's barycentrics in the fragment
  shader.** The rule needs l0 and l2 per fragment, and which vertex carries
  which weight. `gl_PrimitiveID` parity would only reproduce this helper's
  split (#314, "Do not repeat"). The general form needs
  `VK_KHR_fragment_shader_barycentric` (or `geom.c` passing per-vertex
  texcoords flat) *and* the arithmetic that produces the rule. We do not have
  that arithmetic.

**Recommendation: no code lane.** The recoverable pixels (156,844 tie px over these
captures, the binade rule's gain over today) are synthetic-checkerboard ties. A game hits this only with a
point-sampled texture at an exact texel-to-pixel ratio *and* a v tie in a
triangle whose weights sit in these binades. A rule that is right on one
helper's two triangles, with no mechanism, would move every other quad's
ties blind.

## For #286 (lane.aasample): which half-column the resolve tie selects

The resolve (`three_d_primitive_tests.cpp:1044-1059`) is a
**PassthroughVertexShader** quad on the same four corners (0,0)-(640,480),
sampling a 1280-wide LU_IMAGE with u = 0..1280. At pixel x it samples
u = 2x+1, an exact u tie.

- u ties on this corner geometry: **599,841 px, 99.80% up**. Every one of
  the 1,172 down pixels is FF, and #314's census found our captures match
  all of them.
- **On vertex-program draws: 92,506 of 92,506 u-tie px up, 0 down.**
- Silicon is deterministic here (console == golden on all 145 tests).

So silicon's resolve selects **texel 2x+1, the right (odd) half-column**. We
select the same one (GL nearest on an exact tie, plus the `texelTieBias` u
half), so the half-column choice needs no change. Because silicon's AA path
is transparent (#286 sec. 3, 0 px over 48 captures), **the odd column 2x+1
is the one that must hold the pixel-centre sample**: AA column 2x+1 centred at
guest x + 0.5. Column 2x holds the corner sample, which this resolve never
displays. Today ours are centred at x + 0.25 and x + 0.75, so the fix is a
horizontal shift of -1/4 guest px (-1/2 AA px) in the AA viewport. Caveat:
this carries over the u-tie direction measured on the checkerboard, whose
texture is 256 wide and normalised; the resolve's is 1280 wide and
unnormalised. The aasample falsifier (`O_X == O_P` on the 48 no-op captures)
tests it directly.

## Do not repeat

- **Do not fit a plane evaluator to this map.** dv/dx = 0 on both triangles,
  so no plane or DDA, at any precision, can produce the x 320-479 band.
- **Do not split the checkerboard suites into train and test.** It is one
  geometry. Held-out means another quad.
- **Do not use the console run as an independent silicon sample for these
  suites.** It is byte-identical to the goldens.
- Do not implement the binade rule in `psh.c`. It is a fit to two triangles.

## What would move this forward

A second geometry with exact v ties whose weights cross other binades. The
candidate on disk is `Texture_render_target` row 240 (v = 128), where silicon
breaks a v tie down on part of the row (`docs/investigations/edge-defect.md`
sec. "The v axis"). Its quad is `DefineBiTri(0, -1.75, 1.75, 1.75, -1.75,
0.1)` under the XDK matrices, so w = 7.1 (not a power of two) and the weights
differ. Tabulate its row-240 directions by weight binade with `binades.py`'s
method. If the same binade conditions predict where that row goes down, the
rule is a mechanism. If not, it is this helper's.
