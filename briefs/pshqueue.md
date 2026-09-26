# pshqueue -- land the five queued glsl/psh.c hunks, one arm each

Issues: #278 (fog INF), #279 (DOT_ZW), #285 (G8B8), #315 (BRDF), #271 (X1A7 read side).
Base: master at the fold of PR #268 (lane.wbufdepth24). Wave 213, job.board.
DISPATCH GATE: psh.c is held by lane.wbufdepth24 (PR #268, draft, arm pending).
Dispatch the tick after #268 folds and `psh.c` shows free in territory.toml.
Files: hw/xbox/nv2a/pgraph/glsl/psh.c, hw/xbox/nv2a/pgraph/glsl/psh.h,
       docs/testing/predictions/pshqueue-*.json, docs/lanes/pshqueue/**
       (psh.h is lane.texvol283's -- ask for it, do not edit it unheld.
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
