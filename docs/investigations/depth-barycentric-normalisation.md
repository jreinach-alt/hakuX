# The z24 one-unit depth residual is the barycentric normalisation

**Issue #52, cell 2 of 4** (`z24` fixed-point depth). Measured 2026-09-12
against the `a1fe59400e` fix arm
(`1789257380-f24-fix-599733`), which is the most recent depth measurement on
the current disc, and against the test's own geometry evaluated in exact
rationals.

## The four cells, re-measured at the tip

Nine mantissas per cell on the current disc, `Cn` and `Cy` identical to the
pixel throughout, differing counts in pixels from the arm's own `scores1.tsv`
and the depth magnitudes from the zeta word decoded as ARGB8888
(`depth = A<<16 | R<<8 | G` for `z24`):

| cell | captures | exact | differing px | max \|Δdepth\| |
|---|---:|---:|---:|---:|
| `z16` fixed depth | 18 | **18** | **0** | 0 |
| `z16` float depth | 18 | 6 | 1,436 | — |
| `z24` fixed depth | 18 | 2 | **72,138** | **1** |
| `z24` float depth | 18 | 2 | 12,816 | 12,585 |
| colour, all four cells | 72 | 6 | 1,479,886 | 2 |

All eight cells are on the disc, and the five rows sum to the suite's 1,566,276.
The `z24` float cell is the ±12,584/12,585 quad-split family that
`a1fe59400e` deliberately left alone. Note that the `z16` `_ZB` captures do
**not** use the `z24` ARGB packing — the ARGB decode agrees with the golden on
all but 48 pixels of the `z16` float cell where the capture as a whole differs
on 1,436, so something outside the depth bytes differs there and the encoding
has to be established before that cell can be worked.

One correction to the issue as filed falls straight out of decoding the zeta
word rather than counting PNG channels:

* **The `z24` fixed residual is not "88 % upward".** Decoded, it is 8,478
  pixels above silicon against 27,591 below, per compression half — and the
  direction is not even uniform across the sweep: `+1` dominates on the four
  smallest masks and `−1` on the three largest. The "one unit *high*, hence a
  scale divisor" reading came from counting channels, where a `+1` that
  carries across a byte boundary reads as a `−255`.

## A third opinion: the test's own geometry

`DepthFormatTests::CreateGeometry` draws 995 quads with **integer** vertex
depths — the guest accumulates `z_left` in float32 and truncates to `uint32_t`
— on axis-aligned rectangles, front to back under LESS:

| primitive | pixels | span | denominator of z(pixel centre) |
|---|---:|---:|---:|
| 992 grid quads, 8×8, z linear in x | 63,488 | ≤ 254,200 | 16 |
| bottom quad, 360×5, z linear in x | 1,800 | 12,582,910 | 720 |
| right quad, 8×390, z linear in y | 3,120 | 8,388,606 | 780 |
| big quad, 384×400, z linear in y | 85,192 | 5,592,405 | 800 |

Every pixel's exact depth is a rational with one of four small denominators,
so `floor(exact)` is computable in integers, with no reference to the goldens.
`docs/testing/depth_exact_floor.py` does that and replays the depth test.

**It lands within one unit of silicon on every pixel of every mask**
(`max|oracle − golden| = 1`, nine masks), which is what makes it usable as a
reference rather than a guess. On `Mffffff_ZB`:

| region | px | golden vs floor(exact) | ours vs floor(exact) |
|---|---:|---|---|
| big quad | 85,192 | −3,060 / 79,160 / +2,972 | **−9,738 / 75,314 / +140** |
| right quad | 3,120 | −218 / 2,732 / +170 | **−16 / 2,494 / +610** |
| bottom quad | 1,800 | −203 / 1,450 / +147 | −106 / 1,554 / +140 |
| grid quads | 63,488 | 0 / 63,488 / 0 | −240 / 63,248 / 0 |

Silicon sits on the exact floor and one either side **symmetrically** — that
is its own edge walk, and it is the floor under any fix. We sit one side of
it, and **which** side differs per primitive: low on the big quad, high on
the right quad.

