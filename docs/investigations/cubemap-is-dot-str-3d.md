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

## Why the coordinate reaches a corner: the magnitude underflows, the sign does not

The section above ends on two guesses -- saturation after the cube divide, or a
face coordinate held at very low precision -- and a refusal to pick between them
without a measurement. Here is one, from the goldens already on disk, no device.

### What the pattern can and cannot say

`GenerateMaxContrastNoisePattern` has three binary channels, so the whole thing
holds **eight colours across all six faces**. Face seeds are written
`r | g<<8 | b<<16` into an A8B8G8R8 texture, so mask `0x0000FF` is the *red*
channel -- not the obvious order; it is fixed here by #40's independent hardware
reading, which has +X texel (0,0) of the radial gradient at `(191,0,0)`.

The four corners of a 64x64 face, by sign group:

| faces | their four corner colours |
|---|---|
| **+X, +Y, +Z** | `#FF0000` `#0000FF` `#FFFFFF` `#00FF00` |
| **-X, -Y, -Z** | `#FF00FF` `#000000` `#FFFF00` `#00FFFF` |

All three positive faces carry the *same* corner set, permuted; so do the
negatives. **Colour therefore identifies the sign group and the corner, and
cannot identify which face.** The entry in `nv2a_issues.toml` calls these "the
four +X-face corners": right about the set, over-specified about the face, and
corrected here. Nothing downstream depended on it being +X.

### The measurement

Colours the golden holds over the *entire* 640x480 image, not just where we
differ:

| capture | distinct colours, whole image | of the negative corner set |
|---|---|---|
| `-1to1`, `-1to1D3D`, `-1to1GL` | 5 | none but `#000000` |
| `0to1`, `HiLoHemi`, `HiLo_1` | 4 | none but `#000000` |

`#000000` is in the negative corner set but is also the background, so it
discriminates nothing. `#FF00FF`, `#FFFF00` and `#00FFFF` are the three that
would betray a negative face, and **they appear nowhere in any of the six**.

Over the ~56,909 differing pixels the golden holds all four positive corners in
near-equal quarters on the `-1to1*` captures (`#FF0000` 14,562, `#0000FF`
14,446, `#FFFFFF` 14,178, `#00FF00` 13,723 on `-1to1`), and exactly two of them
on the others. Those two, on any positive face, are the pair that **share one
coordinate extreme and differ in the other** -- one sign pinned, one free. That
is the recorded rule (`sign(dot_{i-2})`, `sign(dot_{i-1})`, third component
selects nothing) arrived at independently, and it is why the unsigned dotmaps
can only reach half the corners.

Three things follow, none of them an inference:

1. **The sign group is positive, throughout.** Not "rarely negative" -- absent.
2. **Silicon is pinned to the corner block, not roaming.** One face holds 8
   distinct colours over an 8x8 patch, and the pattern holds 8 in total; the
   golden spends 57,000 pixels on 4 of them, all corners.
3. **No interior colour appears at all.**

### Which guess this kills

Saturation after the cube divide would land on a corner of *whichever* face the
major axis selects, negative faces included -- a divide does not care about
sign. The negative faces are absent, so that is not the mechanism.

### What would have to be true -- the question this note was left on

**The magnitude would have to underflow while the sign survives.** That single
condition produces every measured fact at once:

- The dots are bounded by `|dot1|, |dot2| <= 0.00299` and `|dot3| <= 9.37e-7`.
  An 8-bit fixed-point fraction has a half-quantum of 0.0039, *above* all three
  bounds, so on any dot path of eight or fewer fractional bits the triple
  arrives as **exactly zero**. Here the bound is the right instrument, because
  it is an upper bound and the claim needs only that every value fall under one
  threshold -- unlike the edge/corner prediction further up, where a shared
  bound said nothing about a ratio. Same number, different question.
- A zero-magnitude direction is exactly what #40 measured from the other end:
  `f6609964` records silicon resolving a degenerate cube direction to a single
  face at its `(0,0)` texel, confirmed on two textures at once. A degenerate
  magnitude explains the *face* being fixed and positive.
- But the corners vary per pixel in near-equal quarters, so something still
  carries information. The two sign bits are what a magnitude underflow leaves
  behind, and two bits select exactly four corners -- the recorded rule.

