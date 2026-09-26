# #53 ring weights on silicon: each method's advance of the six-slot ring

**Measured 2026-09-26 (06:33 PDT) on the project console.** Registered
beforehand in [`docs/lanes/xbox/ringw-run.md`](../lanes/xbox/ringw-run.md)
(`5dc3456c53`, on a branch cut fresh from master). The host routed it on #53
from lane.ring53's NOTES s6 (PR #391).

**Every registered leg held, and all 15 cases were readable.**
- **C0:** the no-method baseline steps exactly 4 per single-quad draw.
- **P1:** every method's step is a single constant over its five gaps.
- **P2:** a `pb_fill` weighs the same between tests and between draws.

## Per-method weights (step − 4, mod 6)

| case | method between VS draws k and k+1 | window starts, draws 1–6 | step | **weight** |
|---|---|---|---:|---:|
| M0 | nothing (baseline) | 4 2 0 4 2 0 | 4 | **0** |
| M1 | NOP 0x100 | 1 5 3 1 5 3 | 4 | **0** |
| M2 | `COMBINER_COLOR_ICW` (the same value) | 1 0 5 4 3 2 | 5 | **+1** |
| M3 | `SPECULAR_ENABLE`, the same value | 1 0 5 4 3 2 | 5 | **+1** |
| M4 | `SPECULAR_ENABLE`, toggled | 4 3 2 1 0 5 | 5 | **+1** |
| M5 | `LIGHT_CONTROL` (the same value) | 1 5 3 1 5 3 | 4 | **0** |
| M6 | one `pb_fill` | 0 3 0 3 0 3 | 3 | **5 (≡ −1)** |
| M7 | one `SET_TRANSFORM_CONSTANT` vec4 | 1 0 5 4 3 2 | 5 | **+1** |
| M8 | an empty `BEGIN_END` pair | 5 3 1 5 3 1 | 4 | **0** |

**Three things stand out:**
- **A redundant write can still weigh.** `SPECULAR_ENABLE` weighs +1 with the
  same value or toggled, and `COMBINER_COLOR_ICW` weighs +1 with the same
  value. `LIGHT_CONTROL` with the same value weighs 0.
- **NOP and an empty `BEGIN_END` pair weigh nothing.**
- **The weight does not count method dwords.** A vec4 constant (4 dwords)
  weighs +1. B3's group of seven writes, below, also weighs +1 in total.

## The between-test constant (C cases, no label text)

| case | fills before the first VS draw | first-draw start | then steps |
|---|---:|---:|---|
| C0 | 0 | 5 | 4 ×5 |
| C1 | 1 | 4 | 4 ×5 |
| C2 | 2 | 3 | 4 ×5 |

**Each fill moves the start by −1**, the same as M6's between-draw fill. With
no fill and no label, the first draw after a priming test starts at cycle
position 5.

## Front against back (B cases, `MakeBackFaceFront`)

| case | what is added | starts | step |
|---|---|---|---:|
| B1 | per-vertex back diffuse and back specular inside each quad | 2 0 4 2 0 4 | 4 (**0**) |
| B2 | the face state alone | 2 0 4 2 0 4 | 4 (**0**) |
| B3 | `MATERIAL_ALPHA_BACK` + six `SPECULAR_PARAMS_BACK` between draws | 2 1 0 5 4 3 | 5 (**+1** for the group) |

- **The back-face reads work:** back-facing lit vertex-program draws read the
  same ring, windows and all.
- **The face state and the per-vertex back attributes weigh 0.**
- **The back material-and-specular group weighs +1.** `Specular_back`'s setup
  issues exactly those writes, which makes them a candidate for its +1 phase
  against `Specular` (PR #351). The attribution is for lane.ring53 to
  confirm against its model.

## hakuX

The dry run completed all 31 tests cleanly. As registered, no draw reads as a
window, because hakuX lights with each vertex's own normal (PR #355).

## Files

- [`ringw-run.md`](../lanes/xbox/ringw-run.md): the registration.
- [`ringw_score.py`](../lanes/xbox/ringw_score.py): the scorer.
- [`ringweights.patch`](../lanes/xbox/ringweights.patch): the tests-tree patch.
- The captures are on the host under
  `~/hakux-work/hardware/runs/2026-09-26-ringweights/console-run/console/`.
