# lane.x1a7271: #271, X1A7R8G8B8's 7-bit alpha (2026-09-25)

Analysis-only. The code is written and priced but not landed: its three files
are held (`glsl/psh.c` by lane.wbufdepth24 #268, `vk/texture.c` by
lane.texvol283 #289). `glsl/psh.h` is in `[free]` on `origin/board` but still
needs claiming. The hunks are `x1a7-read-side.diff` in this directory,
and they apply cleanly to master `724a0dd868`. **Not compiled**: this host
has no desktop build tree. Re-run everything with:

    python3 docs/lanes/x1a7271/derive_x1a7.py \
        --capture <dispatch result>/captures1      # goldens: ~/goldens/results

## 1. The rule, re-derived rather than taken from #176

`derive_x1a7.py` does not start from PR #176's rules. It enumerates rival
stages of `TestDstAlpha`'s draw sequence (`blend_surface_tests.cpp:492`) and
keeps the combinations that reproduce **every half-swatch of all four
DstAlpha goldens, both rows, in all four channels**. That is 64 halves, and
the framebuffer alpha is included because `score_sweep.py` counts alpha. #176
checked 32 halves, R channel only. Every golden half is a single flat RGBA.

| stage | survivors | refuted |
|---|---|---|
| blend-off write, 8-bit a -> A7 | `a>>1` and `round(a*127/255)` (indistinguishable here) | keeping 8 bits (today) |
| blend unit's Ad read of A7 | bit replication `(v<<1)\|(v>>6)` == `round(v*255/127)` **on all 128 values** | `v<<1` |
| blended write -> A7 | `round8(x)>>1`, `floor8(x)>>1` | `x*127/255` truncated or rounded (8 halves wrong) |
| texture unit's read | `(X<<7) \| A7` | replicate(A7), `A7<<1`, X-as-constant |

8 of 112 combinations fit 64/64. They differ only where the goldens cannot
tell them apart. So: **the guest byte is `(X<<7)|A7`, the texture unit
returns that byte, and the blend unit reads `A7` bit-replicated**. That is
#176's R1+R2, now confirmed on alpha and on the second row. One useful fact
falls out: because replication equals `round(v*255/127)` exactly, storing
`A7/127.0` in a UNORM8 target already produces the replicated byte. That is
why `pgraph_get_clear_color()`'s `/127.0f` already stores the right host
byte (the Clear figures below confirm it).

**The 1,772 px it cannot reproduce** are `XA_{Z,O}1A7RGB8_Add_SrcA_DstA`,
886 structural each (37,007 differing, 36,121 off-by-one, on every device
run checked). Hardware quantises alpha after the blend, and fixed-function
blending cannot. Neither this design nor #176 touches them.

## 2. The design on master: the read side carries all of it

Priced in host terms. The host keeps B8G8R8A8 with an 8-bit alpha `h`. The
blend unit reads `h` by identity, and the blended swatch pass stores
`round8(0x22*f)` whatever the shader does. The control is that `today`
reproduces the device capture **on 64 of 64 halves**, on nova `851650a27937`
(`1790361025-vtxarr262-base`) and on thor `a7b9d28e6b84`
(`1790359589-xbox-full6743-dry2`).

| design | golden halves wrong | 4 DstAlpha, structural | 4 DstAlpha, differing |
|---|---:|---:|---:|
| today (identity both ways) | 36/64 | 229,376 | 294,912 |
| W: blend-off writes store expand7 | 28/64 | 229,376 | 229,376 |
| **R: sample reads `(X<<7)\|(h>>1)`** | **8/64** | **0** | **65,536** (all off-by-one) |
| W + R (#176) | 0/64 | 0 | 0 |

**The read side alone recovers all 229,376 structural px.** The write side
is worth only the 65,536 off-by-one px (the `bg 0x80` bottoms: 128 vs 129).
Neither needs `vk/draw.c`. The brief's LOCATE-FIRST named it for the write
side, but a blend-off quantisation is a `psh.c` uniform staged from the live
`NV_PGRAPH_BLEND` (the `signedBlendPass` pattern), and blended draws must be
left alone anyway.

### Hunks per file (`x1a7-read-side.diff`)

| file | holder | hunk |
|---|---|---|
| `glsl/psh.h` | `[free]` (unclaimed) | `enum PshX1A7Readback {NONE, Z, O}`, `pgraph_glsl_set_texture_x1a7_readback()`, and `DECL(S, texX1A7, int, 4)` in `PSH_UNIFORM_DECL_X` |
| `glsl/psh.c` | lane.wbufdepth24 (#268) | a static per-stage array plus its setter. In the per-stage fetch block, **before alphakill**: `if (texX1A7[i] != 0) t_i.a = (float((texX1A7[i]-1)*128) + floor(floor(t_i.a*255+0.5)*0.5))/255`. Staged in `pgraph_glsl_set_psh_uniform_values()` |
| `vk/texture.c` | lane.texvol283 (#289) | in `create_texture()`, beside `pad_alpha_override`: mode = Z/O when `surface_is_texture_source()` (#48's gate) `&& !surface->upload_pending` and `pgraph_vk_surface_drawn_format()` is X1A7. In `pgraph_vk_bind_textures()`, disabled slots reset to NONE |

A uniform, not `PshState`, for `signedBlendPass`'s reason: the value depends
on which surface a stage samples, and nothing that invalidates a shader
watches that. GL never calls the setter, so it stages 0 and is unchanged.

Optional write-side hunk (`psh.c` only, not in the diff): a uniform staged as
`X1A7(surface_shape.color_format) && !(BLEND & EN)` that does
`fragColor.a = floor(fragColor.a*127+0.5)/127`. It is worth the 65,536
off-by-one px. It is left out because it is a second change to one quantity
(the read side's arm would be uninterpretable if both moved at once).

## 3. Priced offline, beyond the four

The same read rule reaches every X1A7 surface sampled as a texture, so the
other X1A7 rows move too:

| capture | now differing / structural | predicted | basis |
|---|---:|---:|---|
| 4 DstAlpha (must_move) | 294,912 / 229,376 | **65,536 / 0** | full model, control 64/64 |
| `Clear::SCF_X1A7R8G8B8_Z` | 65,568 / 49,200 | **0 / 0** | each sampled texel shows h raw on both halves; rule applied per pixel |
| `Clear::SCF_X1A7R8G8B8_O` | 65,472 / 49,104 | **0 / 0** | same; 131,040 of 131,040 differing px reproduced |
| `Surface_format::Fmt_X1A7R8G8B8_Z` | 32,743 | improves | GL measured this rule at 32,774 -> 6,311 (`5df42da3`) |
| `Surface_format::Fmt_X1A7R8G8B8_O` | 16,383 | **worse by >= 58,754** | see below |

### The known regression: `Fmt_X1A7R8G8B8_O`'s CPU-memset background

`SurfaceFormatTests::RenderToTextureStart` memsets the region to 0 and then
draws only part of it. On hardware the untouched pixels keep byte `0x00`. The
rule reads them as `(1<<7)|0 = 0x80`, and the top half composites them as
`[16,16,16,191]` where the golden is `[32,32,32,255]`. Counted on the thor
capture, 58,754 px are `h = 0` over a black bottom. That is a lower bound,
and it matches GL's 59,025 for the same rule, which took the capture to
122,552 on GL. `_Z` is immune because its X is 0.

**The per-pixel fix is refuted, so do not retry it.** Tagging each pixel's X
in the host LSB (h's bit 0 vs bit 7) breaks on blended writes: the swatch
pass stores `round8(34*f)`, whose LSB is arbitrary (`9` at `bg 0x40`), so
half the X bits would read flipped. There is no free per-pixel bit without a
second attachment. #176's NOTES reached the same place ("how the download
learns which bytes the GPU wrote, clears included").

**The per-surface gate is undecided, and it needs a probe, not an argument.**
Every new VK target is created `upload_pending = true` (`vk/surface.c:3351`).
So "this surface was uploaded from guest bytes" separates Surface_format's
surface from the DstAlpha ones only if the DstAlpha binding is *reused*
across swatches rather than recreated. Offline, nothing says which. The cheap
probe is to log, per X1A7 texture bind, whether the source surface has been
uploaded since its last full-surface clear. On Blend surface all eight
DstAlpha swatches must read "no" and on Surface format "yes", or the gate
does not work. The gate itself lives in `vk/surface.c`, held by lane.remote.

## 4. The arm, ready to register (not registered)

**Not registered.** Its b_ref would need `psh.c`, `psh.h` and `vk/texture.c`,
none of which this lane may commit. Whoever gets the files should apply
`x1a7-read-side.diff`, merge master, and register the following after the
last rebase:

- **must_move**: `Blend_surface/DstAlpha_XA_Z1A7RGB8`,
  `Blend_surface/DstAlpha_XA_O1A7RGB8`, `Blend_surface/1-DstAlpha_XA_Z1A7RGB8`,
  `Blend_surface/1-DstAlpha_XA_O1A7RGB8` each go to **16,384 differing, 0
  structural**. The residue is exactly the two `bg 0x80` bottom halves per
  capture, off by one.
- **must_move (bonus, same rule)**: `Clear/SCF_X1A7R8G8B8_Z1A7R8G8B8` 65,568
  -> 0 and `Clear/SCF_X1A7R8G8B8_O1A7R8G8B8` 65,472 -> 0.
- **declared regression**: `Surface_format/Fmt_X1A7R8G8B8_O1A7R8G8B8` rises
  by at least 58,754. Register it as a failing leg, not a hidden one, unless
  the per-surface gate above lands first.
- **must_not_move**, each with the change that would move it:
  - `Fmt_/SCF_/Blend X8R8G8B8_{Z,O}`, `A8R8G8B8`, `X1R5G5B5_{Z,O}`, `R5G6B5`:
    the mode is set only when `drawn_format` is `0x06`/`0x07`. A wrong
    `drawn_format` (the #55 stale-binding class) or a stale per-stage mode
    left on a slot would move them.
  - `XA_{Z,O}1A7RGB8_Add_SrcA_{1-SrcA,DstA}`: they sample the surface with
    alpha forced opaque (`SRC_ZERO, true, true`), so a changed texel alpha
    cannot reach them. If they move, the uniform is reaching a stage it
    should not.

## What the next lane should not repeat

- Do not put X1A7 in `pgraph_glsl_surface_pad_alpha_mode()`. Storing the
  guest byte refutes the blend read (23/32 in #176's `DESIGNS`).
- Do not price a design on the R channel alone. The scorer counts alpha, and
  the framebuffer alpha of each top half is `s*s/255 + 255 - s`.
- Do not implement the write side and the read side in one arm. The read side
  is the whole structural yield and the write side is 65,536 off-by-one px,
  and one arm moving both cannot say which moved what.
- The issue's figures are **structural** (differing minus off-by-one). The
  four DstAlpha captures are 294,912 *differing*, not 229,376.