So the corner rule, which was derived from goldens and had no mechanism, gets
one: the addressing hardware receives a magnitude of zero and two surviving
signs, and resolves that to the corner those signs name. #51 and #40 are then
one phenomenon from two directions -- #40's input is a literal zero from a black
normal map, #51's a triple too small to represent.

### What this does *not* establish

- **The bit width is not measured.** The bound is under an 8-bit half-quantum
  and over a 10-bit one, so "eight or fewer fractional bits" is what the
  evidence is consistent with, not a width read off silicon.
- **Which positive face is selected is not determined by colour** -- see above.
  A fix that picks the wrong positive face would score identically here, so the
  face must be settled some other way before one is written.
- **Whether the underflow happens to the direction or to the face coordinate**
  is not separated. Both routes end at the same texel.
- **This is not a fix and has not been run.** It is a reading of goldens already
  on disk, and it constrains an implementation rather than being one.

### Which two bits select the corner: measured, and not the two that were recorded

The mechanism above leaves one thing open -- of the three dot signs, which
select the corner. It is settled by the unsigned dotmaps, from the goldens,
and the answer corrects the rule recorded in `nv2a_issues.toml`.

On a face the projection is `(s,t) = (-z/x, -y/x)`. **Both coordinates carry
`sign(x)`.** So flipping `sign(x)` alone flips `s` and `t` together and maps
each corner to its *diagonal* opposite. The prediction of "the unsigned
dotmaps cannot flip `sign(dot_{i-2})`" is therefore that they reach a
**diagonal pair** of corners.

They do not. The two corners those captures reach are an **edge pair sharing
an `s` extreme**, and that holds on all three positive faces, so it does not
depend on the face being unidentifiable from colour:

| face | the two corners reached | shape |
|---|---|---|
| +X | (63,0), (63,63) | edge pair, `s` pinned, `t` free |
| +Y | (0,0), (0,63) | edge pair, `s` pinned, `t` free |
| +Z | (0,0), (0,63) | edge pair, `s` pinned, `t` free |

The diagonal pairs, for contrast, would have been `{#00FF00,#FF0000}` or
`{#0000FF,#FFFFFF}` -- and the goldens hold neither combination.

So what is pinned is **`s` itself**, the product `sign(z)*sign(x)`, and what
varies is **`t`**, the product `sign(y)*sign(x)`. The corner is selected by
those two products, not by two of the three signs taken alone.

This needs no separate addressing rule. It is the ordinary cube-face
projection applied to a direction that has lost its magnitude and kept its
signs -- which is the mechanism of the previous section, and the reason that
mechanism is worth more than the rule it explains: the rule had to name two
bits and named the wrong ones; the mechanism hands you the right ones for
free.

**Still not measured:** the threshold at which the magnitude underflows. Every
pixel of every affected capture is below it, so a fix using an 8-bit quantum
and one using a 6-bit quantum score identically on this corpus. The corpus can
confirm the rule and cannot calibrate the threshold; that needs a capture whose
dot magnitudes straddle it, and none exists here.

#### The white column was text, and checking it nearly cost the right answer

The corner counts recorded in `nv2a_issues.toml` carried a `W` column that was
non-zero on the three *unsigned* dotmaps -- 1042, 1170, 1376 -- which flatly
contradicts the two-corner reading above. Taken at face value it says those
captures reach three corners, and three corners cannot come from two sign bits
at all: two bits give four, or two if one is pinned, never three. That would
have falsified not just the edge-pair argument but the whole mechanism.

It is white **title text**. Each capture draws its own name across the top of
the frame, and those pixels are exactly `#FFFFFF`:

| capture | W as recorded | W over `y >= 45` | white in the `y < 45` banner |
|---|---:|---:|---:|
| `0to1` | 1042 | **0** | 1042 |
| `HiLo_1` | 1170 | **0** | 1170 |
| `HiLoHemi` | 1376 | **0** | 1376 |
| `-1to1` | 15220 | 14178 | 1042 |
| `-1to1D3D` | 16594 | 15262 | 1332 |
| `-1to1GL` | 15282 | 14076 | 1206 |

The give-away was shape, not count: on the unsigned captures the white pixels
occupy `x[20..146] y[25..40]` and are only 43% interior -- a thin strip of
glyph strokes. On `-1to1` white spans `x[20..506] y[25..318]` at 87% interior,
which is a solid region of cube. `R`, `B` and `G` are unaffected, since white
text on a black banner cannot contribute to them.

