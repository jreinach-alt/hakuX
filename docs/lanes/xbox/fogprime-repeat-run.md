# #112 item 2, follow-up: V3 on the fogprime binary, and a repeat of the priming suite

**Status: PRE-REGISTERED.** This file and its scorer were committed and pushed
before the emulator dry run and before the console run.

## Why

1. **V3 was not tested.** In PR #346 the six `FogGen_VS-*-radial` tests ran
   with no fixed-function radial draw before them. Their goldens need Fog
   gen's FF tests first, so V3 could not hold in that composition. That was
   my error. This run is the composition V3 needed.
2. **One run cannot say what reproduces.** PR #346 found that silicon carries
   six per-vertex slots from the priming draw's last two quads, read by the
   quad's draw index mod 6, and that the slots' phase moves between tests.
   One run cannot say whether the six values reproduce, or whether the phase
   is set by the work between tests or by timing.

## What runs

- **The XBE:** the same binary as PR #346, sha256 `5dd5b6cd10d8…`,
  unchanged.
- **The tests:** all 60 `Fog gen` tests, then the 11 `Fog radial priming`
  tests.
  - Tests run in name order, so Fog gen's 30 `FogGen_FF-*` tests run before
    its 30 `FogGen_VS-*`, as in the golden run and in PR #340's full run.
- **Order of runs:**
  - First, an emulator dry run through the dispatcher at hakuX `84a67b9cf8`,
    the ref of PR #346's dry run, so that E5 compares like with like.
  - Then the console, via `pgraph_run.py`: app `PgraphFogPrime2`, output
    `e:/fogprime2`, shutdown-on-completion off, networking off, progress log
    on.

## Legs

Scored by [`fogprime_repeat.py`](fogprime_repeat.py) as
`fogprime_repeat.py <PR #346 run> <this run>`, with `--hakux` for the
emulator legs. It was mutation-tested before this commit on seven synthetic
cases, and each leg fails on its own mutation and on no other.

**Silicon:**

| leg | what must hold | the world in which it fails |
|---|---|---|
| **R1** | All 60 `Fog gen` captures are bit-identical to their goldens, the six VS radial included. PR #340's full run on this console gave 60 of 60 | The build or the rig moved, or the radial captures need more than the FF tests before them |
| **R2** (control) | The five priming `*_FF` captures are bit-identical to PR #346's. The FF path computes its own per-vertex distance, and nothing carried reaches it | The FF path is nondeterministic, or the rig moved |
| **R3** (the values) | Each priming `*_VS` capture matches PR #346's same capture, quad by quad, at a single quad shift. The bar is ≥ 0.99 of quads for A1, A2, A4pad and A4radial, and ≥ 0.85 for A0 and A3, whose values straddle the 31/32 rounding edge; PR #346's own A0→A3 match was 0.95 | The slots' contents depend on something besides the priming draw, such as timing or what was in flight when it ended |
| **R4** (the phase) | Within this run, the relative shifts are A0→A3 = 3, A2→A4pad = 3 and A4pad→A4radial = 2, as in PR #346 | The phase is set by timing, not by the work between tests |

**Recorded, not predicted:** the absolute shift between PR #346's A0 and this
run's. This run has 60 more tests before it.

**R4 is not a formality.** Suppose every draw and every test boundary
advanced the phase by some constant. A2→A4pad spans two VS draws, two FF
draws and four boundaries, so its shift would have to be even mod 6, and
PR #346 measured 3. So the phase depends either on something that differs
from test to test (the printed label's length is one candidate) or on timing.
R4 holding says it is deterministic; R4 failing says timing.

**hakuX** (the dry run):

| leg | what must hold |
|---|---|
| **E4** | The six `FogGen_VS-*-radial` are bit-identical to their goldens (#41's arm measured 181,016 → 0 in this composition) |
| **E5** | Every priming capture is bit-identical to PR #346's dry run, `0-0-x-1790388908-xbox-fogprime-dry-1122165`. hakuX carries only the last FF vertex, and the `*_FF` test before each VS test sets it |

**Voids.**
- A console run without "Testing completed normally" voids everything.
- R2 failing voids R3 and R4, because they read reproducibility through an
  instrument that moved.
