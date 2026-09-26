# lane cloud-271: #271, X1A7R8G8B8's 7-bit alpha (2026-09-26)

Two sessions. The first (PR #365, folded) was analysis only: it re-derived
#306's rule by a second, independent method, re-priced it against the two
newest device captures, and regenerated the hunks on master. The second
(this PR) **lands the read side** in `glsl/psh.c`, `glsl/psh.h` and
`vk/texture.c` and registers its arm (section 6). The code is type-checked
against the NDK compile line, not built: this host has no desktop build tree,
and the arm's APK is the dispatcher's.

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

## 4. The arm's legs

Registered in the second session as
`docs/testing/predictions/cloud-271-x1a7-read.json` (section 6). The legs as
first written:

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

## 6. Landed, and the arm registered (second session, master `02374a6847`)

**What landed.** `x1a7-read-side.diff` applied to master `02374a6847`: the
`psh.c` and `vk/texture.c` hunks at an offset, the `psh.h` hunk with one
line of context relaxed, because #347 has since folded `surfaceBSwap` into
`PSH_UNIFORM_DECL_X` above `texScale`. The applied hunks are the diff's, byte
for byte. `nv2a_index.json` is regenerated for the two new `case` sites
against the fold pins (tests `6743b6ab`, the committed provenance): 104
suites, 2,884 sites, `check` clean.

**Checked offline.**

- `typecheck.py` compiles `glsl/psh.c`, `vk/texture.c`, `vk/shaders.c` and
  `gl/shaders.c` with the dispatcher build tree's NDK clang line, pointed at
  this worktree. All four exit 0. The only warnings are on unchanged lines.
  `vk/texture.c` reaches `psh.h` through `renderer.h` -> `glsl/shaders.h`.
- `preflight.sh --allow-tracker`: psh_differ builds and reports, aci_vmstate,
  territory, coverage and board files are ok. The nv2a index gate was the one
  failure, and the regeneration above fixes it.
- A test merge with PR #393 (lane.pshaniso284, unfolded, also `psh.c`/`psh.h`
  /`vk/texture.c`) is clean on all three sources. Only the generated index
  conflicts. #393's hunks are the anisotropy probe loop and BRDF, and none is
  in the fetch block this rule sits in.
- The VRAM path does not double-apply the rule. A surface downloaded to VRAM
  keeps the host's 8-bit alpha (no X1A7 conversion on download), so a texture
  uploaded from those bytes carries `h`, and the rule converts it once.

**What the gate cannot see (not a defect today, recorded).** The mode is
staged when `create_texture()` runs. `pgraph_vk_bind_textures()` skips that
call for a slot whose registers are unchanged, and the stage then keeps the
last staged value. This is the same staleness `pad_alpha_override` has, since
that is baked into the view at the same point. A surface that changes drawn
format (for example 0x06 to 0x04) at the same address and extent, with no
texture register write in between, would keep the old mode. No golden
exercises that sequence.

**The arm.** `docs/testing/predictions/cloud-271-x1a7-read.json`,
`02374a6847 -> 81e74b9ac9`, disc `Blend surface, Clear, Surface format`,
written by `register.sh` here. Its legs are section 4's, with these changes:

- `Fmt_R5G6B5` (0 today) is added to must-not-move. It is a 2-byte surface,
  like X1R5G5B5.
- `XA_{Z,O}1A7RGB8_Add_SrcA_DstA` (37,007 each) and `Fmt_X1A7R8G8B8_Z`
  (32,743) are must-not-regress.
- `{R5G6B5,X_Z1RGB5,X_O1RGB5}_Add_SrcA_*` are left unguarded.
  `R5G6B5_Add_SrcA_DstA` read 14,833 and then 11,964 on two runs of one
  binary (`pshqueue-base`).
- **`Fmt_X1A7R8G8B8_O1A7R8G8B8` is registered at its base value, 16,383, as
  a leg that is expected to fail.** `expect` is exact-only, so its failure
  line reports the measured cost. So the verdict this arm should get is
  **FAIL on exactly that one leg**. Any other failure line is a real finding.

Base values were checked on the newest runs before registering. The Blend
and Surface_format rows are from `1790394110-arms-pshqueue-base` (both runs
agree, except the unguarded R5G6B5 row). The Clear rows, 65,568 and 65,472,
are from `1790417358-arms-zrtz272-base`/`-fix` and `vkpointsize34`. The older
solo-Clear `z-b-v040j1` reads 98,208, but it is an older APK.

**The net, and who accepts the regression.** The predicted gains are
229,376 structural px across the four Blend rows (294,912 -> 65,536
differing) and 131,040 on Clear. The declared loss is at least 58,754 on one
Surface_format capture, which is a clear net gain. It is still a capture
that gets worse, and the brief says an accepted regression is the owner's.
It is put to the owner on #271, not accepted here. The alternative is the
per-surface gate (section 5), which needs `vk/surface.c` and the probe.

## What the next lane should not repeat

- Do not invert the top half's alpha alone. It is quadratic in `s` and
  two-valued. The first pass of `invert_x1a7.py` reported 32 of 32
  "breaks", and every one was the wrong root. Pair it with the RGB.
- Do not take "every other surface-format row is exact today" from a brief.
  X1R5G5B5 is not, so read the base run's `scores1.tsv`.
- Do not apply #306's original diff to a branch carrying #347. Use the
  regenerated one here; its `psh.h` context is current.
- Do not expect `ab_compare.py --register` to write `must_not_regress`: it
  has no flag for it. `register.sh` adds it to the JSON before the commit.
- Do not repoint every `-I<build tree>` path at a worktree for a type check.
  The build tree also holds glib's install and generated headers. Repoint
  only the paths that exist in the worktree, and the bare root, which the
  `hw/xbox/...` includes resolve through (`typecheck.py`).
