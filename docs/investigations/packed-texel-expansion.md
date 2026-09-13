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

Two places in the tree already agreed with this rule and are worth naming,
because they were each derived independently and neither was read across to
the others:

- `s3tc.c`'s `expand5()`/`expand6()` — DXT1's palette endpoints are 565
  words, and #6 expanded them by replication.
- `gl/texture.c`'s Android `android_expand_5_to_8()` — the GLES upload path
  had a hand-written 5551 expansion, also by replication.

Three independent derivations of the same rule, on three different paths,
while the Vulkan texture path used the other one. The Android GL copy is
removed by this change; keeping it would have decoded the decoded buffer.

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

### Predicted, but not registered: what `Blend_surface` should do

Written before the arms landed, and deliberately kept out of the registered
prediction because these captures carry blend residual as well and a
must-not-move on them would fail on the improvement.

Simulated offline by applying the ratio→replicate remap to our own captures
and re-scoring against the goldens — the most conservative model, since it
only moves a channel where ours is a ratio-only level *and* the golden is the
matching replicate level:

| capture | now | predicted | delta |
|---|---:|---:|---:|
| `X_O1RGB5_Add_SrcA_DstA` | 98,705 | 43,756 | −54,949 |
| `X_Z1RGB5_Add_SrcA_DstA` | 98,705 | 43,756 | −54,949 |
| `R5G6B5_Add_SrcA_DstA` | 99,178 | 44,239 | −54,939 |
| `X_O1RGB5_Add_SrcA_1-SrcA` | 110,709 | 56,414 | −54,295 |
| `X_Z1RGB5_Add_SrcA_1-SrcA` | 110,709 | 56,414 | −54,295 |
| `R5G6B5_Add_SrcA_1-SrcA` | 111,098 | 56,840 | −54,258 |
| five `*_Add_SrcA_1-SrcA` 8-bit surfaces | 57,535 ea | 56,979 | −556 ea |
| `XA_{O,Z}1A7RGB8_Add_SrcA_DstA` | 51,892 | 51,839 | −53 |
| `ARGB8_Add_SrcA_DstA` | 47,272 | 47,268 | −4 |

The **8-bit surface** rows moving at all is not coincidence and was nearly
mis-read as one: `blend_surface_tests.cpp:448` composites every surface
format through a fixed list of texture stages that includes `SZ_R5G6B5`,
`SZ_R6G5B5`, `SZ_X1R5G5B5` and `SZ_A1R5G5B5`. So an `ARGB8` capture contains
a small 565-sampled region regardless of its own surface format. That is why
this suite is carried for visibility and constrained nowhere.

### The rest of the corpus is coincidence, and says so

A corpus-wide scan for the same signature finds 828 captures with at least
one matching pixel, but outside the rows above the fraction is under 10 % and
is coincidence: an 8-bit value of 25 is in the map whatever produced it. **A
matching value is not evidence on its own** — the rows above are named
because their *formats* are 16-bit, not because the numbers matched.

## Measured on the device: PRE-REGISTERED PASS

`5e612529b9` → `0b7e5de8dd`, two runs each, prediction sha `fad0e0c0f117`
bound at queue time. All 106 registered checks held.

| suite | caps | better | worse | differing A | differing B |
|---|---:|---:|---:|---:|---:|
| `Surface_clip` | 47 | 7 | 0 | 1,175,741 | **0** |
| `Texture_format` | 40 | 6 | 0 | 309,333 | 139,389 |
| `Blend_surface` | 32 | 14 | 4 | 1,452,903 | 1,256,426 |
| `Texture_DXT` | 15 | 0 | 0 | 34,911 | 34,911 |
| `Texture_render_target` | 41 | 0 | 0 | 3,209,634 | 3,209,634 |
| **total** | 175 | 27 | 4 | 6,182,522 | **4,640,360** |

All fifteen predicted captures went byte-exact. The offline level-set
derivation was exact: the baseline reproduced every figure taken from the
31-commit-old sweep column, so nothing landed that day had touched them.

Two things worth keeping:

**The converted-format guard was measured inert.** It was this document's
least-certain point, argued from the tables with no capture behind it.
`Texture_render_target` is 41 captures, 0 better and 0 worse, byte-identical
totals — including `TexFmt_R5G6B5`, an `A8R8G8B8` surface sampled through a
565 stage, which is precisely the case the guard exists to reject. It held.

**`Texture_DXT` did not move**, which is the check that #6's DXT1 routing and
this change do not interact.

### And the regression it cost, which is #48's, not the expansion's

