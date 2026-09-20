# lane.cloud-112 -- #112 items 1 and 2: register predictions ahead of hardware

Cloud lane, no device, 2026-09-19. Branch `lane/cloud-112` from `origin/master`
at `01047cf32c`.

## What was asked and what landed

Two of #112's five experiments -- item 1 (the Viewport 9/16 boundary sweep,
#49) and item 2 (radial fog carryover, #41) -- needed a registered prediction
naming must-move and must-not-move captures for both competing models, plus a
`docs/investigations/` note per item explaining the derivation. Four files:

| | |
|---|---|
| `docs/investigations/2026-09-19-viewport-substep-threshold.md` | item 1 derivation |
| `docs/testing/predictions/2026-09-19-viewport-substep-threshold.md` | item 1 prediction |
| `docs/investigations/2026-09-19-fog-radial-priming-scene.md` | item 2 derivation |
| `docs/testing/predictions/2026-09-19-fog-radial-carryover-priming.md` | item 2 prediction |

Neither prediction registers an arm. Both follow
`2026-09-18-pvideo-overlay-size-pitch-limits.md`'s shape: prose, no
`a_ref`/`b_ref`, no golden key. **Every capture either one predicts is of a
test that does not exist yet**, so a `.json` with a golden key would be refused
at queue time and a `.json` without one would be inert -- the third way a
prediction reads `PRE-REGISTERED` and binds nothing. Nothing here can be queued
and nothing should be.

## Item 1: two of the three models were settled offline, for free

The brief asked for "the truncation model and the 9/16 threshold hypothesis".
Working out what the second one means produced the lane's main result, and it
is arithmetic over tables already on disk -- no device, no new capture.

**"The rounding threshold is 9/16" names two models, not one.** Either the
coordinate is reduced to four fractional bits rounding up at 9/16 *of a step*
(**R**), or the fill rule samples at `n + 9/16` instead of the pixel centre
(**S9**). They are not variants; only one number is shared.

1. **S9 is refuted by the goldens.** It moves coverage only where the snapped
   edge lands at exactly 9/16, which on this sweep is #49's two captures and
   nothing else, and it predicts every vertex `LOW` in both. Gold has x = 120
   and x = 220 `HIGH`. It is the same frame as the small negative pre-snap bias
   `viewport-9-16-boundary.md` already priced at **888 px** -- a different
   mechanism reaching an already-computed residual.
2. **R is invisible in all twelve existing captures.** Every sweep offset has a
   sub-step remainder of 0 or 1/2, and 1/2 < 9/16, so R and truncation produce
   the identical snap at every vertex of every capture at both scales. Coverage
   can only change where the snap crosses 8/16 -> 9/16, which needs
   `floor(offset*16) mod 16 == 8` **and** a remainder above the threshold.
3. **So two sentences in #112 are wrong**, and they are wrong in the direction
   that makes the experiment look more expensive than it is. A real 9/16
   threshold does *not* "predict both failing captures" -- under R it predicts
   exactly what we render today, all nine vertices `HIGH`. And it does not have
   to be "reconciled with the 820,000-pixel regression": that regression was
   **round-half-up, threshold 8/16**, and R's threshold is above 1/2, so R
   costs zero of it. Different constants; only one has been measured against.

What is left for silicon is a **measurement of θ over (1/2, 1]**, and the only
offsets that carry information are two 1/32-wide windows,
`[k+0.53515625, k+0.5625)` and `[k−0.46484375, k−0.4375)`. Both of #49's
failing offsets sit at the *top edge* of one, which is why they are where they
are and still cannot see this. The prediction's primary discriminator is the
window midpoint, `+0.548828125`, at 0.01367 px from both candidate thresholds.

**Do not re-run the existing twelve expecting an answer.** They are the
validity gate and nothing else: T, R and R' all predict them unchanged.

## Item 2: rotate the draw order, do not change the scene

The experiment #41 and #112 both name is "a VS RADIAL scene after a different
fixed-function one". Drawing a *different* scene confounds it -- any
downstream difference then has a second cause. `fog_gen_tests.cpp`'s 374 quads
do not overlap and each carries its own fog, so **rotating the draw order
produces a bit-identical priming frame** and changes exactly one thing: which
vertex the transform unit saw last. Three rotations put the register at
coordinate ~216, ~95 and ~12.

Three things worth not re-deriving:

- **The suite's own fog multiplier is the wrong instrument for this.** At
  −0.00225 the incumbent case reads f8 = 1, in the tail `psh.c:1456` says is
  not modelled, where one f8 step is 17.74 coordinate units -- wider than the
  band being scored against. At **−0.000875** the three rotations read 31, 102
  and 225, each with ≤ 3.3 coordinate units per step. #41's note suggests "a
  multiplier around −0.0023 works"; it works and it measures worse.
- **The decisive reading needs no model of silicon's exp unit.** Carryover
  predicts three different factors across the rotations; a hardware constant
  predicts three identical ones. That is a comparison between captures from one
  run at one multiplier, so the uncharacterised `2^x` cancels exactly. The f8
  windows are the second, stronger leg and they are the one that inherits the
  uncertainty -- which at a 65-step separation it cannot close.
- **Rotation alone leaves "the label is the last FF vertex" degenerate with
  "it is a constant"**; both predict a flat row. A fourth capture with the
  *priming* test's label moved breaks it, and it measures the text-vertex
  exclusion that `fog_radial_stale_vertex.py` currently infers from two
  captures 40 px apart.

A rotation also separates last-wins from first-wins, but **only at r = 0**: at
r = 188 and r = 21 the first and last quads are adjacent in the grid and their
windows overlap. That is enough, because r = 0 separates them by 200 f8 steps.

## What the next lane should not repeat

- Do not write a `.json` prediction for either of these. There is no golden to
  key it to and no ref to bind it to; `request.sh` refuses the first and the
  second is inert.
- Do not spend a capture on a fully legal / fully expected variant beyond the
  one gate each file names. Both files have a §"which variants carry no
  information" section, derived rather than guessed, and between them they
  retire the obvious choices: grid-exact viewport offsets, remainders at or
  below 1/2, scale-2.0 twins, rotations whose last quad is already in the band,
  the suite's own fog multiplier, and any change to the programmable scene.
- The two emulator-side companions (§3 and §4 respectively) need no hardware --
  a desktop lane under lavapipe settles every leg -- and each is the positive
  control for its hardware run. They are the cheapest next unit on this issue
  and they need the test discs to exist first, which is the real blocker.

## On the brief's "no PR"

The brief ends `No device time, no code change, no PR`. A PR is nevertheless
open, because `docs/testing/jobs/roles/lane.md` makes it the definition of
done and it is the only path by which these four files reach `master`:
`fold.sh` folds PRs, and a lane with no PR is work nobody can find. Read as
"no code-change PR", which this is not -- the diff is four documents and this
file, and touches nothing under `hw/xbox/`.
