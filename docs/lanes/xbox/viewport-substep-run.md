# #112 item 1: the Viewport sub-step threshold on silicon -- the run, registered before it boots

**Status: PRE-REGISTERED.** The prediction is
[`docs/testing/predictions/2026-09-19-viewport-substep-threshold.md`](../../testing/predictions/2026-09-19-viewport-substep-threshold.md)
(registered 2026-09-19, folded in PR #179), unchanged. This file adds only
the disc, the order the runs happen in, and how the table is read. It is
committed and pushed before either run.

## The disc

Tests tree `6743b6a` + [`viewport_substep.patch`](viewport_substep.patch)
(branch `hakux/viewport-substep` @ `dc9e79bf0f`): the seven offsets D1-D6 and C1
appended to `kTestCases` exactly as registered, the existing twelve
untouched. XBE sha256
`ede1b0327355e90b2c759fd7a8093f937ad91ad82b2d638d339d2fd1be8732ac`, ISO
`f30903b5a151a172f5079b6f2b3af58d4954d78efcc92ba0b2a6baa0884624bd`.

Capture names come from the suite's own `%.03f` printf. None of the seven
values lies on a rounding tie at three decimals, so every printf spells them
the same way: `0.549`, `0.535`, `0.539`, `0.559`, `-0.451`, `1.549` and `0.234`
(`<x>_<x>-0.000_0.000`). The runs confirm that; a missing name is reported,
never guessed at.

## Order

1. **Emulator first, on the Thor through the dispatcher.** This is the lockup
   safeguard and also the prediction's section 3 (E1-E3), the positive
   control: E2 checks that the disc programs `VPOFF` with the registered
   values. **If E2 fails, the console run does not happen.**
2. **The console**, running the same nineteen scale-0 and scale-2.0 tests via
   `tools/xbox/pgraph_run.py`, with shutdown off and networking off.

## Reading it

`docs/lanes/xbox/score_viewport.py` appends the seven to
`probe_viewport_ff_extents.py`'s SWEEP and edits nothing.
`score_viewport.py SILICON_DIR EMULATOR_DIR` is the probe itself.
`--extents DIR` prints every capture's four fixed-function extents from one
directory, and that is how the prediction's cross-capture sentences are read:

- **T:** silicon D1's extents equal silicon `+17/32`'s. **R:** they equal
  **our** `+9/16`'s. D2 separates R from R'.
- **C1 must not move under any model.** D5 and D6 are the direction and
  translation controls, read per the prediction's section 2 table.
- **Validity:** the twelve existing captures on this console must match
  their goldens (the calibration run had all Viewport captures bit-identical).
