# lane cullnf276 -- #276 CULL_NEAR_FAR_EN (whole-primitive z reject)

Base: master @ 2de6431cf5, merged to 081dcf4a38 before registering.
Mechanism, pricing and the rule are in `docs/lanes/zclamp276/NOTES.md`; this
lane lands that analysis and does not re-derive it.

## What landed

`ed8e1cd3be` is `docs/lanes/zclamp276/nearfar_cull.diff` as one commit. It
applied to 2de6431cf5 with no conflicts; the offsets moved (psh.c's clip block
now sits at ~:2589) and the text did not. The four files:

| file | change |
|---|---|
| `nv2a_regs.h` | `NV_PGRAPH_ZCOMPRESSOCCLUDE_CULL_NEAR_FAR_EN (1<<0)`, `NV097_SET_ZMIN_MAX_CONTROL_CULL_NEAR_FAR_EN 0xF` |
| `pgraph.c` `SET_ZMIN_MAX_CONTROL` | store bit 0 |
| `glsl/psh.h` `PshState` | `bool cull_near_far` |
| `glsl/psh.c` | read the bit (~:312); after the window-clip block and before `if (ps->state->depth_needed)`, discard when all three `vtxPos{0,1,2}.z` are < `clipRange.z` or all are > `clipRange.w`, emitted only for `cull_near_far && (!depth_clipping \|\| z_perspective)` |

psh.c's hunks are outside lane.pshqueue's (fog INF, DOT_ZW, G8B8, BRDF).
CULL_IGNORE_W (bit 8) stays unmodelled.

## Build check

- `pgraph.c` and `psh.c` compile with the exact NDK clang line from the main
  tree's `compile_commands.json`, with every `-I` re-pointed at this worktree
  (`-c -o /dev/null -Wall`): exit 0, no new warnings. Note the bare
  `-I/home/justin/hakuX` (no trailing slash): a rewrite of
  `/home/justin/hakuX/` alone misses it and silently checks the main tree's
  headers, which reads as "undeclared identifier" for anything new.
- `make -C docs/testing/psh_differ` builds against the new psh.c.
- **Not done:** compiling the generated GLSL for the ZMinMaxControl shapes.
  This session could not run a freshly built binary (psh-differ) without an
  approval nobody was there to give, so the dumped shaders were never fed to the
  NDK's `glslc`. The emitted text is six lines that only read `vtxPos0..2`
  (fragment inputs that are always declared, common.c:66) and `clipRange` (an
  unconditional uniform, psh.h:198). The device arm is the compile check: a
  shader that does not compile shows as a `worse` or unreadable capture, not
  as the priced figures.
- The desktop build is not available on this host (AGENTS.md); not claimed.

## Arm

`docs/testing/predictions/cullnf276-nearfar.json`: a_ref = 081dcf4a38
(master), b_ref = 41be7c432c (master merged onto the fix). Machine legs:
better = 12, worse = 0; the eight Ctrl* / WBuf ZCULL movers exact at 6,737 /
3,384 / 3,490; the other 20 ZMinMaxControl captures and Depth_buffer,
Depth_buffer_fixed_function, W_buffering, Blend_surface, Surface_format,
Depth_Clamp bit-identical. The four CtrlFixed `*NEARFAR_ZCLAMP*` rows carry a
prose band (<= 7,189, max_rgb <= 1).

The exact figures were priced against a run at 8af1bbb18e; no ZMinMaxControl
run exists on a newer master (checked the dispatch results, newest is that
run). Between the two, `wbufdepth24`, `wparamcode223`, `nanfix281` and
`sphere273fix` touched the shader generators. If an exact leg misses, compare
it with A's non-NEARFAR sibling first (`Ctrl_ZCLAMP`, `Ctrl_WBuf_ZCULL`,
`CtrlFixed_WBuf_ZCULL`): a mover that equals its sibling's new residual is
base drift, not the hunk.

## Do not repeat

- Do not rebase this branch: the prediction names 41be7c432c.
- Do not look at `depthClampEnable` (zclamp276's note stands).
