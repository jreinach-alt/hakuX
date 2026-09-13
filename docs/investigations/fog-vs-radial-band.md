# `VS radial` is not saturated: the coordinate is pinned to (204.06, 221.81)

`Fog_gen`'s `VS radial` cell -- a vertex program with `FOGGEN = RADIAL` -- is
2,172,192 channels, 99.3% of the suite and the largest single residue on the
structural board. It has been written up twice as **unfalsifiable**: the
golden holds one colour across the whole region we differ in, so every model
that saturates the fog scores identically, and a fix fitted to it cannot be
checked. A distance was shipped on that cell and reverted (`e90c3c80`).

**The premise is wrong.** Two of the six captures are not saturated, and the
coordinate inverts straight out of them.

Reproduce with `docs/testing/fog_radial_band.py`.

## The two captures that were never clipped

`fog_gen_tests.cpp` sets diffuse to `(0, 0, 1)` and the fog colour to
`(1, 0, 0)`, and its final combiner is `f*diffuse + (1-f)*fog`. That mix
clips at neither end, so **every drawn pixel carries the 8-bit fog factor**:
blue is `f`, red is `255 - f`. Reading the drawn region of all six:

| capture | drawn colour | px | f8 | |
|---|---|---:|---:|---|
| `FogGen_VS-linear-radial` | (255, 0, 0) | 181,016 | 0 | clipped |
| **`FogGen_VS-exp-radial`** | **(254, 0, 1)** | **181,016** | **1** | **interior** |
| `FogGen_VS-exp2-radial` | (255, 0, 0) | 181,016 | 0 | clipped |
| **`FogGen_VS-exp_abs-radial`** | **(254, 0, 1)** | **181,016** | **1** | **interior** |
| `FogGen_VS-exp2_abs-radial` | (255, 0, 0) | 181,016 | 0 | clipped |
| `FogGen_VS-linear_abs-radial` | (255, 0, 0) | 181,016 | 0 | clipped |

One step short of the fog colour is not a clip. `unfalsifiable-goldens.md`
already carries the rule that catches this -- *"a single-colour golden still
pins a value exactly if that colour is a partial mix rather than a clip"* --
and still lists this cell as its headline case. That file has now been found
wrong three times, and the third time is on the example that produced the
rule.

The immediate consequence, before any inversion: **a saturating model does
not match these goldens.** It renders (255, 0, 0) where gold holds
(254, 0, 1), on 181,016 px in each of two captures.

| model | channels left in the cell |
|---|---:|
| today (`oFog.x`, the explicit coordinate) | 2,172,192 |
| "just fully fog it" | **724,064** |
| a coordinate in the measured band | **0** |

## Calibrating silicon's exp unit rather than assuming it

`psh.c:1456` warns that the hardware's own `2^x` "sits above the true value
by up to a step at small factors, and is not modelled here" -- which is
precisely the region an f8 of 1 lands in. Assuming truncation gives one
window, assuming rounding another, and the difference is larger than the
answer. So the quantiser is measured.

`fog_param_tests.cpp` sweeps a *known* coordinate (`-1.4`, step `0.01`) at
multipliers ±2, ±1, ±0.5 with the bias at exp's zero point, which drives
`fogX = bias + c*m - 1.5` straight through the tail. Three sweeps, three
different coordinate steps, one answer:

| f8 | fogX observed | mult −2.00 | mult −1.00 | mult −0.50 |
|---:|---|---|---|---|
| 0 | [−3.5700, −0.5000] | [−3.5700, −0.5100] | [−1.7800, −0.5000] | [−0.8850, −0.5000] |
| **1** | **[−0.4950, −0.4650]** | [−0.4900, −0.4700] | [−0.4900, −0.4700] | [−0.4950, −0.4650] |
| 2 | [−0.4600, −0.4150] | [−0.4500, −0.4300] | [−0.4600, −0.4200] | [−0.4600, −0.4150] |
| 3 | [−0.4100, −0.3850] | [−0.4100, −0.3900] | [−0.4100, −0.3900] | [−0.4100, −0.3850] |

The three agree, which is the check that the model of `fogX` is right and not
just its quantisation. Bounded by the nearest neighbouring observations:

> silicon reports **f8 = 1 iff fogX ∈ (−0.5000, −0.4600)**

The true `2^x` crosses `1/255` at fogX = −0.49965 and `2/255` at −0.43715, so
silicon's unit is *low* here by about half a step at the 2→1 edge, not high.

## The coordinate

`fog_gen_tests.cpp` uses bias 1.5 for the exponential modes, so the bias
cancels and `fogX = coord * m` with `m = -0.025 / (2 ln 256)`. Inverting each
mode's observation:

| mode | f8 | coordinate |
|---|---:|---|
| linear, linear_abs | 0 | > 199.24 |
| **exp, exp_abs** | **1** | **(204.06, 221.81)** |
| exp2, exp2_abs | 0 | > 94.43 |

