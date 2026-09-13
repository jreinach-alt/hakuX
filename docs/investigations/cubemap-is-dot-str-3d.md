# `Texture_cubemap` is one texture shader mode, and `Line_width` is not

Two board entries put through the same split -- per capture, with the one-step
share and the worst channel error rather than channel counts alone. They come
out opposite ways, which is the point of doing it.

> **Correction, 2026-09-12.** The `Texture_cubemap` section below has been
> rewritten. Its headline table was sound -- its six per-capture channel counts
> reproduce exactly on today's build -- but the mechanism it proposed, and the
> two inferences it drew from a pair of probes, were not. The `Line_width`
> section is unaffected and stands as written.
>
> **A correction to this correction, in the same sitting.** The first version
> of this rewrite claimed the old numbers predated `ad1caa07` and were measured
> through a stale texture. That was wrong and I should have checked before
> pushing it: the old table's per-capture counts (88,392 / 86,055 / 84,550 /
> 84,531 / 80,292 / 70,032) match the post-`ad1caa07` captures to the channel.
> The old measurements were fine. What follows replaces the mechanism only.

## What `ad1caa07` did, since it is nearby and easy to confuse

`ad1caa07` ("notice when the guest rewrites a bound texture") landed because
the texture bind loop only runs when a texture register or `texture_vram_gen`
changes, and a CPU rewrite of the texels changes neither. `Texture_cubemap` is
the worst case for that: **every test in the suite writes a new cubemap to the
same address with the same registers.** `Cubemap_q-0.0` sorts first and writes
a checkerboard; before the fix the other 71 tests wrote noise or a radial
gradient into the same bytes and got the checkerboard back.

Measured across `Texture_cubemap` + `Texture 2D as cubemap`, since the three
generators use disjoint palettes and the classification is unambiguous:

| | captures | differing px | `DotSTR3D_*` | the other 71 |
|---|---:|---:|---:|---:|
| before `ad1caa07` | 78 | 2,565,441 | 341,454 | 2,223,987 |
| after | 78 | **320,535** | 315,891 | **4,644** |

Before the fix all 78 captures painted the cube from the checkerboard palette,
56,909 px each, in tests where silicon uses none of it. This is context, not
the subject: the numbers in this note are all from after it.

## The two probes stay, the inferences do not

The earlier version recorded two negatives -- returning `samplerCube` when
`tex_cubemap[i]` moved zero captures, and mirroring `DOT_STR_CUBE`'s
`remapCubeTo2D` fallback also moved zero -- and read two register facts out of
them: that `tex_cubemap[3]` is false here, and that `dim_tex[3]` is 3, "a
genuine volume texture".

Both register facts are wrong, and neither needed a run to check:

- `texture_cubemap_tests.cpp` calls `stage.SetCubemapEnable()` on stage 3
  outright, so **`tex_cubemap[3]` is true**.
- `TextureStage::GetDimensionality()` returns 3 only when `depth_ > 1`. The
  test calls `SetTextureDimensions(64, 64)`, leaving depth 1, so
  **`dim_tex[3]` is 2**, and the stage is a cubemap-flagged 2D texture rather
  than a volume.

The probes themselves stay on the record as measured, with one number worth
noticing: the `remapCubeTo2D` row reported **+59,142** on
`Texture_2D_as_cubemap`, and 59,142 channels is exactly what
`DotSTR3D_Bad2D` differs by on the current build with no probe applied at all.
So that row cannot be told apart from a change of baseline, and should not be
cited as the cost of the probe.

What the probes were taken to prove does not follow from them either, and a
register value written down in the test source should never have been inferred
from a pixel count.

With `dim_tex[3] == 2`, `get_sampler_type()` sends `DOT_STR_3D` through the
`PROJECT3D` case to `sampler2D`, and the emission is
`texture(texSamp3, dotSTR3.xy)` -- a 2D fetch with the raw first two dot
products, `tex_remap` empty because the stage is not `rect_tex`. That is
structurally the same fetch the rule below attributes to hardware, which is
why the defect is narrower than "wrong mode" and is worth stating precisely.

