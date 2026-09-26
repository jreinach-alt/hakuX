# #10: does silicon still separate Y16 from Y8 when the vertical bump term is 5.0?

**Status: PRE-REGISTERED.** This file, its scorer and the tests patch were
committed and pushed before the emulator dry run and before the console run.

**Result (2026-09-25):** M is COLLAPSE and C1 holds. But the m11 = 5.0 image
is all horizontal stripes and cannot show #10's horizontal flip, so the
inference registered for COLLAPSE below is withdrawn. #10's `Bump env lum`
control is blind the same way. See
[`xbox-bumpm11-2026-09-25.md`](../../testing/xbox-bumpm11-2026-09-25.md).

## The question

#10's Y16 class covers `BumpMap_Y16` and `BumpMap_Y16_L`, 22,374 px each
against silicon. PR #187 localised it: hakuX renders a Y16 bump source exactly
as Y8, while silicon separates them. The published golden Y16 and Y8 differ on
21,584 px outside the label rows, and the `_L` pair on 21,526. This console's
full `6743b6a` run reproduced all four goldens byte for byte (PR #340).

`BumpEnvLum_Y16` binds the same Y16 source over the same kind of seam and does
**not** separate (hakuX sits at the 1,576 px floor). Three things differ
between the two suites:
- the vertical matrix term m11: 0.5 in `Bump map`, 5.0 in `Bump env lum`;
- `BUMPENVMAP` against `BUMPENVMAP_LUMINANCE`;
- the luminance values: 82/83 against 46/47.

#10's analysis names the cheapest cut: re-enable `bump_map_tests.cpp`'s own
commented line, `SetBumpEnv(0.3, 0, 0, 5.0, 0, 0)`, and capture on silicon.

## What runs

- **The XBE:** nxdk_pgraph_tests `6743b6a` plus [`bumpm11.patch`](bumpm11.patch)
  (tests branch `hakux/bump-m11` `d8c5f38`): sha256 `5516a74bd4d6…`, ISO
  `c8e6a0069643…`. The amendment below says what changed.
- **The patch** adds four tests to `Bump map`, `BumpMap_{Y16,Y16_L,Y8,Y8_L}_m11x10`.
  Each is the unchanged draw with m11 = 5.0. Every existing test is unchanged:
  `Test()` takes m11 as a parameter that defaults to the original 0.5.
- **The console config:**
  - `Alpha func::AlphaFuncAlways_Disabled` runs first, as a sacrificial test
    under the first-test rule (PR #348).
  - Then the four unchanged `BumpMap_{Y16,Y16_L,Y8,Y8_L}` tests, as controls.
  - Then the four `_m11x10` variants.
  - Shutdown-on-completion off, networking off, progress log on.
- **An emulator dry run** of the same selection runs first, on the Thor at
  hakuX `84a67b9cf8`. #283's later Y16 change (`a5b4141064`) leaves any texel
  a bump stage consumes alone, so hakuX's bump path is the same at master.

## Legs

Scored by [`bumpm11_score.py`](bumpm11_score.py). Counts exclude the label
rows 20–44. It was mutation-tested before this commit on seven synthetic
cases, including the two pairs disagreeing and a touched control, which voids
the run and suppresses M.

| leg | what must hold, or what decides | the world in which it fails |
|---|---|---|
| **C1** | The four unchanged controls are bit-identical to their goldens | The build or the rig moved. That voids M |
| **M** | Silicon `Y16_m11x10` against `Y8_m11x10`, and the `_L` pair. **COLLAPSE** if both are ≤ 2,000 px; **SURVIVES** if both are ≥ 10,000 px; anything else is **X** | — |

- **COLLAPSE:** the separation needs m11 = 0.5, so the Y16 class is an
  interaction with the vertical scale rather than a Y16 read.
- **SURVIVES:** m11 is eliminated. Two candidates remain (the LUMINANCE stage
  and the luminance values), each for a second capture.

**The world each outcome rules out.** This is text only, added before any
silicon run, at the host's request. No prediction changes.

- **COLLAPSE rules out** a world where silicon reads a Y16 bump source
  differently from Y8 whatever the matrix is: a read-side defect would
  separate them at m11 = 5.0 as well. What is left is an interaction between
  the Y16 source and the small vertical term.
- **SURVIVES rules out** a world where m11 is the trigger. What is left is
  the LUMINANCE stage and the luminance values.
- **X** is a world where m11 modulates the separation without explaining
  it. It covers a count between the thresholds, and the swizzled and
  linear pairs disagreeing. That disagreement would bring the swizzle in as
  a factor.
- **hakuX's own leg fails** in a world where its bump path separates Y16
  from Y8 at m11 = 5.0. That would contradict PR #187's finding that its Y16
  is byte-identical to its Y8.

**hakuX (the dry run):** its pairs **COLLAPSE**, because it renders Y16 as Y8.
Its `BumpMap_Y16` against the golden is recorded, not predicted.

**Recorded, not predicted:** silicon `Y8_m11x10` against hakuX's. It says
whether a tenfold m11 exposes a second defect on the Y8 path, which would
matter for a fix but not for M.

**Void:** a run without "Testing completed normally", or a failed C1.

## Amendment, before any silicon run

The first emulator dry run (`1790393963-xbox-bumpm11-dry-32559`, first XBE
`58bffa3d0fc1…`) completed all nine tests, but it returned only four
`Bump map` captures.

- **The cause.** `DrawRectangles()` names its capture with `MakeTestName()`,
  which drops the `_m11x10` suffix. Each variant runs after its base test in
  name order, so it overwrote the base test's file.
- **The fix** (`d8c5f38`) carries the suffix into the saved name through
  `name_suffix_`. Base tests still save under their own names, and no
  on-screen text changes, so the controls are unchanged.
- **What stays the same:** the legs, the thresholds and the console
  selection.
- **Order:** the dry run is repeated on the fixed XBE before the console
  runs anything. The console run also waits for the host's word, since
  console work is paused for the smart-plug install.
