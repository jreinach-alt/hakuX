# lane.shade224 -- #224: Shade model, 3,757,101 px over 168 captures, no owner

Base: master @ a6bb4a13d4. Issue: #224 (read its body; the numbers are there).
Files: docs/testing/predictions/shade224-*.json, docs/lanes/shade224/**.
Anything under hw/ is a board-request, granted the tick after you ask -- name
the file and the hunk. glsl/psh.c is lane.wbuf31fix's, glsl/vsh*.c is
lane.wparam223's; do not wait on either, ask.

## Goal

Find which family of the 168 `Shade model` captures owns the residual and
whether the cause is coverage (edges) or value (interiors). Measured on the
Thor 2026-09-20 (result 1789968297-arms-primpv13-base-2094212, ref
4955050b31): 32 captures over 50k px, largest `W_Fixed_QuadStrip_Smooth_First`
and `_Last` (139,551 each, equal to the pixel), `W_Fixed_Poly_Smooth_Last`
129,102. NOT the provoking-vertex path: #194 moved the suite 3 px.

## Steps

1. Rebaseline at master (a fresh arm, or the newest score on disk dated
   AFTER #194's fold 2026-09-25T08:04Z -- date the result you derive from).
2. Classify by primitive x shade mode (Flat/Smooth) x `W_`/non-`W_`, then
   edge versus interior. lane.wparam223 wrote a classifier
   (docs/lanes/wparam223/wparam_split.py, PR #228); reuse it, do not rewrite.
3. PR #228 says half of #223's residual is wash. Say in NOTES whether the
   `W_Fixed_*_Smooth` captures are the same captures, and if so close this
   as a duplicate of #223 with the evidence rather than working it twice.

## Falsifier

Register a prediction before any arm: must_move is the family's captures with
direction and size, must_not_move the Shade model captures that pass today.
Name the world in which each leg fails; a leg your patch forces true tests nothing.

## Done when

A PR carries the classification, a named mechanism (or a measured refutation
of each lead with the next family named), the prediction file and NOTES.md.
An offline-only result is fine: say so, and name the arm it needs.