> **Superseded.** That paragraph was written before the validation layer was
> pointed at this suite. The fetch was not "structurally the same" as anything
> -- declaring `sampler2D` against the cube view made it **undefined**. See
> "It was undefined behaviour" at the end of this note; read that before acting
> on anything between here and it.

## What the texture actually is

Also wrong in the earlier note: "the 3D texture here is the eight corners of
the colour cube, so the rendered colours name which texels were sampled."

Stage 3 holds a **cubemap**: six 64x64 faces, each filled by
`GenerateMaxContrastNoisePattern` with a per-face seed from
`kColorMasks = {0x0000FF, 0xFF00FF, 0x00FF00, 0x00FFFF, 0xFF0000, 0xFFFF00}`
for `+X, -X, +Y, -Y, +Z, -Z`. Per texel the generator is

```
r = (x % 2) * 255 ^ seed_r
g = (y % 2) * 255 ^ seed_g
b = ((x/2 + y/2) % 2) * 255 ^ seed_b
```

so every texel is a corner of the RGB cube, and **all eight corners occur on
every face** at a 2x2 period. The colours therefore name texel *values*, not
texel indices, and reaching eight of them says nothing on its own. The one
thing they do pin down is *which* texel, because the four corners of a face
are four distinct colours:

| face (seed) | (0,0) | (63,0) | (0,63) | (63,63) |
|---|---|---|---|---|
| `+X` (`0x0000FF`) | `#0000FF` | `#FF0000` | `#00FF00` | `#FFFFFF` |
| `-X` (`0xFF00FF`) | `#FF00FF` | `#000000` | `#FFFF00` | `#00FFFF` |
| `+Y` (`0x00FF00`) | `#00FF00` | `#FFFFFF` | `#0000FF` | `#FF0000` |
| `-Y` (`0x00FFFF`) | `#00FFFF` | `#FFFF00` | `#000000` | `#FF00FF` |
| `+Z` (`0xFF0000`) | `#FF0000` | `#0000FF` | `#FFFFFF` | `#00FF00` |
| `-Z` (`0xFFFF00`) | `#FFFF00` | `#00FFFF` | `#FF00FF` | `#000000` |

The three positive faces carry one-channel seeds and so have the odd-parity
corner set `{R, G, B, W}`; the three negative faces carry two-channel seeds
and have the even-parity set `{C, M, Y, K}`.

## The rule: `DOT_STR_3D` lands on a corner texel, and which one is two signs

Silicon's six `DotSTR3D_*` goldens contain **no colour outside
`{#0000FF, #FF0000, #00FF00, #FFFFFF}`** -- zero pixels, all six captures,
once the 20/20/20 background is set aside. Those are exactly the four corners
of a positive face. Ours contains all eight, at texel frequency.

| capture | golden's cube | ours |
|---|---|---|
| `DotSTR3D_-1to1` | 4 colours, flat regions | 8 colours, noise |
| `DotSTR3D_0to1` | **2** colours, flat regions | 8 colours, noise |

The reading that survives every check below, stated at the level of the
observable and no further:

> Under `PS_TEXTUREMODES_DOT_STR_3D` the fetched texel is a **corner** of the
> texture, chosen by `sign(dot_{i-2})` and `sign(dot_{i-1})`. The third
> component selects nothing.

Four independent legs follow. **What is deliberately not in that statement is
*why* the address saturates**, because the first answer I gave is falsified
below and I would rather leave the mechanism open than write a second guess
into the tracker.

Four independent legs:

