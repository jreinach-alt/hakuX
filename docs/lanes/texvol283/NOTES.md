# texvol283 -- Volume texture Y16 / R16B16 (#283)

Base: master @ d709a8d1fa (rebased from d92ae5d7f3 before registering).
Fix: a5b4141064, `hw/xbox/nv2a/pgraph/glsl/psh.c` + `psh.h`.
Prediction: `docs/testing/predictions/texvol283-bytes16.json`.

## Step 1: re-measure

No Volume texture run newer than `z-repeat-c866527e03-093-Volume_texture`
(09-14, apk 6bf6a11955f3) exists. The 2b04d4d422 full sweep was at suite
004 of ~100 when this lane started, with Volume texture near the end. So the
base arm of this lane's prediction IS the fresh measurement: it runs master
d709a8d1fa on the same six suites. The 09-14 figures, for the record:

| capture | status | differing | off_by_one |
|---|---|---|---|
| Volume_texture/Y16 | white-content | 65,819 | 450 |
| Volume_texture/R16B16 | ok | 48,412 (42,954 by my own PIL diff of the PNGs) | 6,000 |

Nothing that touches the texture decode or the Y16/R16B16 view swizzles
landed between c866527e03 and d709a8d1fa (`git log` over vk/texture.c,
texture.c, gl/texture.c, vk/constants.h, psh.c: pad-stamp, W-clip and
DOT_STR_3D work only). So a residual was expected, and the mechanism below
predicts one.

## The mechanism (derived from the capture, not from #10)

The volume test uploads **raw RGBA8888 bytes** for these two formats:
`TextureStage::SetVolumetricTexture` does `SDL_ConvertSurfaceFormat` to the
format's `sdl_format` (RGBA8888 for both) and swizzles at 4 Bpp. The
per-format converter in `SetTexture` never runs. So in memory each 4-byte
texel is `A, B, G, R` (b0..b3) of `GenerateSurface`'s layer, and Y16 reads the
same buffer at 2 Bpp.

Decoding by hand against the golden:

- **Y16.** R = 255 everywhere in both images. Our G == our B (the
  `{ONE,R,R,ONE}` view). Silicon's G != B. Test with no geometry model at all:
  on **75,822 of 75,840** quad pixels, our G equals
  `round((gold_G * 256 + gold_B) / 257)` -- i.e. silicon (G, B) is exactly the
  (high, low) byte pair of the very 16-bit texel we sample. Every current G
  difference is exactly 1 (21,235 px): UNORM narrowing rounds, silicon takes
  the high byte.
- **R16B16.** Output is alpha-blended over the 0x20 background, alpha = b3 in
  both. At (160,168) silicon is R=118 G=24 B=97 = blend of (b2=x, b1=255-y,
  b0=(x+y)&255) by b3=y; ours is (b3, b1, b1). The diagonal in the golden is
  `(x+y)` wrapping at 256 in the A byte. Whole-frame fit of a
  nearest-sampling model (`texsim.py`/`fitall.py`, below): silicon model vs
  golden 99.3% of quad pixels within 2 levels; our model vs golden 44.6%.

So silicon hands the combiner these formats' **bytes in A8R8G8B8 order**:
R16B16 -> (b2, b1, b0, b3), Y16 -> (1, b1, b0, 1).

**Why every 2D capture is blind to it.** `SetTexture`'s converter writes Y16
as `y * 257` (low byte == high byte) and R16B16 as `{b, b, r, r}`. With equal
bytes, "narrow the field" and "take a byte" are the same number. vk/constants.h
already says so ("the test's converter byte-replicates"). TexFmt_Y16/R16B16
are 0 px today and must stay 0.

## Relation to #10

Not the same mechanism, and this patch does not touch #10's paths. #10's
BumpMap_Y16 / R16B16 and BumpEnvLum classes are the texel consumed by a
BUMPENVMAP / dot stage (`dotmap_hilo_1_16`, `append_hilo16_texel`,
bump_signed), with byte-replicated data. vk/constants.h's own comment puts
that residual in "a 16->8 bit narrowing in psh.c's bump_signed/bump_unsigned
and the byte reconstruction in dotmap_hilo_1". The split here is skipped for
any stage `stage_consumed_raw()` reports, and the `{G,R,R,G}` view stays, so
the gather-based HILO rebuild reads the same fields as before.

## The fix and its limits

`psh.h`: new `tex_bytes16[4]`, a cache-key field computed from TEXFMT and
TEXFILTER. Both are on `pgraph_glsl_check_shader_state_dirty`'s list.
`psh.c`: after the fetch, before the signed-channel block, split the 16-bit
value back into bytes: `round(t * 65535)`, then `& 255` / `>> 8`.

- **Point sampling only** (MIN BOX_LOD0 or BOX_NEARESTLOD, MAG BOX_LOD0,
  which is pbkit's default 0x1012000). A TENT fetch on silicon presumably
  blends each byte on its own. A blended 16-bit value cannot be split back
  into that. Doing it right would need a byte-typed image view
  (MUTABLE_FORMAT + R8G8B8A8 / R8G8 view alongside the 16-bit one), which is
  vk/texture.c work. No capture on the disc exercises it: Bump_env_lum's TENT
  stage is a bump source anyway.
- Not for SNORM views (all four sign flags set).

## Files

The brief listed vk/texture.c, gl/texture.c, texture.c. The fix is none of
those: the decode is right, and the defect is how the combiner sees the
texel. It lives in `glsl/psh.c` + `psh.h`, shared by both renderers. psh.c is
`[free]` on origin/board's territory.toml. Open PR #244 (lane.wbuf31sel)
also lists psh.c in its body; its 36-line hunk is the W-buffer top-cut
clause, a different function. A board request is filed for the grant.

## Measurement / arm

Prediction registered at a_ref d709a8d1fa (master) / b_ref a5b4141064, 2
runs per arm, suites Volume texture, Texture format, Bump map, Bump env lum,
Texture render target, Texture BRDF. Legs: `expect_counts better=2 worse=0`,
with the other 18 Volume texture captures and the other five suites
`must_not_move`. So only Y16 and R16B16 may move, and both must improve.
Magnitudes in the prose: Y16 to at most ~100 px, R16B16 to at most ~2,000.

## Scratch tools (not committed)

`.scratch/texsim.py` rebuilds the test's texture memory: GenerateSurface ->
RGBA8888 bytes -> xbox-swizzle `swizzle_box` at 4 Bpp. It unswizzles at 2 or
4 Bpp with the same masks. `fitall.py` renders both byte models. Its geometry
model (texel centre, slice = floor(p*4)) is only approximate: our model vs
our own capture fits 83% (Y16) / 94% (R16B16). So it separates models but
cannot predict exact pixel counts. **Do not use it for absolute counts.** The
geometry-free G-vs-(G,B) identity above is the test that settles Y16.

## Do not repeat

- Do not look for this in the 2D Y16/R16B16 captures or in vk/texture.c's
  decode. They are exact because the data is byte-replicated.
- Do not change the VkFormat of SZ_R16B16. The `{G,R,R,G}` R16G16 view is what
  #10's textureGather HILO rebuild reads (psh.c `append_hilo16_texel`).
