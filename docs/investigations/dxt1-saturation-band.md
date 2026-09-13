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

### The L1 residual is a separate defect, and not the DXT3/DXT5 floor

Tempting to transfer, and wrong. Per `AGENTS.md`'s rule, `intersection ==
union` first:

- `MIPDXT3_64x256_bands` and `MIPDXT5_64x256_bands` are **3,086 px each and
  byte-identical masks** (intersection == union == 3,086), max |Δ| **1** —
  a pure rounding floor.
- The DXT1 remapped mask is 2,355 px and intersects that mask in **71 px**.
  |A|=2,355, |B|=3,086, union 5,370. Nearly **disjoint**, and DXT1's max |Δ|
  there is **10**.

So the bands mip residual is not one floor shared by three formats. DXT3/DXT5
have a rounding floor in those quads; DXT1 has something structural, and it is
a minification/LOD question on a non-square compressed texture rather than a
colour-decode question. It is out of scope here and is the natural next entry
if `Texture DXT` is pushed further.

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
- **The `Texture_render_target` DXT1 path is untouched and unmeasured.** No
  golden binds a DXT texture over a surface.

## Least certain point

That `MIPDXT1_64x256_bands` improves at all. Its level-0 quad is 5,336 of its
7,594 px and goes to 0 by the same arithmetic that takes five other captures
to bit-exact, so the capture should improve by roughly 5,300 px. But its L1
and L2 quads (2,148 px) are a tent-filtered minification of a non-square
texture whose decoded texels this change also moves, and the offline
simulation is invalid exactly there — it reports them getting slightly
*worse*. If the real arm comes back with bands above about 2,600 px, the
level-0 half of the prediction should be checked in isolation before anything
about the rule is doubted: the five point-sampled captures are the evidence,
and this one capture mixes the rule with a filtering question.
