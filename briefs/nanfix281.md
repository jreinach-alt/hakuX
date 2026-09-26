# nanfix281 -- NaN vertex colours: land the sign-bit rule (#281 code half)

Issue: #281 (Attrib float `-NaNs_NaNs` 14,646 px, `-NaNq_NaNq` 14,586 px; game-visible: low).
Base: origin/master at 9b3b0bb086 or later (rebase to the tip before you register anything).
Files: hw/xbox/nv2a/pgraph/glsl/vsh.c, hw/xbox/nv2a/pgraph/glsl/vsh-prog.c,
       docs/testing/predictions/nanfix281-*.json, docs/lanes/nanfix281/**
       (vsh-ff.c is lane.wparamcode223's, psh.c is lane.wbufdepth24's: do not edit either.
        Ask the board, on the PR, for any other file you find you need.)
Needs device: yes for the arm (Nova or Thor); the change is desktop-buildable. Needs NDK: no.

## What is already known -- read, do not re-derive
docs/lanes/nanattr281/NOTES.md (PR #302, merged, analysis only) found: silicon clamps a NaN
colour by its SIGN BIT -- -NaN -> 0, +NaN -> 1, the same as +-INF, drawn as the ordinary
ramp, not culled. NaNs and NaNq are one mechanism (console 0 px apart). Ours maps every NaN
to 1 in `NaNToOne` (vsh.c:513, used on oD0/oB0/oD1/oB1 at vsh.c:954-973), and `_MUL` in
vsh-prog.c (~:643, `zero_components` uses NaNToOne) must make a NaN product +NaN.
Adjacent, already landed: #245 (vertex outside Begin/End), #288 (subnormal inputs), #290
(R12/oPos ordering, ~30 lines from the `_MUL` hunk: do not carry or disturb it).

## Goal
Part 1 (vsh.c): the sign-bit NaN map on the four colour outputs. Part 2 (vsh-prog.c): `_MUL`
yields +NaN for a NaN product. Land both in one PR with ONE arm covering both.

## Falsifier
must_move: Attrib_float `-NaNs_NaNs` and `-NaNq_NaNq` fall to <= 60 / 0 px against the golden
(the console's own distance from it), or the residual is measured and explained.
must_not_move: every other Attrib float capture exact today, the Inf captures (register one
Inf leg -- a fix that treats all non-finite alike breaks them), and the Exceptional Float rows.
Name the patch change that would move each. Read scores1.tsv `status` for `unreadable` and the
run log for PARTIAL COVERAGE before you call a leg held. If must_move lands on a figure other
than predicted, that refutes the model: report it, do not tune to it.

## Done when
Both hunks are in a ready PR (not draft) with the arm verdict cited and NOTES.md naming the
mechanism, or a hunk the arm refuted is left out and named with its measured figure.
The #281 tracker row is for the board to update (board-request), not the lane.
