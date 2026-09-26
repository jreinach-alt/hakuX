# lane.pshaniso284 -- land the anisotropy probe-loop and the BRDF fix in psh.c (#284, #315)  [HELD: psh.c is lane.tiecode282's]

NOT STARTABLE until glsl/psh.c is free or released-at-ready (lane.tiecode282, PR #379). Dispatch it the tick it is, one lane for both
issues so two agents do not edit psh.c. Base: master at dispatch. Needs device: yes (arms). Needs NDK: yes.
Files: hw/xbox/nv2a/pgraph/glsl/psh.c, hw/xbox/nv2a/pgraph/vk/texture.c, hw/xbox/nv2a/pgraph/gl/texture.c (guard only),
docs/testing/predictions/pshaniso284-*.json, docs/lanes/pshaniso284/**. (vk/texture.c: confirm no open lane PR holds it.)

## #284: anisotropy (Texture_anisotropy 60,074 px)
docs/lanes/cloud-284/NOTES.md sec "The hunk for the board" has the full model and three hunks: a `tex_aniso[i]` PshState field
(only when MIN is BOX_LOD0), a probe loop in the PROJECT2D 2D path (fractional outer pair, per-2x2-quad coarse derivatives,
count capped at N by widening spacing, texelTieBias per probe), and anisotropyEnable = VK_FALSE for a shaded stage. Offline model:
x2 15,496 -> 404, x4 21,981 -> 2,488, x8 22,617 -> 5,444 (a bound, not a value). Read its "Do not repeat" list first.
Falsifier: the Texture_anisotropy x2/4/8 captures move toward the golden by at least half; x1 unchanged; must-not-move: the
texture-filter suites and lane.tiecode282's tie-rule captures (rebase onto its folded rule; the texelTieBias applies per probe).

## #315: PS_TEXTUREMODES_BRDF (1,842 px, low game value)
docs/lanes/brdf315b/brdf315b-psh.diff is the hunk plus a BRDF case in stage_consumed_raw(); the fit is right when fed 16-bit
fields, not bytes (#283 confusion). Arm: the 3 Texture_BRDF captures; must-not-move: Pixel shader and Texture format suites.
Do it second; the anisotropy hunk is the larger and riskier one.

## Done when
One PR with both hunks (or #284 alone if #315's arm still refutes, saying so), prediction registered after the last rebase, arm
verdicts posted on #284 and #315, out of draft with CI green.