Two things worth keeping from this:

- **Every `W` in the old table was wrong, including the signed ones**, each by
  its own capture's glyph count. A fix scored against those targets would have
  been tuned to reproduce text.
- The near-miss is the same failure as everywhere else in this note. The
  two-corner reading was taken from the *differing* pixels, which is a biased
  sample: it silently drops every pixel where we already agree with the golden.
  Re-deriving it over the whole image was the right instinct and produced a
  contradiction -- and the contradiction was in the instrument, not the claim.
  A count of a colour is not a count of a texel.

## The prediction was registered, the arm was run, and it FAILED

`docs/testing/predictions/dot-str-3d-underflow-corner.json`, registered
04:07Z against `2f14403e`, before the arm existed. The arm: the diff applied
to the peer tip `0f708c8d`, built (`NINJA_EXIT=0`, 63 compile steps, links,
no new warnings), GLSL compiled clean at runtime, `iso_cube.iso` run, 78
captures.

**Verdict: FAIL on both substantive legs.**

| leg | predicted | measured |
|---|---|---|
| 1. positive-face corners only | no negative-face colour | holds, `neg=0` — but see below |
| 2. no interior texel | none | holds — but see below |
| 3. unsigned reach exactly 2, edge pair | 2 | **4, on all three** |
| 4. corner counts over `y>=45` | `0to1` B/R/G/W 28114/0/28795/0 | **3394/25471/8002/20042** |
| `expect_counts` | better 6, worse 0 | **better 2, worse 4** |

`-1to1` 49k -> 38,290 and `-1to1GL` -> 38,511 improved; `0to1`, `HiLo_1`,
`HiLoHemi` went to 56,908-56,909, which is essentially every cube pixel wrong,
and `-1to1D3D` to 54,558.

### Legs 1 and 2 were not falsifiers and I should not have written them

Both describe what *our own output* does after a change that forces exactly
that. A fix that substitutes a positive-face corner direction cannot produce a
negative face or an interior texel, so neither leg could ever have failed. They
read like measurements and are tautologies. **A falsifier your own change
guarantees is not a falsifier** -- the same shape as scoring a fix against
targets contaminated by the thing it draws.

### What the failure says, which is more than "wrong"

The corner confusion matrix, ours against the golden's, over the 56,909 cube
pixels:

`0to1` -- golden reaches only B and G:

| golden | our R | our B | our W | our G |
|---|---:|---:|---:|---:|
| B (28,114) | 0 | 70 | **20,042** | **8,002** |
| G (28,795) | **25,471** | **3,324** | 0 | 0 |

Exact agreement 0.1%, but the best permutation would give **80%** against 25%
for chance. So the mechanism carries real information and the *mapping* is
wrong -- it is not noise.

Read the rows. Each golden corner maps onto a pair of ours differing in
exactly **one** coordinate: golden B goes to our W and G, which share `t` and
differ in `s`; golden G goes to our R and B, likewise. So **one of our two
bits tracks the golden and the other varies spuriously**. And the direction is
inverted: golden B lands on our `t=63`, golden G on our `t=0`.

Meanwhile the golden for these captures pins `s=63` and varies `t`. We pin
nothing and vary both.

So two separate errors, not one: **one product is inverted, and the coordinate
the golden pins is being driven from a sign that is noise here.** That is a
sharper statement of what is wrong than the mechanism had before the arm ran,
and it is what the arm bought.

### What survives

The underflow-and-signs mechanism is not refuted by this: 80% recoverable by a
fixed permutation is not what a wrong mechanism looks like. What is refuted is
the specific claim that the corner is `(-z/x, -y/x)` of the sign-only
direction with `x` forced positive. The next attempt needs its own registered
prediction; this one is spent.

### The A arm, and what it corrects in the verdict above

The first pass at judging this checked the `must_not_move` set against the
*goldens* and reported 64 of 72 non-zero. **That was the wrong instrument.**
`must_not_move` means unchanged between arm A and arm B; those 64 are the known
residuals that survive on both arms. Judging a must-not-move against a golden
cannot distinguish "my change moved it" from "it was already wrong", which is
the entire question.

With the A arm actually run (`0f708c8d` unmodified, same disc, same harness):

**`must_not_move`: 72 of 72 held, 0 px moved. PASSES.** So this substitution
does not touch a single capture `#40` fixed, and the two changes are not
fighting over the same pixels -- they are in different modes and the measurement
confirms it.

