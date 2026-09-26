# Audit pass 1: PR #371 (lane/vkpointsize34), #34

Head audited: b00f39daf5 (merge of origin/master 2dc2b5c49a). Diff read:
`glsl/geom.c`, `glsl/geom.h`, `vk/shaders.c`, `vk/renderer.c`, the prediction
and `docs/lanes/vkpointsize34/`.

**Result: no HIGH, no MEDIUM, two LOW.** Next state: `needs-audit-2`.

## What was checked and holds

- All three `gl_PointSize` writes in `glsl/geom.c` are gated. A grep finds no
  other GS site that writes or reads `gl_PointSize`; `vsh.c:976` is the VS,
  which needs no feature. With the writes gone the `gl_in[].gl_PointSize`
  reads go too, so glslang no longer emits `GeometryPointSize` (lane's
  `capcheck.sh`).
- GL is unchanged: `gl/shaders.c:377` memsets the key before filling it, so
  `no_point_size` is 0 and the GS text is byte-identical.
- Vulkan: `vk/shaders.c:828` memsets `geom_key` before setting the flag, and
  `hash_shader_module_key` / `compare_shader_module_key` cover the whole
  `key->geom` (`sizeof(key->geom)`), so the flag reaches both hash and compare.
- The flag reads the *enabled* feature. `instance.c:846` requests
  `shaderTessellationAndGeometryPointSize` as optional, so it is enabled
  whenever available and the flag is 0 on every fleet device.
- Persisted keys: `SHADER_STATE_LAYOUT_VERSION` is 4 after the merge. Master's
  3 is `aa_offset_x` (#286); the lane's own 3 was renumbered in b00f39daf5, so
  there is no collision. A driver swap (system driver to adrenotools or back)
  changes `gpu_driver_id.bin` (vendor, device, driverVersion,
  pipelineCacheUUID) and wipes the cache, so a key stored with
  `no_point_size=1` cannot be replayed onto a driver that has the feature.

## LOW-1: point-mode polygons draw 1 px on a driver without the feature

Scenario: a title draws triangles with `POLY_MODE_POINT` and a point size > 1
on the Adreno system driver (feature `missing`). The GS (`geom.c:503`,
`layout(points)`) no longer writes `gl_PointSize`, so the spec fixes the size
at 1.0. Before the fix the shader was invalid and the size was whatever the
driver chose. The lane records this (NOTES: "Only the POLY_MODE_POINT branch
emits points"). No run measures it: the arm is on the fleet driver, where the
flag is 0, and the system-driver survey ran Clear only. `Point_size/*` draws
POINTS, which `pgraph_glsl_need_geom` sends around the GS, so it would not
exercise this either. It trades an invalid module for a defined 1 px, confined
to one driver and one polygon mode. If it matters later, the fix is to expand
points to quads in the GS for that path, not to restore the write.

## LOW-2: the PR body and the prediction still say "2 -> 3"

The PR body and the prose of `vkpointsize34-fleet-inert.json` describe
`SHADER_STATE_LAYOUT_VERSION 2 -> 3`; the head has 3 -> 4 after the master
merge. The prediction's `b_ref` 97f221cac0 predates that merge. The merge only
renumbers the version and brings in master, so the arm verdict (78/78
byte-identical) still describes the fix's shader text. Correct the body when
next touching the PR; nothing to re-run.

## For pass 2

Neither LOW needs a code change. LOW-1 is a recorded trade. LOW-2 is wording
in the PR body. The `needs-rebase` label looks stale: at audit time the head's
merge-base is origin/master 2dc2b5c49a.