**1. The suite isolates the mode, not its inputs.** `DotSTRCube_*` feeds the
identical `vec3(dot1, dot2, dot3)` -- same normal map, same three constant
matrix rows, same `dotmap_*`, same texture, same final combiner -- and differs
only in the lookup. Post-fix it is within **130 px** of the golden, as are all
66 `DotReflect*` captures (worst 178). The dot products, the dot mapping, the
inverse composite matrix and the cubemap contents are therefore all correct,
and `DOT_STR_3D` is the only broken piece.

**2. The palette is the corner table, exactly.** Not a near match: the
golden's four colours are the `+X` row of the table above, and its unsigned
captures hold exactly the `x = 0` pair of that row.

**3. The unsigned captures predict `#FF0000` = 0, and it is 0.** Under
`dotmap_zero_to_one` and `dotmap_hilo_1` the mapped normal is non-negative, so
`dot_{i-2}` cannot change sign and the `s` axis always saturates the same way.
The rule then forbids the two `x = 63` corners. In all three unsigned goldens
the `#FF0000` count is **exactly zero** and the `#FFFFFF` count is exactly the
on-screen text (1,042 / 1,170 / 1,376 px, identical to ours, which renders the
same text). That is a two-of-four prediction that could have failed on any of
~87,000 cube pixels and did not.

**4. The flat regions are sign fields of a smooth function.** `SetTexCoord1/2/3`
are set to rows of `GetFixedFunctionInverseCompositeMatrix()` -- the *same*
value at every vertex, so `pT1..3` are constant over the whole draw. The only
thing varying is the normal-map sample, and
`cube_normals_object_space.png` is smooth (24,507 distinct colours over
256x256). A sign field of `M_i . f(N)` is exactly what the goldens look like:
large flat areas with smooth curved boundaries. Nothing about a texture fetch
with a varying coordinate produces that.

The one thing the goldens cannot settle is *which* positive face. `+X`, `+Y`
and `+Z` share the corner set, and `{#0000FF, #00FF00}` is reachable as an
edge pair on all three. Slice 0 is `+X` because that is the order
`GenerateCubemap` writes, but the pixels alone only say "a positive face, at
its corners".

### My own mechanism, falsified by arithmetic

The first version of this note said the dot products are "far outside `[0,1]`,
so every axis saturates at `CLAMP_TO_EDGE`". **That is wrong, and the numbers
are not close.** The three vectors are rows of
`GetFixedFunctionInverseCompositeMatrix()`, and that composite is
`model_view x (perspective x viewport)` -- the viewport included, with a
640x480 scale and a depth scale of `0x00FFFFFF`. Its inverse is correspondingly
tiny. Reconstructing the exact chain (`CreateD3DLookAtLH`,
`CreateD3DPerspectiveFOVLH(pi/4, 4:3, 1, 200)`, `CreateD3DViewport(640, 480,
0x00FFFFFF)`, then `MatrixInvert`) gives, for both draws:

| row | value | bound on `|dot|` over any mapped normal |
|---|---|---:|
| `pT1.xyz` | `[+1.220e-3, +8.629e-4, +8.629e-4]` | **0.00299** |
| `pT2.xyz` | `[0, -1.220e-3, +1.220e-3]` | **0.00299** |
| `pT3.xyz` | `[-4.403e-7, +2.224e-7, +2.224e-7]` | **9.37e-7** |

So `dotSTR3` never leaves a box of side 0.003 about the origin, and `dot3` is
seven orders of magnitude smaller still. Nothing saturates a `[0, 1]` address
from there. The rotation convention is the only part of that chain I assumed
rather than read, and it cannot matter: rotations are orthonormal, so they
turn the rows without changing their length.

**It also leaves our own output unexplained**, which is the more useful half.
At `(0.003, 0.003)` with box filtering on a 64x64 texture every fragment
should land on texel `(0, 0)` and the cube should be one flat colour. Ours is
high-frequency noise across all eight corners. So the coordinate reaching our
sampler is *not* `dotSTR3.xy` as computed above either, and one of the
assumptions in that sentence -- the texcoord that reaches `pT3`, the filter,
or the sampler the cube view is bound to -- is wrong.

