# Prediction: the M1/M2/L8 remediation of DOT_STR_3D is inert on every disc we can build

Registered 2026-09-18 after the baseline runs and BEFORE the edited generator was
built or run. Change: `glsl/psh.c`, the `PS_TEXTUREMODES_DOT_STR_3D` cube arm --
signs read from the raw dot products and the border remap applied to the
synthesised direction (M1), `textureLod(..., 0.0)` (M2), the constant moved into
the arm and the global `#define` dropped (L8). Baseline binary
`0.4.0-j1-371-g9d8a737d` plus the committed N1-N6 edits; `iso_cube` under both
renderers, 78 captures each; GL and Vulkan byte-identical on 78 of 78.

## Why inert, by construction

- M1 changes output only when a bordered cubemap sits on a DOT_STR_3D stage.
  No disc carries one (`border_logical_size` is zero on every stage of every
  test on `iso_cube`), so `apply_border_adjustment()` emits nothing either way.
- M2 changes output only when the cubemap has more than one level. The test
  stage defaults to `mipmap_levels_{1}` and never calls `SetMipMapLevels`, so
  `textureLod(..., 0.0)` and `texture(...)` select the same texels.
- L8 moves a constant with the same value.

**So every capture on `iso_cube` and `iso_surf1` must be byte-identical to its
baseline under both renderers**, with one named exception: `Surface_pitch::Swizzle`
under OpenGL, the guest/pgraph race, which may move within its 13,160-15,360 band.

## Kill conditions

1. Any `Texture_cubemap` or `Texture_2D_as_cubemap` capture not byte-identical to
   its baseline, either renderer: the edit changed semantics where the argument
   says it cannot. Then the argument is wrong and the finding is the change.
2. Any `iso_surf1` capture other than `Surface_pitch::Swizzle` under GL moving.
3. `psh_differ` refusing to build or a baseline no longer generating.

## Baseline values, both renderers (differing px vs golden)

| renderer | suite | capture | px |
|---|---|---|---:|
| GL | `Texture_2D_as_cubemap` | `Cubemap_Bad2D` | 0 |
| GL | `Texture_2D_as_cubemap` | `DotReflectDiffuse_Bad2D` | 116 |
| GL | `Texture_2D_as_cubemap` | `DotReflectSpecConst_Bad2D` | 15 |
| GL | `Texture_2D_as_cubemap` | `DotReflectSpec_Bad2D` | 30 |
| GL | `Texture_2D_as_cubemap` | `DotSTR3D_Bad2D` | 0 |
| GL | `Texture_2D_as_cubemap` | `DotSTRCube_Bad2D` | 101 |
| GL | `Texture_cubemap` | `DotSTR3D_-1to1` | 73 |
| GL | `Texture_cubemap` | `DotSTR3D_-1to1D3D` | 0 |
| GL | `Texture_cubemap` | `DotSTR3D_-1to1GL` | 4 |
| GL | `Texture_cubemap` | `DotSTR3D_0to1` | 70 |
| GL | `Texture_cubemap` | `DotSTR3D_HiLoHemi` | 2 |
| GL | `Texture_cubemap` | `DotSTR3D_HiLo_1` | 1 |
| Vulkan | `Texture_2D_as_cubemap` | `Cubemap_Bad2D` | 0 |
| Vulkan | `Texture_2D_as_cubemap` | `DotReflectDiffuse_Bad2D` | 116 |
| Vulkan | `Texture_2D_as_cubemap` | `DotReflectSpecConst_Bad2D` | 15 |
| Vulkan | `Texture_2D_as_cubemap` | `DotReflectSpec_Bad2D` | 30 |
| Vulkan | `Texture_2D_as_cubemap` | `DotSTR3D_Bad2D` | 0 |
| Vulkan | `Texture_2D_as_cubemap` | `DotSTRCube_Bad2D` | 101 |
| Vulkan | `Texture_cubemap` | `DotSTR3D_-1to1` | 73 |
| Vulkan | `Texture_cubemap` | `DotSTR3D_-1to1D3D` | 0 |
| Vulkan | `Texture_cubemap` | `DotSTR3D_-1to1GL` | 4 |
| Vulkan | `Texture_cubemap` | `DotSTR3D_0to1` | 70 |
| Vulkan | `Texture_cubemap` | `DotSTR3D_HiLoHemi` | 2 |
| Vulkan | `Texture_cubemap` | `DotSTR3D_HiLo_1` | 1 |

Not predicted: anything about the bordered-cubemap path or a mipmapped cube,
which no capture reaches. Those two paths are correct by construction and unmeasured,
and the commit says so.