> **MEASURED: the program-mode RADIAL fog coordinate is in (204.06, 221.81),
> a window 17.74 wide, and is the same on all 181,016 drawn pixels.**

The issue's inferred `[194, 222]` was close; it assumed truncation of an
exact exponential, which is the one thing the `Fog_param` sweeps say is not
what happens.

Two things this kills outright, which a saturation argument could not:

- **200 is not the value.** `kFogEnd` and the projection far plane are both
  200.0, which made "the coordinate is the far plane" the obvious guess. At
  coord 200 silicon's exp reads f8 = 2, and the golden says 1. Out by more
  than the band.
- **Every geometry-derived coordinate is dead, quantitatively.** The
  coordinate varies by less than 17.74 across the 374 quads. Over the same
  geometry the *fixed function* radial distance runs from about 19 to about
  222, a range of 203. The program-mode coordinate's spatial variation is
  under 8.7% of the fixed-function one's, on the same vertices. That is why
  `length(oPos.xyz * oPos.w)` produced 255 distinct colours: not because it
  was too large, because it varied at all.

## The mechanism, to the resolution the corpus allows

#41 proposes that the fog mux still honours RADIAL under a program and reads
lighting eye-vector intermediates that a program never writes -- stale state
from the last draw that did. That is testable here, because the same suite
draws the same 374-quad grid under fixed function, where the radial distance
*is* computed, and those captures carry it.

In `FogGen_FF-exp-radial`, **5 of the 374 quads read f8 ≤ 1 across their
interior: 352, 370, 371, 372, 373.** With 22 quads per row those are the
corners of the final row -- the farthest points in the scene. The last quad
drawn, i = 373, is one of them.

So the program-mode coordinate and the fixed-function radial distance at the
last vertex the transform unit processed land in the same 17.74-wide window,
which only 1.3% of the scene occupies. Measured consistency, on one
observation; not proof.

It also explains the shape of the result without any extra assumption. Tests
run in name order, so all 30 `FogGen_FF-*` run before all 30 `FogGen_VS-*`,
every one of them drawing the identical grid. A program never updates the
intermediate, so the value the first VS test inherits is the value all six
radial VS captures see -- one constant, frame after frame, which is exactly
what the goldens hold.

## Why this still does not become a code change

The measurement makes the number knowable. It does not make it computable.

If the mechanism above is right, the constant is a property of the **test
scene** -- the farthest vertex of a 374-quad grid -- and not of the silicon.
Writing 212.0 into `vsh.c` would take this cell to zero and be arbitrary for
every guest that is not this test. That is the same fit as `a110957a` with a
better-measured constant, and the correct reading of a fitted constant is
still that it fits.

The faithful version is the same shape as #42's carried fog coordinate, one
level harder: the CPU would have to carry `|modelview · v|` of the last
vertex of the last fixed-function draw. #42's shadow works because the
priming write is a `mov` from a constant or an attribute the CPU can read
back; a transformed vertex position is not. Refused for the same reason #42
refused the GPU-resident version, at a smaller payoff.

**So: measured, not modelled.** `oFog.x` stays. The value it differs from
gold by is now known to ±4% instead of "≥ 200".

## The experiment that would close it

One capture, and it is a small one: **a second VS RADIAL scene preceded by a
different fixed-function scene**, with fog params chosen to keep the factor
interior (bias 1.5, multiplier around −0.0023 works, as here).

- coordinate moves with the preceding scene → the mechanism is confirmed, the
  value is scene state, and this cell is permanently unmodellable. File it and
  exclude it from the ranking for good.
- coordinate stays in (204.06, 221.81) → it is a hardware constant, and the
  fix is one line in `vsh.c`.

Nothing in the corpus can run this: `FOG_GEN_MODE_V_RADIAL` under a vertex
program appears in `fog_gen_tests.cpp` and nowhere else.
`fog_tests.cpp:27` and `fog_exceptional_value_tests.cpp:98` both comment
RADIAL out of their gen-mode lists, citing
[abaire/nxdk_pgraph_tests#214](https://github.com/abaire/nxdk_pgraph_tests/issues/214),
"the radial generator tests change occasionally on HW". That instability is
also the strongest independent support for the stale-state reading: a value
derived from the preceding draw is exactly the kind that changes when the
test order or the harness does.

## What generalises

The one-line check in `unfalsifiable-goldens.md` was *count the distinct
colours*. Its own correction added *and check whether the transfer function
clips at that value*. This cell needed the second half applied **per capture
within a cell**, not per cell: four of these six goldens are clipped and two
are not, they were scored together as "one colour each", and the two that
carry the answer were averaged into the four that do not.

So the check has a third clause: **a cell is only as unfalsifiable as its
least-saturated capture.** Where a suite sweeps several transfer functions
over one unknown, look for the function whose output is interior -- that is
the one capture doing the measuring, and it does not need company.
