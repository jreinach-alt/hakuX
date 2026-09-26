# lane cloud-271: #271, X1A7R8G8B8's 7-bit alpha (2026-09-26)

Analysis-only, no `hw/` file. It builds on lane x1a7271's analysis
(PR #306, folded, `docs/lanes/x1a7271/`). This lane re-derives the rule by a
second, independent method, re-prices it against the two newest device
captures, rebases the hunks onto master `71188b079b`, and re-maps them to
today's holders. **The code is not compiled**: this host has no desktop
build tree.

    python3 docs/lanes/cloud-271/invert_x1a7.py          # the rule, by inversion
    python3 docs/lanes/x1a7271/derive_x1a7.py --capture <run>/captures1   # the price

## 1. The rule, read off the goldens by inversion

`derive_x1a7.py` (#306) enumerates rival stages and keeps the ones that fit.
`invert_x1a7.py` assumes no stage. Per swatch it inverts two flat golden
halves:

- **Bottom RGB is the blend factor itself**, because the draw is white times
  the factor with dfactor ZERO. So it reads `Ad` (DstAlpha) or `255-Ad`
  (1-DstAlpha) directly.
- **Top half: RGB and alpha pin the sampled byte `s`.** The alpha is
  `s*s/255 + 255 - s`, which has two roots. The RGB over the 0x55 grey is
  linear in `s` and picks one.

Result: **0 of 32 swatches break the rule**, and `s` is pinned to one value
on 20 of 32. Where 8-bit rounding leaves 2 to 8 candidates, all of them
satisfy the rule. The rule:

| stage | rule | the row that would refute a rival |
|---|---|---|
| blend-off write of 8-bit `a` | stores `A7 = a>>1` | (not separable from `round(a*127/255)` here) |
| blend unit's `Ad` read | bit replication `(A7<<1)\|(A7>>6)` | bg 0x80 reads **129** on all 8 swatches; identity and `A7<<1` give 128 |
| texture unit's read of the stored byte | `(X<<7)\|A7`, no expansion | Z at bg 0xFF: `s` = **17** uniquely; replication or `A7<<1` give 34. O: every candidate has `s>>7 = 1` = X |

This is the same rule #306 states and #176's R1+R2. It now has two methods
behind it, the enumeration and the inversion, on RGB and alpha of both rows.

**The 1,772 px it cannot reproduce** are `XA_{Z,O}1A7RGB8_Add_SrcA_DstA`,
886 structural each: 37,007 differing minus 36,121 off-by-one. That holds
identically on the two newest runs below. Hardware quantises alpha after
the blend, and fixed-function blending cannot. No design here touches them.

## 2. Priced against the newest device captures

| run | ref | device | control: `today` reproduces |
|---|---|---|---|
| `1790394110-arms-pshqueue-base` | `24546d197b` (apk `47f492ec0654`) | nova | 64 / 64 halves |
| `0-a-now-8e683b3a26-008-Blend_surface` | `8e683b3a26` (apk `423469eb5d42`) | thor | 64 / 64 halves |

The two runs are identical row for row:

| capture | now differing / off-by-one / structural | read side only (R) | R + write side (#176) |
|---|---:|---:|---:|
| `DstAlpha_XA_Z1A7RGB8` | 65,536 / 16,384 / 49,152 | 16,384 / 0 | 0 / 0 |
| `DstAlpha_XA_O1A7RGB8` | 81,920 / 16,384 / 65,536 | 16,384 / 0 | 0 / 0 |
| `1-DstAlpha_XA_Z1A7RGB8` | 65,536 / 16,384 / 49,152 | 16,384 / 0 | 0 / 0 |
| `1-DstAlpha_XA_O1A7RGB8` | 81,920 / 16,384 / 65,536 | 16,384 / 0 | 0 / 0 |
| **total** | 294,912 / 65,536 / **229,376** | 65,536 / **0** | 0 / 0 |

(R cells are differing / structural.) **The read side alone recovers all
229,376 structural px.** The write side is worth only the 65,536 off-by-one
px, and belongs in a second arm (section 4). The Clear and Surface_format
X1A7 prices are #306's (`docs/lanes/x1a7271/NOTES.md` section 3). Neither of
these runs has a Clear capture, so they are not re-measured here.

## 3. The hunks per file, on master `71188b079b`

`x1a7-read-side.diff` here is #306's diff regenerated on master. It applies
without fuzz. It changes one thing: the `vk/texture.c` gate also requires
`kelvin_color_format_vk_map[state.color_format].component_map.a ==
VK_COMPONENT_SWIZZLE_IDENTITY`. `surface_is_texture_source()` compares only
texel strides, so an X8R8G8B8 texture (`SZ_`/`LU_IMAGE_`; its view swizzles
alpha to ONE) sampling an X1A7 surface would otherwise get the mode. The
rule would then read its 1.0 as `(0*128 + 127)/255` on `_Z`, where hardware
returns 1.0. No golden exercises that case, and the DstAlpha test samples
through an A8R8G8B8 texture, so the extra gate changes no price above. It also **merges cleanly with open PR #347** (lane.pshqueue's
`psh.c`/`psh.h`): the old diff's `psh.h` hunk failed there only on context,
because #347 adds `surfaceBSwap` two lines above. The only conflict in that
test merge was `docs/testing/nv2a_index.json`, which is #347's own conflict
with master. Every symbol the diff uses exists on master:
`surface_is_texture_source`, `pgraph_vk_surface_drawn_format`,
`upload_pending`, `pad_alpha_override` and `pgraph_glsl_set_psh_uniform_values`.

| file | holder today (`origin/board`) | hunk |
|---|---|---|
| `glsl/psh.h` | **lane.pshqueue** (PR #347) | `enum PshX1A7Readback {NONE, Z, O}`, the setter's prototype, and `DECL(S, texX1A7, int, 4)` at the end of `PSH_UNIFORM_DECL_X` |
| `glsl/psh.c` | **lane.pshqueue** (PR #347) | a static per-stage array and its setter. In the per-stage fetch block, **before alphakill**: `t_i.a = (float((texX1A7[i]-1)*128) + floor(floor(t_i.a*255+0.5)*0.5))/255`. The mode is staged in `pgraph_glsl_set_psh_uniform_values()` |
| `vk/texture.c` | **lane.remote** | in `create_texture()`, beside `pad_alpha_override`: mode Z/O when `surface_is_texture_source() && !surface->upload_pending` and the drawn format is X1A7. In `pgraph_vk_bind_textures()`, disabled slots reset to NONE |
| `vk/draw.c` | (not needed) | the brief's LOCATE-FIRST named it for the write side. The read side needs nothing there, and the optional write side is a `psh.c` uniform |

The holders have changed since #306: `psh.c` moved from lane.wbufdepth24 to
lane.pshqueue, `psh.h` from `[free]` to lane.pshqueue, and `vk/texture.c`
from lane.texvol283 to lane.remote. `vk/surface.c` (the per-surface gate in
section 5) is in no lane's `files` list today. It was released at waves 218
and 219.

The natural lands: **lane.pshqueue takes the `psh.[ch]` hunks and
lane.remote takes the `vk/texture.c` hunk**, or the board grants one of them
all three for one PR. The arm needs all three in one b_ref, because the
`psh.c` uniform is inert until `vk/texture.c` sets it.

## 4. The arm (legs written, not registered)

It is not registered because its b_ref needs the three files above, and
this lane holds none of them. A prediction file committed here would name
refs with no code, and the arms job would run it anyway. Whoever lands the
diff: merge master, then register the legs below after the last rebase.

- **must_move** (key, base -> predicted, differing):
  - `Blend_surface/DstAlpha_XA_Z1A7RGB8`: 65,536 -> 16,384
  - `Blend_surface/DstAlpha_XA_O1A7RGB8`: 81,920 -> 16,384
  - `Blend_surface/1-DstAlpha_XA_Z1A7RGB8`: 65,536 -> 16,384
  - `Blend_surface/1-DstAlpha_XA_O1A7RGB8`: 81,920 -> 16,384

  Each residue is exactly the two `bg 0x80` bottom halves, 128 vs 129
  (off-by-one; 0 structural). The O captures fall further than the Z ones
  because their top halves also carry X. **What makes this leg fail while
  the code is present:** the mode never reaches the stage (drawn_format not
  0x06/0x07 at bind, or `upload_pending` true on these surfaces). Z and O
  would then both stay at base. A wrong `(X<<7)` term would leave O
  structural and fix Z only.
- **must_move (same rule)**: `Clear/SCF_X1A7R8G8B8_Z1A7R8G8B8` 65,568 -> 0
  and `Clear/SCF_X1A7R8G8B8_O1A7R8G8B8` 65,472 -> 0. These are #306's
  prices, and Clear is not in the two runs above.
- **declared regression**: `Surface_format/Fmt_X1A7R8G8B8_O1A7R8G8B8`,
  16,383 today, rises by at least 58,754. The CPU-memset background (byte
  0x00) reads as 0x80. Register it as a failing leg unless the per-surface
  gate (section 5) lands first. `Fmt_X1A7R8G8B8_Z1A7R8G8B8` (32,743) is
  predicted to improve. Register it as a direction only; there is no
  device-side count.
- **must_not_move** (all exact today on both runs), each with the change
  that would move it:
  - `Blend_surface/{,1-}DstAlpha_{ARGB8,R5G6B5,X_ZRGB8,X_ORGB8,X_Z1RGB5,X_O1RGB5}`
    (12 rows, 0 today). They run the same sample-the-blended-surface path
    on other formats. They move if the mode is set for a surface whose
    drawn format is not X1A7, or if a stale per-stage mode survives on a
    slot, which is the job of the disabled-slot reset in
    `pgraph_vk_bind_textures()`.
  - `Blend_surface/{ARGB8,X_ZRGB8,X_ORGB8}_Add_SrcA_{1-SrcA,DstA}` (6 rows,
    0 today): they move if the uniform reaches a non-X1A7 stage.
  - `Blend_surface/XA_{Z,O}1A7RGB8_Add_SrcA_1-SrcA` (2 rows, 0 today).
    These sample the X1A7 surface with alpha forced opaque, so a changed
    texel alpha cannot reach them. If they move, the new line runs after
    the alpha override when it should run before it.
  - `Surface_format/Fmt_A8R8G8B8`, `Fmt_X8R8G8B8_{Z8,O8}R8G8B8` (0 today):
    they move if the drawn-format gate misreads 0x07 (X1A7_O) against
    0x04/0x05 (X8R8G8B8).
  - **Correction to the brief:** `Fmt_X1R5G5B5_{Z1,O1}R5G5B5` are **not**
    exact today (12,988 and 13,734 differing on `pshqueue-base`). Their leg
    is "equal to base", not "0". A drawn-format misread cannot reach them,
    because a 2-byte surface already fails `surface_is_texture_source()`'s
    stride test against the 4-byte texture. So if they move, that stride
    gate has been loosened, or the uniform leaked to a stage bound to no
    X1A7 surface.

## 5. Left undecided, not re-litigated

`Fmt_X1A7R8G8B8_O`'s regression needs a per-surface "these bytes came from
the CPU" gate. #306 section 3 refutes the per-pixel LSB tag: the blended
swatch pass writes arbitrary LSBs. It also names the probe that decides
whether `upload_pending` can serve as the gate: log, per X1A7 bind, whether
the source surface was uploaded since its last full clear. Nothing in this
lane changes that analysis.

## What the next lane should not repeat

- Do not invert the top half's alpha alone. It is quadratic in `s` and
  two-valued. The first pass of `invert_x1a7.py` reported 32 of 32
  "breaks", and every one was the wrong root. Pair it with the RGB.
- Do not take "every other surface-format row is exact today" from a brief.
  X1R5G5B5 is not, so read the base run's `scores1.tsv`.
- Do not apply #306's original diff to a branch carrying #347. Use the
  regenerated one here; its `psh.h` context is current.
