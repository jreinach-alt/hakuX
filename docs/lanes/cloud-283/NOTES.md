# cloud-283 -- the +-1 low-byte residual on Volume texture Y16 / R16B16 (#283)

Base: origin/master @ e2f617ed99. Desktop-only analysis; no hw/ file edited.
Inputs (all on disk, dated): arm result dirs
`1790367468-arms-texvol283-{base-1190693,fix-1190715}` (Nova, fix apk
acad684607ae @ a5b4141064, the fold of PR #289); goldens
`/home/justin/goldens/results/Volume_texture` (abaire 6e159f1532, 08-11);
console set K `hardware/runs/2026-09-19-calib/full/out/run1`.

## Answer

**None of the three readings. The residual is not a 16-bit defect.** It is a
texel-selection (position) difference that every Volume texture capture
carries, the plain UNORM8 formats included, where no byte split runs. No
hunk in psh.c's split and no byte-typed R8G8B8A8 / R8G8 view would move it.
Neither changes which texel is fetched. #283's 16-bit part is finished at
PR #289. What is left belongs to a suite-wide Volume texture class, which
has no issue yet (see "For the board").

- Reading (1), the `round(t*65535)` recovery, is **refuted**.
- Reading (3), an Adreno UNORM16 fetch floor, is **refuted**.
- Reading (2) holds only in its "filter tie" form: nearest-texel selection
  in 3D point sampling. It is not a low-byte rounding rule, and it is not
  specific to Y16 / R16B16.

## Evidence

### 0. The golden is stable silicon

Console set K vs the golden: **0 px** on every Volume_texture capture
checked (Y16, R16B16, the four 8888 orders, X8R8G8B8, A8Y8, G8B8, R8B8, Y8,
AY8, A8). The two fix-arm replicates are pixel-identical.

### 1. The recovery arithmetic is exact

fp32 `round(float(v)/65535 * 65535)` returns v for **65,536 of 65,536**
UNORM16 values. So given the fetched value, the split's low byte equals the
fetched low byte on every pixel, the mispredicted ones included. That is
the brief's falsifier for (1), and it fires.

A reduced-precision (fp16) fetch would have to be the carrier instead. It
would get the low byte right on only 7,169 of 65,536 values, with errors up
to 255, and would miss the high byte on 2,712. We see the high byte (G)
exact on every pixel and only +-1 on the low byte. That is not an fp16
signature.

### 2. The same residual is in formats with no split

Fix arm vs golden, Volume_texture (RGB channels; the scorer's figure
includes alpha):

| capture | differing px (scorer) | off-by-one (scorer) | RGB px | per-channel deltas |
|---|---|---|---|---|
| Y16 | 2,605 | 2,604 | 2,605 | B only: +1 x2,070, -1 x534, +255 x1 |
| R16B16 | 1,638 | 1,493 | 1,110 | B: +1 x737, -1 x228, -2 x136, +2 x5; A -1 x1,396 |
| A8R8G8B8 (and A8B8G8R8, B8G8R8A8, R8G8B8A8, identical) | 2,734 | 2,594 | 1,961 | R/G/B +-1, a few +-2 and +-32 |
| X8R8G8B8 | 2,529 | 2,529 | 2,529 | R +1 x1,388 / -1 x372; B -1 x692 / +1 x77 |
| A8Y8, G8B8, R8B8 | 710 | 709 | 710 | +1 x564, -1 x145, +226 x1 |

The 8888 / X8 / A8Y8 formats are fetched as UNORM8 and are not touched by
`tex_bytes16`. They carry the same one-signed-majority +-1 at the same
magnitudes, and the base arm scored them identically (A8R8G8B8 2,734 / 2,594
in both arms). So the residual is older than PR #289's split and does not
depend on it.

**The same pixels.** 2,069 of Y16's 2,605 differing pixels lie inside
A8R8G8B8's differing-pixel mask. By chance you would expect 94 (the mask
covers 2,734 of 76,063 quad pixels). The Y16 and 8888 quads read different
bytes of the same buffer through the same geometry, so a shared location
means shared texel selection.

### 3. The Y16 error is not a function of the texel value

This test needs no geometry model. Only Y16's quads are opaque (R=255,
A=255), so each pixel's (G, B) is the fetched texel's (hi, lo) with no
blend. An error that lives in the value (readings 1 and 3) maps each 16-bit
v to one f(v) everywhere. Of the 1,021 distinct silicon values at differing
pixels, **209 are also rendered exactly at another pixel**. For those values
we show more than one answer. They cover **1,382 of the 2,605** differing
pixels. So those 1,382 are refuted as value errors outright.

The other 1,223 pixels carry values that never occur at an exact pixel, and
this test cannot decide them. They co-locate with the 8888 residual just as
strongly: 1,016 of 1,223 against 44 by chance. The decided set gives 1,053
of 1,382 against 50.

The single +255 at (343,122), and A8Y8's +226, are neighbour-texel jumps
across the `(x+y) & 255` wrap in the test's A byte. A rounding error cannot
produce either.

## Tests that do not discriminate here (recorded so they are not re-run)

- **"Is our (hi, lo) pair present in the uploaded texture?"** It is present
  for all 2,605 pixels, but so is every silicon-hi / lo+-1 pair (5,210 of
  5,210). The texture holds 64,771 of 65,536 values. This test cannot fail.
- **"Nearest texel carrying our pair is 1 texel from silicon's."** True for
  all 2,605, and true by construction for any lo+-1 in this texture.
- **"Our pixel equals a golden 4-neighbour pixel."** This matched 3 of 2,605
  on Y16. That is not a refutation of selection: each quad is about 135 px
  across 256 texels, so the adjacent texel is not the adjacent pixel's
  value. It does match 71% on Y8 / AY8 and 62% on A8, whose layouts
  differ.

## What was not chased

- **Why 3D selection differs when 2D does not.** Every TexFmt 2D capture
  of these formats is 0 px. This class has not been separated into u/v
  selection vs the slice (r) coordinate, and there is no candidate rule yet.
  texvol283's geometry model fits our own capture only 83%, so it cannot
  score a candidate rule pixel-exact. Any rule would have to hold across all
  20 Volume texture captures and move nothing on the 2D suites.
- **R16B16 in detail.** Its quads are alpha-blended over 0x20, so (G, B) is
  not the raw texel and the value test above does not apply. The co-location
  (889 of its 1,110 RGB px lie inside the 8888 mask) and the same +-1/+-2
  shape are the evidence here. Its four outliers up to 242 are on quad
  edges, like the 8888 formats' +-32.
- **A8, Y8, AY8.** Their residuals (up to 223) include larger, per-format
  differences on top of the shared one. Not looked at.

## For the board

- Record #283's residual as **not a 16-bit defect, not a precision floor**:
  it is the Volume texture suite-wide texel-selection class, shared with
  A8R8G8B8 / X8R8G8B8 / A8Y8 etc. No psh.c or vk/texture.c hunk for
  pshqueue follows from #283. Recommend close of #283 as fixed by PR #289,
  with its 2,605 / 1,638 px carried by a new Volume texture texel-selection
  issue. Its ceiling is roughly the sum of the ±1 masks: 2,734 (x4 8888
  orders) + 2,529 + 710 (x3) + Y16 2,605 + R16B16 1,638, all one-step.
- That issue is offline work first. Separate u/v selection from the slice
  coordinate on the opaque formats. X8R8G8B8 is the likeliest start: only R and B
  move, and X8 should carry no alpha to blend with. Check that on the
  capture first.
