# Audit pass 1 -- PR #288, lane/vshsubneg255 (#255)

Head audited: `99b2c6c659`. Diff: `hw/xbox/nv2a/pgraph/pgraph.c` (+79/-22),
`docs/lanes/vshsubneg255/NOTES.md` (new), `docs/testing/nv2a_index.json`
(regenerated, line moves). CI green (build x2, check); MERGEABLE/CLEAN.

**Result: no HIGH, no MEDIUM, two LOW.** Next state: `needs-audit-2`.

## What was checked

The new `vsh_apply_step` was read against the evaluator it splits,
`subprojects/nv2a_vsh_cpu` @ `1115255708` (`nv2a_vsh_emulator.c`,
`nv2a_vsh_emulator_execution_state.{c,h}`):

- **Read-before-write order is preserved.** `apply()` fetches both units'
  inputs, then writes MAC, then ILU. The split takes `ilu_full = *full` before
  the MAC runs, so the ILU reads pre-MAC registers, and the ILU copy-back runs
  last. The ILU's copy-back overwrites a MAC write to the same components, as
  `apply_operation` does.
- **The copy is complete.** `Nv2aVshCPUFullExecutionState` holds arrays only,
  including `address_reg`. The struct assignment copies A0, so an ILU op with
  `c[A0+n]` reads the pre-step A0 (which is what `apply` does too, since it
  fetches before an ARL writes). `ilu_state`'s pointers go to `ilu_full`'s
  own arrays, so the assignment after the memset does not break them.
  `context_dirty` stays NULL in both states and is not read by the writeback
  (it uses `written`/`known`).
- **Copy-back targets.** `vsh_output_reg` covers TEMPORARY/OUTPUT/CONTEXT.
  The ILU never writes ADDRESS (ARL is a MAC op), and NONE is skipped.
  `NV2AWM_X >> c` matches the enum (X=8 ... W=1), and it is the same idiom the
  writeback loop already uses. The copy-back is now writemask-aware. The old
  `vsh_flush_outputs` flushed all four components of the destination,
  including ones the op did not write. Those were flushed on the way in
  anyway, so nothing changes there.
- **The ILU sees flushed data wherever it comes from.** Constants, inputs, a
  MAC result from an earlier step and R12/oPos (`fetch_value` index 12 reads
  `output_regs`) all go through `vsh_flush_all` on the copy.
- **No stale callers.** `vsh_flush_outputs` is gone and nothing else
  references it. `vsh_flush_denormal` has no other users outside `pgraph.c`.
- **Reach.** The change is inside `pgraph_vsh_writeback_constants`, which
  returns early unless a program token writes a constant. The GLSL/SPIR-V
  shaders are untouched, so the rendered output of no program can move.
- **Evidence.** The NOTES register the prediction before the run, with
  failing worlds named for each must-move leg. The verdict table cites both
  arm ids, refs and apk shas, and says the runs landed on Nova (not the
  Thor it named), with a reason why that does not change the result. The
  must-not-move set includes ILU RCP. That suite is the one that would catch
  a missing ILU output flush (`rcp(-Max)` would print `-0.000000`) or a
  zeroed copy. It stayed IDENTICAL.

## Findings

### LOW-1: MAC arithmetic on a subnormal is now unflushed, on no evidence either way

`pgraph.c` `vsh_apply_step`: MUL/ADD/MAD/DP*/MIN/MAX/SLT/SGE on the MAC now
run host IEEE arithmetic on subnormal operands, and their results are not
flushed. Before this PR both were flushed. The only MAC evidence is MOV
(Exceptional Float). Scenario: a program computes `mul c[n], c[a], c[b]` with
a product below 2^-126. It now writes back a subnormal where silicon may
write a zero. It is LOW, not MEDIUM, because the old behaviour was an
extrapolation from the ILU with no MAC evidence behind it either. No golden
or game on disc is known to exercise it, and the NOTES disclose it and name
the settling run: CPU Shader Tests with `USE_EXCEPTIONAL_VALUES`,
`cpu_shader_tests.cpp:21`. The one gap is that the open question lives only
in the lane NOTES, and the NOTES are not a work queue. Recommend that the
board file an issue for the console run, so the question has a row.

### LOW-2: the split has no desktop-side test

`vsh_apply_step` rests on one device A/B plus reading the source. The NOTES
say the `.scratch/` harness was never compiled. Two regressions would pass
CI: a future edit that took the ILU copy after the MAC runs, or that dropped
the writemask test. Only the next vsh arm would catch them, and only if the
program in it pairs a MAC and an ILU writing the same register. This is
quality, not a defect. A small unit test around the evaluator would pin it.

## Not findings

- `vsh_flush_all` copies and flushes about 3.7 KB per ILU step. It runs only
  for constant-writing programs, once per draw, over the last vertex, so the
  cost is negligible.
- A relative read past c[191] reads beyond `context_regs` in the evaluator.
  That existed before this PR (the copy only moves it to another stack
  object), and `known` already keeps the old value for such writes.
