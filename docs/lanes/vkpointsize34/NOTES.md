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

## Why attempt 1 did not finish
The grant landed on origin/board (ae93c49630, delivered as a PR #371 comment)
while the session sat waiting. The session had applied the patch to the
worktree but not committed it. It then ended saying it would continue when a
background notification arrived. A headless session's background tasks end
with it, so that notification could never arrive. Nothing was queued or
registered.

## Attempt 2 (2026-09-26)
- 97f221cac0: the granted hunks (vk/shaders.c sets `no_point_size`;
  vk/renderer.c layout version 3).
- Which driver lacks the feature (`featgrep.py` over dispatch logcats):
  every fleet run (purple adrenotools driver, Thor and Nova) logs
  `vk feature shaderTessellationAndGeometryPointSize: available`. Only the
  system-driver run 1790317606-vklayer34-4071708 logs `missing`. So on the
  fleet the fix leaves the shader text unchanged. It changes the shader only
  where the VUID was seen.
- Two measurements, because one ref pair cannot cover both drivers:
  1. **Arm** (fleet driver, arms job): `predictions/vkpointsize34-fleet-inert.json`
     (sha256 6be17e7a...), a=6550967a5e (master) b=97f221cac0, must_not_move
     Clear/*, Point_size/*, Point_params/*.
  2. **VUID survey** (system driver + layer): 386af38184 = e2c9fef860's
     instrumentation cherry-picked onto the fix, reverted by 1cd7991284 (the
     branch diff is unaffected). Queued as 1790408065-vkpointsize34-3720485
     (Clear, thor, the same shape as the A run). Count it with
     `python3 docs/lanes/vklayer34/count_vuids.py <result dir>`. The pass
     condition is 08740 = 0, with every control line present and the
     `hakuX` log line reading `missing`.
- Desktop is not armed: lavapipe has the feature, so the flag is 0 and the
  shader text is the same.

## VUID survey result (2026-09-26, `survey_ab.py`)
| | A 1790317606-vklayer34-4071708 | B 1790408065-vkpointsize34-3720485 |
|---|---|---|
| ref / apk_sha | e2c9fef860 / 6b99875f661e | 386af38184 / e71fca32c816 |
| device, driver feature | thor, `missing` | thor, `missing` |
| control lines (5) | PASS | PASS |
| captures, progress_log_proof | 32, true | 32, true |
| validation messages | 1 (08740) | **0** |

The must-move leg passes: 1 -> 0, with the layer shown loaded and the
feature off.

Six Clear captures differ between A and B (SCF_R5G6B5 40,920 -> 0, and so
on). A was built on a Sep 24 base and B on today's master. B's six values
(0 / 65,472 / 65,568 / 0 / 0 / 0) equal every fleet-driver Clear run on
master since 1790361025-vtxarr262-base (`clear_recent.py`), so the move came
from master, not from this fix. The same-base pixel check is the fleet arm.

## Why attempt 2 did not finish
It ended correctly, on a `[lane.vkpointsize34] waiting:` comment naming the
arms job's verdict (outside the session). The resume that followed carried an
addendum written about attempt 1 ("half the fix in, no arm queued"); by then
the fix was committed and the arm was queued. Nothing was lost.

## Fleet arm verdict (2026-09-26, attempt 3)
`ab_compare.py --a 1790408995-arms-vkpointsize34-base-14733
--b 1790408995-arms-vkpointsize34-fix-14755
--expect docs/testing/predictions/vkpointsize34-fleet-inert.json`:

| | A base | B fix |
|---|---|---|
| ref / apk_sha | 6550967a5e / b5f276b45557 | 97f221cac0 / 3abe701ef94d |
| captures, progress-log proof | 78, yes | 78, yes |
| feature in logcat | `available` | `available` |
| Clear / Point_params / Point_size differing | 131,040 / 13,128 / 20,579 | same |

better 0, worse 0, same 78; every capture is byte-identical between the arms.
**VERDICT: PASS, all 78 registered checks hold.** ab_compare prints
"UNBOUND" because the arms job queued the arm without `request.sh --expect`.
The prediction was committed at 07:34Z, before either arm ran.

Both legs pass: VUID 1 -> 0 on the system driver (survey above), and no pixel
moves on the fleet driver, which has the feature.

## Why attempt 3 did not finish (and did not need to)
It finished: verdict recorded, PR #371 marked ready, audited (`verified`).
The fold then failed on 2026-09-26 02:20 PDT because master had moved
under it: `vk/renderer.c` conflicted at `SHADER_STATE_LAYOUT_VERSION`.
Attempt 4 is the merge only.

## Attempt 4 (2026-09-26): merge origin/master, resolve the version bump
- Conflict: both sides bumped `SHADER_STATE_LAYOUT_VERSION` 2 -> 3. Master's
  3 is `aa_offset_x` (#286, PR fold after this branch's merge base); this
  branch's 3 was `no_point_size`.
- Resolution: keep both comment entries, master's field stays 3, ours becomes
  **4**. A cache written by a master build at version 3 has `aa_offset_x` but
  reads `no_point_size` as 0 (padding), which is exactly the trap the bump
  exists to avoid, so the merged tree must not share master's number.
- `cc_check.py` on renderer.c, shaders.c, geom.c after the merge: rc=0.
- `git merge`, not rebase: the registered prediction's refs (6550967a5e,
  97f221cac0) stay ancestors. Nothing was re-measured; the arm's shas are
  unchanged and the only new hunk is a comment plus an integer.