| capture | A vs golden | B vs golden | delta |
|---|---:|---:|---:|
| `-1to1` | 49,541 | 38,290 | **−11,251** |
| `-1to1GL` | 49,449 | 38,511 | **−10,938** |
| `-1to1D3D` | 50,033 | 54,558 | +4,525 |
| `0to1` | 48,597 | 56,839 | +8,242 |
| `HiLoHemi` | 50,526 | 56,908 | +6,382 |
| `HiLo_1` | 48,031 | 56,908 | +8,877 |
| **total** | **296,177** | 302,014 | **+5,837** |

The A-arm total reproduces the 296,180 quoted for this defect to within 3 px,
so the baseline here is the same baseline.

### Why "gate it on the triple being zero" does not explain the split

The natural reading of two-better-four-worse is a right mechanism firing where
it does not belong, gated on the dot mapping. The numbers do not support that
reading:

- `0to1` (`DOTMAP_ZERO_TO_ONE`, identity) and `-1to1` (`sign3`) **both** carry a
  zero texel to exactly zero. `-1to1` improved by 11,251 and `0to1` got worse by
  8,242. A gate on "the triple is actually zero" cannot separate them, because
  it treats them the same.
- The split is not signed versus unsigned either: `-1to1D3D` is signed and got
  *worse*.

What the magnitudes say instead. With a near-uniform four-corner golden, a
substitution that lands on corners with no correlation to silicon would sit near
75% wrong, about 42,700 of 56,909. `-1to1` at 38,290 is better than chance;
`-1to1D3D` at 54,558 is **worse than chance**, which means it is not
uncorrelated but systematically *anti*-correlated -- a permutation error, and a
different one per dotmap.

That is consistent with the one thing the dotmaps demonstrably do differently:
they change the *signs* the dots arrive with. `MINUS1_TO_1_D3D` carries a zero
texel to −1.008 where `_GL` carries it to +0.0039 -- opposite signs from the
same input. A single fixed sign-to-corner mapping cannot be right across six
mappings that disagree about sign, and forcing `x = +1` discards `sign(x)`
rather than folding it in correctly.

So the next attempt is not a gate. It is the mapping, per dotmap, and it needs
its own registration.

### Pixel count and mechanism fit are anti-correlated, so do not bank the two that improved

The obvious next move after the failed arm is to gate the substitution to the
two captures it improved and bank −22,189 px. The corner confusion matrix says
that would keep the worst evidence and throw away the best.

Per capture on arm B: direct corner agreement, and agreement under the single
best fixed permutation of the four corners (chance is 25%):

| capture | delta px | direct | best permutation |
|---|---:|---:|---:|
| `-1to1` | **−11,251** | 32.7% | 64.4% |
| `-1to1GL` | **−10,938** | 32.3% | 64.5% |
| `-1to1D3D` | +4,525 | 4.1% | **91.8%** |
| `0to1` | +8,242 | 0.1% | **80.0%** |
| `HiLo_1` | +8,877 | 0.0% | 75.6% |
| `HiLoHemi` | +6,382 | 0.0% | 66.4% |

**The two captures that improved fit the mechanism worst.** `-1to1D3D`
regressed by 4,525 px and is 91.8% correct under one relabelling -- nearly
right, with the corner labels permuted. `-1to1` improved by 11,251 px and is
64% at best.

The reason is the golden's own shape, not the fix. `-1to1`'s golden is
near-uniform over four corners, so a wrong-but-uniform output collects ~33% by
coincidence and the pixel count flatters it. `0to1`'s golden holds two corners,
so a four-corner output is catastrophic in pixels even when the underlying rule
is one permutation from correct. **A pixel count is a bad judge of this defect,
and gating on it would have selected against the mechanism.**

### The permutations, and why they are not yet a fix

Reading the best permutation as a transform of the face coordinates:

| capture | fit | implied |
|---|---:|---|
| `0to1`, `HiLo_1` | 80.0%, 75.6% | `s` flip **and** `t` flip |
| `-1to1`, `-1to1GL` | 64.4%, 64.5% | `t` flip only |
| `-1to1D3D` | 91.8% | `s` flip, `t` mixed |
| `HiLoHemi` | 66.4% | mixed |

There is real structure here -- every row is far above chance, and two rows
agree exactly. But **no permutation reaches 100% on any capture**, so no single
relabelling fully explains even one, and the transforms differ by dotmap.

