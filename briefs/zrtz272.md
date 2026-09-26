# #272 (+#275 Swap): land the round-toward-zero fixed-function screen-z hunk and run its arm

Lane: zrtz272            Issues: #272 (275,358 px; up to 323,036), #275 (Swap 165,447 px, same defect)
Base: origin/master @ dcea2d7840 (PR #321 folded as 4bc77c3171, so vsh-ff.c's position tail now carries hunk A;
      rebase to the tip before you register anything).
Files: hw/xbox/nv2a/pgraph/glsl/vsh-ff.c (function pgraph_glsl_gen_vsh_ff ONLY), docs/testing/predictions/zrtz272-*.json,
       docs/lanes/zrtz272/**. psh.c is NOT needed (lane.pshqueue holds it; the NOTES show the D24/D16 floor is already exact).
Needs device: yes for the arm (Nova or Thor, whichever the arms job has free). Needs NDK: yes for the build.

## The defect and the finished analysis
Silicon rounds every step of the fixed-function screen z toward zero (z-column products, sums, w, a 24-bit reciprocal,
the final multiply); we round to nearest. That explains the #272 curve (-8 at the near plane, +4 near max depth), #275's
Swap (silicon 4 below exact), ZetaIntoColor's 3, and cloud-297's near-plane 8. Read
docs/lanes/zdepth272/NOTES.md first (derivation, pricing, "Do not repeat"). The hunk is
docs/lanes/zdepth272/vsh-ff-zrtz.patch, +87 lines, verified op-for-op in numpy over 93,080 cases; it merged cleanly over #321.

## The job, in order
1. `git apply docs/lanes/zdepth272/vsh-ff-zrtz.patch` on the tip. It was written against 8af1bbb18e and #321 landed in the
   same position tail, so fix offsets by hand. Keep it ONE commit that changes only `vtxPos.z` (oPos, vtxPos.w, x/y untouched).
2. NOTES say the GLSL was never compiled (no glslang on the host). Compile it (geom_dump/glslc as #235 did) before the build.
3. Register the NOTES "The arm" command (`ab_compare.py --register docs/testing/predictions/zrtz272-rtz.json`) AFTER your
   last rebase, on concrete shas: a_ref = the tip, b_ref = the fix commit. Add the `must_not_regress` list to the JSON by hand
   as the NOTES say. Commit the JSON and let the arms job run it; do not queue arms yourself.

## Falsifier
must_move: Color_zeta_overlap/Swap -> 0; z24_C?_FZn_M000003 (+_ZB) -> 0; z24_C?_FZy_M*_ZB -> 0; the z16 legs and the stated
bands in the NOTES (z24 Mffffff 144,566 -> 47,935..53,852, and the rest of that table).
must_not_move: W_buffering WBuf*/_V1_*, Depth_buffer/*, Blend_surface, Surface_format, Color_zeta_overlap ColorIntoZeta/Adjacent.
Failing world: Swap lands but an exact z16 row or a W-buffer row moves (the hunk touched w or the programmable path). A value
outside its band means "host arithmetic + 3-step correction = exact RTZ" failed: report it, do not retune to it.
Read scores1.tsv `status` for `unreadable` and the run log for PARTIAL COVERAGE before believing any `=0`.

## Done when
The arm verdict is PASS (or each refuted leg is named with its measured figure and its hunk is out), the PR is ready for
review with the verdict cited, and #275's Swap result is stated in the PR body. Do not edit the board files.
