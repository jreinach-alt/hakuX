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

## State at end of session 1 (2026-09-26; superseded, see Arm verdicts)

Waiting on two things outside this session: the arms job's `[job.arms]`
verdicts for both predictions on PR #393, and CI on the pushed head. On
resume: read both verdicts (the #284 at-least-half leg by hand from the
table), merge master again (the brief's addendum; #379 may have folded), and
if psh.c changed underneath, re-register on new refs and re-run the arms before
marking ready.

## Arm verdicts (session 2, 2026-09-26)

Session 1 ended on a `waiting:` comment. The arms finished at about 07:09 PDT,
but the arms job never posted a `[job.arms]` verdict on #284, #315 or PR #393,
so nothing resumed the lane until the host's idle resume. Session 2 read the
four result dirs directly (`scores1.tsv` status `ok` on every row, and
progress-log proof on both arms of each pair), and judged them with
`ab_compare.py --expect`:

| prediction | device | capture | base | fix | change |
|---|---|---|---|---|---|
| pshaniso284-aniso (#284) | nova | Anisotropy-2 | 15,496 | 116 | -99.3% |
| | | Anisotropy-4 | 21,981 | 3,313 | -84.9% |
| | | Anisotropy-8 | 22,617 | 6,003 | -73.5% |
| | | Anisotropy-1 and the other 83 | | | same |
| pshaniso284-brdf (#315) | thor | BRDF_e0_l0 / e0_l1 / e1_l0 | 614 each | 0 each | exact |
| | | the other 72 | | | same |

Both verdicts: PASS (86/86 and 74/74 registered checks). The at-least-half leg
holds on all three anisotropy levels. x4 and x8 land a little above the
offline bound (2,488, 5,444), which the prediction called a bound, not a value.
Each arm is one run. The only captures that differ byte-for-byte are the three
predicted movers per pair, so no unpredicted capture moved.

After this, origin/master @ a5b5b628f2 was merged. It touches none of psh.c,
psh.h, vk/texture.c or gl/texture.c (#387 and #394: vk/surface.c, draw.c,
docs). The binaries the arms measured therefore differ from the merged head
only in code outside the fetch path. The arms were not re-run. The
nv2a_index.json conflict was resolved by rebuilding it at the fold pins
(tests 6743b6ab16), and `check` is clean. #379 (tiecode282) has not folded,
and its head has gained only an audit doc since 6321ec4477.

## Not covered, do not extend without a measurement

- Anisotropy under TENT or with mipmaps: `tex_aniso` stays 1 there, and the
  host sampler keeps its own anisotropy. Games use that case; no capture
  measures it (cloud-284 "What is NOT covered").
- Cube, 3D, rect-under-scale and projective-bump stages take the old fetch.
- A signed-flagged R16B16 feeding BRDF now reaches it unsigned (brdf315b sec 3).

## Audit pass-1 remediation (2026-09-26)

MEDIUM-1: the samplers had dropped host anisotropy for every MIN = MAG =
BOX_LOD0 stage, but the shader takes the probes only on the plain PROJECT2D
path, so cube, 3D, shadow, dependent-read and dot-product stages, and
point-sampled Y16 / R16B16, lost anisotropy with nothing replacing it. Now
there is one predicate, `pgraph_glsl_tex_aniso_probes(pg, i)` in psh.c. It
checks the stage mode (PROJECT2D), that the texture is 2D and not a cube
or depth format, MIN = MAG = BOX_LOD0, and the byte-split test (now
`tex_split_bytes16`, shared with `tex_bytes16`). `tex_aniso` and both
samplers read it. VK folds the result into `TextureKey.max_anisotropy`, so
the two samplers are separate cache nodes. GL passes it through the
`max_anisotropy` it already hands to `apply_texture_parameters`. The
predicate reads SHADERPROG, so SET_SHADER_STAGE_PROGRAM now goes through the
slow method path, which marks dirty the slots whose 5-bit mode changed.
Without that, neither binder would look at the slot again.

LOW-2 fixed as well (`j >= 2` on the BRDF raw-consumption exemption). LOW-1
is left alone: taking the derivatives before the tie bias could move pixels
the arms have already measured.

The arms were not re-run. On every stage the arms measure (2D PROJECT2D
BOX_LOD0, not bytes16), the predicate returns the value the old condition
gave, so the shaders and samplers there do not change. The only change is
on stages where the old code had tex_aniso > 1 and emitted no probes, and
there only the shader key changes, not the GLSL.
