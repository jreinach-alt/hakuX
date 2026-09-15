# A colour surface sampled as a texture is decoded twice, and we only do it once

Scope: Vulkan renderer. Found while working issue #14 (`Blend tests`), but the
defect is in the surface-to-texture path, so it is issue #4's neighbourhood, not
the blend unit's.

## The one-line version

**VERIFIED.** The texture unit decodes memory using the format set on the
*texture stage*, and it does that even when the memory it reads is a colour
surface pgraph rendered a moment earlier. We bind the surface's own
`VkImageView` instead, which carries the *surface's* host format and an identity
component mapping, so the declared texture format is ignored. A surface written
as `A8R8G8B8` and sampled as `A8B8G8R8` therefore comes back with red and blue
in the order they were written, where hardware re-reads the bytes and swaps
them.

`hw/xbox/nv2a/pgraph/vk/texture.c:1191` `check_surface_to_texture_compatiblity()`
compared only `host_bytes_per_pixel`, so `B8G8R8A8_UNORM` (surface `A8R8G8B8`)
and `R8G8B8A8_UNORM` (texture `SZ_A8B8G8R8`) were accepted as interchangeable —
4 bytes each.

## Why the blend captures show it

`Blend tests`' 105 `#spot_*` captures each render a 5x3 grid into a 512x512
render target declared `SCF_A8R8G8B8` (`blend_tests.cpp:175`), then blit it to
screen through texture stage 1 declared `SZ_A8B8G8R8`
(`blend_tests.cpp:124`, in `RenderTexturedQuad`). Every pixel inside the
blitted region goes through the mismatched decode.

## The trap that nearly inverted the conclusion

**VERIFIED.** `NV097_SET_DIFFUSE_COLOR4I`, which is what `SetDiffuse(uint32_t)`
writes (`pbkitplusplus/src/nv2astate.cpp:647`), packs **ABGR** — red in the low
byte — not ARGB. `ZPass_pixel_count/ZPass.png` pins it: `SetDiffuse(0xFF777733)`
renders as `(51, 119, 119)` on silicon, which is `R=0x33, G=0x77, B=0x77`. Read
as ARGB it would be `(119, 119, 51)`.

Read with the wrong convention, `blend_tests.cpp`'s `DrawColorStack` colour
`0xDDDD0000` looks like red, hardware's capture looks like "no swap", and the
whole chain reads backwards: it appears that *we* introduce a swap silicon does
not have. With the right convention `0xDDDD0000` is blue, silicon's red is the
byte reinterpretation, and the direction is the opposite one. Both readings fit
the golden; only the diffuse convention separates them.

## What was checked before believing it

- **`SZ_A8B8G8R8` really is byte order R,G,B,A on silicon.**
  `Texture_perspective_enable/TexPerspective_Textured.png` draws a CPU-written
  checkerboard of the raw dword `0xFF00FFFF` through that format. Silicon
  renders it **yellow** `(255,255,0)` — `R=0xFF, G=0xFF, B=0x00`, the low byte
  first. Our mapping in `vk/constants.h:344` and `gl/constants.h:354` agrees.
- **`Texture_render_target` cannot see this.** Its display quad always resets
  the stage to `SZ_A8R8G8B8` (`texture_render_target_tests.cpp:132`), so all
  five of its 32-bit format goldens are byte-identical to each other. That
  suite's 40/41 failures (issue #4) are a different cause.
- **`Texture_format` cannot see it either.** SDL converts the source image to
  match whatever layout is declared, so the test is self-consistent by
  construction.

## The measurement

An R/B swap applied offline to the blitted region of our captures, against the
75 `#spot_` captures that are not `FUNC_ADD_SIGNED`/`FUNC_REVERSE_SUBTRACT_SIGNED`
(those 30 belong to #43):

| | differing px | exact |
|---|---|---|
| before | 2,843,948 | 1/75 |
| after the offline swap | 518,010 | 16/75 |

81.8% of the residual, and all fifteen `MAX` captures go from 51,360 differing
pixels each to byte-exact — that is, our `VK_BLEND_OP_MAX` mapping was already
right and the channel order was hiding it.

The built fix reproduces the offline prediction pixel for pixel: `#spot_0_ADD`
5,412 and `#spot_0_MIN` 4,950 residual in both.

## The fix

`surface_view_decodes_as_texture()` in `vk/texture.c`: direct-bind only when the
surface's host format equals the texture's host format *and* the texture's
component mapping is identity. Otherwise fall through to
`copy_surface_to_texture()`, which fills the texture's own image bit-for-bit —
the two formats are in the same Vulkan compatibility class, so `vkCmdCopyImage`
does no conversion — and that image carries the declared format and mapping.

The same gate is needed on the "same `draw_time`, reuse the direct view" branch,
which would otherwise hand back the view the miss path had just declined.

## Regression coverage

A disc of the fourteen surface- and texture-path suites — `Blend surface`,
`Color Zeta Disable`, `Color mask blend`, `Color zeta overlap`, `Image blit`,
`Null surface`, `Surface clip`, `Surface format`, `Surface pitch`,
`Texture Framebuffer Blit`, `Texture format`, `Texture perspective`,
`Texture perspective enable`, `Texture render target` — was run at `25d92294`
and again with the fix. All 236 captures are **byte-identical** between the two
runs: 5,945,124 differing pixels against silicon either way, and the same 94
exact. The four suites that share the blend disc (`Specular`, `Specular back`,
`Material color source`, `Lighting spotlight`, 91 captures) are likewise
unchanged.

The gate is narrow by construction: it only diverts a bind where the surface's
host format differs from the texture's, and nothing outside `Blend tests`'
`#spot_` captures does that in the corpus.

| | differing px | exact |
|---|---|---|
| `Blend tests` before | 5,893,287 | 1/105 |
| `Blend tests` after | 3,562,479 | 16/105 |

79 captures better, 0 worse.

## UNRESOLVED

- The component-mapping half of the gate is a **correctness** tightening that
  has no test behind it: `SZ_X8R8G8B8` sampled from an `A8R8G8B8` surface should
  force alpha to one and previously did not. No golden in the corpus exercises
  it, so it is argued from the tables, not measured.
- What remains in `Blend tests` after this — 518,010 px over 75 captures,
  `MIN` uniformly 4,950 per capture regardless of factors — is the actual
  issue #14 material and is not addressed here.