**The candidate worth testing first, and it is only a candidate:** the test
writes `SetTexCoord1/2/3(row.x, row.y, row.z, 0.f)` -- **`w` is zero**. Every
other `pT` consumer in `psh.c` that divides does `pT.xy / pT.w`; the dot modes
take `pT.xyz` raw and never divide. If the hardware's address unit applies its
projective divide here, every component becomes `±inf` and saturates to an
edge with the sign of the numerator -- which is exactly the structure the
goldens show, and it would make the magnitudes irrelevant by construction.
That is a hypothesis with a mechanism and no measurement behind it, so it is
written here and not in the tracker.

Settling it needs one instrumented run: emit
`vec4(clamp(abs(dotSTR3), 0, 1), 1)` in place of the fetch and read the
magnitudes off the capture. The run is what this lane currently cannot do.

### The prediction, in exact counts

The rule says the fixed renderer must produce these and nothing else, per
capture, over the 57,951-58,285 px cube. `#FFFFFF` in the unsigned rows is the
text and nothing more.

| capture | `#0000FF` | `#FF0000` | `#00FF00` | `#FFFFFF` |
|---|---:|---:|---:|---:|
| `DotSTR3D_0to1` | 28,114 | **0** | 28,795 | 1,042 |
| `DotSTR3D_HiLo_1` | 28,385 | **0** | 28,524 | 1,170 |
| `DotSTR3D_HiLoHemi` | 28,958 | **0** | 27,951 | 1,376 |
| `DotSTR3D_-1to1` | 14,446 | 14,562 | 13,723 | 15,220 |
| `DotSTR3D_-1to1D3D` | 13,093 | 13,722 | 14,832 | 16,594 |
| `DotSTR3D_-1to1GL` | 14,527 | 14,457 | 13,849 | 15,282 |

A change that reaches the right *palette* but the wrong counts has the fetch
right and a sign wrong; a change that reaches neither has not found the rule.

Two structural notes that fall out of the table and are worth keeping. The
`-1to1` and `-1to1GL` goldens agree to **207 px** while `-1to1D3D` differs
from both by ~14,000, so `sign3` and `sign2` are the same transform to within
rounding and `sign1` is genuinely a different one -- the D3D variant is not a
bias shift of the other two, or its regions would nest inside theirs, and they
do not. And `HiLoHemi` maps to a *signed* pair yet still holds `#FF0000` at
zero, so on that mapping `dot_{i-2}` happens to stay one-signed over the
reachable hemisphere rather than being forced to by the mapping's range.

### `DotSTR3D_Bad2D`: a second confirmation, and a regression to own

The sibling suite binds a plain 2D texture to stage 3: a 2px checkerboard of
`#FFFF44` and `#3399AA`. Corners `(0,0)` and `(63,63)` are `#FFFF44`; `(63,0)`
and `(0,63)` are `#3399AA`.

**The golden is `#FFFF44` across the entire cube, all 56,909 px** -- one
texel, on a texture with 4,096 of them. That is the rule again, on a different
texture in a different suite, with both dot signs agreeing everywhere.

We now render 37,195 px of `#FFFF44` and 19,714 px of `#3399AA`: we land on
both checker squares, so our sample point moves through the texture's interior
where silicon pins to a corner.

That capture was **exact before `ad1caa07` and is 19,714 px off after it**, and
that is a real regression to record rather than round off. It is not evidence
against the fix -- across the two suites the same commit took 2,565,441
differing pixels to 320,535 -- but the earlier exactness was luck, and saying
so is cheaper than rediscovering it.

## `Line_width`: not concentrated, and not available

61 captures, 2,516,604 channels, 1,009,664 structural -- and the structural
part is spread, **80% of it across nineteen of the sixty-one captures**, with
each capture's error growing smoothly with the width:

