# DXT1's ordered dither saturates at both ends, and that is #6's whole residual

The dither landed and was verified (`a8bf9137fb` -> `9b8f1915e8`, PRE-REGISTERED
PASS, `Texture DXT` 402,999 -> 34,911 px). The issue then recorded two gaps as
defects rather than as a floor:

> **A code of exactly 1 decodes to 0 where the model says 8**, and
> `MIPDXT1_64x256_bands` keeps **7,594 px** of which only **637 of 1,342**
> residual texels are code-1.

They are **one rule**, it is **not a rule about code 1**, and the 637/1,342
split was an artefact of how the residual was classified rather than two
mechanisms.

## The rule

For a channel of `bits` bits (5 for R and B, 6 for G) write `k = 8 - bits` and
`half = 2^(k-1)`. The dither picks `o`, the value in `[v - half, v + half - 1]`
congruent to the matrix entry modulo `2^k`, where `v` is the palette entry's
8-bit value. Then:

    out = 0    if o <  2^k + half - 1        (11 for 5 bit,  5 for 6 bit)
    out = 255  if o >  255 - half - 1        (250 for 5 bit, 252 for 6 bit)
    out = o    otherwise

So the texture unit's DXT1 output takes values only in

| channel | allowed output levels |
|---|---|
| R, B (5 bit) | `{0}` ∪ `[11, 250]` ∪ `{255}` |
| G (6 bit) | `{0}` ∪ `[5, 252]` ∪ `{255}` |

Both bounds are the same expression — **the top of the dither window of the
extreme non-saturating code**, `replicate(1) + half - 1` and
`replicate(2^bits - 2) + half - 1` — and both are measured at **both** channel
widths, so neither is a free parameter fitted at one width and extrapolated to
the other.

**It removes two special cases rather than adding one.** The landed code
carried `if (v == 0 || v == 255) return v;`. Those clauses exist because a
saturated code does not dither — and under this rule they are unnecessary: the
whole window of `v = 0` lies below the low bound and the whole window of
`v = 255` lies above the high bound. One rule replaces two exceptions. That is
the structural argument that this is a rule and not a curve fit to code 1,
and it is the opposite shape from the failure `AGENTS.md` names as *one reason
per exception*.

## Why it is not "code 1 is special"

The decisive set is every observation where this rule and the landed one
disagree, so that the golden chooses between them. There are **1,384** of them
and the rule is right on all 1,384:

| limb | source | obs | palette values involved |
|---|---|---:|---|
| low | endpoint whose code is 1 | 680 | 4, 8 |
| low | **interpolated** palette entry | 346 | 3, 4, 5, 8, 11, 12, 13, 14 |
| high | **interpolated** palette entry | 358 | 250, 251, 252 |

An interpolated palette entry is an arbitrary 8-bit value: it has no 5- or
6-bit code at all. **704 of the 1,384 decisive observations are therefore
unreachable by any rule keyed on the code**, and a rule keyed on the output
value reaches all of them with no extra clause. A "code 1 is black" rule
scores 757 misses; "code 1 does not dither" scores 1,555.

The high limb has no endpoint evidence at all, and that is not a weakness: an
endpoint code of 31 or 63 expands to exactly 255, which the landed `v == 255`
clause already got right. The limb is visible *only* through interpolants,
which is why nobody found it while looking at codes.

## How it was read out of the goldens: level sets, no mapping

The same instrument as #59. Each candidate rule permits a different **set** of
8-bit output values, and the sets differ, so the only question is which values
a channel of a golden contains — no screen-to-texel mapping, no regression
fit, no assumption about which texel landed where. The `Texture DXT` DXT1
quads are point magnifications (checked, not assumed: `dxt_dither_fit.golden`
refuses a capture whose magnified cells are not constant), so those pixels
*are* texels.

| channel | forbidden low band | forbidden high band | present anywhere in five goldens |
|---|---|---|---|
| R (5) | 1..10 | 251..254 | **NONE** |
| G (6) | 1..4 | 253..254 | **NONE** |
| B (5) | 1..10 | 251..254 | **NONE** |

Each bound is pinned from both sides: `11` by the presence of 11 and the
absence of 10; `5` the same way for green; `250` by the presence of 250 and the
absence of 251.

