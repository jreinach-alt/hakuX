# Sub-8-bit texels: silicon replicates bits, the native packed formats use the ratio (#59)

One rule covers the whole family, and it is not expressible by any native
packed host format. So the fix is a *format* change, not a decode change —
which is the same shape as #6 (DXT1) and for the same reason.

## The rule

Silicon expands a packed colour field narrower than 8 bits by **replicating
the field's high bits into the low ones**. Vulkan and GL both define their
native packed UNORM formats as the **exact ratio**, `round(v·255/(2ⁿ−1))`.

| width | rules disagree at | example |
|---|---|---|
| 6 bit | v = 11–15, 48–52 | v=12 → **48**, ratio 49 |
| 5 bit | v = 3, 7, 24, 28 | v=3 → **24**, ratio 25 |
| 4 bit | *nowhere* | both are v·17 at all 16 values |
| 1 bit | *nowhere* | both are 0 / 255 |

Everywhere else the two coincide — 5-bit 19 → 156 and 6-bit 38 → 154 under
either rule — which is why this read for years as an occasional off-by-one
rather than as a format rule, and why #38 filed it as vertex-colour
quantisation.

**It is one fix, not five.** `A1R5G5B5`, `X1R5G5B5`, `R5G6B5` and `R6G5B5`
all take it. `A4R4G4B4` takes nothing: at 4 bits there is no gap between the
rules, and its two captures were already byte-exact.

## How it was read out of the goldens: level sets, no mapping

The obvious method is to fit the screen→texel mapping, recover each pixel's
source field value and compare — which is what
[`r6g5b5-golden-packing.md`](r6g5b5-golden-packing.md) did. It works, but it
makes the answer depend on a regression fit with a residual *and* on the
test's source bytes being the ones the golden was captured with, which for
`R6G5B5` they demonstrably are not.

None of that is needed to separate two rules, because each rule maps a field
to a **fixed set of at most 64 8-bit levels**, and the two sets differ:

```
5-bit  replicate-only  24  57 198 231        ratio-only  25  58 197 230
6-bit  replicate-only  44  48  52  56  60    ratio-only  45  49  53  57  61
                      195 199 203 207 211               194 198 202 206 210
```

So the only question is *which values does this channel of this golden
contain* — no mapping, no fit, no assumption about which texel landed where.
`Texture_format` walks a 256×256 gradient, so every field value appears.

| golden | 5-bit channels | 6-bit channels |
|---|---|---|
| `TexFmt_R5G6B5`, `_L` | R, B: all 4 replicate-only, 0 ratio-only | G: all 10 replicate-only, 0 ratio-only |
| `TexFmt_A1R5G5B5`, `_L` | R, G, B: all 4, 0 ratio-only | — |
| `TexFmt_X1R5G5B5`, `_L` | R, G, B: all 4, 0 ratio-only | — |
| `TexFmt_R6G5B5` | G, B: all 4, 0 ratio-only | R: all 10, 0 ratio-only |
| `TexFmt_A4R4G4B4`, `_L` | *(4 bit — cannot discriminate)* | — |

**21 channels, every replicate-only level present, not one ratio-only level
anywhere in the corpus.** `docs/testing/packed_expansion_rule.py` re-derives
this and exits non-zero if any other rule survives.

`Surface_clip/rt_*` is the same rule seen through a single colour: the dark
green quad is `SetDiffuse(0.1, 0.6, 0.1)` stored in a 565 target as
(3, 38, 3), and the golden holds **(24, 154, 24)** where we produced
(25, 154, 25). Green agrees at 154 only because v=38 is one of the values
where the rules coincide — which is precisely why the group was
mis-attributed to a red/blue rounding wobble.

## Why a decode fix alone would have measured nothing

