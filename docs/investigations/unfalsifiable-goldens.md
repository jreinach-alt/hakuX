# Where the corpus bounds the hardware value but cannot determine it

Some goldens are saturated. Where hardware's output has clipped to one colour
across the whole region we differ in, the capture tells you the hardware value
was *at least* past the clipping threshold and nothing else. Every model that
clears that threshold scores identically, so the corpus cannot choose between
them, and a fix fitted to such a capture is unfalsifiable by the measurement
that motivated it.

This came out of getting it wrong. The route in is written up first because
the failure mode is the transferable part.

## The case that found it

`Fog_gen`'s `VS radial` cell is 2,172,192 of the suite's 2,186,760 structural
channels. I shipped a fog distance for it on the strength of a 94.9% reduction
and had to revert.

Calibrating the fog chain empirically rather than deriving it settles what the
captures can say. `FOG_X` drives a coordinate the test sets explicitly -- 50,
decreasing by 0.2 per quad across 374 quads -- so reading quad centres out of
`FogGen_VS-linear-fog_x` maps coordinate to output directly:

| coordinate | quad-centre colour |
|---|---|
| 49 | `(63, 0, 192)` |
| 46 | `(60, 0, 195)` |
| <= 0 | `(0, 0, 255)` — no fog |

Fog fraction is coordinate/200, so **the output saturates at a coordinate of
200**. Now the radial captures:

| capture | distinct colours in the whole drawn region |
|---|---:|
| `FogGen_VS-*-radial`, all six | **3** — background, fog colour, and the printed test name |
| `FogGen_FF-*-radial`, all six | 250 - 258 |

Every one of the 374 quads is fully fogged, in all six fog mode functions,
with no variation anywhere. The fixed function captures of the same gen mode
carry a full gradient and reach saturation on only 14 quads of 374.

So the six captures establish one fact -- the coordinate exceeds every mode's
saturation threshold for every quad -- and destroy everything else. A constant
and a geometry-derived quantity that happens to be large everywhere are
indistinguishable. My 94.9% was the fraction of pixels a large enough number
pushes past the threshold; `length(oPos.xyz)` scored 27% for being smaller,
not for being less correct, and I presented two points on a saturation curve
as converging evidence. The tell was in my own output and I read past it: the
change produced 255 distinct colours where the golden has two.

### No unsaturated observation exists

The two suites that would provide one both exclude the mode deliberately.
`fog_tests.cpp:27` has `// FogTests::FOG_GEN_RADIAL,` commented out of its gen
mode list, and `fog_exceptional_value_tests.cpp:98` the same. The test author
tracks these captures as unstable on hardware
(`abaire/nxdk_pgraph_tests#214`, "the radial generator tests change
occasionally on HW"), which is why they were removed.

**So this is closed by the evidence rather than by judgement**: the corpus
cannot determine the value, no capture in it can, and the observation that
would -- a hardware capture of a vertex program with RADIAL and fog params
that do not saturate -- does not exist and cannot be produced without hardware.
Issue #41 reached "do not implement" from a plausibility argument about stale
lighting intermediates; the measurement above reaches the same place without
needing the mechanism to be true.

The reverted behaviour, `oFog.x`, is not "correct" either. It is the safe
default every driver forces, on a combination shipped games do not use, and it
differs from the one hardware sample by a known and bounded amount.

## How much of the board this affects

Scanned every capture on disk with a matched golden and more than 8,000
differing channels, counting the distinct colours the *golden* holds where we
differ. 468 captures; 46 of them have four or fewer.

| suite | captures | channels | what they are |
|---|---:|---:|---|
| `Fog_gen` | 6 | **2,172,192** | `VS radial`, one colour each |
| `Fog_carryover` | 11 | 357,032 | the draw with no fog coordinate |
| `Depth_buffer` | 28 | 270,650 | float Z depth dumps |
| `Fog_coord_vec4` | 1 | 91,710 | `CoordNotSet` |
| **total** | **46** | **2,891,584** | |

Two things worth taking from that.

**It is bounded.** 46 captures of 468, and everything else has hundreds to
tens of thousands of distinct colours in the region we differ in --
`Depth_buffer`'s fixed point captures run to 26,157. The board is not built on
sand; one cell of it is.

**The families are not arbitrary.** Three of the four are the guest declining
to specify a value: radial under a program, `Fog_carryover`'s unset
coordinate, `Fog_coord_vec4`'s `CoordNotSet`. Where the guest does not say,
hardware returns something the test cannot control, and the capture saturates.
That is the same territory as #42, and it means a fix aimed at #42 would be
fitted to saturated observations too -- worth knowing before starting, not
after.

## What to do with these entries

Not "ignore them". Bound them and say so:

- rank them separately, or exclude them from a ranking that drives effort, so
  2.17M channels of clipped output do not outrank a real defect a tenth its
  size;
- state the bound where it is known -- for `VS radial`, coordinate >= 200 on
  every quad, calibrated from `FOG_X` rather than derived;
- record what observation would settle each one, so that if hardware access
  ever appears the experiment is already specified.

And the check that would have saved the afternoon, which costs one line:
**before fitting a model to a capture, count the distinct colours in the
region it differs in.** If it is one, the capture cannot tell you whether you
are right.
