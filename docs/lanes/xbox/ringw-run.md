# #53 ring weights: how far does each method advance the six-slot ring?

**Status: PRE-REGISTERED.** This file, its scorer and the tests patch were
committed and pushed before the emulator dry run and before the console run.
The branch was cut fresh from `origin/master` (`0e7ba4c334`). The host routed
it on #53 at 06:09 PDT, from lane.ring53's NOTES s6 (PR #391). Its purpose is
to unblock the #53 ring fix, which is at chance on held-out rows.

## What runs

- **The XBE:** nxdk_pgraph_tests `6743b6a` plus
  [`ringweights.patch`](ringweights.patch) (tests branch `hakux/ring-weights`
  `3b3833a`), a new `Ring weights` suite registered after `AlphaFuncTests`.
  sha256 `d9f922b1bdb9…`, ISO `3c8a883cac6f…`.
- **Every case K is two tests:** `Ka_FF`, PR #355's priming (two lit FF quads
  whose vertices 0..7 carry N·L 0.9 … 0.2), then `Kb_*`, six single-quad lit
  vertex-program draws. Every test resets culling and the front face first.
- **The session:** `Alpha func::AlphaFuncAlways_Disabled` first (PR #348's
  rule), then all 30 tests. Shutdown-on-completion off, networking off,
  progress log on.
- **The dry run:** an emulator dry run of the same selection comes first.

| case | what sits between VS draws k and k+1 (s6 step) |
|---|---|
| **M0** | nothing: the baseline |
| **M1–M8** | exactly one of NOP 0x100 · `COMBINER_COLOR_ICW` (the same value) · `SPECULAR_ENABLE` same · `SPECULAR_ENABLE` toggled · `LIGHT_CONTROL` (the same value) · one `pb_fill` (8×8 px off every quad) · one `SET_TRANSFORM_CONSTANT` vec4 (the load pointer is set to slot 180 before the first draw) · an empty `BEGIN_END` pair (step 2) |
| **C0, C1, C2** | 0, 1 or 2 `pb_fill`s before the first VS draw, with no label text in either test (`pb_erase_text_screen` before `FinishDraw`) (step 3) |
| **B1, B2, B3** | `MakeBackFaceFront` for the VS draws. **B1** adds per-vertex back diffuse and back specular. **B2** is the face state alone. **B3** puts `MATERIAL_ALPHA_BACK` and the six `SPECULAR_PARAMS_BACK` between draws (step 4, covering both readings of "the back material and specular writes") |

## Legs

Scored by [`ringw_score.py`](ringw_score.py), which reads the window of every
draw as `litprime_score.py` does. It was mutation-tested before this commit on
five cases:
- a baseline off by one;
- a broken step in the middle;
- a fill-weight mismatch;
- an own-value corner;
- a consistent run, which passes.

| leg | must hold | the world in which it fails |
|---|---|---|
| **S** (per case) | Its priming values are pairwise ≥ 10 apart | The priming cannot name its vertices |
| **R** (per case) | Every draw reads as a window: four corners, priming vertices 2–7, consecutive and ascending | That test's weight is unreadable, and it is reported, not guessed |
| **C0** | M0 steps exactly 4 on all five gaps (PR #355 measured this) | The weights have no baseline, and every weight is void |
| **P1** | Each M case steps by one constant | A method's weight depends on the state it writes or on history, not on the method alone |
| **P2** | The fill weight from C0/C1/C2's first-draw starts (C1−C0 = C2−C1) equals M6's | A fill between tests and a fill between draws weigh differently |

**Recorded, not predicted:**
- each method's weight, which is step − 4 (mod 6);
- the C cases' first-draw starts, which give the between-test constant;
- the B cases' starts and steps. A back-facing reader may not name priming
  vertices at all, and that is reported if so.

**hakuX (the dry run):** it lights with each vertex's own normal (PR #355), so
no draw reads as a window there. R is expected to fail on hakuX and passes
only on silicon.

**Void:** a run without "Testing completed normally", or C0 failing.
