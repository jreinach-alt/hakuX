# lane.pshaniso284: #284 anisotropy probes and #315 BRDF in glsl/psh.c

Base: master @ 0e7ba4c334, with lane/tiecode282 (PR #379 @ 6321ec4477) merged
first for its psh.c tie rule, then master @ 98990d3c7c merged (docs only).

## What landed

| commit | issue | change |
|---|---|---|
| 1557f40923 | #284 | `PshState.tex_aniso[i]` = 1 << TEXCTL0 MAX_ANISOTROPY when MIN = MAG = BOX_LOD0 (and not a #283 byte-split stage), else 1. PROJECT2D 2D non-cube: `psh_append_aniso_probes()` replaces the single `textureProj` when it is > 1. vk and gl samplers: host anisotropy off for MIN = MAG = BOX_LOD0. `tex_aniso` added to the psh-differ field table. |
| 929efa3d4e | #315 | `docs/lanes/brdf315b/brdf315b-psh.diff` applied as is (`git apply`, offsets only): BRDF sampler3D, the volume lookup, and the BRDF case in `stage_consumed_raw()`. |

The probe loop is cloud-284's model exactly: coarse derivatives (`dFdxCoarse`
on Vulkan; desktop GL 400 and GLES have no coarse form and take `dFdx`), in
guest texels (`textureSize / texScale`, times `surfaceScale` so an upscaled
surface keeps the guest footprint), the minor axis floored at 1 texel, spacing
widened to Pmaj/N, the fractional outer pair, `textureLod(..., 0.0)` per
probe on `uv + texelTieBias<i>`.

MAG is required to be BOX_LOD0 as well as MIN because `textureLod(lod 0)` has
lambda = 0, which Vulkan resolves with the MAG filter.

## Checked offline

- psh-differ: `tex_aniso[i]` changes the shader in 7 of 8 probes per stage,
  0 aborts. The loop is reached by the basic, stages, border and bumpenv
  baselines; each probe shader (N = 8 and N = 3) compiles with the NDK's
  `glslc` for Vulkan 1.1 and for OpenGL. GLES cannot be checked with glslc
  (SPIR-V wants ES 310 and uniform blocks); the unmodified base shader fails
  there identically.
- `gen_brdf.c` emits Texture_BRDF's wiring (CUBEMAP, CUBEMAP, BRDF on 3D,
  R16B16 cube stages with `tex_bytes16`). It compiles for Vulkan and GL, the
  lookup is `texture(texSamp2, vec3(t0.r, t1.r, fract(t1.g - t0.g)))`, and
  neither t0 nor t1 is rewritten after its fetch, so the fields reach the
  lookup whole.

## Predictions (registered after the last merge)

- `docs/testing/predictions/pshaniso284-aniso.json` (#284): a 31d6ec49b0,
  b 1557f40923. Anisotropy-2/4/8 better (the at-least-half leg is read off the
  table; ab_compare has no threshold leg), Anisotropy-1 and the filter, BRDF,
  and #282 tie-rule suites bit-identical.
- `docs/testing/predictions/pshaniso284-brdf.json` (#315): a 1557f40923,
  b 929efa3d4e. The 3 Texture_BRDF captures better (614 -> <= 4 each);
  Pixel shader, Texture format, Volume texture, Texture anisotropy
  bit-identical.

## State at end of session 1 (2026-09-26)

Waiting on two things outside this session: the arms job's `[job.arms]`
verdicts for both predictions on PR #393, and CI on the pushed head. On
resume: read both verdicts (the #284 at-least-half leg by hand from the
table), merge master again (the brief's addendum; #379 may have folded), and
if psh.c changed underneath, re-register on new refs and re-run the arms before
marking ready.

## Not covered, do not extend without a measurement

- Anisotropy under TENT or with mipmaps: `tex_aniso` stays 1 there, and the
  host sampler keeps its own anisotropy. Games use that case; no capture
  measures it (cloud-284 "What is NOT covered").
- Cube, 3D, rect-under-scale and projective-bump stages take the old fetch.
- A signed-flagged R16B16 feeding BRDF now reaches it unsigned (brdf315b sec 3).