`Blend_surface/DstAlpha_X_O1RGB5` and `1-DstAlpha_X_O1RGB5` went from
bit-exact to 65,536 differing pixels — eight half-swatches, every pixel.

The diagnosis came from the captures, not from reading. Those tests draw each
swatch in two halves: the top half with **the sampled TEX0 alpha as its
coverage**, the bottom with alpha forced by the combiner.

| capture | half | golden | before | after |
|---|---|---|---|---|
| `DstAlpha_X_O1RGB5` | **top** | 255,255,255,255 | 255,255,255,255 | **85,85,85,255** |
| `DstAlpha_X_O1RGB5` | bottom | 255,255,255,255 | same | same |
| `DstAlpha_X_Z1RGB5` | top | 85,85,85,255 | same | same |

85 is the test's own `PrepareDraw(0xFF555555)` clear showing through an alpha
of 0 where it must be 1.0. **The bottom half — the blend result — is
unchanged on both suffixes**, so the blend still substitutes `Ad = 1.0` and
the blend unit is not involved; `vk/draw.c` was never touched.

The cause is #48's *other* half, the texture-unit pad readback, applied as an
alpha swizzle in `create_texture()` and gated on `surface_to_texture`.
Widening 565/5551 to RGBA8 makes a 2-byte surface size-incompatible with its
4-byte texture image, which pushes those binds onto the VRAM path — and the
override went with them. **The gate was always wrong**: what the texture unit
reads for a surface's pad bits is a property of the surface format, not of
how the host image got filled.

**The Z variant was not broken, and that was luck.** Its pad bits happen to be
stored as 0, so reading them raw gives the 0.0 its format promises. A fix that
hardcoded 1.0, or that wrote alpha in the decode, passes O and breaks Z. Both
are registered as expect-0 so that failure would be visible.

### The scope mistake that cost a second round

The first attempt at that fix keyed the override on
`pgraph_vk_surface_get(addr) != NULL`, which answers *"is a surface
registered here"* — a weaker claim than *"is this the memory the texture
reads"*. Surfaces outlive the test that created them and these suites share a
disc, so a 128×128 `X1R5G5B5_O1R5G5B5` surface left behind by `Surface
format` was still registered when `Texture DXT` bound its 256×256 DXT1
texture at the same address:

| capture | before | after v1 |
|---|---:|---:|
| `Texture_DXT/DXT1_plasma_dxt1` | 384 | 65,536 `[ok → blank]` |
| `Texture_DXT/DXT1_plasma_alpha_dxt1` | 448 | 65,536 `[ok → blank]` |
| `Surface_format/Fmt_X1R5G5B5_O1R5G5B5` | 16,096 | 91,757 |
| `Surface_format/Fmt_X1R5G5B5_Z1R5G5B5` | 29,881 | 31,331 |

Both plasma captures went to a single flat `(16,16,16,254)` over the whole
256×256 region where the golden and the baseline agree to within 384 px —
a texture that never decoded, not one decoded wrong, because the override
also sets `pad_alpha_needs_rebuild`, which releases and re-uploads the
binding on every `create_texture` call.

`surface_to_texture` had been supplying the extent filter for free. That is
why gating on it looked sufficient, and why removing the gate had to restore
the filter rather than drop it. `surface_is_texture_source()` states it now:
same extent, one level, not a cubemap, colour, and **not compressed**. The
last clause matters on its own — v1 excluded *native BC*, which does not
cover DXT1, because #6 deliberately stopped claiming DXT1 for native BC.

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

**A third cost, added by the pad-alpha fix.** `pad_alpha_needs_rebuild`
releases and re-uploads a binding on every `create_texture` call, because
`TextureKey` records no baked swizzle and the Z and O variants share a
`VkFormat`. It now applies on the VRAM path too, where a rebuild means a
re-upload and not just a new view. It is confined to textures that really
are a pad-alpha surface's memory at matching extents — four surface formats —
but it is a per-call cost where the surface-to-texture path paid only for a
pooled image and a `vkCreateImageView`. One field recording the baked swizzle
would remove it; that field lives in `renderer.h`.

**And the host image is now twice the size.** A 565 texture's `VkImage` is
RGBA8, so its device memory doubles. The cache's own accounting does not
change — `estimate_texture_image_bytes()` already assumed 4 bytes per pixel
for every non-BC format, so it was over-counting these before and is exact
now — which means the eviction threshold will be reached *later* in real
bytes than it used to be, not sooner. That is a pre-existing inaccuracy this
change happens to correct rather than one it introduces, but it is a second
place where the trade is real.

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
