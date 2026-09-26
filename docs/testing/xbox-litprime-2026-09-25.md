# #53 on silicon: a lit vertex program reads the last six fixed-function lighting results, four consecutive per quad

**Measured 2026-09-25 on the project console.** It was registered in
[`docs/lanes/xbox/litprime-run.md`](../lanes/xbox/litprime-run.md)
(`a1cdbc0260`, amended at `34fc51cedb` before any silicon run). The host routed
it on #112. It is the direct test of PR #351, which inferred the mechanism from
existing captures.

**Result: every registered leg held.**
- **The mechanism.** Under a vertex program with `LIGHTING_ENABLE`, each lit
  vertex takes the fixed-function lighting result of **one of the preceding FF
  draw's last six vertices**.
- **The reading pattern.** A quad reads **four consecutive entries**, in the
  cycle of those six vertices' draw order and ascending UL→LL. The window
  start advances by **+4 per quad**.
- **The precision.** Corners match their source vertex's value to within 0.56
  levels. This is the six-slot carry PR #346 measured for #41's RADIAL fog.

## What ran

- **The XBE:** nxdk_pgraph_tests `6743b6a` plus
  [`litprime.patch`](../lanes/xbox/litprime.patch), a new `Lighting priming`
  suite. sha256 `2abce6e5e821…`.
- **The session:** `Lighting normals::NoNormal` first (PR #348's rule), then
  the four tests. The console took 53 s and ended "Testing completed
  normally".
- **Dry runs:** two on the Thor. The first showed the suite running before
  `Alpha func`, so the config was amended to put `NoNormal` first. The
  second was clean.

## The legs

| leg | result |
|---|---|
| **S** (sensitivity) | holds. The priming values for vertices 0–7 are 237.9, 83.6, 160.8, 212.0, 110.2, 187.3, 135.2 and 59.2 (N·L 0.9 … 0.2 plus ambient); the minimum separation is 24.5 |
| **M1** | holds. All 48 lit corners, over both tests, name a priming vertex, and none sits at its own-normal value |
| **M2** | holds. Every source is one of vertices 2–7, the priming draw's last six |
| **M3** | holds. In `L0_VSdraws` (six draws) the windows are [2,3,4,5] [6,7,2,3] [4,5,6,7] [2,3,4,5] [6,7,2,3] [4,5,6,7], with starts 0, 4, 2, 0, 4, 2 and a step of +4 |
| **R** (recorded) | In `L1_VSsingle` (one draw) the windows are [5,6,7,2] [3,4,5,6] [7,2,3,4] …, also consecutive and ascending, with a step of +4 from a different start |

- **Every corner is exact:** it is its source vertex's value to within 0.56
  levels, mean −0.08.
- **They are pure lighting results:** green and blue are 8 inside every quad,
  the scene ambient under a red-only light. That rules out a blend with the
  vertex program's own colour output.

## hakuX (`84a67b9cf8`)

hakuX lights each vertex-program vertex with **its own normal**. Every lit
corner is (255, 8, 8), which is N·L = 1 plus ambient. Silicon never does that
here. All 55,296 px of the six quads differ in each lit test.

## What it means for #53 and #41

**One ring model covers both issues.**
- **The ring:** six entries of fixed-function per-vertex outputs (lighting
  colours here, the RADIAL fog coordinate in #41).
- **Writing:** FF vertices fill it in draw order.
- **Reading:** a vertex program reads it where it does not supply the value
  itself. Each quad reads four consecutive entries, and the start advances +4
  per quad, one per vertex.

**Measured now:**
- the contents: the last six FF vertices, 2–7;
- the order: ascending, in draw order;
- the step: +4 per quad, in both six draws and one draw.

**Still open:**
- **The absolute phase** at the start of a vertex-program draw. `L0` started
  at cycle position 0 and `L1` at 3, and PR #351's `ControlFlags_VS` rows add
  an unexplained −1 between rows.
- **#41's fog scene.** It showed a pattern of period 6 in the quad index, but
  a +4 step with four consecutive entries gives period 3. That scene draws
  differently from this suite, and what makes the difference is not measured.

## Files

- [`litprime-run.md`](../lanes/xbox/litprime-run.md): the registration.
- [`litprime_score.py`](../lanes/xbox/litprime_score.py): the scorer.
- [`litprime.patch`](../lanes/xbox/litprime.patch): the tests-tree patch.
- The captures are on the host under
  `~/hakux-work/hardware/runs/2026-09-25-litprime/console-run/console/`.
