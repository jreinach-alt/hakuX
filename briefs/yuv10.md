# lane.yuv10 -- #10 YUV class: implement SET_CONTROL0's colour-space conversion as silicon measured it

Lane: yuv10
Issue: #10
Base: origin/master (merge origin/master first; never rebase)
Files: hw/xbox/nv2a/pgraph/pgraph.c, hw/xbox/nv2a/nv2a_regs.h, hw/xbox/nv2a/pgraph/texture.c, hw/xbox/nv2a/pgraph/glsl/psh.c, hw/xbox/nv2a/pgraph/glsl/psh.h, docs/testing/predictions/yuv10-*.json, docs/lanes/yuv10/**

pgraph.c is LENT from lane.ring53impl (PR #395) for ONE hunk: the `DEF_METHOD(NV097, SET_CONTROL0)` handler
(and nothing else in the file). ring53impl's own pgraph.c hunks are in the reg-category table, the method
fast/slow paths and SET_BEGIN_END; do not touch those regions. The file returns to ring53impl when this PR is ready.

## Why (evidence)
lane.xbox measured the mechanism on the project console on 2026-09-26 (PR #411, docs-only, fold-ready;
results on #10, comment 5848958489; full write-up `docs/testing/xbox-csc-2026-09-26.md` on lane/xbox-csc10).
Every registered leg held (K1, K2, K3, K4, A1, B1). The rules:
1. SET_CONTROL0 bits 28-31 = CRYCB_TO_RGB converts EVERY texture stage's output, any format, no dependent read
   needed. hakuX drops the field (pgraph.c SET_CONTROL0 handler).
2. The converter is util.h `convert_ycbcr_to_rgb()` with Y=R, Cb=G, Cr=B, alpha unchanged, red rounding
   constant 128 (exact on 256/256 cells; 127 gives 241/256).
3. YUY2/UYVY fetch RAW as (texel's own Y, pair's Cb, pair's Cr, 255). With the field off that raw value is the
   stage's output. hakuX decodes at upload regardless (texture.c:516 FIXME).
4. Conversion happens AFTER the texture shader: bump offsets and luminance read the unconverted fetch; the
   luminance product is truncated (PR #168), then converted.
Under these rules `docs/lanes/xbox/csc_measured_model.py` takes BumpMap_YUY2_L, BumpMap_UYVY_L,
BumpEnvLum_YUY2_L and BumpEnvLum_UYVY_L from 111,496 px each to 1,688 (the 422 px/quad sign-label floor).

## Build
1. nv2a_regs.h: define the SET_CONTROL0 colour-space field (bits 28-31) and a NV_PGRAPH_CONTROL_0 home for it.
   pgraph.c: store it in the SET_CONTROL0 handler (mark the shader state dirty if needed).
2. psh.h / psh.c: carry the field in PshState (it is part of the shader key); when set, convert each stage's
   output with the measured converter after all texture-shader math (bump, luminance, dot products) has read the
   raw fetch.
3. texture.c: upload YUY2/UYVY raw as (Y, Cb, Cr, 255) per texel. CAUTION: texture.c:500-503 records that
   Texture_format's TexFmt_YUY2_L / TexFmt_UYVY_L are 0 px today; check which SET_CONTROL0 those tests send.
   If they rely on the field being set, rule 1 keeps them exact; if not, silicon says the raw value is right and
   the golden decides. Read the goldens before you change the upload, and say in NOTES which it is.
4. Truncate the luminance product for YUV sources as for the rest (confirm PR #168's truncation already covers it).

## Proof
- Register a prediction `docs/testing/predictions/yuv10-csc.json` after your last rebase (a_ref = parent,
  b_ref = your commit): the four captures above 111,496 -> <= 2,000 each; Texture_format's YUY2/UYVY captures
  must not rise (a must-not-move leg); every other Bump capture unchanged within noise.
- Dry-run the model first: `csc_measured_model.py` against the goldens must reproduce 1,688 before you edit C.
- The arm job runs the A/B; do not queue a full sweep (pilot rule: nothing over 30 min on a device without a
  reviewed pilot).

## Do not
- Touch pgraph.c outside the SET_CONTROL0 handler.
- Edit board files (territory.toml, nv2a_issues.toml, briefs/).
- Mark the PR ready before the arm verdict is in; then merge origin/master and mark it ready.