| capture | channels | structural | one-step |
|---|---:|---:|---:|
| `Line_0063.0` | 106,131 | 47,640 | 55.1% |
| `Line_0063.7` | 106,256 | 47,282 | 55.5% |
| `Line_0061.0` | 104,768 | 47,156 | 55.0% |
| `Line_0057.0` | 101,600 | 45,688 | 55.0% |

Every capture is about 55% one-step with a worst error of 223, and the
ordering follows the register value (in eighths -- `Line_0063.7` is 63.875, not
63.7). There is no cell holding the mass, which matches the earlier reading
that this suite has three separate causes and wants generated line geometry.

It is also the one entry in the top ten that this lane should not touch
unprompted: the fix runs through `roundScreenCoords` in `glsl/vsh.c`, which is
rasteriser-wide and needs the owner's say-so.

## Why both tables are here

The split is the same three columns each time, and it has now reclassified
four board entries in a day: `Fog_gen` collapsed to one cell, `Specular` and
`Specular_back` to four captures, `Texture_cubemap` to one texture mode, and
`Line_width` refused to collapse at all. Counting differing channels without
their magnitude ranks a precision floor next to a missing feature; adding the
one-step share and the worst error separates them in one pass.

## The probe, and what a sorted comparison cannot see

Added 2026-09-12, from the device run at `ec13c70e60` (`dot-str-3d-probe.md`).
Two results land, one does not.

**Confirmed: the magnitude.** Every cube pixel comes back in the `[0.001,
0.01)` bucket, so the 0.00299 bound derived from the inverse composite is what
the shader actually computes. The saturation mechanism was correctly killed
before a run was spent on it.

**Confirmed, and stronger than predicted: the unsigned captures reach only two
sign pairs.** `sign(dot_{i-2})` is uniformly non-negative under the unsigned
dotmaps, so `#FF0000 = 0` holds at the mechanism level and not merely in the
output. That one is spatial and it is real.

**Not confirmed: "only the sign-to-corner assignment is left."** That came
from comparing the four sign-pair populations against the golden's four corner
populations **sorted**, which discards where they are. The golden's four are
15,262 / 14,832 / 13,722 / 13,093 -- all within 17% of each other -- so any
four-way partition of the same cube into roughly-equal parts matches the list
to a couple of hundred pixels. Two exact hits is what near-equal areas do.

Per pixel, on the same captures:

| capture | ours on the 4 reachable corners | ours on the other four | agreement | chance | lift |
|---|---:|---:|---:|---:|---:|
| `-1to1D3D` | 50.1% | **49.9%** | 24.2% | 24.9% | **-0.7** |
| `-1to1` | 50.3% | **49.7%** | 25.9% | 25.4% | **+0.5** |
| `-1to1GL` | 50.1% | **49.9%** | 26.5% | 25.3% | **+1.2** |

Chance grants us the right areas, since it is each corner's own marginal.
**We are at chance**, the ours-to-gold confusion table has no dominant
permutation, and **half our cube lands on the four texels the corner rule
forbids** -- the even-parity set, which a wrong assignment among four corners
cannot reach.

The shape of the difference says the same thing. Fraction of cube pixels
agreeing with all four neighbours:

| capture | gold | ours |
|---|---:|---:|
| `-1to1D3D` | **95.1%** | **7.2%** |
| `-1to1` | 90.8% | 9.9% |
| `0to1` | 97.1% | 41.3% |
| `HiLo_1` | 98.0% | 78.8% |

7% is texel-frequency dither. With `REPEAT` addressing (`vk/texture.c:1308`)
and a coordinate spanning 0.19 texels across the whole cube, the fetch cannot
produce that: it would give one flat region per sign pair.

### The fork this leaves, and the one number that decides it

