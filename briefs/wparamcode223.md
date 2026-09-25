# #223: build the ff-position carry (vsh-ff.c) and the zero-area rule (geom.c) that PR #304 priced

Lane: wparamcode223        Issue: #223 (W param; ff bitri 1,145,823 px + ff quad 494,632 px)
Base: origin/master @ 8af1bbb18e (PR #304 folded; rebase to the tip before you register anything).
Files: hw/xbox/nv2a/pgraph/glsl/vsh-ff.c (position tail, lines ~878-887), hw/xbox/nv2a/pgraph/glsl/geom.c
       (append_wedge, hunk B only), docs/testing/predictions/wparamcode223-*.json, docs/lanes/wparamcode223/**
Needs device: yes for the arm (Thor W_param, and the must-not-move globs); pricing is desktop. Needs NDK: no.

## Read first
docs/lanes/wparamff223/NOTES.md section 4 (both hunks, verbatim, with prices) and "For the next lane";
its tools homog_price.py / ff_port.py rerun in about a minute. Re-derive the priced numbers before you
trust them: the NOTES say the hunk was "Not compiled".

## The job, in order
1. Hunk (A), vsh-ff.c: nv2a's 0*x = 0 multiply branch for non-finite tPosition, and the homogeneous carry
   where |pos| >= 2^19. Compile it (geom_dump / glslc as #235 did; compositeMat is a macro, bind it to cm).
2. Hunk (B), geom.c append_wedge(): exactly one w < 0, every q finite, kahan_det on pz[i].xy exactly 0 ->
   emit nothing, return true. (A) alone makes bitri w-0.00 WORSE (68k -> ~146k); land them together.
3. Before (B) is kept: run ff_port.py's gate over every capture a must-not-move glob covers, especially
   w_gaps and w_gaps_tex_persp (145,687 each: do the golden's 1-px lines belong to those triangles?).
   A zero-area triangle that draws a line the golden also has would move: that leg decides (B).

## Falsifier / arm (register after the last rebase)
must_move: ff quad w-0.00 / -1.50e-36 / -1.88e-37 / -3.76e-37 / -7.52e-37 (79,174 each) -> ~314; quad w0.00
(72,012) and winf (25,600) -> ~0; bitri w-inf (114,508) -> ~0; bitri extreme rows -> hundreds of px.
must_not_move: the 20 prog_*quad rows (0), prog bitri rows fixed by PR #250 (451/451), every finite ff row,
rcc_w_zero_inf (different mechanism), Lighting/Shade suites (vsh-ff.c neighbours). Name the hunk line that
would move each. If the bitri extremes stay ~146k the divide is not the cause: refuted, say so.
Do NOT build a w scale (wparamgeom223) and do NOT add a two-negative rule to geom.c (NOTES: cone already right).
Check scores1.tsv `status` for `unreadable` and the run log for PARTIAL COVERAGE.

## Done when
The compiled hunks are in the PR, the priced numbers re-derived in NOTES.md, the arm is registered and its
verdict posted, every must-not-move leg holds, and the PR is ready. If (B) fails its must-not-move leg, ship
(A) alone only if no row gets worse, and say which rows wait on a different rule.
