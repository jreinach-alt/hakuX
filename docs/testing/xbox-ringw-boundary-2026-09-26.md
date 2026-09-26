# #53 ring weights, the test-boundary methods: every one weighs 0

**Measured 2026-09-26 (07:51 PDT) on the project console.** Registered
beforehand in
[`docs/lanes/xbox/ringw-boundary-run.md`](../lanes/xbox/ringw-boundary-run.md)
(`ab8209895e`). It was asked for by lane.ring53impl on #53 (14:37Z): its ring
is 2 slots off after every test boundary, and the mis-weighed method is in the
set every gap carries once.

**Every leg held, and all 8 cases were readable.** The N0 baseline steps
exactly 4, each method's step is constant, and **every method below weighs
0**:

| case | method between VS draws (value) | window starts, draws 1–6 | step | weight |
|---|---|---|---:|---:|
| N0 | nothing (baseline) | 0 4 2 0 4 2 | 4 | 0 |
| N1 | `WAIT_FOR_IDLE` (0) | 3 1 5 3 1 5 | 4 | **0** |
| N2 | `SET_TRANSFORM_EXECUTION_MODE` (PROGRAM \| PRIV) | 3 1 5 3 1 5 | 4 | **0** |
| N3 | `SET_TRANSFORM_PROGRAM_CXT_WRITE_EN` (0) | 3 1 5 3 1 5 | 4 | **0** |
| N4 | `SET_TRANSFORM_PROGRAM_LOAD` (0) | 0 4 2 0 4 2 | 4 | **0** |
| N5 | `SET_TRANSFORM_PROGRAM_START` (0) | 3 1 5 3 1 5 | 4 | **0** |
| N6 | `SET_CONTEXT_DMA_COLOR` (9) | 2 0 4 2 0 4 | 4 | **0** |
| N7 | `SET_TRANSFORM_CONSTANT_LOAD` (180) | 3 1 5 3 1 5 | 4 | **0** |

## What it means for the boundary

- **`SET_TRANSFORM_CONSTANT_LOAD` = 0 is confirmed,** as lane.ring53impl
  inferred from M7.
- **The residual belongs elsewhere.** None of `WAIT_FOR_IDLE`, the four
  transform-program methods or `SET_CONTEXT_DMA_COLOR` carries the 2-slot
  error when written between draws. Of lane.ring53impl's fixed set, that
  leaves the flip pair, `FLIP_INCREMENT_WRITE` and `FLIP_STALL`, which only a
  test boundary issues. The residual falls to them by lane.ring53impl's own
  reasoning.
- **Caveat:** these weights are measured between draws. A method whose
  effect depends on a frame boundary, a flip in particular, is not isolated
  by this shape.

**The first-draw starts differ between cases,** at 0, 3 and 2.
- **Only one thing differs before each case's first draw:** the priming
  test's printed name (`N0a_FF` … `N7a_FF`). The shader test's own name is
  drawn after its draws.
- **Label text is drawn with `pb_fill`s,** and PR #394 measured each fill
  at −1.
- **So the starts should follow each label's fill count.**
  lane.ring53impl's `textfills.py` can check that as a held-out consistency
  test.

## hakuX

The dry run was clean. As registered, no draw reads as a window on hakuX.

## Files

- [`ringw-boundary-run.md`](../lanes/xbox/ringw-boundary-run.md): the
  registration.
- [`ringw_score.py`](../lanes/xbox/ringw_score.py): the scorer, run with
  `--cases N0,…,N7 --baseline N0`.
- [`ringweights2.patch`](../lanes/xbox/ringweights2.patch): the tests-tree
  patch.
- The captures are on the host under
  `~/hakux-work/hardware/runs/2026-09-26-ringweights2/console-run/console/`.