Fitting six permutations to six captures is six free parameters for six
observations: it would score beautifully and mean nothing. That is the same
trap as a threshold tuned until the counts match. **The corner mapping has to
be derived from what each dotmap does to the dots' signs, not fitted per
capture**, and until it is derived there is nothing here worth landing -- not
even the two captures that improved.

### Held-out permutation test: it is per-mapping, and the residue is a region

Registered as `dot-str-3d-corner-permutation.json` (sha256 `a0e3181e...`,
`a4237834`) before any of it was computed, because quoting agreement under a
permutation fitted to the same capture cannot fail -- the permutation is chosen
to maximise the number being quoted. Fit on `-1to1` alone, applied unchanged to
the other five.

`P` fitted on `-1to1`: `R->R, B->G, W->W, G->B`.

| capture | under `P` | its own best | predicted | |
|---|---:|---:|---|---|
| `-1to1` | 64.4% | 64.4% | >=60% | holds *(tautological: this is the fit capture)* |
| `-1to1GL` | **64.5%** | 64.5% | >=60% | **holds -- transfers exactly** |
| `-1to1D3D` | 8.2% | 91.8% | <40% | holds |
| `0to1` | 19.9% | 80.0% | <40% | holds |
| `HiLo_1` | 24.4% | 75.6% | <40% | holds |
| `HiLoHemi` | 51.7% | 66.4% | <40% | **fails** |

**Five of six legs hold, and the sixth lands in the 40-60% band the
registration declared undetermined in advance** -- so the prediction told me
how to treat `HiLoHemi` before it was measured, rather than after.

**It is not one permutation.** `P` transfers to exactly one capture, `-1to1GL`,
reproducing its own best figure to a tenth of a point -- the same transform
family, as the earlier table implied. On everything else it collapses, most
sharply on `-1to1D3D`, which goes from 91.8% under its own permutation to 8.2%
under `P`. The corner encoding therefore depends on the dot mapping, and the
fix is not a transposed constant.

The `-1to1` row is quoted only for completeness. It is the capture `P` was
fitted on, so its agreement is guaranteed and carries no information; the
transfer evidence is `-1to1GL`.

### The residue is a region, not noise

Second and independent: after each capture's *own* best permutation, is what
remains structured or scattered? Measured as the mean number of 4-neighbours a
residue pixel has that are also residue, against the value expected if the same
count were scattered at random over the cube region.

| capture | fit | residue px | observed | random | ratio |
|---|---:|---:|---:|---:|---:|
| `-1to1D3D` | 91.8% | 4,639 | 3.66 | 0.33 | **11.2x** |
| `0to1` | 80.0% | 11,396 | 3.86 | 0.80 | **4.8x** |
| `HiLo_1` | 75.6% | 13,865 | 3.89 | 0.97 | **4.0x** |
| `-1to1` | 64.4% | 20,264 | 3.85 | 1.42 | **2.7x** |

Predicted >2x; measured 2.7x to 11.2x. A residue pixel has on average 3.7 to
3.9 of its four neighbours also in the residue -- these are solid regions, not
salt and pepper.

**So the corner rule is exact with a labelling bug and a second, smaller,
spatially coherent rule on top** -- not an approximation that a better
relabelling would finish. Those are different things to chase, and this
distinguishes them. The next question is what that region *is*: whether it
follows a cube, a face boundary, or a silhouette.

### What the residue region follows: it mirrors with the geometry

The region half of the previous section, characterised. `-1to1D3D` is the
specimen -- 91.8% under its own permutation, so its residue is the smallest and
cleanest at 4,639 px.

**It is not a seam.** Only 12.3% of residue pixels sit on a boundary in the
golden's corner field, against a 4.9% base rate over the cube region. Enriched
2.5x, but 88% of it is interior, so this is an area rather than an edge effect
-- consistent with the 3.66 mean neighbour count.

**It is 16 components, and the large ones come in pairs.** The cube region
itself is exactly two blobs, 28,455 px at x[117..314] and 28,454 px at
x[325..522] -- the two cubes, the same size to one pixel. The residue's six
largest components pair off across them at matching `y`:

| left cube | right cube |
|---|---|
| 1,058 px x[130..197] y[103..205] | 1,101 px x[442..511] y[103..209] |
| 759 px x[264..314] y[115..179] | 814 px x[325..379] y[112..180] |
| 427 px x[190..244] y[282..300] | 465 px x[394..451] y[281..300] |