`R5G6B5` resolved to `VK_FORMAT_R5G6B5_UNORM_PACK16`. That format's
expansion is in the Vulkan spec, below anything a component mapping, a
sampler flag or a fragment shader can reach. A correct rule written into
`pgraph_convert_texture_data` while the native format stayed claimed would
never have been called — exactly as `s3tc.c`'s ordered dither was inert until
DXT1 stopped being claimed for native BC1 (#6).

The expansion also has to happen **before** filtering: hardware expands the
texel and filters the 8-bit result. A post-sample correction would be wrong
on every filtered fetch, so it belongs in the upload, not the shader.

Hence: six texture formats now convert to RGBA8 on the way in, alongside
`SZ_R6G5B5` which already did.

## What the goldens say is *not* wrong

The non-`rt_` `Surface_clip` R5G6B5 captures — a 565 *backbuffer*, captured
directly — are **9 of 9 byte-exact**, before and after. The 16-bit words we
write into a 565 surface are right; the guest's own image writer does that
expansion on the CPU, identically on silicon and here. Only the GPU's
texel expansion diverged. That asymmetry is what places the whole defect in
the texture path and nothing of it in the surface-write or readback path, and
it is why those 9 captures are on the must-not-move list.

The `A8R8G8B8`, `B8` and `G8B8` variants of the same test are 27 of 27
byte-exact. The 8-bit path was never in question.

## Measured scope, offline, against the goldens

Every differing channel in these fifteen captures is exactly one
ratio→replicate pair — **100.0 % explained, residual 0** — so the pixel
consequence is not an estimate:

| suite | captures | differing px | differing channels | explained |
|---|---:|---:|---:|---:|
| `Surface_clip/rt_*` | 7 | 1,175,741 | 2,351,482 | 100.0 % |
| `Texture_format` 565/5551 | 6 | 169,944 | 268,990 | 100.0 % |
| **total** | **13** | **1,345,685** | **2,620,472** | **100.0 %** |

(The other two `rt_` captures are already exact and must stay so.)

Partially affected, deliberately left unconstrained because they carry other
mechanisms as well — they sample a 16-bit surface through a 16-bit texture
stage, so they should improve but not to zero:

| capture | differing channels | ratio→replicate pairs |
|---|---:|---:|
| `Blend_surface/X_O1RGB5_Add_SrcA_DstA` | 257,912 | 166,836 (64.7 %) |
| `Blend_surface/X_Z1RGB5_Add_SrcA_DstA` | 257,912 | 166,836 (64.7 %) |
| `Blend_surface/X_O1RGB5_Add_SrcA_1-SrcA` | 307,712 | 164,330 (53.4 %) |
| `Blend_surface/X_Z1RGB5_Add_SrcA_1-SrcA` | 307,712 | 164,330 (53.4 %) |
| `Blend_surface/R5G6B5_Add_SrcA_DstA` | 206,429 | 113,029 (54.8 %) |
| `Blend_surface/R5G6B5_Add_SrcA_1-SrcA` | 257,000 | 110,841 (43.1 %) |

A corpus-wide scan for the same signature finds 828 captures with at least
one matching pixel, but outside the rows above the fraction is under 10 % and
is coincidence: an 8-bit value of 25 is in the map whatever produced it. **A
matching value is not evidence on its own** — the rows above are named
because their *formats* are 16-bit, not because the numbers matched.

## The throughput cost, honestly

Two different costs, and only one of them is small.

**A 565 texture uploaded from guest memory** now runs a scalar CPU decode
instead of a `memcpy`, once per cache fill. That is the same price `R6G5B5`,
`I8` and the YUVs already pay, and texture cache fills are not per-draw.

**A 565 surface sampled as a texture** — render-to-texture in 16 bit — is the
expensive one. That bind used to be served by handing the sampler the
surface's own `VkImageView`, entirely on the GPU. It now cannot be, because
the surface's image holds 565 words and the texture's image is RGBA8: it
becomes a surface download to VRAM plus a software decode. `Surface_clip`'s
`rt_*` row is exactly that shape, seven times.

**Nobody has counted how much of a real title's texture working set is 565,
and this document does not pretend to know.** What would settle it is a soak
(`docs/testing/request.sh --title ...`) with a counter on
`NV2A_PROF_SURF_TO_TEX` and on texture-cache fills by colour format — the
question is not "is a decode slower than a memcpy", which is obvious, but how
many fills per frame a title actually takes in these formats. #6's cost is
owed on the same terms and for the same reason.

## Least certain point

The surface-to-texture guard. Widening the host format to 4 bytes makes an
`A8R8G8B8` *surface* byte-size-compatible with a 565 *texture*, which it was
not while 565 was two bytes on the host, so
`check_surface_to_texture_compatiblity()` now rejects every converted format
outright rather than relying on a size mismatch to do it. That rule is right
by construction — a raw `vkCmdCopyImage` cannot fill an image whose format
says its bytes are something else — but it is argued from the tables, not
from a capture: no golden binds a DXT, `I8` or YUV texture over a surface,
because the hardware cannot render into those formats. `Texture_DXT/*`,
`Texture_format/TexFmt_SZ_Index8*` and `Texture_format/TexFmt_UYVY*` are on
the must-not-move list to check that rather than to assert it.

The capture that would expose a mistake there is
`Texture_render_target/TexFmt_A1R5G5B5`: it renders into a 16-bit surface and
samples it back through the matching texture stage, which is the one place
where the old direct-bind and the new VRAM round-trip meet. It is uniformly
81,225 px / max delta 255 on *every* format today — the whole suite fails
identically for a reason that is #4's, not this one's — so it cannot confirm
the fix, but it can still catch a break.

The GL renderer's half of the guard (`gl/surface.c`) has no measurement
behind it at all; the device measures Vulkan.
