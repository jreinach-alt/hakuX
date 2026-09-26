# #10 axis follow-up: which bump offset reads the Y16 texel's low byte?

**Status: PRE-REGISTERED.** This file, its scorer and the tests patch were
committed and pushed before the emulator dry run and before the console run.
The branch was cut fresh from `origin/master` (`9743f78f38`), and nothing is
rebased after this commit. The host routed it on #112 at 05:31Z.

## Why

PR #359 measured on silicon that a Y16 bump texel's **low byte feeds one
offset and its high byte the other**. It could not say which offset reads
which. A bump-path fix needs that assignment.

## What runs

- **The XBE:** nxdk_pgraph_tests `6743b6a` plus
  [`y16axis.patch`](y16axis.patch) (tests branch `hakux/bump-y16-axis`
  `2293021`, on top of #359's low-byte patch). sha256 `9358aa7df9ca…`, ISO
  `2e00a67fba1c…`.
- **The variants:**
  - `_h` has only the horizontal term live: m00 = 0.3, m11 = 0.
  - `_v` has only the vertical term live: m00 = 0, m11 = 0.5.
  - Each axis has three tests: `BumpMap_Y16_<axis>`, `BumpMap_Y16_<axis>_lo00`
    (every low byte forced to 0x00) and `BumpMap_Y8_<axis>`.
- **The controls, carried over from #359:** `BumpMap_Y16`, `BumpMap_Y8`,
  `_patchSame` and `_zero`.
- **The console config:** `Alpha func::AlphaFuncAlways_Disabled` first (PR
  #348), then those ten `Bump map` tests. Shutdown-on-completion off,
  networking off, progress log on.
- **The dry run:** a handheld dry run comes first.

## Legs

Scored by [`y16axis_score.py`](y16axis_score.py). It was mutation-tested before
this commit on six cases:
- a split with each axis as the low-byte reader;
- both axes low;
- the two readings disagreeing;
- a stale texture, which Z voids;
- a striped `Y8_h`, which S voids.

| leg | must hold, or decides | the world in which it fails |
|---|---|---|
| **C1, C0, Z** | as in PR #359: the controls equal their goldens, the patch path is inert, `_zero` moves ≥ 10,000 px | The rig moved, the patch changes the draw by itself, or the GPU never saw the patched texels |
| **S** | `Y8_h` varies along x (≤ 10% single-colour rows); `Y8_v` varies along y (≤ 10% single-colour columns) | That axis's image cannot move along it, so it is not read (PR #350's lesson). **It is checked on the dry run first, and the design is amended before silicon if it fails there** |
| **M** per axis | `Y16_<axis>_lo00` against `Y8_<axis>`: LOW ≥ 10,000 px, HIGH ≤ 2,000, X otherwise | — |
| **N** per axis | `Y16_<axis>` against `Y8_<axis>`, the native byte-replicated seam: SWEEP ≥ 5,000 px, NONE ≤ 1,000, X otherwise | — |

**The prediction (the split from PR #359):**
- **Exactly one axis is LOW**, and on each axis the two independent readings
  agree: LOW with SWEEP, HIGH with NONE.
- **Which axis is the result,** and it is not predicted.

**The world each failure names:**
- **Both axes LOW:** both offsets read the low byte. That contradicts #359's
  `_lo00` ≠ `_zero`, unless the high byte enters some other way.
- **Neither LOW:** #359's low-byte effect needs both terms live, an
  interaction.
- **M and N disagree on an axis:** the native seam and the forced low byte are
  not the same mechanism.
- **Any of these is X,** reported with its values.

**hakuX (the dry run):** C0, Z and S must hold. It converts the full value, so
it is predicted HIGH and NONE on both axes.

**Void:** a run without "Testing completed normally", or a failed gate.