**The 6-bit high bound is pinned by a sixth capture, from a different suite.**
Green never approaches saturation in the `Texture DXT` images (its maximum
there is 232), so `252` would have been an extrapolation. `Texture_format`'s
`TexFmt_DXT1` walks green through **249, 250, 251, 252 and then jumps to 255**,
with 253 and 254 at exactly 0 px in a continuous gradient. Its source blocks
are produced by a completely different compressor — `pbkitplusplus`
`texture_stage.cpp` writes `c0 = 0`, `c1` = the block's top-left pixel in 565
and all-one or all-three indices, so every block is punch-through — and its
quad is 480x360 rather than a 256x256 point magnification. **None of its blocks
were used to derive the rule.**

**And a seventh capture pins all four bounds at once.**
`Volume_texture/DXT1` is a third suite and a 3D texture, and it samples
densely enough — 225, 247 and 242 distinct levels per channel — that its
lowest non-zero and highest sub-255 values land on every bound
simultaneously: R 11/250, G 5/252, B 11/250. It is evidence about silicon and
**not a leg**: our own render of it fails for an unrelated reason (6,129 px at
max delta 255), so it cannot confirm a fix, only the rule the golden obeys.
Nothing here says whether the dither matrix is also keyed on `z` — the level
set cannot see that, and `s3tc.c` indexes `(y & 3, x & 3)` per slice.

### The control that says it is the format path and not the images

`DXT3` and `DXT5` carry the identical colour-block layout, target
`A8R8G8B8`, and do not dither. Their goldens contain **8** in R — which is
`replicate5(1)`, exactly the value DXT1 never emits. So the forbidden band is
a property of this decode path, not of the test images.

## Every rival, and what kills it

Scored over 61,416 channel observations from the five DXT1 captures. A rule
that is merely better in aggregate is a fit; the one with zero misses is the
derivation.

| rule | agree | MISS |
|---|---:|---:|
| **this rule** | 61,416 | **0** |
| landed: window, `v==0`/`v==255` pass through | 60,032 | 1,384 |
| window only, plain clamp to 0..255 | 49,362 | 12,054 |
| code 1 is simply black | 60,659 | 757 |
| code 1 does not dither | 59,861 | 1,555 |
| low limb only | 61,058 | 358 |
| high limb only | 60,390 | 1,026 |
| clamp to the bounds instead of saturating | 35,032 | 26,384 |

The last row matters: the values below the low bound come out as **0**, not as
11. A clamp is the obvious reading and it is wrong by 26,384 observations.

`docs/testing/dxt1_saturation_rule.py` re-derives all of the above and exits
non-zero if any rival survives, if any code other than 1 deviates from the
landed window model, or if a forbidden value turns up in a golden. It writes
nothing.

## What the other ~705 texels are

The issue's 637-of-1,342 split came from a classifier that counted only
*endpoint* texels whose code was literally 1. Re-attributed at the texel
level on `MIPDXT1_64x256_bands`:

| class | texels | what it is |
|---:|---:|---|
| 976 | the low limb alone fixes it | output below the low bound, from a code-1 endpoint **or** an interpolant |
| 351 | the high limb alone fixes it | output above the high bound, all from interpolants |
| 7 | needs both limbs | wrong in two channels at once, one per limb |
| 8 | not a decode defect | punch-through *transparent* texels, where the golden holds the framebuffer background `(16,16,16,254)` and not a texel at all |

976 + 351 + 7 + 8 = **1,342**, which is the whole residual. Measured by
running each limb on its own: low limb only leaves 366 texels, high limb only
leaves 991, both leave 8. The classes are not subtracted from a total -- each
number is a separate scoring run, because a class count is a count of texels a
mechanism *touches* and the two limbs genuinely overlap on 7 of them.

The last eight are a defect in the offline *model*, not in the decoder: our
own capture already shows the background there, matching the golden, which is
why the simulation on real captures scores that quad at 0.

So at the texel level the residual is **100% accounted for** and nothing is
left over.

## Simulated offline against our own captures

The conservative check #59 used: take the landed arm's captures
(`1789265953-dxt6-fix-243517`, ref `9b8f1915e8`), move every channel the rule
forbids to 0 or 255, and re-score against the goldens.

