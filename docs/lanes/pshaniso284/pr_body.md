Lane: pshaniso284            Issue: #284 #315
Base: master @ 0e7ba4c334 (+ lane/tiecode282 @ 6321ec4477, PR #379, merged for its psh.c tie rule; + master @ 98990d3c7c, then a5b5b628f2)
Files: hw/xbox/nv2a/pgraph/glsl/psh.c, hw/xbox/nv2a/pgraph/glsl/psh.h, hw/xbox/nv2a/pgraph/vk/texture.c, hw/xbox/nv2a/pgraph/gl/texture.c, docs/testing/psh_differ/differ.c, docs/testing/nv2a_index.json, docs/testing/predictions/pshaniso284-aniso.json, docs/testing/predictions/pshaniso284-brdf.json, docs/lanes/pshaniso284/NOTES.md, docs/lanes/pshaniso284/gen_brdf.c, docs/lanes/pshaniso284/pr_body.md
Prediction: docs/testing/predictions/pshaniso284-aniso.json @ f19c1ec651d0d6ab3d8c47adb8e5c0fa1acb73f987e87ac55a5983dc9dbf57bc ; docs/testing/predictions/pshaniso284-brdf.json @ 6b5688632f73317ed8eaeae61fddbb815b36bafd46078067cab7c86144e5d5e0
Needs device: yes    Needs NDK: yes

Until #379 folds, `git diff origin/master...HEAD` also lists #379's files (docs/lanes/tiecode282/**, docs/testing/predictions/tiecode282-*.json, and its share of psh.c/psh.h/differ.c). They are not this lane's edits.

## Verdicts

| arm | capture | base | fix |
|---|---|---|---|
| #284 (nova) | Anisotropy-2 / 4 / 8 | 15,496 / 21,981 / 22,617 | 116 / 3,313 / 6,003 |
| #315 (thor) | BRDF_e0_l0 / e0_l1 / e1_l0 | 614 each | 0 each (exact) |

Both PASS: 86/86 and 74/74 registered checks, with no other capture moved. The merge of master after the arms leaves psh.c, psh.h and both texture.c files unchanged.

## #284: NV2A anisotropic probes (1557f40923)

`PshState.tex_aniso[i]` = 1 << TEXCTL0 MAX_ANISOTROPY when MIN = MAG = BOX_LOD0, else 1. When it is > 1, the PROJECT2D 2D non-cube fetch becomes cloud-284's probe model: per-quad (coarse) derivatives in guest texels, probes one minor width apart along the major column, the minor floored at 1 texel, spacing widened to Pmaj/N past N probes, a fractional outer pair, each probe a `textureLod(.., 0)` point sample on `uv + texelTieBias<i>`. The vk and gl samplers drop host anisotropy for MIN = MAG = BOX_LOD0 so a driver that honours it under NEAREST cannot filter twice. N = 1 keeps the old fetch, so Anisotropy-1 and every capture that never raises MAX_ANISOTROPY take unchanged code.

Offline model bound (not a value): x2 15,496 -> 404, x4 21,981 -> 2,488, x8 22,617 -> 5,444.

## #315: PS_TEXTUREMODES_BRDF (929efa3d4e)

`docs/lanes/brdf315b/brdf315b-psh.diff` as is: the BRDF volume lookup plus a BRDF case in `stage_consumed_raw()` so #283's byte split leaves the two feeding stages' 16-bit fields whole. Predicted 614 -> <= 4 px on each Texture_BRDF capture.

## Checked offline

| check | result |
|---|---|
| psh-differ `tex_aniso[i]` | changes the shader in 7 of 8 probes per stage, 0 aborts |
| glslc (NDK), aniso loop N = 8 and N = 3 | compiles for Vulkan 1.1 and OpenGL in the 4 baselines that reach it |
| glslc, Texture_BRDF wiring (`gen_brdf.c`) | compiles for Vulkan and OpenGL; t0/t1 are not rewritten before the lookup |
| preflight.sh | passed (after the nv2a index rebuild) |

## Arms

Two registered predictions, one per commit: #284 a 31d6ec49b0 -> b 1557f40923; #315 a 1557f40923 -> b 929efa3d4e.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
