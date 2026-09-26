# lane.zrtz272 -- round-toward-zero fixed-function screen z (#272, #275 Swap)

Base: origin/master @ 24208f15cb (#321's position tail already in); merged
origin/master @ 6550967a5e on 2026-09-26 for arm 2.
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

## Why attempt 1 did not finish

It ended its session on a `waiting:` comment for the `[job.arms]` verdict. That was
correct: the wait was on something outside the session. The arm then judged FAIL at
00:22 PDT and marked the PR `regressed`, but nothing resumed the lane until hostops did
at 12:33 AM. Attempt 2 (this one) judges the arm and carries the PR.

## Arm 1 verdict: FAIL, 48 of 1263 checks (`zrtz272-rtz.json`)

Results `1790402845-arms-zrtz272-base-1549230` and `-fix-1549317`, one run each, 983
captures each. Neither log has `UtilAcceptVsock`. PARTIAL COVERAGE is the known
Depth_buffer 144/784 and ZPass 72/78 floor, the same in both arms. No row is
`unreadable`.

**Landed as predicted:**

| capture (×2, Cn and Cy) | A | B | predicted |
|---|---:|---:|---|
| `Color_zeta_overlap/Swap` (#275) | 165,447 | **0** | 0 |
| `z24_C?_FZn_Mffffff_ZB` | 144,566 | 47,935 | 47,935 .. 53,852 |
| `z24_C?_FZn_Mc00000_ZB` | 4,834 | 989 | 989 .. 1,037 |
| `z24_C?_FZn_M800001_ZB` | 2,868 | 520 | 520 .. 568 |
| `z24_C?_FZn_M400002_ZB` | 1,506 | 113 | 113 .. 145 |
| `z16_C?_FZn_M00ffff_ZB` | 2,840 | 424 | 424 .. 456 |
| `z24_C?_FZn_M000003` and `_ZB` | 24 | 0 | 0 |
| `z16_C?_FZn_M00{4002,8001,c000}_ZB` | 16/32/32 | 0 | 0 |
| `z16_C?_FZy_M008001_ZB` | 13 | 0 | 0 |

Every band landed on its pure-replay edge exactly. Unpredicted gains:
`W_buffering/ZBuf24D_FloorQuad_V0_*_Z` 161,700 → 15,530 and 153,860 → 59,873;
`ZBuf24F_FloorQuad_V0_*_Z` −980 to −1,698.

**Refuted, with the measured figure:**

- `z24_C?_FZy_M*` (F24, 10 colour and 10 `_ZB`): 24 → **406** colour and **403** `_ZB`.
  The model predicted 3 and 0. Pixels: 0x300 is the F24 clear. Silicon draws a
  zero-depth vertical line at x=136 and a short horizontal one at y=53. RTZ makes the
  near-plane vertex z exactly 0, which passes the depth clip (`zvalue < clipRange.z`),
  so we draw y=53 as silicon does. We also draw a horizontal line at y=56, a diagonal,
  and a 373-px vertical line at x=502, none of which silicon has. The model had the
  vertex z right (0) and did not model which of those zero-depth edges the rasteriser
  keeps. **Hunk out for F24** (see below).
- `z16_C?_FZy_M00c000_ZB`: 34 → 1 (predicted 0). `z16_C?_FZy_M00ffff_ZB`: 495 → 393
  (predicted 392). Each is 1 px from the model, and each is a large improvement. They
  are left in, and arm 2 registers the measured figures as a replication.

**Not attributable to the hunk (noise), from other runs on disk:**

- `Blend_surface/R5G6B5_Add_SrcA_DstA` 11,964 → 14,833. 14,833 is the value in every
  one of about 40 other scored runs, so the base arm was the outlier.
- `Stencil/Stencil_ZERO`, `_ST_DT`, `_ST_DT_ZB` 0 → 40,000/30,000. The Stencil_ZERO*
  family reads 0, 5,050, 20,000, 30,000 or 40,000 between runs, including between two
  runs of the same apk (`a7b9d28e6b84`: region200 dryrun vs full6743 dry2). Arm 2
  guards `Stencil/Stencil_REPLACE*` only.

## The F24 gate (`e603fb3540`)

`vtxPos.z = ffScreenZ(...)` now also requires `clipRange.y <= 16777216.0`. clipRange.y
is f24_max (1e30) on F24 and at most 2^24 on D24, D16 and F16
(`common.c pgraph_glsl_set_clip_range_uniform_value`). It is a uniform, so the shader
key and the cache are unchanged. Compiled: `check_rtz.py` passes 8/8 and rejects all 3
mutants. The emitted body contains the gate.

What it gives up: arm 1's `ZBuf24F_FloorQuad_V0_*_Z` gains (−4,638 px over 4
captures) go back, against 20 × ~380 px refuted on DBFF. F24 near-plane RTZ needs the
rasteriser's zero-depth edge rule first. That is a separate issue, not this hunk.

## Arm 2 (`zrtz272-rtz2.json`)

a_ref `6550967a5e` (origin/master at the merge), b_ref `e603fb3540` (merge + RTZ hunk
+ F24 gate). The disc is arm 1's. It has the same legs, with these changes:
`z24_C?_FZy_M*` and `_ZB` `=24` (unchanged from master); `z16 FZy M00c000_ZB=1` and
`M00ffff_ZB=393` (arm 1's measured figures); `must_not_regress` has `Stencil_REPLACE*`
instead of `Stencil/*`, and `ZetaIntoColor*` as before. The five bands are still judged by
reading.

**Status (2026-09-26):** waiting for arm 2's `[job.arms]` verdict and CI. PR #364
stays in draft until then. On resume: check scores1.tsv status and PARTIAL COVERAGE,
judge the bands, then mark ready.

## Do not repeat

- `git apply` of the zdepth272 patch fails on master after #321. Place hunk 2 by
  anchoring on the `carry);` block. Do not re-derive the hunk.
- The Bash tool rejects heredocs that contain quoted braces. Write scratch
  scripts to files.
- Do not put RTZ back on F24 as it stands. Arm 1 measured 24 → 403..406 on all 20
  z24 FZy captures, from zero-depth edges passing the clip.
- Do not debug `Stencil_ZERO*` or `Blend_surface/R5G6B5_Add_SrcA_DstA` movement from
  a single-run arm. Both move between runs of one apk.
