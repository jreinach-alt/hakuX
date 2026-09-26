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

## Arm 2 verdict: FAIL, 1 of 1255 checks (`zrtz272-rtz2.json`)

Results `1790410947-arms-zrtz272-base-885745` (apk `b5f276b45557`) and `-fix-885784`
(apk `7c6260f3f710`), one run each, 983 captures each, judged 09:50Z. Neither log has
`UtilAcceptVsock`. PARTIAL COVERAGE is the same Depth_buffer 144/784 and ZPass 72/78
floor in both arms. No row is `unreadable` (base: 874 ok, 100 white-content, 9
label-differs; fix: 876 / 98 / 9).

**Every registered leg held, and every band landed on the value arm 1 read:**

| capture (×2, Cn and Cy) | A | B | leg |
|---|---:|---:|---|
| `Color_zeta_overlap/Swap` (#275) | 165,447 | **0** | =0 |
| `z24_C?_FZn_Mffffff_ZB` | 144,566 | 47,935 | 47,935 .. 53,852 |
| `z24_C?_FZn_Mc00000_ZB` | 4,834 | 989 | 989 .. 1,037 |
| `z24_C?_FZn_M800001_ZB` | 2,868 | 520 | 520 .. 568 |
| `z24_C?_FZn_M400002_ZB` | 1,506 | 113 | 113 .. 145 |
| `z16_C?_FZn_M00ffff_ZB` | 2,840 | 424 | 424 .. 456 |
| `z24_C?_FZy_M*` colour and `_ZB` (20) | 24 | 24 | =24 (F24 gate holds) |
| `z24_C?_FZn_M000003` and `_ZB` | 24 | 0 | =0 |
| `z16_C?_FZn_M00{4002,8001,c000}_ZB` | 16/32/32 | 0 | =0 |
| `z16_C?_FZy_M008001_ZB` | 13 | 0 | =0 |
| `z16_C?_FZy_M00c000_ZB` / `M00ffff_ZB` | 34 / 495 | 1 / 393 | =1 / =393 (replicated) |
| `W_buffering/ZBuf24D_FloorQuad_V0_*_Z` | 161,700 / 153,860 | 15,530 / 59,873 | must_not_regress |

`ZBuf24F_FloorQuad_V0_*` did not move (the F24 gate gives those back, as priced).
Totals: 38 better, 1 worse, 944 same; exact 278 → 290. `Stencil/Stencil_ZERO_ST_ZB`
0 → 30,000 is the unguarded Stencil_ZERO* family again.

**The one violated check:** `must_not_move Blend_surface/X_O1RGB5_Add_SrcA_DstA`
15,016 → 12,274 (better). It is not the hunk's, on four independent reads:

1. **The capture has exactly two images on disk.** Its fix-arm image is byte-identical
   (sha256 `737252c6f3ff`) to `padwrite59-base` (09-14), `pad59A` runs 1-3 (09-18) and
   the `z-c866527e03` sweep, all builds without this hunk. Its base-arm image
   (`07624ee15fe9`) is the one every other 2026-09-25/26 run produced.
2. **The two images differ in one block**, x 32..159, y 92..203 (8,389 px): the first
   128×128 render-to-surface swatch at `kMargin`/`top` in `blend_surface_tests.cpp`.
   One state is mostly white there (1,549 white px), the other has content. The
   6,627 px outside that block are identical between the arms and against the golden.
3. **The sibling `R5G6B5_Add_SrcA_DstA` flips the same block within one apk:**
   pshqueue base `47f492ec0654` run1 14,833 vs run2 11,964, and its fix
   `dafaf822bc87` the same; the diff is 8,393 px in the identical bbox. That is the
   row arm 1 moved the other way. Arm 2 did not move it.
4. **The hunk cannot reach the test.** `BlendSurfaceTests` sets
   `NV097_SET_DEPTH_TEST_ENABLE` false, so vertex z decides nothing in it, and
   `X_Z1RGB5_Add_SrcA_DstA`, the same draw calls with a different surface format,
   was byte-identical across the arms.

One-run arms cannot separate a nondeterministic flip from a build-correlated one
(pad59A read 12,274 in 3 of 3 runs, pad59B 15,016 in 3 of 3), and this arm does not
try. What it can say is that the fix arm drew a picture that other builds without
the hunk have drawn, in a test the hunk cannot influence.

## Arm 3 (`zrtz272-rtz3.json`, sha256 `6a2077be38c7`)

Same refs as arm 2 (a_ref `6550967a5e`, b_ref `e603fb3540`), same disc, same
`expect` and `must_not_regress`. The only change: `Blend_surface/*` in must_not_move
is replaced by seven globs that cover the other 30 Blend_surface captures and leave
`R5G6B5_Add_SrcA_DstA` and `X_O1RGB5_Add_SrcA_DstA` unguarded, the way arm 2 left
`Stencil_ZERO*`. `arms.sh` supersedes by newest registration on the issue, so arm 3
supersedes arm 2's FAIL when it is judged. Re-reading arm 2's two result dirs under
arm 3's file (`.scratch/dryjudge3.txt`, a post-hoc read, not a verdict) gives PASS on
1,253 checks, which shows every remaining guard matches a capture.

**Status (2026-09-26 10:00Z):** waiting for arm 3's `[job.arms]` verdict. PR #364
stays in draft until then. On resume: check scores1.tsv status and PARTIAL COVERAGE,
judge the five bands by reading, then mark ready.

## Why attempt 2 did not finish

It judged arm 1, pushed the F24 gate and registered arm 2 (`18b0df7f8d`), then ended on a
`waiting:` comment for arm 2's verdict and CI. Both are outside the session. `handback.sh`
resumed the lane (attempt 3) 242 s after that push. The trigger was the unsuperseded arm-1
`regressed` label and a draft PR, not a new verdict. At that point arm 2 had no request or
result dir under `dispatch/`, and CI on `18b0df7f8d` was still pending (build ×2). Nothing
had resolved. Attempt 3 records this and waits again. The PR stays in draft until arm 2 is
judged: the label still reads arm 1's FAIL, and the F24 gate is unmeasured.

## Why attempt 3's first session did not finish

It ended on a `waiting:` comment for arm 2, which is outside the session. It did not wait on
a background task of its own. The resume at 08:11Z carried hostops's "background job died"
addendum, but that addendum was about attempt 1's wait. At 08:11Z CI on `11dc42ef74` was
green (build ×2, check). Arm 2 still had no request under `dispatch/queue` and no result dir.
The host's 00:54 PDT delivery said the arms job had hit its two-pairs-per-tick cap, so arm 2
is first on the next tick. Nothing new was measured, so the lane waits again.

## Why attempt 3 did not finish

Both of its sessions ended on a `waiting:` comment for arm 2, which was queued at
08:22Z and judged at 09:50Z, both outside the session. Neither waited on a task of its
own. `handback.sh` resumed the lane one minute after the verdict (attempt 4, 09:51Z).
Attempt 4 judged arm 2 (above), registered arm 3 and waits on it.

## Do not repeat

- Do not guard `Blend_surface/R5G6B5_Add_SrcA_DstA` or `X_O1RGB5_Add_SrcA_DstA` with
  must_not_move. Each has two images on disk that differ in the first swatch block,
  and the R5G6B5 pair occurs within one apk. Arm 1 failed on one, arm 2 on the other.
- `git apply` of the zdepth272 patch fails on master after #321. Place hunk 2 by
  anchoring on the `carry);` block. Do not re-derive the hunk.
- The Bash tool rejects heredocs that contain quoted braces. Write scratch
  scripts to files.
- Do not put RTZ back on F24 as it stands. Arm 1 measured 24 → 403..406 on all 20
  z24 FZy captures, from zero-depth edges passing the clip.
- Do not debug `Stencil_ZERO*` or `Blend_surface/R5G6B5_Add_SrcA_DstA` movement from
  a single-run arm. Both move between runs of one apk.
