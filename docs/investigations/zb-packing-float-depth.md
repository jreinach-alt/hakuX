# The `_ZB` packing, and why "float Z is structurally wrong" was the instrument

Established 2026-09-13 by PNG decode against the test's own geometry. No device,
no build: the goldens and `nxdk_pgraph_tests`' own source settle it.

## The answer

A `*_ZB` capture is the zeta surface's bytes as they sit in memory, handed to
SDL with a pixel format chosen **by the zeta surface's width, not by whether
the format is fixed or float**. `TestHost::SaveZBuffer`
(`nxdk_pgraph_tests` @ `33e7c6b`, `src/test_host.cpp:168`):

```c
uint32_t depth = depth_buffer_format_ == NV097_SET_SURFACE_FORMAT_ZETA_Z16 ? 16 : 32;
auto format = depth_buffer_format_ == NV097_SET_SURFACE_FORMAT_ZETA_Z16
                  ? SDL_PIXELFORMAT_RGB565 : SDL_PIXELFORMAT_ARGB8888;
```

So there are two packings, and the float flag selects neither:

| zeta format | container | depth | stencil |
|---|---|---|---|
| `Z16` — fixed **and float** | **RGB565** | `R5<<11 \| G6<<5 \| B5` | none (16bpp has no stencil) |
| `Z24S8` — fixed **and float** | ARGB8888 | `A<<16 \| R<<8 \| G` | `B` |

The float formats do **not** get a packing of their own. `FZy` changes only what
the stored integer *means* — an `e4m12` (`Z16`) or `e8m16` (`Z24S8`) float with
an implicit leading one — never where its bits live. The test and this emulator
already agree bit-for-bit on that meaning: `z16_to_float` in
`src/pbkit_ext.cpp:16` and `convert_f16_to_float` in `hw/xbox/nv2a/pgraph/util.h:30`
are the same expression, `(val << 11) + 0x3C000000`.

`docs/testing/score_sweep.py:85` already implements both branches. **It is
correct.** That was previously an assumption; it is now measured — see below.

## The evidence, and what would have refuted it

### 1. z16 is RGB565, not any 32-bit reinterpretation

*Falsifier.* Under RGB565 the three channels are 5-, 6- and 5-bit fields
expanded to bytes, so R and B can hold only 32 distinct byte values and G only
64, and alpha is manufactured. Under ARGB8888 — or any other 32-bit
reinterpretation — nothing constrains them. The world in which this leg fails
is one differing byte: any pixel whose R or B is outside the 32-value set, or
whose G is outside the 64-value set. Nothing in this analysis can force that
set to be small; it is a property of the golden.

*Measured*, over all 216 z16 `_ZB` goldens of `Depth_buffer` and
`Depth_buffer_fixed_function`:

```
channel samples checked against the 5/6/5 lattices: 199,065,600
lattice violations:                                          0
images with alpha identically 255:                     216/216
```

The lattices themselves, recovered from the goldens rather than assumed, are
`R,B: floor(255i/31)` and `G: 4i + i//24` — note that the second is **not**
the textbook `(i<<2)|(i>>4)`, and `G` never reaches 255. Both are nevertheless
inverted exactly by score_sweep's `>>3` and `>>2`, checked for all 32 and all
64 indices.

### 2. The decoded word is the test's own clear value

*Falsifier.* The suite clears the zeta buffer to the mask printed in its own
test name (`PrepareDraw(0xFF000000, depth_cutoff, 0x00)`), so the region no
primitive covers must decode to exactly that hex. A wrong container gives a
wrong number there. This is a region, not a point sample: 153,600 px per image
on `Depth_buffer`'s 640×480 minus the big quad.

*Measured*: `DepthFmt_z16_*` — 153,600 of 153,600 px equal the name's mask,
on 8 of 8 images spanning `FZn`/`FZy` and `Cn`/`Cy`, `M00000f` / `M008007` /
`M00ffff`. Corpus-wide, across all 432 z16 **and** z24 `_ZB` goldens in both
suites, the modal decoded word equals the name's mask on **432 of 432**.

