# #53 ring weights, the test-boundary methods

**Status: PRE-REGISTERED.** This file, the scorer change and the tests patch
were committed and pushed before the emulator dry run and before the console
run. The branch was cut fresh from `origin/master` (`02374a6847`).

## Why

lane.ring53impl (#53, 14:37Z) implemented the ring with PR #394's weights. It
matches silicon within every test, but it is **2 slots off after every test
boundary**, on all 33 held-out rows. The mis-weighed method is in a fixed set
every gap carries once, so this measures those methods one at a time.

## What runs

- **The XBE:** nxdk_pgraph_tests `6743b6a` plus
  [`ringweights2.patch`](ringweights2.patch) (tests branch
  `hakux/ring-weights-boundary` `4911267`). It is PR #394's `Ring weights`
  suite plus cases N0–N7. sha256 `23339df6d08b…`, ISO `f660eeb27d5f…`.
- **The shape is the same as PR #394:** `Na_FF` priming, then six single-quad
  lit vertex-program draws. Exactly one method sits between draws k and k+1,
  each written with the value the harness already holds under a vertex
  program (`VertexShaderProgram::Activate`, and the default colour surface):

| case | method (value) |
|---|---|
| N0 | nothing (baseline) |
| N1 | `WAIT_FOR_IDLE` (0) |
| N2 | `SET_TRANSFORM_EXECUTION_MODE` (PROGRAM \| PRIV) |
| N3 | `SET_TRANSFORM_PROGRAM_CXT_WRITE_EN` (0) |
| N4 | `SET_TRANSFORM_PROGRAM_LOAD` (0) |
| N5 | `SET_TRANSFORM_PROGRAM_START` (0) |
| N6 | `SET_CONTEXT_DMA_COLOR` (9, `kDefaultDMAColorChannel`) |
| N7 | `SET_TRANSFORM_CONSTANT_LOAD` (180, as M7) |

- **The session:** `Alpha func::AlphaFuncAlways_Disabled` first (PR #348's
  rule), then the 16 N tests. Shutdown-on-completion off, networking off,
  progress log on.
- **The dry run:** an emulator dry run of the same selection comes first.

## Legs

Scored by [`ringw_score.py`](ringw_score.py) with `--cases N0,…,N7 --baseline N0`.
- **What changed in the scorer:** only the `--cases` and `--baseline` options.
- **Its defaults are unchanged:** PR #394's five mutation cases give the same
  verdicts, and the real ring-weights run still passes.
- **The N path is checked too:** a good synthetic set passes, and one with an
  off baseline fails.

| leg | must hold | the world in which it fails |
|---|---|---|
| **S, R** (per case) | As in PR #394: the priming separates, and every draw reads as a window | The case is unreadable, and it is reported |
| **C0** | N0 steps exactly 4 | No baseline, so every weight is void |
| **P1** | Each N case steps by one constant | The method's weight depends on something other than the method |

- **Recorded, not predicted:** each method's weight (step − 4, mod 6).
- **lane.ring53impl's inference:** `SET_TRANSFORM_CONSTANT_LOAD` = 0. N7
  confirms or corrects it.

**Void:** a run without "Testing completed normally", or C0 failing.
