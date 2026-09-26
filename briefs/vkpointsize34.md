# #34: gate the geometry-shader gl_PointSize writes on shaderTessellationAndGeometryPointSize

Lane: vkpointsize34      Issue: #34 (Vulkan validation layer; harness/robustness, no scored pixels)
Base: origin/master @ 6561442869 (rebase to the tip before you register anything).
Files: hw/xbox/nv2a/pgraph/glsl/geom.c, hw/xbox/nv2a/pgraph/glsl/geom.h, hw/xbox/nv2a/pgraph/vk/instance.c,
       docs/testing/predictions/vkpointsize34-*.json, docs/lanes/vkpointsize34/**
       (if the flag must reach the geometry-shader builder through another file, board-request it; do not guess)
Needs device: yes for the verdict (Thor, Adreno 740 system driver). Needs NDK: yes for the apk.

## The defect
The Adreno 740 Clear run under the Khronos layer (issue #34, [lane.vklayer34] comment, request 1790317606-vklayer34-4071708) counted ONE
VUID: VUID-VkShaderModuleCreateInfo-pCode-08740, SPIR-V capability GeometryPointSize declared without
VkPhysicalDeviceFeatures::shaderTessellationAndGeometryPointSize. glsl/geom.c writes gl_PointSize in the geometry shader whenever
`!opts.gles` (three sites: emit_wedge_vertex ~:194, the emit-vertex block ~:714, the line-clip lerp ~:809). vk/instance.c:846 lists the
feature as `false` (optional), so a device without it gets the capability with the feature off. Lavapipe has the feature, so the desktop
lane reads 0 and cannot see this. Per the spec a GS-emitted point is 1.0 px without the feature.

## The job
1. Give the geometry-shader builder a way to know the feature is off (a field beside `gles` in glsl/geom.h's options, filled from
   r->enabled_physical_device_features where the Vulkan renderer builds them) and skip the three gl_PointSize writes when it is.
   The GL renderer's behaviour stays exactly as it is.
2. Read docs/testing/vk_validation_android.md and #34's Adreno comment first; they name the run, the positive control and the other
   findings. Findings 1-4 in the issue body (descriptor-set updates, push-template layout, LOAD_OP_LOAD hazards) are NOT this lane's:
   shaders.c, surface-compute.c and draw.c are held elsewhere.

## Falsifier
Register one prediction (ab_compare.py --register docs/testing/predictions/vkpointsize34-*.json) AFTER your last rebase, on concrete shas.
must_move: the Adreno Clear run's VUID count 1 -> 0 (same request shape, positive-control lines all present).
must_not_move: the Clear suite's 32 captures, a point-size suite (Point params / Primitive smoothing) on Thor, and every desktop
capture (lavapipe keeps the feature on, so its GS must still write gl_PointSize). Failing world: the count stays 1 (the gate is
keyed on the wrong flag) or a point capture moves on a device that HAS the feature. Read `status` for `unreadable` before trusting any `=0`.

## Done when
The arm verdict is PASS (or each refuted leg is named with its figure) and the PR is ready for review with the verdict cited. Do not edit
the board files; do not queue arms.
