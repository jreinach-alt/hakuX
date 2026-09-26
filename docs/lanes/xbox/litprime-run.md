# #53: which fixed-function vertex does each lit vertex-program corner read?

**Status: PRE-REGISTERED.** This file, its scorer and the tests patch were
committed and pushed before the emulator dry run and before the console run.

## Why

PR #351 found, from existing captures, that #53's lit `ControlFlags_VS` quads
read the **six-slot ring of stale fixed-function lighting results** measured
for #41 in PR #346. That analysis had two limits:
- the corpus supplies only two distinct N·L values, so it could fit H/L codes
  but could not name a corner's source vertex;
- the ring's contents were inferred rather than set by the test.

This run sets them.

## What runs

- **The XBE:** nxdk_pgraph_tests `6743b6a` plus
  [`litprime.patch`](litprime.patch) (tests branch `hakux/lighting-priming`
  `34b2cde`), a new `Lighting priming` suite. sha256 `2abce6e5e821…`, ISO
  `a13e14e06eda…`.
- **The priming tests (`L0_FF`, `L1_FF`):** two lit fixed-function quads, each
  its own draw.
  - The eight vertices, in draw order (P1 UL, UR, LR, LL, then P2), carry
    N·L = 0.90, 0.30, 0.60, 0.80, 0.40, 0.70, 0.50, 0.20: a red directional
    light at full diffuse, with normals tilted from the camera.
  - The eight values are distinct, and they are in no monotone order.
- **The lit shader tests:** `L0_VSdraws` has six lit quads under
  `ControlFlags_VS`'s vertex program, **six separate draws**. `L1_VSsingle`
  is the same six quads in **one draw**.
  - Their own normal faces the camera, N·L = 1, a value no priming vertex
    carries.
  - Each lit shader test runs immediately after its priming test.
- **The console config:**
  - `Alpha func::AlphaFuncAlways_Disabled` runs first (PR #348's rule).
  - Then the four tests.
  - Shutdown-on-completion off, networking off, progress log on.
- **The dry run:** an emulator dry run of the same selection comes first,
  on a handheld.

## Legs

Scored by [`litprime_score.py`](litprime_score.py). It was mutation-tested
before this commit on six synthetic cases, each failing on its own leg:
- a corner at the own value;
- a source outside 2–7;
- descending windows;
- a broken step in the middle quad;
- duplicate priming values, which voids everything.

| leg | must hold | the world in which it fails |
|---|---|---|
| **S** (sensitivity) | Each `*_FF` capture's eight priming values are pairwise ≥ 10 levels apart | The priming cannot tell its vertices apart, and nothing below is read (the lesson of PR #350) |
| **M1** | Every lit shader corner is within 6 levels of a priming vertex, and none sits at its own-normal value | A lit vertex program lights its own normal, or reads something other than the priming vertices |
| **M2** | Every source is one of vertices 2–7 (the last six) | The ring is longer than six, or keeps older vertices |
| **M3** | In `L0_VSdraws`, each quad reads four consecutive entries of the cycle 2,3,4,5,6,7, ascending UL→LL, and the start advances by a constant 4 per quad | The per-draw reading PR #351 inferred from `ControlFlags_VS` is wrong in its order or its step |

- **Recorded, not predicted:** `L1_VSsingle`'s sources and per-quad step.
  #41's scene was a single long draw and advanced differently.
- **hakuX (the dry run):** it emits the constant lighting term under a vertex
  program (#53). Its corners are recorded, and S must hold on its `*_FF`
  captures.
- **Void:** a run without "Testing completed normally", or S failing.
