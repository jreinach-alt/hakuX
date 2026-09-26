# dpforce345 -- DP3/DP4/DPH zero-force each product (#345 half 1, the GLSL helpers)

Issue: #345 (silicon-measured; game-visible: possible, unmeasured -- a DP whose zero component meets
inf/NaN, e.g. after RSQ of 0, yields NaN instead of a finite value at a position or colour).
Base: origin/master at 2dc2b5c49a or later (rebase to the tip before you register anything).
Files: hw/xbox/nv2a/pgraph/glsl/vsh-prog.c, docs/testing/predictions/dpforce345-*.json,
       docs/lanes/dpforce345/**
       (glsl/vsh.c is free but you should not need it; vsh-ff.c is lane.zrtz272's, psh.c and geom.c are
        lane.tiecode282's: do not edit them. Ask the board, on the PR, for any other file you need.)
Needs device: yes for the arm (Nova or Thor); the change is desktop-buildable. Needs NDK: no.

## What is already known -- read, do not re-derive
PR #344 (lane.xbox, folded; docs/lanes/xbox/, raw rows and vsh_score.py output) ran nxdk_vsh_tests
`CPU Shader Tests` on the console. Silicon forces each 0*inf and 0*NaN product to 0 INSIDE DP3/DP4:
(0,1,2).(inf,1,1) = 3. `_DP3`/`_DPH`/`_DP4` in vsh-prog.c (~:677-693) are a plain `dot()`, which returns
NaN for that input. `_MUL` (~:651) is already right: its per-component `zero_components` test forces a
zero factor to +0. #281's NaN sign rule (PR #336) is merged in `_MUL`/`_PosNaN`: keep it, do not disturb.
Confirmed right, change nothing: `_RCC`'s signed-zero clamp; ILU NaN outputs canonical 0x7FFFFFFF.

## Goal
Each of the (3, 3+1, 4) terms of a dot product takes the same zero-forcing `_MUL` applies, then sums.
DPH's implicit w=1 term is not forced (1 is finite). Half 2 of #345 (the nv2a_vsh_cpu constant-writeback
library) is NOT this lane: it is a meson wrap / Android CMake fetch / pgraph.c question, filed as a
follow-up if you find the call-site fix is small -- say so in NOTES.md, do not build it.

## Falsifier
Score with docs/testing/vsh_score.py against the console text (PR #344 has the reference rows).
must_move: the DP3/DP4/DPH zero-x-inf and zero-x-NaN rows agree with silicon (0 disagreeing rows), or the
residual is measured and named.
must_not_move: every MUL/MAD/ADD/RCC/RSQ row already exact today, the #255 subnormal rows, the #281
Attrib float NaN captures, and the lit-vertex-program (Lighting_*) suites -- a DP is on every lit
path. Name the source change that would move each leg; a must_move that lands on another figure refutes
the model: report it, do not tune to it.

## Done when
The hunk is in a ready PR (not draft) with the arm verdict cited and NOTES.md naming the mechanism, or the
hunk is left out with the measured figure that refuted it. The #345 tracker row is the board's
(board-request), not the lane's.
