# #242: run the vertex program for a vertex sent outside Begin/End

Lane: vshnobegin242            Issue: #242 (vsh, lone SET_VERTEX4F)
Base: origin/master 21946df29b (rebase first; `rev-list --left-right` in case it moved)
Files: hw/xbox/nv2a/pgraph/pgraph.c, docs/testing/predictions/vshnobegin242-*.json,
docs/lanes/vshnobegin242/**
Read-only (lane.toolsmith's, do not edit): docs/testing/vsh_score.py, docs/lanes/vsh-program/**
Needs device: yes for the proof (Thor, nxdk_vsh_tests). Needs NDK: no.

## What is wrong (issue body + verdict on #112 item 4 have the evidence)

nxdk_vsh_tests' Exceptional Float sends SET_NORMAL/DIFFUSE/SPECULAR/FOG_COORD then
SET_VERTEX4F with NO SET_BEGIN_END around it. Program: `mov c[188..], v0..v15`,
read back over RDI. Console holds inf/-inf/nan/-nan, +-Max, 0/-0; hakuX reads all
0.000000, byte-identical before and after #234. Even finite +-Max reads 0, so the
program never ran. MAC mov (inside Begin/End) is IDENTICAL, so #234's path is right.

Mechanism, pgraph.c at master: SET_VERTEX4F (`DEF_METHOD_INC(NV097, SET_VERTEX4F)`)
at slot 3 calls pgraph_finish_inline_buffer_vertex(), which only appends. The
program runs and pgraph_vsh_writeback_constants() is called only at Begin/End END
(`DEF_METHOD(NV097, SET_BEGIN_END)`), and the next Begin's
pgraph_reset_inline_buffers() drops the lone vertex unexecuted.

## The job

When slot 3 of SET_VERTEX4F arrives with `pg->primitive_mode == PRIM_TYPE_INVALID`,
execute the vertex program for that one vertex and apply its constant writes,
through the SAME evaluator and writeback #234 built. Nothing is rasterised.
Do not touch the inside-Begin/End path: it must stay byte-identical.

Settle before coding (from the test's own expectations, or ask lane.xbox via a
GitHub comment): do position/varying outputs of such a vertex go anywhere on
silicon? If unknown, write only the constants and say so in NOTES.

## The arm (register BEFORE building; Thor, nxdk_vsh_tests, scored by vsh_score.py)

- **must_move:** Exceptional Float's c[188] rows go from all-zero to the console's
  values: Inf/-Inf/NaN/-NaN row, Max/-Max/Min/-Min row, MaxSub row
  (`hardware/runs/2026-09-25-vsh/stage2/console`).
- **must_not_move:** every other nxdk_vsh_tests suite that is IDENTICAL today
  (MAC mov above all); and the pgraph suites through
  `nv2a_index.py blast hw/xbox/nv2a/pgraph/pgraph.c` (a wide blast -- name a
  representative set, do not skip it).
- **The world in which must_move fails:** the program does run but the lone
  vertex's outputs reach c[188] by a path other than the constant writeback
  (e.g. the RDI readback sees a different bank), or the NaN/-0 rows differ from
  the console for an arithmetic reason. Then score the finite rows separately
  and report which rows moved -- a partial fix is a diagnosis, not a revert.

Before trusting the verdict: read both arms' status column for `unreadable`, and
run1.log for PARTIAL COVERAGE and UtilAcceptVsock. An unreadable capture scores
as exact.

## Do not

- Fix #112 item 4's `_MUL`-zero / `_RCC`-clamp behaviours here; this lane only
  makes them measurable.
- Edit board files (territory.toml, nv2a_issues.toml); the board owns them.

## Done when

Arm verdict on your PR with its status column checked, NOTES record the result,
PR carries the lane template and `Files:` line, preflight passes, PR marked ready.
