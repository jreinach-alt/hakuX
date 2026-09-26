# lane.zrtz272 -- round-toward-zero fixed-function screen z (#272, #275 Swap)

Base: origin/master @ 24208f15cb (#321's position tail already in).
Analysis, pricing and "Do not repeat": `docs/lanes/zdepth272/NOTES.md`. This lane
lands its hunk (`docs/lanes/zdepth272/vsh-ff-zrtz.patch`) and registers its arm.

## What landed

`aa2b4e1582`, one commit, `hw/xbox/nv2a/pgraph/glsl/vsh-ff.c` only, +86 lines, in
`pgraph_glsl_gen_vsh_ff`:

1. The RTZ helpers (`ffRtz`, `ffTwoProd`, `ffMulRtz`, `ffAddRtz`, `ffDotRtz`,
   `ffAboveOne`, `ffRcpRtz`, `ffScreenZ`) go after the `texPlaneQ3` define block,
   as the patch has them.
2. `vtxPos.z = ffScreenZ(tPosition)` for finite tPosition. This goes after #321's
   `carry` block, which is where the patch's hunk 2 was offset to. Nothing else
   changes: `oPos`, `vtxPos.w` and x/y are untouched.

The patch's hunk 1 applied at its own offset. Hunk 2 failed `git apply` only
because #321 had grown the context above it. It was placed by anchoring on the
closing `carry);` of that block. The added lines are byte-for-byte the patch's.

## Compiled

`check_rtz.py` reuses wparamcode223's `vshemit` emitter, which is the real
`vsh-ff.c` built with gcc against psh_differ's shims, and its glslc harness (the
NDK's `glslc`). It compiles the full FF vertex shader, skinning off/on × lighting
off/on, for vulkan1.0 and opengl: **8/8 OK**. Every variant contains the helpers and
the `vtxPos.z` statement. Three type mutants of the new code are all **REJECTED**
(one in the body statement, one in `ffScreenZ`, one in `ffRcpRtz`), so the new code
really is what glslc read.

    bash docs/lanes/wparamcode223/vshemit/build.sh
    python3 docs/lanes/zrtz272/check_rtz.py

This compiles the source. It does not check how Adreno honours `precise`, and
psh.c's depth floor already depends on the same thing. The arm checks that.

**The shader cache cannot make the arm inert.** `spv_cache` is keyed on a hash of
the GLSL text (`vk/glsl.c` `pgraph_vk_create_shader_module_from_glsl`), and the
dispatcher clears the app's shader caches whenever the apk changes
(`dispatcher.sh` `clear_shader_caches_on_apk_change`). No enum or state-struct
field was added.

## The arm

`docs/testing/predictions/zrtz272-rtz.json`: a_ref `b2cf2a6624` (the fix's
parent: master 24208f15cb plus this lane's first notes commit, docs only), b_ref
`aa2b4e1582`. It was registered with the zdepth272 NOTES command. The disc is the
same 12 suites. The departures from that command:

- `ZetaIntoColor*` is in **must_not_regress**, not must_not_move. It is left off
  the brief's must_not_move list. Its colour capture differs by 71,663 px today,
  and silicon's depth word there is 3 off our RNE value, so an improvement must
  not fail the arm.
- `must_not_regress` was added by hand (the flag does not exist):
  `Depth_buffer_fixed_function/*`, `ZetaIntoColor*`, `W_buffering/ZBuf*_V0_*`,
  `Depth_Clamp/*`, `Depth_function/*`, `Stencil/*`, `Stencil_func/*`,
  `ZPass_pixel_count/*`, `Clear/*`. Every leg was checked against
  `/home/justin/goldens/results` and every one matches at least one golden.
- The per-capture figures were checked against a scored run
  (`0-a-now-8e683b3a26-023`): the z24 FZy rows are 24 px **per capture**, both
  colour (status `blank`) and `_ZB`, so `=3` and `=0` per capture are the right
  legs.

The stated bands, judged by reading the table because `--register` cannot express
a range:

| capture | now | band |
|---|---:|---|
| `z24_C?_FZn_Mffffff_ZB` | 144,566 | 47,935 .. 53,852 |
| `z24_C?_FZn_Mc00000_ZB` | 4,834 | 989 .. 1,037 |
| `z24_C?_FZn_M800001_ZB` | 2,868 | 520 .. 568 |
| `z24_C?_FZn_M400002_ZB` | 1,506 | 113 .. 145 |
| `z16_C?_FZn_M00ffff_ZB` | 2,840 | 424 .. 456 |

## Status

Waiting for the arms job's `[job.arms]` verdict on PR #364. Before believing any
`=0`, read `scores1.tsv` `status` for `unreadable` and the run log for PARTIAL
COVERAGE.

## Do not repeat

- `git apply` of the zdepth272 patch fails on master after #321. Place hunk 2 by
  anchoring on the `carry);` block. Do not re-derive the hunk.
- The Bash tool rejects heredocs that contain quoted braces. Write scratch
  scripts to files.
