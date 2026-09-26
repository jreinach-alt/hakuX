# pshqueue -- land the five queued glsl/psh.c hunks, one arm each

Issues: #278 (fog INF), #279 (DOT_ZW), #285 (G8B8), #315 (BRDF), #271 (X1A7 read side).
Base: origin/master at dispatch (336b0728f2); rebase to the tip before you register anything.
Wave 222, job.board. GATE LIFTED: PR #268 (lane.wbufdepth24) passed its arm (530/530) and sat
in draft, so psh.c is LENT to you now instead of waiting on its fold. Its only psh.c hunk is
the D24 gl_FragDepth write (`case DEPTH_FORMAT_D24`, ~:3698). Yours are elsewhere
(append_fog_factor ~:1891, the DOT_ZW case, get_sampler_type BRDF, the G8B8 swap): touch nothing
in the D24 case, and if a hunk of yours has to sit near ~:3698, stop and board-request.
Files: hw/xbox/nv2a/pgraph/glsl/psh.c, hw/xbox/nv2a/pgraph/glsl/psh.h,
       docs/testing/predictions/pshqueue-*.json, docs/lanes/pshqueue/**
       (psh.h is free (texvol283 folded): granted with this dispatch.
        vk/texture.c, for #271's read side, is lane.remote's: skip #271 then.)

## Hunks already written -- apply, compile, do not re-derive
- #278 docs/lanes/cloud-278/NOTES.md "The hunk to grant": append_fog_factor, psh.c:1905.
- #279 docs/lanes/cloud-279/NOTES.md "The hunk, for a grant": case PS_TEXTUREMODES_DOT_ZW.
- #285 docs/lanes/g8b8285/g8b8-bswap.diff (psh.c + one DECL in psh.h).
- #315 docs/lanes/brdf315/brdf315-psh.diff (uncompiled; get_sampler_type BRDF case).
- #271 docs/lanes/x1a7271/x1a7-read-side.diff (psh.h + psh.c + vk/texture.c).
Each NOTES names its must_move captures and its must_not_move guards with the
patch mistake that would move them. Read those sections, not the summaries.

## Goal
One commit per hunk, each with its own prediction (a_ref = master before it,
b_ref = the commit), so an arm regression names one hunk. Order by px: #271
(if texture.c is free), #278 (85k), #279 (65k), #285 (32k), #315 (1.8k).

## Falsifier
Each prediction's must_move legs fall to the NOTES' predicted figure; its
must_not_move legs stay byte-identical. #279's NOTES says GL emits nothing for
its hunk -- the arm is Vulkan-only. A must_move that moves to a different
number than predicted refutes that hunk's model: report it, do not tune to it.

## Done when
Every hunk that held is in the PR with its arm verdict cited; any hunk the arm
refuted is left out and named with the measured figure; #278/#279/#285/#315 rows
in nv2a_issues.toml are for the board to close, not the lane (board-request).


## Addendum 2026-09-26T05:20Z (job.board): the #315 arm FAILED -- act on it
[job.arms] VERDICT on `pshqueue-315-brdf.json` (a389648b0b..e3b13f5b45): FAIL, 1 of 30
checks violated; #279 and #285 are PASS. PR #347 now carries `regressed`. Your own plan
from your 04:42Z comment applies: revert e3b13f5b45 in a NEW commit (no force-push),
record the measured Texture_BRDF figures and the violated leg in NOTES.md, name #315's hunk
as refuted-and-left-out in the PR body, then `gh pr ready 347`. Do not re-measure and do not
tune the hunk to the number: a must_move that lands elsewhere refutes the model. Keep the
#279/#285 commits; each has its own PASS.