That the same test works for z24 `FZy` is the whole answer for the z24 float
cell: `DepthFmt_z24_Cn_FZy_M00002f_ZB` is `A=0 R=0 G=47 B=0`, and
`A<<16|R<<8|G = 0x00002f`. Float z24 shares the fixed z24 container exactly.

### 3. The mapping is 1:1 — no stride skew

A uniform background cannot detect a wrong pitch. The geometry can.
`CreateGeometry` puts 992 8×8 quads on a 12-px lattice from (134, 48); build
that mask and, at `M00ffff`, **63,488 of 63,488** mask pixels hold something
other than the clear value. A misalignment of one pixel in either axis would
drop some mask pixels into the 4-px gaps, where they would read the mask. The
bottom and right quads land on their predicted rows and columns too.

## What this does to #52's z16 float cell, and to #16

The z16 float cell is **1,436 px of real disagreement** — not a scoring
artefact. The packing was already being applied correctly by `score_sweep.py`.
But its *character* is the opposite of what both issues record.

Measured on the 18 z16 `FZy` captures of arm `1789257380-f24-fix-599733`
(`a1fe59400e`), decoded as RGB565:

```
differing PIXELS                : 1,436
of which |delta word| == 1 ULP  : 1,436   (100.00%)
differing CHANNELS              : 1,484
channels with |delta| == 1      :     0
channel delta histogram         : {+8: 1084, +9: 304, +4: 48, -255: 48}
```

**Every differing pixel is one ULP out, and not one differing channel is.**
That is arithmetic, not coincidence: one unit in a 5/6/5 word moves `B` by a
5-bit lattice step — 8, or 9 where the lattice rounds — and on the 48 pixels
where `B` wraps 31→0 it carries one unit into `G`, giving `+4` and `-255`.
A channel delta of exactly 1 is *unreachable* in this packing.

So "float Z is structurally wrong — not one of F16's 469,927 channels is
one-step", which is the sentence carried by both `[issue.16]` and `[issue.52]`,
is a statement about the instrument. It is the same failure as the z24 "+1
reads as −255" already recorded in
[`depth-barycentric-normalisation.md`](depth-barycentric-normalisation.md),
one packing further in: there a byte boundary, here a 5-bit field boundary.
The 48 channels that carry are also exactly the 48 pixels that doc noticed the
ARGB decode could still see — an ARGB decode reads `A`, `R`, `G` and discards
`B`, so it is blind to the 1,388 pixels that move `B` alone.

### The float encoding is not the defect, and #16 closes clean

*Falsifier.* If this emulator's float-Z surface encoding were wrong — the
`// FIXME: Support float 16,24b float format surface` that #16 was filed on —
the 992-quad grid would show it. The grid writes 63,488 px whose stored F16
patterns cover **every exponent 0 through 15**, the entire `e4m12` range, at
`M00ffff`. The world in which this leg fails is any nonzero grid count.

*Measured*, by region, on all 18 z16 `FZy` captures:

| region | px | differing |
|---|---:|---:|
| 992-quad grid (exponents 0–15) | 63,488 | **0** |
| big quad | 85,192 | **0** |
| right quad | 3,120 | **0** |
| bottom quad | 1,800 | 159 (max) |

Every one of the 1,436 pixels is in the bottom quad, and all are `+1`. A
broken float encode cannot leave 63,488 pixels spanning all sixteen exponents
bit-identical. **#16 should stay closed.** Its close note is right that the
conversion is exact; only the parenthetical about the float half being "a real
encoding defect" needs retiring, and that sentence is the channel-counting
artefact above.

### Where the 1,436 px actually comes from