`pT1..3` are constant over the draw, so every bit of spatial variation in
`dot_{i-2}` and `dot_{i-1}` comes from `t0`, the stage-0 normal map sample.
So the probe's own sign channels decide where the defect is:

- **sign map flat** -- stage 0 is sampled correctly and the defect is
  downstream in the stage-3 fetch.
- **sign map dithered** -- the dots flip sign per pixel, which with constant
  `pT` can only mean `t0` is wrong, and **#51 is filed against the wrong
  stage**. A magnitude that stays in one bucket is consistent with this: a bad
  `t0` keeps `|dot|` in range while the sign flips.

Everything above points at dithered, but that is inference from the output
where the probe capture has it directly.

### The assignment, pre-registered

With `REPEAT` and nearest on 64x64: `dot > 0` gives `frac ~ 0.003` and
addresses texel 0; `dot < 0` gives `frac ~ 0.997` and addresses texel 63. So
ours should be `(+,+) -> (0,0)` blue, `(-,+) -> (63,0)` red, `(+,-) -> (0,63)`
green, `(-,-) -> (63,63)` white -- which already reproduces the golden's sets,
`{blue, green}` for the unsigned captures included. **If that is also the
golden's assignment then the assignment was never the defect**, and the dither
is the whole of what is left.

## The four "forbidden" colours are the `-Z` face, and the position dithers too

The sign field turns out to be **flat** -- 92 to 99.9% of interior cube pixels
share `(sign_1, sign_2)` with all four neighbours, within a couple of points of
the golden's own output flatness. So `t0` does not dither, the dot products are
clean, and the corruption is between `dotSTR3` and the sampled texel.

Half of that is now explained from the colours alone. The four colours we
produce outside the golden's set are not stray texels: they are exactly the
four corner texels of the **`-Z` face**, seed `0xFFFF00`.

| corner | `+X` (slice 0) | `-Z` (slice 5) |
|---|---|---|
| `(0,0)` | `#0000FF` blue | `#FFFF00` yellow |
| `(63,0)` | `#FF0000` red | `#00FFFF` cyan |
| `(0,63)` | `#00FF00` green | `#FF00FF` magenta |
| `(63,63)` | `#FFFFFF` white | `#000000` black |

The split between the two faces is 50.1/49.9, 50.3/49.7, 50.0/50.0 -- a coin
flip, which is what the sign of a quantity bounded by `9.37e-7` does. A third
component reaching slice 0 or slice 5 accounts for it exactly.

**It does not account for the rest.** Strip the face out and map each colour to
its corner *position*, which under a `.xy` fetch must be a function of the two
flat signs:

| capture | our position field flat | gold's | agrees with gold |
|---|---:|---:|---:|
| `-1to1D3D` | **8.4%** | 95.1% | 24.8% |
| `0to1` | **41.6%** | 97.1% | 24.5% |

Chance, with a flat confusion matrix and no permutation in it. With
`|dot|` in `[0.001, 0.01)` and `REPEAT` on 64 texels the entire bucket maps to
texel 0 for a positive sign and texel 63 for a negative one -- `0.0099 * 64 =
0.63`, `(1 - 0.0099) * 64 = 63.4`. Two texels per axis, no room for anything
else, so a flat sign field *must* give a flat position field. It does not.

**So the coordinate reaching the sampler is not the `dotSTR3` the probe read.**
The probe replaced the fetch with a readout of that value and therefore
measured upstream of whatever changes it.

`DotSTR3D_Bad2D` shows the same thing with no cubemap in it at all -- plain 2D
texture, valid 2D view, no third component available to blame:

| | gold | ours |
|---|---:|---:|
| flat | 98.1% | **51.1%** |
| `#FFFF44` | 100% | 65.4% |

The measurement that closes it is the resolved texel index, not another sign:
emit `ivec2(fract(dotSTR3.xy) * textureSize(texSamp3, 0))` into R and G. Only
0 and 63 are permitted per axis on the reading above, so anything else names
the step that corrupts the address.