| capture | landed | with rule | delta |
|---|---:|---:|---:|
| `Texture_DXT/DXT1_plasma_dxt1` | 384 | **0** | −384 |
| `Texture_DXT/DXT1_plasma_alpha_dxt1` | 448 | **0** | −448 |
| `Texture_DXT/MIPDXT1_plasma_dxt1` | 510 | **0** | −510 |
| `Texture_DXT/MIPDXT1_plasma_alpha_dxt1` | 595 | **0** | −595 |
| `Texture_DXT/MIPDXT1_64x256_bands_dxt1` | 7,594 | 2,355 | −5,239 |
| `Texture_format/TexFmt_DXT1` | 4,487 | **0** | −4,487 |
| *control* `DXT3_plasma_dxt3` | 1,536 | 1,984 | **+448** |
| *control* `DXT3_plasma_alpha_dxt3` | 1,024 | 1,792 | **+768** |
| *control* `DXT5_plasma_dxt5` | 1,536 | 1,984 | **+448** |
| *control* `MIPDXT3_plasma_dxt3` | 2,120 | 2,715 | **+595** |
| *control* `MIPDXT5_plasma_alpha_dxt5` | 5,427 | 6,363 | **+936** |

Five of six DXT1 captures go **bit-exact**, including the four the issue said
were "every remaining disagreement". The control is the point: the same remap
applied to DXT3 and DXT5 makes them *worse* by a measured amount, so this is
not a rule about 8-bit output in general and it must stay inside
`write_dxt1_block_to_texture`. That also gives the must-not-move list teeth —
the failure it guards against is a real one with a known sign.

## The one capture the simulation cannot predict, and why

`MIPDXT1_64x256_bands` is the only non-square DXT1 texture, and `TestMipmap`
gives it `MIN_TENT_TENT_LOD`. Localised per quad:

| quad | landed | remapped |
|---|---:|---:|
| L0, 256x256 at (5, 80) | 5,336 | **0** |
| L1, 128x128 at (270, 80) | 2,046 | 2,207 |
| L2, 64x64 at (410, 80) | 102 | 108 |
| L3, 32x32 at (480, 80) | 105 | 35 |
| L4 / L5 | 5 | 5 |

L1 magnifies a 64-wide texture in x while *minifying* 256 rows in y, so it
selects mip level 1 and blends through a tent filter. A filtered pixel is an
average of expanded texels, and remapping the average is not the same
operation as changing the texels that were averaged — which is why the remap
makes L1 slightly worse rather than better, and why the post-fix value there
is genuinely unknown.

**The goldens say the same thing from the other side**: the golden's own L1
region *does* contain forbidden-band values (G 1..4, B 1..10). The band is a
property of the unfiltered texel, so **filtering happens after expansion** —
which is the same ordering #59 established for packed texels and is the reason
the rule belongs in the upload and not in a shader.

`MIPDXT1_plasma`'s four quads are all magnifications of its 32x32 level 0, so
they are all point-sampled and all go to 0.

### Measured: the L1 residual was the simulation's artefact, not a defect

**The arm settled this and the simulation had it wrong, in the direction the
simulation said it might.** Measured on `886fbd11ea -> 9ef86d78b7`,
`MIPDXT1_64x256_bands` came back at **279 px, max |Δ| 1, 279 of 279
off-by-one, structural 0** — against the ~2,355 the simulation projected and
the ~2,600 ceiling registered. Per quad: **L0 = 0**, L1 = 220, L2 = 43,
L3 = 11, L4 = 4, L5 = 1.

So the minified quads did not keep a structural residual at all: changing the
texels the tent filter blends moved the blends onto the golden, to within a
rounding step. What the offline simulation reported there — L1 getting
*worse* — was the artefact of remapping an already-filtered pixel, which the
prediction named in advance as the reason no value was registered for this
capture. **The instrument changed, not the conclusion**: the simulation is
invalid on filtered pixels and the device arm is the measurement.

And it is **not** the DXT3/DXT5 floor, `intersection == union` first:

- `MIPDXT3_64x256_bands` and `MIPDXT5_64x256_bands` are **3,086 px each with
  byte-identical masks** (intersection == union == 3,086), max |Δ| 1.
- DXT1's post-fix mask is 279 px and intersects that mask in **24 px**;
  |A| = 279, |B| = 3,086, union 3,341, and A is **not** a subset of B.

Same *shape* — a ±1 rounding floor with zero structural error — and a
different *set*, which is what one expects of three formats with three
palettes in the same quads. Nothing is transferred between them, and #6 has
no structural error left anywhere in `Texture DXT`.

## Cost

