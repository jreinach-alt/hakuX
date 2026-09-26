# #276: land the CULL_NEAR_FAR_EN hunk (whole-primitive z reject) and run its arm

Lane: cullnf276          Issue: #276 (ZMinMaxControl, 143,673 px beyond one step -> 0; 129,337 px credited)
Base: origin/master @ 09f3061bc5 (rebase to the tip before you register anything).
Files: hw/xbox/nv2a/pgraph/pgraph.c, hw/xbox/nv2a/nv2a_regs.h, docs/testing/predictions/cullnf276-*.json, docs/lanes/cullnf276/**
       LENT from lane.pshqueue (disjoint hunks only; its row keeps psh.c/psh.h): glsl/psh.h (one field, cull_near_far, ~:106)
       and glsl/psh.c (state capture ~:309 and the clip block after the ZCLAMP discard, ~:2553). pshqueue's hunks are the
       fog INF (~:1905), DOT_ZW, G8B8 and BRDF cases; if yours must sit inside one of those, stop and board-request.
Needs device: yes for the arm (Nova or Thor). Needs NDK: yes for the build.

## The defect and the finished analysis
NV097_SET_ZMIN_MAX_CONTROL's CULL_NEAR_FAR_EN (bit 0) is dropped by pgraph.c; silicon rejects a primitive whose vertices are
ALL below CLIP_MIN or ALL above CLIP_MAX in screen z, whatever ZCLAMP_EN and w-buffering say. Read
docs/lanes/zclamp276/NOTES.md first (mechanism, per-capture pricing, "Do not repeat"). The hunk is
docs/lanes/zclamp276/nearfar_cull.diff (nv2a_regs.h, pgraph.c, psh.h, psh.c), cut against 8af1bbb18e: fix offsets by hand.

## The job, in order
1. Apply the four-file hunk on the tip as ONE commit. CULL_IGNORE_W (bit 8) stays unmodelled.
2. Build, and check the shader compiles on the ZMinMaxControl shapes (z-buffered and w-buffered, ZCLAMP and ZCULL).
3. Register the arm AFTER your last rebase, on concrete shas: a_ref = the tip, b_ref = the fix commit
   (ab_compare.py --register docs/testing/predictions/cullnf276-nearfar.json). Commit the JSON; the arms job runs it.
   Do not queue arms.

## Falsifier
must_move: the 12 ZMinMaxControl captures priced in NOTES (Ctrl/CtrlFixed x NEARFAR_ZCLAMP, WBuf_NEARFAR_ZCLAMP,
WBuf_NEARFAR_ZCULL, each +IgnW) to their priced residuals (6,737 / 3,384 / 3,490 / ~10,800 px, one-step or sliver).
must_not_move: the other 20 ZMinMaxControl captures, z-buffered *_NEARFAR_ZCULL (already exact to one step), Depth_buffer/*,
W_buffering, Blend_surface, Surface_format.
Failing world: the 12 move but a must_not_move row moves too (the reject leaked into shaders with no cull_near_far), or a mover
lands outside its priced band. Report the measured figure; do not tune the rule to it. Read `status` for `unreadable` before
trusting any `=0`.

## Done when
The arm verdict is PASS (or each refuted leg is named with its figure and its hunk is out) and the PR is ready for review with
the verdict cited. Do not edit the board files.