## It was undefined behaviour, and that is why nothing added up

Added 2026-09-12, and it retires most of the puzzles above.

Running the cube suite **twice on the same binary**, 71 of the 78 captures are
byte-identical and the seven that move are exactly the `DotSTR3D_*` family:

| capture | run A vs golden | run B vs golden | **A vs B** |
|---|---:|---:|---:|
| `DotSTR3D_0to1` | 49,606 | 48,597 | **42,554** |
| `DotSTR3D_-1to1D3D` | 49,523 | 50,033 | **43,976** |
| `DotSTR3D_HiLo_1` | 44,075 | 48,031 | **13,865** |
| `DotSTR3D_Bad2D` | **0** | 19,714 | **19,714** |

The validation layer names the cause, eight times over the suite:

```
VUID-vkCmdDrawIndexed-viewType-07752
the descriptor (binding 3, index 0) ImageView type is
VK_IMAGE_VIEW_TYPE_CUBE but the OpTypeImage has (Dim = 2D)
```

`get_sampler_type()` routed `DOT_STR_3D` through the `PROJECT3D` case, which
ends in `sampler2D`/`sampler3D` and never consults `tex_cubemap[i]` -- where
`CUBEMAP`, `DOT_STR_CUBE` and all three `DOT_RFLCT_*` do. A cubemap-flagged
stage gets a cube view, so the fetch was undefined.

**That accounts for every observation this note could not explain**: the
texel-frequency dither, half the cube on texels the corner rule forbids, the
corner position at chance with a flat confusion matrix, and a demonstrably
flat sign field feeding a fetch that produced noise. The inputs were always
clean; the fetch was not.

Two things it voids. **Every single-run score on these seven captures**, ours
and the device lane's, including the "`samplerCube` when `tex_cubemap[i]` moves
zero captures" negative -- that was noise against noise, and it was probably
testing the right change. And **the `DotSTR3D_Bad2D` regression attributed to
`ad1caa07`**: that capture is byte-exact in some runs and 19,714 px out in
others on one binary, so the commit had nothing to do with it.

What it does **not** void is the probe, which replaced the fetch with an
arithmetic readout and so never went through the UB: the 0.003 magnitude and
the flat sign field are measurements of `dotSTR3` itself and stand. Nor the
rule or the predicted counts, which come from the goldens.

### The fix, and what it did and did not buy

`dot_str_3d_is_cube()` now gates both the sampler declaration and the fetch --
one predicate for both, because they have to agree or the shader does not
compile and two copies of an expression drift. `PROJECT3D` is deliberately
left alone despite sharing the case: it emits `textureProj()`, which has no
cube form, so a cube sampler there would trade a wrong result for one that
does not build. **It carries the same latent violation and wants its own fix.**

Measured against a bar registered before the run:

| | result |
|---|---|
| determinism, three runs, all seven captures | **0 px**, was 13,865-43,976 |
| `viewType-07752` under validation | **8 -> 0** |
| `DotSTR3D_Bad2D` vs golden | **19,714 -> 0**, byte-exact and stable |
| the six cubemap captures | **unchanged**, still 48,031-50,526 px |
| corner counts vs the prediction | **not met**, and the unsigned captures still produce a non-zero red where the rule forbids one |

So the mode is now deterministic and spec-clean and **still does not implement
the hardware rule**. That was the registered expectation rather than a
disappointment: a `samplerCube` lookup is a smooth direction sample and the
rule says silicon lands on a corner texel, which are different operations.
The gain is that these captures are instruments now. The corner rule has never
actually been tested, because until this landed there was nothing stable to
test it against.

One loose end, flagged rather than asserted: the six cubemap captures come out
byte-identical to one of the two pre-fix outcomes, which is not what two
different sampling operations should do. Most likely lavapipe's undefined 2D
read of a cube view was already indexing layer 0 through the same filtering
path. Unproven, and it changes none of the numbers above.

