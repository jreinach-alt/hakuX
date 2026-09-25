# #223: the ff bitri and ff quad families of W_param (1.64 M px) after PR #250's wedge

Lane: wparamff223          Issue: #223 (W param)
Base: origin/master @ 8e683b3a26 (PR #250 folded; rebase to the tip before you register anything).
Files: hw/xbox/nv2a/pgraph/glsl/geom.c (ff-quad two-negative rule only),
       docs/testing/predictions/wparamff223-*.json, docs/lanes/wparamff223/**
       (vsh-ff.c is lane.shadetie224b's, PR #263 in audit: name the function and ask, do not edit.)
Needs device: yes for the arm (Thor W_param); the pricing half is desktop. Needs NDK: no.

## Read first
docs/lanes/wparamclip223/NOTES.md section 9 and "For the next lane" -- they are this brief's source.
After #250: ff bitri 1,145,823 px, ff quad 494,632 px, none moved. The same vertices through the prog
path reach 0 on the quads, so the ff residual is vsh-ff.c's vertex positions, not geometry.

## The job, in order
1. PRICE OFFLINE with wedge_price.py / wedge_port.py: swap vsh-ff.c's divide and clampAwayZeroInf at
   w = -0 / -inf for the prog path's homogeneous carry. Does ff bitri reach 0 coverage mismatch?
   Score against the golden REGIONS, not points, and on every capture a must-not-move glob claims.
2. If yes: the fix is vsh-ff.c. Report the function and the hunk on the PR and issue; the board grants
   it when lane.shadetie224b folds. If no: say what silicon keeps that our divide collapses.
3. ff quads have two negative w per half: derive the two-negative rule; the 20 prog_*quad rows stay 0.

## Falsifier
The ff bitri extreme rows (w-0.00, -1.88e-37, -3.76e-37, -7.52e-37, ~146k each) land at ~0 in the port.
If the port leaves them at ~146k the divide is not the cause: refuted, say so.
Do NOT rebuild a uniform or per-triangle w scale (wparamgeom223). rcc_w_zero_inf is a different mechanism.

## Done when
The priced verdict (with the ported numbers) is in NOTES.md, the requested hunk is named, geom.c is changed
only if the two-negative rule prices to 0 mismatch and keeps prog_*quad at 0, a prediction is registered
after the last rebase, and the PR is ready. Analysis-only with the exact vsh-ff.c hunk is a complete outcome.
