# #255: a negative subnormal vertex input reaches its constant as +0; silicon keeps -0

Lane: vshsubneg255            Issue: #255 (component vsh; #242's neighbour, #112 item 4)
Base: origin/master @ d92ae5d7f3 (PR #245 folded; the MaxSub row is visible on master now).
Files: hw/xbox/nv2a/pgraph/pgraph.c, docs/testing/predictions/vshsubneg255-*.json,
docs/lanes/vshsubneg255/**
Needs device: yes (Thor arm, nxdk_vsh_tests Exceptional Float). Needs NDK: no.

## The defect
Exceptional Float, MaxSub/-MaxSub/MinSub/-MinSub: console `0,-0,0,-0`; hakuX with #245
`0,0,0,0`. The sign of a negative subnormal is lost between SET_VERTEX4F and the constant
writeback RDI reads. Silicon flushes the subnormal but keeps the sign. Normal -Min keeps it.

## Read first; the location is a CLAIM
`vsh_flush_denormal()` (pgraph.c ~4063) already returns `-0.0f` for a negative subnormal, and
it is applied to the constants (~4333), the inline attribute (~4346) and the outputs
(`vsh_flush_outputs`, ~4251). So "the flush returns 0.0f" is probably NOT the cause.
Re-derive: run the program on the CPU evaluator in a scratch harness (desktop, no device) with
a -MaxSub input and print the value at each stage: `inline_value` after SET_VERTEX4F, after the
~4346 flush, out of the thirdparty evaluator (MOV/ADD/MUL on -0), after `vsh_flush_outputs`,
into `pg->vsh_constants`. Name the stage where the sign bit dies. Candidates: an evaluator op
turning -0 into +0 (`-0 + +0`, a `0.0f - x` or max() idiom), the writeback's own copy, or the
`known`/mask handling. The console reads -0 for all four rows, so the fix is whatever keeps
the sign through that stage; do not special-case the four rows.

## The arm (register BEFORE building, after the last rebase)
- must_move: Exceptional Float MaxSub, -MaxSub, MinSub, -MinSub -> `0,-0,0,-0`.
- must_not_move: Inf/-Inf/NaN, Max/-Max/Min/-Min rows and every IDENTICAL vsh suite
  (`nv2a_index.py blast hw/xbox/nv2a/pgraph/pgraph.c`), including ILU RCP Tests (#233).
- Failing world: a fix that keeps -0 for -MinSub but leaves -MaxSub at +0 (or the reverse):
  register the four rows as separate legs.
- Oracle: lane.xbox's console goldens for nxdk_vsh_tests (docs/testing/xbox-*.md).
Check `scores1.tsv` status for `unreadable` and the run log for PARTIAL COVERAGE.

## Done when
The four rows match the console on the Thor, every must-not-move leg holds, the stage where
the sign was lost is named in docs/lanes/vshsubneg255/NOTES.md, and the PR is ready with the
arm verdict.
