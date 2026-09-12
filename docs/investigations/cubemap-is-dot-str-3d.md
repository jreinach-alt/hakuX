# `Texture_cubemap` is one texture shader mode, and `Line_width` is not

Two board entries put through the same split -- per capture, with the one-step
share and the worst channel error rather than channel counts alone. They come
out opposite ways, which is the point of doing it.

> **Retraction, 2026-09-12.** The first version of the `Texture_cubemap`
> section below was measured on a build that predates `ad1caa07`, and every
> number and mechanism in it was wrong for the same reason: the suite was
> rendering a texture from a *different test*. What follows replaces it. The
> `Line_width` section is unaffected and stands as written.

## The suite had two defects, and the first one hid the second

`ad1caa07` ("notice when the guest rewrites a bound texture") landed because
the texture bind loop only runs when a texture register or `texture_vram_gen`
changes, and a CPU rewrite of the texels changes neither. `Texture_cubemap`
is the worst case for that: **every test in the suite writes a new cubemap to
the same address with the same registers.** `Cubemap_q-0.0` sorts first and
writes a checkerboard; the other 71 tests wrote noise or a radial gradient
into the same bytes and got the checkerboard back.

That is measurable directly, because the three generators use disjoint
palettes. Classifying every pixel of every capture in the two cubemap suites
by which generator could have produced it:

| | captures | total differing px | `DotSTR3D_*` | the other 71 |
|---|---:|---:|---:|---:|
| before `ad1caa07` | 78 | 2,565,441 | 341,454 | 2,223,987 |
| after | 78 | **320,535** | 315,891 | **4,644** |

Before the fix, **all 78 captures painted the cube from the checkerboard
palette, 56,909 px each, in tests where silicon uses none of it.** After it,
71 of 78 are within 178 px of the golden and six of the remaining seven are
`DotSTR3D_*`. The suite went from 2.57M differing pixels to 320K, and 98.6% of
what is left is one texture shader mode.

The lesson is the one the tracker keeps relearning: a measurement taken
through a known-broken stage measures the broken stage. Both negatives the
earlier version of this note recorded ("`samplerCube` moves zero captures",
"`remapCubeTo2D` moves zero captures") were taken through that stage and are
**void** -- no probe to the sampler could have moved a suite that was not
sampling the test's texture. The inferences drawn from them, that
`tex_cubemap[3]` is false and `dim_tex[3]` is 3, are withdrawn;
`texture_cubemap_tests.cpp` calls `stage.SetCubemapEnable()` on stage 3
outright.

## What the texture actually is

Also wrong in the first version: "the 3D texture here is the eight corners of
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

The reading that survives every check below:

> `PS_TEXTUREMODES_DOT_STR_3D` addresses its texture **volumetrically**, with
> the raw `(dot_{i-2}, dot_{i-1}, dot_i)` triple and no normalisation. Those
> dot products are of a constant matrix row against a normal, far outside
> `[0,1]`, so every axis saturates at its wrap mode -- `CLAMP_TO_EDGE` here,
> which is `TextureStage`'s default on all three axes and the test never
> changes it. The fetched texel is therefore a **corner**, chosen by
> `sign(dot_{i-2})` and `sign(dot_{i-1})`, and `r` selects nothing because the
> texture's declared depth is 1.

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
`GenerateCubemap` writes, and depth-1 volumetric addressing lands there, but
the pixels alone only say "a positive face, at its corners".

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
