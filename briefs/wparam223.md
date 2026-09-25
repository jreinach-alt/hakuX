# lane.wparam223 -- #223: W param, 5,117,044 px over 110 captures, the largest suite residual

Base: master @ 82e460e863. Issue: #223 (read its body; the numbers are there).
Files: hw/xbox/nv2a/pgraph/glsl/vsh-prog.c, glsl/vsh.c, glsl/vsh-ff.c,
docs/testing/predictions/wparam223-*.json, docs/lanes/wparam223/**.
psh.c belongs to lane.wbuf31fix: if the fix needs it, file a board-request, do not wait.

## Goal

Find the family of W param captures that owns the most residual pixels and
the mechanism behind it. Measured on the Thor 2026-09-20 (PR #194 base arm,
result 1789968297-arms-primpv13-base-2094212): 110 captures, 42 over 50k px,
largest `prog_w_zero_inf__bitri_w-0.00` 271,518, `rcc_w_zero_inf__z-7.52e-37`
152,648. Already shown NOT leakage (alone == in company, to the digit).

## Steps

1. Rebaseline at master. Classify the 110 captures by family (`prog_` / `ff_` /
   `rcc_` x the w/z values) and by coverage (edges) versus value (interiors).
2. Take the family with the most pixels. Leads, not findings: `_RCC`'s
   signed-zero clamp (vsh-prog.c:669) and `_MUL` zero-forcing (:571), both
   inherited and unconfirmed by silicon. #224 (Shade model) shares its largest
   captures (`W_Fixed_*_Smooth`): say in NOTES whether the cause is shared.
3. lane.xbox has run `nxdk_vsh_tests` on the console (PR #225; Exceptional
   Float has no published goldens). Read its captures as the oracle before
   modelling anything.

## Falsifier

Register a prediction before any arm: must_move is the family's captures with
direction and size, must_not_move is the vertex-shader suites that pass today.
Name the world in which each leg fails; a leg your patch forces true tests nothing.

## Done when

A PR carries a mechanism with an arm verdict (or a measured refutation of
each lead with the next family named), the prediction file, and NOTES.md.
An offline-only result is fine: say so, and name the arm it needs.