## Where the remaining error is: our face selection leaves the positive faces

Measured once the captures became deterministic, which is the first time this
question could be asked. A temporary probe emitted the cube face our lookup
selects, per pixel, over the golden's cube region:

| capture | `+X` | `-X` | `+Y` | `-Y` | `-Z` |
|---|---:|---:|---:|---:|---:|
| `DotSTR3D_HiLo_1` | **100.0%** | - | - | - | - |
| `DotSTR3D_0to1` | 78.4% | 0.1% | 13.6% | 7.9% | - |
| `DotSTR3D_-1to1D3D` | 33.1% | 15.6% | 17.1% | 33.0% | 1.1% |

Set that against what the goldens permit. Every golden colour is in the
odd-parity set `{R, G, B, W}`, which is the corner set of a **positive** face;
the negative faces carry the even-parity set `{C, M, Y, K}` and **not one
golden pixel is ever one of those**. So:

> **Silicon never leaves the positive faces. We reach a negative face on up to
> 49% of pixels.**

That is a measured constraint rather than an inference, and it splits the
remaining error in two:

- **`HiLo_1` picks `+X` on every pixel**, and its golden is the `x = 0` edge
  pair of `+X`, so on that capture our *face* already agrees with silicon and
  only the within-face position is wrong.
- **The signed dotmaps diverge on the face itself**, reaching `-X`, `-Y` and a
  little `-Z` where silicon reaches none.

The obvious candidate is that the hardware address unit works on magnitudes,
which would make a negative face unreachable by construction and sits well
with "lands on a corner". That is a hypothesis and is written here rather than
in the tracker; what is established is the face distribution above and the
goldens' parity, both of which are direct measurements.

## And within the face we land in the interior, where silicon lands on corners

Second probe, same shape: `G = mid/max`, `B = min/max` over `abs(dotSTR3)`,
so a corner reads 255/255, an edge midpoint 255/0, a face centre 0/0.

| capture | mid/max median | min/max median | corner | edge mid | face centre | interior |
|---|---:|---:|---:|---:|---:|---:|
| `HiLo_1` | 63 | 3 | **0.0%** | 0.0% | 3.7% | **96.3%** |
| `0to1` | 125 | 7 | **0.0%** | 0.6% | 1.5% | **97.9%** |
| `-1to1D3D` | 107 | 14 | **0.0%** | 0.3% | 0.8% | **99.0%** |
| `-1to1` | 99 | 9 | **0.0%** | 0.3% | 1.4% | **98.3%** |

**Not one pixel of any capture lands on a corner.** 96-99% land in the face
interior at a mid/max ratio around 0.25 to 0.5, and the third component is
nearly always negligible (min/max median 3 to 14 of 255).

So the gap is now characterised end to end, entirely in measurements:

| | silicon | ours |
|---|---|---|
| face | positive only, never negative | negative on up to 49% of px |
| position in face | corner | interior, 96-99% |

### A prediction of mine this falsified

I expected `mid/max` to come back near 255 -- an edge -- reasoning that the
first two dot products are "both about 0.003" and therefore near-equal. That
was wrong, and the error is worth naming because it is the same shape as
others in this note: **0.00299 is the *bound* on each dot, not its value.**
Both rows of the inverse composite happen to have the same norm, so they share
a bound; the actual per-pixel dots vary with the normal and their ratio sits
around a quarter to a half, not one.

The bound was the right tool for killing the saturation mechanism, where only
the maximum mattered. It is the wrong tool for anything about the *shape* of
the coordinate, and I used it for both.

What it would take to land on a corner from an interior coordinate is for the
two non-major components to be driven to +-max. Per-axis saturation of the raw
dots cannot do that at 0.003. Saturation *after* the cube divide could, and so
could a face coordinate held at very low precision, but both are guesses and
neither is going in until something measures one.