**And the pairing is a reflection, not a translation.** Reflecting the right
cube's residue onto the left:

| capture | residue L / R | IoU mirrored | IoU translated |
|---|---|---:|---:|
| `-1to1D3D` | 2,251 / 2,388 | **0.936** | 0.044 |
| `HiLo_1` | 10,045 / 3,820 | 0.378 | 0.182 |
| `0to1` | 11,347 / 49 | 0.004 | 0.004 |

`-1to1D3D`'s residue is a 94% mirror image of itself. A region that reflects
with the geometry is a function of the **surface direction**, not of screen
position, not of texel address, and not of noise -- which is what a second rule
on top of the corner rule would look like.

`0to1` is the counter-shape and is informative on its own: its residue is
almost entirely on the **left cube alone**, 11,347 against 49. So whatever the
second rule is, the identity dot mapping reaches it on one cube and not the
other, while `_D3D` reaches it symmetrically on both.

That is the boundary the region was worth chasing for. It says the remaining
error is directional, and it gives two shapes -- symmetric and one-sided -- that
any candidate has to produce from the same geometry under different dot
mappings.

**Still not a fix, and still not fitted.** No permutation table has been
written into the shader and none should be until this second rule is named.

### The second rule, named: the residue is exactly `sign(dot_3) >= 0`

The region above is directional, and this is the direction. A probe replaced the
`DOT_STR_3D` cube fetch with the three dot **signs** encoded as a colour, on the
same base the arms were built from (`0f708c8d`), so the pixels correspond.

**The probe validated itself before it was believed.** `t_i` passes through the
combiners only if the capture holds nothing but the sign combinations:
`-1to1D3D` came back with exactly 8 colours plus the scene background, and
`0to1` with exactly 4. If the combiner had transformed the value there would
have been more.

The 4 that `0to1` reaches are `#FFFF00`, `#FF0000`, `#FF00FF`, `#FFFFFF` --
**every one with the red channel set**, so `sign(dot_1) >= 0` throughout. That is
the recorded claim "the three unsigned dotmaps cannot flip `sign(dot_{i-2})`",
measured directly rather than inferred from colour counts.

Cross-tabulating the sign class against the residue:

| capture | sign classes with **no** residue | classes that are **all** residue |
|---|---|---|
| `-1to1D3D` | `---` 11,880 · `x--` 11,268 · `-y-` 14,753 · `xy-` 14,369 | `--z` 1,842 · `x-z` 1,825 · `-yz` 509 · `xyz` 463 |
| `0to1` | `x--` 20,042 · `xy-` 25,471 | `x-z` 8,002 · `xyz` 3,394 |
| `HiLo_1` | `x--` 18,340 · `xy-` 24,704 | `x-z` 10,046 · `xyz` 3,819 |

**0.0% and 100.0%, no exceptions, on three dot mappings with different sign
distributions.** The totals reproduce the residue counts exactly: 4,639,
11,396, 13,865.

So the predicate is **`sign(dot_3)`** -- the third component, which
`nv2a_issues.toml` records as "the third component selects nothing". It selects
the entire residue.

It also explains both shapes the region presented. `0to1`'s residue being
one-sided (11,347 left against 49 right) and `-1to1D3D`'s being a 0.936 mirror
are the same rule seen through different dot mappings: the `z >= 0` set happens
to fall on one cube under the identity mapping and symmetrically under `_D3D`.
One predicate, no per-capture parameter, both shapes.

### What this is a derivation *of*

Stated carefully, because the substitution under test uses `sign(z)` itself.
`dotSTR3dSaturate()` builds `vec3(1.0, s.y*s.x*k, s.z*s.x*k)`, so its output
does depend on the third sign. What the 100/0 split establishes is that **the
error is confined entirely to the `sign(dot_3)` term** -- there is no residue
anywhere `z < 0`, across three mappings. That is a perfect localisation of the
defect in the candidate rule, and it is what the next attempt has to change.

It is *not* yet a statement of silicon's rule. Four corners cannot be selected
by three bits without two combinations sharing a corner, so the third bit is
doing something the corner model does not have a place for -- selecting a face,
or flipping a coordinate. **Naming that is the remaining work**, and it is now a
question about one bit rather than about six permutations.