## The mechanism

`glsl/psh.c` interpolates the guest depth from barycentrics:

    float inv_bcsum = 1.0 / (bc0 + bc1 + bc2);
    bc1 *= inv_bcsum;
    bc2 *= inv_bcsum;
    ... zdh = bc1*zd1 + bc2*zd2, carried as an exact head+tail pair (#32)

For this geometry every input is exact in float32: the coordinate differences
are half-integers, `kahan_det` is compensated, and `bc0+bc1+bc2` is the
integer 153,600 for the big quad. The two-sum from `5dac36b2` then makes the
*summation* exact. What is left inexact is the normalisation — a reciprocal
and two multiplies, each worth up to 2^-24 relative.

A relative error is invisible on a small span and fatal on a large one:

| primitive | span | worst normalisation error | margin from an integer |
|---|---:|---:|---:|
| grid quads (z24) | 254,200 | 0.031 units | **0.0625** |
| big quad (z24) | 5,592,405 | 0.671 units | 0.00625 |
| right quad (z24) | 8,388,606 | 1.007 units | 0.00769 |
| bottom quad (z24) | 12,582,910 | 1.510 units | 0.01389 |
| every z16 primitive | ≤ 49,150 | ≤ 0.0059 units | ≥ 0.00625 |

The margins are geometry, not luck: the exact depth of a pixel centre is
`k/den` for `den ∈ {16, 720, 780, 800}`, so it never comes closer than
`1/800` of a unit to an integer. **That single table explains the whole cell
structure of #52 and #16.** `z16` fixed is 18/18 exact because its worst
error, 0.0059, is smaller than its smallest margin, 0.00625, on the same code
path — not because the 16-bit path is a different or better one. `z24` fixed
is one unit out because the identical code errs by up to 1.5 units against the
identical margins. The grid quads are 240/63,488 for the same reason the z16
cell is exact. It was never a scale divisor, and it is not the sampling
position either.

The reciprocal's share of the error is a **constant for the primitive**, which
is why our residual is one-sided and ramps with the barycentric rather than
scattering: on the big quad the deficit is nil for the first eighth of the
quad and reaches about 0.6 of a unit at the bottom. The correctly-rounded
value of `1/153600` is 2.4e-8 *high*; we measure low, so the device's divide
is itself off by of order an ULP — consistent with a reciprocal-plus-Newton
divide, and the reason the fix must not merely round the reciprocal better.

## Result: the cell is finished

**Landed**, two arms, both with progress-log proof, both predictions
registered before the device ran.

    base2 1789272971-depth52-base2-2789306 (5e612529b9)
    fix2  1789272013-depth52-fix2-2280916  (91b0897e01)

    better 18   worse 6   same 200   noise 0    (224 compared)
    exact  40 -> 40      regressed from exact 0
    Depth_buffer                 144  16  0  128  0   1,566,276 -> 1,537,828
    Depth_buffer_fixed_function   80   2  6   72  0     663,094 ->   663,350
    VERDICT: PASS -- all 72 registered checks hold.

The `z24` fixed depth cell went **72,138 differing pixels to 43,690**, and
43,690 is the oracle's own number: our zeta word is now **equal to the exact
floor on every pixel of all eighteen captures**, `oracle-ours = 0` throughout.
On `Mffffff_ZB` the big quad's `ours − floor(exact)` histogram is
`{0: 85192}` where it was `−9,738 / 75,314 / +140`; the bottom quad is
`{0: 1800}` and the right quad `{0: 3120}`. Every one of the nine predicted
per-capture values was hit to the pixel.

What is left is silicon's own edge walk around that floor — 3,060 low and
2,972 high on the big quad of `Mffffff_ZB` — which a fragment shader cannot
reproduce without an exact fixed-point edge stepper. **This cell is done.**

The other seven cells are byte-identical to the baseline, including all four
colour cells: nothing downstream moved. `Depth_buffer_fixed_function` costs
256 pixels of 663,094, four hundredths of a percent, on six captures whose
vertex depths are not integers and to which the oracle does not apply; that
was registered in advance at a 2,000-pixel tolerance.

## The change

Divide once, at the end, from the **unnormalised** areas, and recover what the
quotient dropped:

    znh/znt = bc1u*zd1 + bc2u*zd2          (exact head + tail)
    zdh     = znh / bcsum
    zdt     = (((znh - qp) - qe) + znt) / bcsum,  qp+qe == zdh*bcsum exactly

`bc1`/`bc2` keep their scaled values, untouched, because `zvalue` — the
F16/F24 path verified by `a1fe59400e` — reads them.

### The first form asked the compiler for something it does not give

The exact products were written with `fma()`, which is exact only if the fma
is fused. That arm (`1789269678-depth52-base` → `1789269684-depth52-fix`) is
worth keeping on the record, because it confirmed the mechanism and did not
finish the job:

| | base | fma form | Dekker form | silicon |
|---|---|---|---|---|
| big quad vs floor(exact) | −9,738 / 75,314 / +140 | −4,308 / 78,827 / +2,057 | **0 / 85,192 / 0** | −3,060 / 79,160 / +2,972 |
| fitted constant relative error | −0.80 ULP | −0.15 ULP | **0** | — |
| bottom quad vs floor(exact) | −106 / +140 | −53 / **+250** | **0 / 0** | −203 / +147 |
| cell total | 72,138 | 63,994 | **43,690** | — |

Four fifths of the constant relative error gone and the one-sidedness with it,
but not the floor — and the **bottom quad moved the wrong way**. That is the
tell. Its span is 12,582,910, so the quotient's own float32 ULP is a whole
depth unit and `zdh - floor(zdh)` is identically zero: every bit of its
fraction has to arrive through the residual term, the one that needs the fma.
The big quad's span puts its ULP at 0.5, so half of its fraction survives
elsewhere, which is why it improved while the bottom quad did not.

Re-modelling the identical chain with `fma()` lowered to multiply-then-add
reproduces both, the bottom quad's one-sided **+95 of 360** included, where a
fused fma predicts zero everywhere. **This driver does not fuse it.**

So the exact products are Dekker's, from multiply and add only — `4097 =
2^12+1` halves a float32 mantissa — which asks the compiler for nothing.
Modelled over all four primitive shapes, 1,550 sampled pixels, 24
combinations:

| | fma form | Dekker form |
|---|---:|---:|
| fma fused, divide correct / 1 ULP low / 2 ULP high | 0 / 0 / 0 | **0 / 0 / 0** |
| fma **unfused**, same three (z24, four shapes) | 98 / 158 / — | **0 / 0 / 0** |
| z16 geometry, all six | 0 | **0** |

It costs about two dozen extra ALU ops per fragment in every depth-writing
shader. If a perf arm ever says that matters, the `fma()` form is the cheaper
two thirds of the win and the table above says exactly what it gives up.

## What it is predicted to be worth

The oracle gives the answer exactly, per capture, because it *is* the value the
fixed shader must write:

| capture (both `Cn` and `Cy`) | now | predicted |
|---|---:|---:|
| `..._M00000f_ZB` | 0 | 0 |
| `..._M055564_ZB` | 14 | 5 |
| `..._M0aaab9_ZB` | 37 | 21 |
| `..._M40000b_ZB` | 488 | 227 |
| `..._M800007_ZB` | 1,187 | 654 |
| `..._Mc00003_ZB` | 1,330 | 1,221 |
| `..._Mf55555_ZB` | 8,574 | 6,177 |
| `..._Mfaaaaa_ZB` | 11,409 | 6,770 |
| `..._Mffffff_ZB` | 13,030 | 6,770 |
| **cell total** | **72,138** | **43,690** |

What remains at 43,690 is silicon's own ±1 edge walk around the exact floor,
which nothing in the fragment shader can reproduce
(`depth-interpolation-residual.md` reaches the same conclusion from the other
side). That is the end of this cell.

## The falsifier, and what the first arm cost by getting its threshold wrong

**`ours == oracle`, pixel for pixel, on all eighteen `z24 * FZn *_ZB`
captures.** Equivalently, on `Mffffff_ZB` the big quad's `ours − floor(exact)`
histogram collapses from `−9,738 / 75,314 / +140` to `0 / 85,192 / 0`, and the
one-sided ramp with the barycentric goes flat.

A differing-pixel total cannot say this, for the reason the F24 arm found out:
a pixel here is wrong for our reason *and* silicon's at once, and the total
counts it once. 43,690 of the 72,138 are silicon's alone and will not move.
`docs/testing/predictions/depth-barycentric-normalisation{,-2}.json`.

The first arm is the other half of that lesson, and it points the opposite
way. Its registered escape clause was *"falsified only if the residual is
still one-sided: |below − above| > 500 of 85,192"*. Measured: 2,251 — down
from 9,598 but four times over the line, so **the falsifier fired**. It was
right to fire. The threshold had been set on the assumption that removing the
reciprocal error would leave *nothing*, which is the same additivity mistake
that cost the F24 prediction: there was a second error underneath, and no
amount of arguing from the 77 % improvement would have found it. Chasing the
remaining 2,251 to its cause — an unfused `fma`, visible in the bottom quad
moving the wrong way — is what produced a form that is exact. A falsifier
that fires is not a defeat; it is the only thing that makes "we are close"
distinguishable from "we are done".

## Must not move

* `DepthFmt_z16_*_FZn_*_ZB`, 18 captures, all bit-identical today. Proved
  above rather than hoped: the worst error of either form is below the
  smallest margin, so no floor can cross, and the simulation agrees on all
  1,550 sampled pixels under three divide behaviours.
* `DepthFmt_*_FZy_*_ZB`, all 36 float-Z captures. `zvalue` is untouched and
  `bc1`/`bc2` are left spelled exactly as they were so a compiler free to
  reassociate `bc0 + bc1 + bc2` cannot change them.
* `Cn` must stay identical to `Cy` on every pair.

## The other three cells, for whoever takes them

* **`z16` fixed depth is done** and is now *explained* as well as measured:
  the margin table above says no floor in that cell can cross under either
  form of the arithmetic. Leave it alone.
* **The colour cell is not a depth defect and should be filed elsewhere.**
  On the big quad the error is 71,000 pixels of 85,192 with a signature that
  is byte-identical between `z16` and `z24`: R low by one on 46,792 and by two
  on 3,399, G high by one on 44,567 and by two on 3,519, B high by one on
  17,808. That is the Gouraud interpolation of the big quad's four vertex
  colours — green/blue/olive/red — quantising differently from silicon's, and
  it cannot be downstream of the depth buffer, because the depth buffer under
  it is bit-exact in the `z16` cell and one unit out in the `z24` cell and the
  colour histograms are the same to the pixel. The vertex-side quantiser is
  already measured and correct (`vertex-colour-quantiser.md`, #38); this is the
  interpolator, one level down.
* **The `z24` float cell is the ±12,584/12,585 quad-split family** that
  `a1fe59400e` priced and deliberately left. 12,816 px.

## Least certain

`Depth_buffer_fixed_function`, and it is now measured rather than feared: six
captures worse by 256 pixels of 663,094 against two better. It draws through
`UnprojectPoint`, so its vertex depths are not integers and the oracle above
does not apply to it; its own error maxes at 9 units rather than 1, and the
previous change to this floor (`5dac36b2`) cost it 204 pixels for the same
reason — a more accurate floor landing on the wrong side of something else
slightly more often. `z24_Cn_FZn_Mc00000_ZB`, which took 115 of the 256, is
the capture that exposes it and the one to read first;
`z24_Cn_FZn_Mffffff_ZB` at 144,566 differing pixels of 307,200 is the larger
defect in that suite and is untouched by any of this.

The second uncertainty is reach. `depth_needed` is set by any draw with the
depth test or depth writes enabled, so this arithmetic is on the path of
essentially all 3D content, and it was measured on two suites. Nothing in it
can make a small-span primitive worse — the margin table is the argument, and
`z16` is the control — but a wider sweep is the honest confirmation.