Against the exact geometry in rationals — the bottom quad is
`z(x) = f16(49150) * (983-2x)/720`, linear in screen x under the passthrough
shader — at the differing pixels **our value is `trunc(exact)` and silicon is
one ULP below it**. Over row 430, ours matches the ideal truncation on 345 of
360 px and silicon on 315 of 360; the 30-px gap is exactly the differing set.
Silicon's interpolated float sits a hair under the exact rational, so its
truncation drops a unit — the same ±1 band that
`depth-barycentric-normalisation.md` already measured for the z24 fixed cell
(`max|oracle − golden| = 1` on every pixel of every mask).

So the z16 float cell belongs to the **barycentric-normalisation ±1 family**,
not to a float-format defect. It is the smallest member of it: 1,436 px against
z24 fixed's 43,690.

The z24 float cell is unchanged by any of this — its container was already
being decoded correctly. Its 12,816 px decompose as 752 px/capture of the known
±12,584/12,585 quad-split family in the grid, plus 92 px of the same `+1`
bottom-quad floor and 32 px in the right quad.

## The one thing the oracle does get wrong

`score_sweep.py` is correct. **`classify_residuals.py` is not.** It loads RGBA
and calls `classify()` with no `_ZB` branch, and `classify()` buckets
`d == ±1` per channel. Every one of these 1,436 one-ULP pixels therefore
classifies as **structural** — its channel deltas are 8, 9, 4 and −255 — and
the sign histogram is inverted by the carries. That is where "structural" came
from, and it will do the same to any future depth capture.

Its own comment names the z24 packing and keeps alpha *because of* it, so the
omission is a half-applied insight rather than an oversight. The measured-impact
note in that comment is about RGB-versus-RGBA only and is not evidence that the
classes are right for `_ZB`.

The fix is to decode before classifying, reusing the branch that is already
written and now verified. In `docs/testing/classify_residuals.py`, not claimed
by this lane and so left unedited:

```diff
@@ def classify(ours, gold):
-def classify(ours, gold):
+def classify(ours, gold, zb_bits=None):
     import numpy as np
+    if zb_bits is not None:
+        # A _ZB capture is packed bits, not colour. One unit of depth is a
+        # channel delta of 8, 9, 4 or -255 in RGB565 and can carry across a
+        # byte boundary in ARGB8888, so per-channel +-1 bucketing calls every
+        # one-step depth pixel "structural". Classify the decoded word.
+        from score_sweep import decode_depth
+        oz, os_ = decode_depth(ours, zb_bits)
+        gz, gs = decode_depth(gold, zb_bits)
+        ours = np.stack([oz, os_], axis=-1)
+        gold = np.stack([gz, gs], axis=-1)
     d = ours.astype(np.int16) - gold.astype(np.int16)
```

with the call site passing the format:

```diff
-            kind, n, pos, neg, band, cols = classify(a, b)
+            from score_sweep import depth_bits
+            zb_bits = depth_bits(test) if test.endswith("_ZB") else None
+            kind, n, pos, neg, band, cols = classify(a, b, zb_bits)
```

`d` must widen past `int16` for a 24-bit word — `np.int64` — and
`golden_colours()` needs the same treatment or it keeps hashing
`R<<16|G<<8|B`, which for z24 hashes the middle byte, the low byte and the
stencil while dropping the depth's top byte. Both are why this is reported
rather than applied: it is a real change to a scoring tool and wants its own
before/after on the 784-capture oracle.

## Least certain

That silicon's `+1` is a *barycentric interpolation* shortfall rather than a
narrower internal mantissa in its float encode. Both produce "one ULP below the
exact truncation" on exactly this geometry, and the bottom quad does not
separate them: its differing pixels sit where the F16 binades are finest
(`z < ~4`, exponent ≤ 8), which is equally what a precision-limited interpolator
and a precision-limited encoder would pick out. Separating them needs a test
whose depth is constant across a primitive — then interpolation cannot be
implicated — and the suite does not contain one. The *classification* above
does not depend on which it is: either way it is a sub-ULP precision floor in
silicon, not a format we fail to support.
