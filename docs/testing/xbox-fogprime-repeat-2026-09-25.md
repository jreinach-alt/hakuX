# #112 item 2, follow-up: V3 holds, the slot structure is deterministic, and the first planar-fog test of a session sees half its fog coordinate

**Measured 2026-09-25 on the project console.** Registered beforehand in
[`docs/lanes/xbox/fogprime-repeat-run.md`](../lanes/xbox/fogprime-repeat-run.md)
(`58af8a9910`, pushed before the dry run and the console run). It follows
[`xbox-fogprime-2026-09-25.md`](xbox-fogprime-2026-09-25.md) (PR #346,
"run 1" below).

## What ran

- **The XBE:** PR #346's binary, sha256 `5dd5b6cd10d8…`.
- **The tests:** all 60 `Fog gen` tests, then the 11 `Fog radial priming`
  tests.
- **The progress log** shows Fog gen's 30 FF tests (1–30), then its 30 VS
  tests (31–60), then the priming suite. The run took 57 s and ended
  "Testing completed normally".
- **The emulator dry run**, `1790391241-xbox-fogprime2-dry-2157566`, ran first
  on the Thor with the same APK as run 1's dry run (`a7b9d28e6b84`,
  hakuX `84a67b9cf8`). It completed all 71 tests with no crash signal.

## The legs

| leg | result |
|---|---|
| **R1** all 60 `Fog gen` captures equal their goldens | **FAILS, on 1 of 60.** The six VS radial captures are bit-identical to their goldens, so **V3 holds** in the composition it needs. The one failure is the session's first test (below) |
| **R2** the five priming FF captures equal run 1's | **holds** |
| **R3** each priming VS capture matches run 1's at one shift | **holds**, at shift 0 on 1.000 of quads for all six. All 11 priming captures, FF and VS, are **bit-identical to run 1** |
| **R4** the relative phases are 3, 3, 2 | **holds**: A0→A3 3 (0.946), A2→A4pad 3 (1.000), A4pad→A4radial 2 (1.000) |
| **E4** (hakuX) the six VS radial equal their goldens | **holds** |
| **E5** (hakuX) every priming capture equals run 1's dry run | **holds**, 11 of 11 |

**Recorded, not predicted.** The absolute phase at `A0far_VS` is the same as
in run 1, although the suite was preceded by 60 tests here and by 6 there.
A 1-in-6 coincidence is not excluded.

## What the repeat settles

- **The six slot values and the phase are deterministic.** Two sessions with
  different histories gave bit-identical priming captures.
- **The phase is set by the work between tests, not by timing.** Run 1
  showed that no model with a constant advance per draw and per test fits its
  shifts: A2→A4pad spans an even count of everything and moved 3. So what
  advances the phase differs from test to test, and R4 now shows it is
  deterministic.
- **V3 holds.** The six radial goldens reproduce on this binary once Fog
  gen's FF tests run first, as PR #340's full run showed for the pristine
  binary. Run 1's V3 failure was its composition.

## The one failure: the session's first test, and a halved fog coordinate

`Fog gen::FogGen_FF-exp-abs_planar` ran first in the session. It differs from
its golden on all 181,016 drawn px:
- f8 is higher everywhere by 2–11 levels (less fog), and the region is the
  same.
- Inverted through the exp curve (`f = 2^(16·m·d)`, m = −0.00225), **the
  coordinate it rendered with is exactly half the golden's:**

  | golden f8 | px | golden coordinate | this run | ratio |
  |---|---:|---:|---:|---:|
  | 20–39 | 13,728 | 88.7 | 44.5 | 0.502 |
  | 40–79 | 13,530 | 60.7 | 30.4 | 0.500 |
  | 80–139 | 10,846 | 35.6 | 17.8 | 0.500 |
  | 140–199 | 7,007 | 17.1 | 8.6 | 0.505 |
  | 200–255 | 3,597 | 6.1 | 3.0 | 0.495 |

**What makes this the session's first planar-fog test rather than the rig:**
- The same capture is bit-identical to its golden in PR #340's full run on
  this console, where Fog gen was not first.
- The second test here, `FogGen_FF-exp-fog_x`, matches its golden, and so do
  the other 58.
- The golden equals `FogGen_FF-exp-planar` outside the printed label rows
  (542 px, rows 27–40), as a positive planar distance should. This run's
  first capture does not.

**What it is not:**
- **Not the first draw of every session.** PR #340's first test,
  `Lighting normals::NoNormal`, is bit-identical to its golden.
- **Not the first fog test of every session.** Run 1 began with
  `FogGen_VS-exp-radial`. Its f8 of 210 equals the fourth test's
  (`exp_abs-radial`), so nothing there was halved.
- What is left is a planar-fog quantity, such as the fog plane or the
  multiplier as the planar path applies it, that is wrong by exactly ½ for
  the first such draw after the XBE starts. This is one observation, and its
  mechanism is not identified.

**The practical rule until it is:** a silicon reference must not be taken
from the first planar-fog test of a session. No earlier lane.xbox console run
began with a fog test other than run 1's VS radial, so no earlier reference
is affected. hakuX does not show it: its dry-run capture differs from the
golden by the same 35,643 px as its `exp-planar`.

## Silicon's exp unit in the mid range (for #38)

Run 1's `A0far_FF` is fixed-function radial exp fog over 374 quads at the
new multiplier (−0.000875). It gives silicon's fog factor from f8 ≈ 30 to
255, where `fog_param_tests` bounds only f8 0–3. Against the continuous
`255 · 2^(16·m·d)` at each quad's centre:

| model f8 | quads | silicon − model, mean (range) | hakuX − model, mean |
|---|---:|---|---:|
| 25–49 | 67 | +0.12 (−0.46 .. +0.65) | +0.04 |
| 50–74 | 69 | +0.34 (−0.27 .. +0.95) | −0.01 |
| 75–99 | 53 | +0.01 (−0.65 .. +0.77) | +0.01 |
| 100–124 | 43 | +0.07 (−0.67 .. +0.71) | +0.07 |
| 125–149 | 38 | +0.55 (−0.07 .. +1.18) | +0.10 |
| 150–174 | 31 | +0.33 (−0.69 .. +1.03) | −0.05 |
| 175–199 | 30 | −0.05 (−0.83 .. +0.57) | +0.02 |
| 200–224 | 22 | −0.36 (−1.13 .. +0.49) | +0.09 |
| 225–249 | 20 | +0.19 (−0.45 .. +0.87) | +0.19 |

- **Silicon wiggles about the exact curve, by up to about ±0.5 f8 in the
  bin means.** hakuX follows the curve.
- **That is where hakuX's ±1 differences on the FF priming captures come
  from:** 46,759 px each, at most 2 levels.
- **The shape** would fit an interpolated 2^x table. The table's segment
  length is not measured here.

## Follow-ups, not run

1. **The first-planar-fog halving.** Two short sessions would separate "the
   first planar draw" from "this test's position":
   - a non-fog test, then `FogGen_FF-exp-abs_planar`, predicted to match its
     golden;
   - `FogGen_FF-exp-planar` first, predicted to be halved.
2. **What advances the phase.** A variant that changes one factor between
   tests, such as the label text length or the pad draw's quad count, with
   the rest held.

## Files

- **The scorer** is [`fogprime_repeat.py`](../lanes/xbox/fogprime_repeat.py),
  mutation-tested before registration.
- **The captures** are on the host under
  `~/hakux-work/hardware/runs/2026-09-25-fogprime2/console-run/console/`.
