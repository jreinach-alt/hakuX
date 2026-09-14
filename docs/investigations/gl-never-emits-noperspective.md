# The GL renderer never emits `noperspective`, and one line says so

`Texture_perspective` splits perfectly on one bit. Every capture where the
OpenGL and Vulkan renderers disagree is a `pers_n` case — `SET_CONTROL0`
texture perspective **off**. Every `pers_y` case is byte-identical between
them.

| capture | OpenGL | Vulkan |
|---|---:|---:|
| `tex_tex_pers_n_bitri` | 60,290 | 4,283 |
| `tex_tex_pers_n_quad` | 56,639 | 1,107 |
| `tex_diff_pers_n_bitri` | 199,975 | 177,149 |
| `tex_diff_pers_n_quad` | 199,933 | 184,281 |
| `TexPerspective_Textured` | 9,014 | 1 |
| `TexPerspective_Untextured` | 29,044 | 27,988 |
| `tex_tex_pers_y_bitri` | 48 | 48 |
| `tex_tex_pers_y_quad` | 22 | 22 |
| `tex_diff_pers_y_bitri` | 184,210 | 184,210 |
| `tex_diff_pers_y_quad` | 181,998 | 181,998 |

A split that clean is a state bit, not an accumulation of small differences.

## The line

`glsl/common.c`, in `pgraph_glsl_get_vtx_header()`:

```c
/*
 * SET_CONTROL0 can turn texture perspective off, and the hardware then
 * interpolates colours and texture coordinates linearly in screen
 * space (Texture_perspective: tex_*_pers_n).  GLSL's noperspective is
 * exactly that; only the Vulkan path gets it, GLES would need
 * GL_NV_shader_noperspective_interpolation.
 */
const char *smooth_s = (noperspective && location) ? "noperspective " : "";
```

All four call sites — `psh.c:1488`, `geom.c:160`, `geom.c:162`, `vsh.c:292`
— pass `opts.vulkan` as `location`. So the guard reads, literally, *Vulkan
only*, and the comment says as much.

The justification is about GLES. But `location` is not a GLES test: it asks
whether the shader uses explicit `layout(location = N)` qualifiers, which
Vulkan requires and desktop GL does not. **Desktop GL has `noperspective`
as a core GLSL 1.30 keyword and needs no extension at all.** The condition
conflates *uses explicit locations* with *can spell the qualifier*, and
desktop GL falls in the gap.

## Measured

A probe dropping the `location` term, so desktop GL emits the qualifier.
Against the head at `c2fb5594`, 236 captures, prediction registered first
in `docs/testing/predictions/issue-texperspective-gl-noperspective.json`:

```
BETTER  Texture_perspective::tex_tex_pers_n_bitri            60,290 ->   4,283
BETTER  Texture_perspective::tex_tex_pers_n_quad             56,639 ->   1,107
BETTER  Texture_perspective::tex_diff_pers_n_bitri          199,975 -> 177,149
BETTER  Texture_perspective::tex_diff_pers_n_quad           199,933 -> 184,281
BETTER  Texture_perspective_enable::TexPerspective_Textured    9,014 ->       1
BETTER  Texture_perspective_enable::TexPerspective_Untextured 29,044 ->  27,988
WORSE   Surface_pitch::Swizzle                               14,848 ->  15,360
```

**6 better, 1 worse, 159,574 px.** All five registered exact values landed
exactly on Vulkan's, and the sixth capture — which was not registered —
landed on Vulkan's too. The four `pers_y` captures did not move, as
registered. Vulkan 236/236 byte-identical, as it must be: for Vulkan
`location` is true, so the edit is a no-op there.

**One registered leg failed.** Falsifier 3 said nothing else on the disc
would move, and `Surface_pitch::Swizzle` moved by 512 px in the wrong
direction — back to the value it held before #70's clip fix took it the
other way. That capture has now moved in four separate arms this session,
which is its own small unexplained thing and is recorded rather than
explained.

## Why this is not the shipping change

Dropping `location` reaches Android GLES too, where the qualifier really
does need `GL_NV_shader_noperspective_interpolation` and a shader that uses
it unguarded may fail to compile. The real fix passes the `gles` flag this
file already knows about — `pgraph_glsl_append_version(out, vulkan, gles,
gles_version)` takes it three lines away — and emits the qualifier for
desktop GL, for Vulkan, and for GLES only behind the extension.

That is one extra argument at four call sites, in `glsl/psh.c`,
`glsl/geom.c` and `glsl/vsh.c`. All three are held by other lanes, so the
probe was run on this lane's own clone with the edit reverted, and the
measurement above is offered as the price of a grant rather than taken as
permission to make it.