**Slightly cheaper per block, not dearer.** The change is entirely inside
`dither_to_residue`: two equality tests on `v` and a two-sided `0..255` clamp
are replaced by two range tests. Same call count, same memory traffic, no new
table. The dither is still three scalar calls per texel in
`write_dxt1_block_to_texture`, which the performance stream has already
priced (`TexU` 1.15 fills/frame, under 1.5% of a frame) and whose real debt is
elsewhere: software DXT1 makes the host image 8x larger so the texture cache's
eviction budget holds 8x fewer, and `s3tc.c`'s "worker pool" forks, runs the
last chunk on the caller and joins, so below 128 blocks it is single-threaded
on `nv2a.pfifo_thread`. **This change makes neither of those worse and does
not address either.**

## Deliberately not concluded

- **No gate-level mechanism.** The rule is measured; *why* the bounds are the
  window tops of the extreme inner codes is not explained. Several readings
  that would have explained it are refuted by the data: a borrow into the code
  followed by the code-0 saturation explains the four low residues that
  borrow and not the three that do not; a rule keyed on the post-dither code
  is contradicted by code 30 and code 31 both producing code 31 with
  different outputs; a symmetric clamp is contradicted by 26,384
  observations. So the bounds are stated as measured constants with one
  formula each, not derived from a circuit.
- **Whether "code 1" or "the value `2^k`" is the trigger** cannot be
  separated: code 1 is the only code whose window straddles the low bound at
  either width. The value-domain form is preferred because it is the only one
  that also reaches the 704 interpolant observations, not because the corpus
  distinguishes the two statements about codes.
- **Mip levels above 0 are still only indirectly verified.** `MIPDXT1_plasma`'s
  higher quads are magnifications of level 0, so they test the same texels.
  Nothing here tests a decode of level 1 in isolation.
- **Whether the dither matrix is also keyed on `z`** for a 3D DXT1 texture.
  `s3tc.c` indexes `(y & 3, x & 3)` per slice, `Volume_texture/DXT1`'s golden
  obeys the band, and a level set cannot distinguish the two — our render of
  that capture is 6,129 px at max delta 255 for a reason that is not this
  one, so the question is not answerable from it today.
- **The `Texture_render_target` DXT1 path is untouched and unmeasured.** No
  golden binds a DXT texture over a surface.

## Measured on the device: PRE-REGISTERED PASS

`886fbd11ea` -> `9ef86d78b7`, two runs each, disc
`2-suites:e85fa791:Texture DXT,Texture format`, prediction sha
`3c499af59290` bound at queue time. **All 16 registered checks hold.**

```
better 6     worse 0     same 49    noise 0      (55 compared)
exact  38 -> 43   repaired to exact 5   regressed from exact 0

better Texture_DXT     DXT1_plasma_dxt1              384 ->     0   now exact
better Texture_DXT     DXT1_plasma_alpha_dxt1        448 ->     0   now exact
better Texture_DXT     MIPDXT1_plasma_dxt1           510 ->     0   now exact
better Texture_DXT     MIPDXT1_plasma_alpha_dxt1     595 ->     0   now exact
better Texture_DXT     MIPDXT1_64x256_bands_dxt1   7,594 ->   279
better Texture_format  TexFmt_DXT1                 4,487 ->     0   now exact

Texture_DXT      15   5  0   10  0    34,911 ->  25,659
Texture_format   40   1  0   39  0   139,389 -> 134,902
```

Arm A reproduced every baseline figure exactly on a **fourth binary and a
third disc composition** (3-suite, 8-suite and now 2-suite discs, four APK
hashes), which is what makes the absolutes legitimate rather than deltas.

`Texture DXT`'s DXT1 half now carries **zero structural error**: five of six
captures bit-exact and the sixth 279 px of pure off-by-one. Across the whole
issue the dither plus this rule is 402,999 -> 25,659 px on the suite.

## Least certain point

Not the rule — the corpus pins all four of its constants from both sides in
three suites, and the arm passed every leg including the one derived from
data the rule never saw. What is least certain is **that this is the whole
story for DXT1 at other precisions of the same pipeline.** Every capture here
decodes into an `A8R8G8B8` host image and is read back through an 8-bit
framebuffer. The band is a statement about what the texture unit emits into
an 8-bit consumer; nothing here says what it emits into a 16-bit render
target, and `Texture_render_target` binds no DXT texture so the corpus cannot
ask. If a title samples DXT1 into a 565 surface and shows a black speckle
where a near-black gradient should be, this rule's low limb is the first
place to look and the second place to doubt.

Runner-up: whether the dither matrix is keyed on `z` for a 3D DXT1 texture.
`Volume_texture/DXT1`'s golden obeys the band, but it is 6,129 px at max
delta 255 on our side for an unrelated reason, so it cannot answer the
question and it is not on any leg.
