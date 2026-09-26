# lane.vkpointsize34 -- #34, GeometryPointSize without the feature

## Defect
The Adreno 740 Clear run under the Khronos layer (request
1790317606-vklayer34-4071708) counted one VUID,
`VUID-VkShaderModuleCreateInfo-pCode-08740`: SPIR-V declares
`GeometryPointSize` while `shaderTessellationAndGeometryPointSize` is off.
`glsl/geom.c` wrote `gl_PointSize` in the GS whenever `!opts.gles`, at three
sites (`emit_wedge_vertex`, `emit_vertex`, the line-clip lerp).

## Change
- `glsl/geom.h`: `GenGeomGlslOptions.no_point_size`. Zero keeps today's
  shader, so GL (which never sets it) and any zeroed key are unchanged.
- `glsl/geom.c`: the three sites are `!opts.gles && !opts.no_point_size`.
- `vk/shaders.c` (**not this lane's file; board-requested**): set
  `no_point_size` from `r->enabled_physical_device_features
  .shaderTessellationAndGeometryPointSize != VK_TRUE` in
  `shader_binding_build_module_keys`. `vk/instance.c` already enables the
  feature whenever it is available (`F(shaderTessellationAndGeometryPointSize,
  false)`), so it needs no edit.
- `vk/renderer.c` (**board-requested**): `SHADER_STATE_LAYOUT_VERSION` 2 -> 3.
  The new bool fits in the struct's padding (sizeof unchanged), so without the
  bump a `shader_module_keys.bin` written by an older build is regenerated at
  startup with the flag 0 -- a GS that writes `gl_PointSize` -- and the VUID
  count stays 1 on whatever build ran before the B arm. Same trap as #224's
  enum value.
- Patch for both: `shaders-renderer.diff` here (`git apply` on this branch).

## Measured offline
- `capcheck.sh`: glslang (turnipfork build) on a point-mode GS: with the
  `gl_PointSize` read+write, `Capability GeometryPointSize` = 1; without, 0.
  The implicit `gl_PerVertex` still declares the member (decorations remain)
  but glslang adds the capability only on use, so dropping the statements is
  enough.
- No other GS source writes `gl_PointSize` (`grep` over `glsl/*.c`: the only
  other one is `vsh.c:975`, a vertex shader, which needs no capability).
- `cc_check.py`: geom.c, vk/shaders.c, vk/renderer.c, gl/shaders.c compile
  (`-fsyntax-only`, desktop compile commands, worktree headers) with the patch.

## Effect on pixels
Only the POLY_MODE_POINT branch emits points from the GS. On a device without
the feature those points are 1.0 px per the spec (previously undefined /
driver-chosen). Every other GS output is lines/triangles, where gl_PointSize
has no effect. Devices with the feature (lavapipe, any desktop) are unchanged.

## Do not repeat
- `cc_check.py` must rewrite the build's `-iquote /home/justin/hakuX`, or the
  shared tree's `geom.h` wins and the check reads the wrong struct.

## State (2026-09-25)
Waiting on the board grant of vk/shaders.c and vk/renderer.c (request in
$DISPATCH_DIR/board-requests/vkpointsize34.md, PR #371 comment). On grant:
`git apply shaders-renderer.diff`, commit, merge master (no rebase), then
register the prediction on those shas. preflight.sh --allow-tracker passed on
f6db20d771.
