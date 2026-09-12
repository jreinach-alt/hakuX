# `Fog_gen` is radial, plus a rounding floor the gen mode has nothing to do with

`Fog_gen` sits second on the structural board at 2,186,760 channels. It runs
five fog gen modes against six fog modes under both vertex paths, 60 captures.
Split by cell (`score_rad1`, `iso_fog.iso`, all eight fog suites):

| path | gen mode | caps | channels | exact |
|---|---|---:|---:|---:|
| **VS** | **radial** | 6 | **2,172,192** | 0 |
| FF | fog_x | 6 | 356,224 | 0 |
| VS | abs_planar | 6 | 356,224 | 0 |
| VS | fog_x | 6 | 356,224 | 0 |
| VS | planar | 6 | 356,224 | 0 |
| VS | spec_alpha | 6 | 356,224 | 0 |
| FF | radial | 6 | 309,324 | 0 |
| FF | abs_planar | 6 | 199,876 | 0 |
| FF | planar | 6 | 199,876 | 0 |
| FF | spec_alpha | 6 | 4,240 | **4** |

One cell is six times the next. Five cells land on the same number to the
channel, which is not a coincidence.

## Under a vertex program, only RADIAL exists

Comparing the goldens against each other rather than against us. `VS-exp`,
each gen mode against `spec_alpha`:

| vs | differing px | where |
|---|---:|---|
| `planar` | 512 | rows 27-40, cols 160-256 |
| `abs_planar` | 310 | rows 27-40, cols 160-256 |
| `fog_x` | 554 | rows 27-40, cols 160-256 |
| **`radial`** | **181,526** | rows 27-475, cols 48-573 |

Rows 27-40, cols 160-256 is the printed test name. **Silicon renders
`spec_alpha`, `planar`, `abs_planar` and `fog_x` identically under a vertex
program** -- the only thing separating those four goldens is the label saying
which one it is. `radial` is a different image over the whole frame.

Under fixed function the same comparison distinguishes them properly:
`planar` against `fog_x` is 181,086 px, against `radial` 181,154 px, against
`spec_alpha` 106,618 px. Only `abs_planar` matches `planar`, at 542 px, and
that is the label too -- this geometry keeps the planar distance positive, so
`abs` changes nothing.

So the rule is measured rather than inferred:

| | gen modes honoured |
|---|---|
| fixed function | all five |
| **vertex program** | **`RADIAL` only**; the rest collapse to the fog coordinate |

That is why honouring `FOGGEN_SPEC_ALPHA` in the programmable path cost
7,449,481 channels across the fog suites (`docs/investigations/fog-carryover.md`).
The current code's unconditional `oFog.x` is right for four modes out of five
and wrong for exactly one, and it is the one carrying 2.17M channels.

## The five equal cells are one rounding floor

The four non-radial VS cells do not merely have equal counts. Their error
masks are **identical** -- same 35,816 pixels, pairwise IoU 1.000 on all six
pairs -- and the error is one step:

| | ours | golden |
|---|---|---|
| first differing pixel, all four | `(182, 0, 73)` | `(181, 0, 74)` |

Four cells rendering the same image and failing in the same places by one is
a precision floor in the fog blend, not a gen-mode defect. `FF fog_x` joins
them at the same 356,224 because the fixed function stage takes the fog
coordinate there too. So five of the ten cells are one shared rounding
question, and it has nothing to do with what this suite is named for.

## Nine of the ten cells are a rounding floor

Counting channels without their magnitude flattered the wrong cells. With the
one-step share and the worst channel error:

| path | gen | channels | one-step | max |
|---|---|---:|---:|---:|
| **VS** | **radial** | **2,172,192** | **0.0%** | 255 |
| FF | fog_x | 356,224 | 99.2% | 2 |
| VS | abs_planar | 356,224 | 99.2% | 2 |
| VS | fog_x | 356,224 | 99.2% | 2 |
| VS | planar | 356,224 | 99.2% | 2 |
| VS | spec_alpha | 356,224 | 99.2% | 2 |
| FF | radial | 309,324 | 100.0% | 2 |
| FF | abs_planar | 199,876 | 100.0% | 1 |
| FF | planar | 199,876 | 100.0% | 1 |
| FF | spec_alpha | 4,240 | 100.0% | 1 |

`VS radial` holds 2,172,192 of the suite's 2,186,760 structural channels --
99.3% -- and is the only cell with structural content worth the name.

That corrects an earlier reading of mine: the fixed function radial and planar
cells are not "implemented, wrong value". `FF-linear-radial` is 2,601 pixels
at a worst error of one. They are the same blend floor as everything else.

## RETRACTED: I fitted saturation and called it a distance

I shipped `length(oPos.xyz * oPos.w)` as the `VS radial` fog distance on the
strength of a 94.9% reduction in that cell, and posted the derivation to the
coordination thread. It is reverted (`e90c3c80`).

The root cause is not a distance formula and not the stale state #41 proposes.
It is that **these six captures cannot discriminate**: the golden holds one
colour across the whole region we differ in, so every model that saturates the
fog scores the same. Calibrated from `FOG_X`, the output clips at a coordinate
of 200; all six radial captures are fully fogged on all 374 quads in all six
mode functions, while the fixed function captures of the same gen mode carry
250-258 distinct colours. And no unsaturated observation exists anywhere --
`fog_tests.cpp:27` and `fog_exceptional_value_tests.cpp:98` both have RADIAL
commented out of their gen mode lists, because the test author tracks these
captures as unstable on hardware (`abaire/nxdk_pgraph_tests#214`).

So 94.9% was the fraction of pixels a large enough number pushes past the
threshold, and `length(oPos.xyz)` scored 27% for being smaller rather than
less correct. The full measurement, and a scan of the rest of the board for
the same property, is in
[`unfalsifiable-goldens.md`](unfalsifiable-goldens.md).

## What the board entry should say

`Fog_gen`'s 2,186,760 structural channels are 2,172,192 in `VS radial`, and
`VS radial` is **not ours to fix**. It is one sample of hardware state the
hardware itself does not hold steady, on a combination shipped games do not
use. The honest entry is 14,568 channels of real residue plus a large
non-deterministic cell that should be excluded from the ranking rather than
worked.

That makes this suite a coverage-quality problem, not a rendering one, and it
raises a question for the whole board: how many other entries are ranked on
goldens that are one sample of something unstable.

## One thing that looks like a bug and is not

`glsl/vsh-ff.c` reads `tPosition` in the fog block and then assigns
`tPosition = position` thirty lines later, guarded by `SKINNING_OFF`, under a
comment about the composite matrix already including the model-view. Read in
order that is a use-before-assign on the common path, and it would hit exactly
the modes that fail -- radial and the two planars -- while sparing
`spec_alpha`, which is exactly the pattern in the table above.

It is not that. `SKINNING_OFF` takes `append_skinning_code` with `count == 0`,
which emits `vec4 tPosition = (position * modelViewMat0).xyzw` at the top: the
eye-space position, which is what radial and planar want. The later assignment
switches it to object space for the composite-matrix path, after fog is done
with it. The ordering is deliberate and correct.

Recorded because the pattern match was good enough that I nearly acted on it,
and the next person reading that file in order will see the same thing.
