# `Texture_cubemap` is one texture shader mode, and `Line_width` is not

Two board entries put through the same split -- per capture, with the one-step
share and the worst channel error rather than channel counts alone. They come
out opposite ways, which is the point of doing it.

## `Texture_cubemap`: 98.2% is `DOT_STR_3D`

72 captures, 504,372 channels, 504,163 of them structural.

| capture | channels | structural | one-step | max |
|---|---:|---:|---:|---:|
| `DotSTR3D_HiLoHemi` | 88,392 | 88,392 | 0.0% | 255 |
| `DotSTR3D_-1to1D3D` | 86,055 | 86,055 | 0.0% | 255 |
| `DotSTR3D_-1to1GL` | 84,550 | 84,550 | 0.0% | 255 |
| `DotSTR3D_-1to1` | 84,531 | 84,531 | 0.0% | 255 |
| `DotSTR3D_0to1` | 80,292 | 80,292 | 0.0% | 255 |
| `DotSTR3D_HiLo_1` | 70,032 | 70,032 | 0.0% | 255 |
| the other 66 captures | 9,311 | 9,311 | | 221 |

**80% of the structural error is in five of seventy-two captures**, and
494,852 of 504,163 is the six `DotSTR3D_*` captures -- every dotmap variant of
`PS_TEXTUREMODES_DOT_STR_3D`. The `DotReflect*` captures use the same dotmap
functions and sit at 300 to 500 channels each, so this is not the dot mapping.
It is that one texture mode.

### What it looks like

The 3D texture here is the eight corners of the colour cube, so the rendered
colours name which texels were sampled:

| capture | ours | golden |
|---|---|---|
| `DotSTR3D_-1to1` | 8 distinct colours | **4** |
| `DotSTR3D_0to1` | 8 distinct colours | **2** |

`(255,0,255)`, `(255,255,0)`, `(0,255,255)` and the rest -- we reach every
corner of the volume; silicon reaches half of them, or on `0to1` just two,
which means its coordinate varies along a single axis where ours varies along
three.

So the defect is the **range of the coordinate** `DOT_STR_3D` builds, not the
sampling or the dot products themselves. `psh.c` assembles it as
`vec3(dot_{i-2}, dot_{i-1}, dot_i)` and samples with it; two of those three
components are not varying on hardware the way they vary here. That is a
bounded question with a six-capture oracle, and it is the whole of this board
entry.

### What it is not: two measured negatives

The test looks like a cubemap case. It calls
`GenerateCubemap(host_.GetTextureMemoryForStage(3), ...)`, sets
`STAGE_2D_PROJECTIVE, STAGE_DOT_PRODUCT, STAGE_DOT_PRODUCT, STAGE_DOT_STR_3D`,
and its own comment says "the final value is a lookup from the cube map in
t3". Meanwhile `psh.c` gives `DOT_STR_3D` a sampler from the same case as
`PROJECT3D`, which never returns `samplerCube` however the stage is flagged,
where every cube mode checks `tex_cubemap[i]`. And `DOT_STR_CUBE`, which
passes in this suite, remaps the direction with `remapCubeTo2D` when the
texture is not flagged as a cubemap, where `DOT_STR_3D` truncates it to `.xy`.

Both readings are wrong, and the runs say so:

| change | `Texture_cubemap` | `Texture_2D_as_cubemap` |
|---|---:|---:|
| return `samplerCube` when `tex_cubemap[i]` | **0 captures moved** | 0 |
| `remapCubeTo2D` fallback, mirroring `DOT_STR_CUBE` | **0 captures moved** | **+59,142** |

The first moving nothing means `tex_cubemap[3]` is false here. The second
moving nothing in this suite means `dim_tex[3]` is **3** -- a genuine volume
texture, so the `dim == 2` branch never fired -- and it broke `DotSTR3D_Bad2D`
in the sibling suite, which was **exact** at zero differing channels before.
That capture is the proof that truncating to `.xy` is correct against a real
2D texture.

So `DOT_STR_3D` here is a real `sampler3D` lookup with a real volume texture,
and the question is narrower than it looked: what range does silicon's
coordinate have, and what does it do outside `[0,1]`. Both probes reverted.

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
