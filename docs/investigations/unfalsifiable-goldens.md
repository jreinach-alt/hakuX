# Where the corpus bounds the hardware value but cannot determine it

> **CORRECTION 2026-09-12 — colour count is a PROXY for saturation, and it has
> a false-negative mode. Two fog entries below are wrongly listed.**
>
> What decides whether a capture can pin a value is not how many distinct
> colours the golden holds, but whether the value sits **interior to the
> transfer function's range** or **at the end of it**. A golden holding a
> single colour still pins the value exactly if that colour is a partial
> *mix* rather than a clip.
>
> `Fog_coord_vec4 CoordNotSet` is the counterexample: **one** colour over
> 30,568 px, and it fixes the fog factor to 1/255. Its final combiner is
> `f*C0 + (1-f)*diffuse` with C0 = (0.5, 0, 0.75) against white diffuse, which
> clips at neither end, so the 8-bit factor inverts straight out of the
> colour -- and exactly one factor in 0..255 reproduces the golden on all
> three channels. `Fog_carryover` is likewise pinning rather than saturated.
>
> **Of the 448,742 fog channels this file calls unfalsifiable, 127,998 are
> pinning evidence.** That is the capture which settled #42, and listing it
> here is what hid the answer.
>
> So: use `golden_colours` to *rank* candidates for suspicion, never to
> exclude a capture. Before discarding one, check whether its transfer
> function clips at the value in question. See #42's note in
> `glsl/vsh.c` and `nv2a_issues.toml`.

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

## Making it machine-readable, and moving the threshold to one

Added 2026-09-12. Everything above was a hand scan. `classify_residuals.py`
now emits a `golden_colours` column per capture -- how many distinct colours
the *golden* holds over the pixels where we differ -- and rolls up, per suite,
the channels sitting in captures where that count is **one**. The join table
for the 1,444-capture corpus is
`docs/testing/run-2026-09-12-golden-discrimination.tsv`, so the existing
ranking can be corrected without re-running anything.

**The threshold is one, not four, and this note's own `<= 4` scan was too
wide.** Two colours is a partition with a boundary in it, and a boundary is a
great deal of information. The counter-example arrived the same day: #51's
`DotSTR3D_0to1` golden holds **two** colours across the whole region we differ
in, and those two colours pinned the hardware rule to four exact texels and a
per-capture count prediction. Under a `<= 4` marker that capture would have
been set aside as unfalsifiable on the morning it was at its most falsifiable.
The line in this note that holds up is the narrow one: *if it is one, the
capture cannot tell you whether you are right.*

**And one colour does not mean stuck.** It means the capture is a **pass/fail
oracle rather than a gradient**: every wrong model scores identically, so it
can confirm a rule and cannot rank candidates. Where the rule comes from
somewhere else, that is plenty. `Image_blit`'s six `ImgBlt_Clip_*` captures
are flat where we differ -- 45,476 channels each of the background colour --
and they are entirely actionable, because the model came from the
unhandled-method log naming class `0x19` with its point and size, not from the
pixels. The marker's instruction is "do not fit here, and do not rank by this
number", never "give up".

### What it is worth across the corpus

On the same column the target ranking uses -- differing channels less the +-1
population less the boundary-shift band -- **2,464,510 of 15,337,853
non-precision channels, 16.1%**, sit in 76 captures whose golden is flat where
we differ. Almost all of it is two suites, and both move a long way down the
board:

| suite | non-precision | flat | **ranked on** | captures | flat |
|---|---:|---:|---:|---:|---:|
| `Blend_tests` | 6,499,208 | 0 | **6,499,208** | 89 | 0 |
| `Fog_gen` | 2,186,712 | 2,172,192 | **14,520** | 56 | **6** |
| `Line_width` | 815,888 | 0 | **815,888** | 60 | 0 |
| `Bump_map` | 780,558 | 0 | **780,558** | 38 | 0 |
| `Texture_format` | 720,384 | 0 | **720,384** | 22 | 0 |
| `Bump_env_lum` | 657,905 | 5,064 | **652,841** | 40 | 7 |
| `Fog_carryover` | 356,144 | 262,144 | **94,000** | 11 | **8** |

`Fog_gen` was the second-largest entry on the board and lands below every
other suite in the top fourteen once its six flat captures are set aside --
a 151-fold correction on one row. That is the distortion this marker exists
to remove.

### What it does to this note's own four families

| family | under `<= 4` | under `== 1` | |
|---|---:|---:|---|
| `Fog_gen` `VS radial` | 6 / 2,172,192 | **6 / 2,172,192** | unchanged; the real case |
| `Fog_carryover` | 11 / 357,032 | **8 / 262,384** | 2 captures hold 2 colours, 1 holds 3 |
| `Depth_buffer` float Z | 28 / 270,650 | **16 / 139,504** | all `z16_*_FZy_*_ZB` |
| `Fog_coord_vec4` `CoordNotSet` | 1 / 91,710 | **0** | holds **2** colours -- comes off the list |

So one of the four families leaves entirely and two shrink. `CoordNotSet` in
particular should be worked, not bounded: a two-colour golden over 91,710
channels is a boundary, and #51 is the demonstration of how much a boundary
can carry.

The `Depth_buffer` row is worth passing on rather than filing: sixteen of the
float-Z depth dumps are flat oracles, so a candidate Z rule cannot be *tuned*
on them, only confirmed. That is a constraint on how that work is measured,
not on whether it can be done.

---

## SECOND CORRECTION 2026-09-12 — the z24 float-depth entry is wrong too

This file has now been found wrong twice, by two different agents, in two
different ways. Both times it had excluded a capture that could in fact pin the
value, and both times that exclusion was hiding an answer.

**The z24 float-depth entry claims 28 captures / 270,650 channels are
unfalsifiable. The F24 cell is fully falsifiable: 0 unfalsifiable pixels.** The
golden holds **57 to 168 distinct depth words** wherever we differ, never one.

The error is in how it was scored, not in the captures. The figure came from
**RGB-only scoring**, which drops the alpha byte — and in a `*_ZB` capture the
depth word is `A<<16 | R<<8 | G`, so dropping A drops the **top byte of the
depth value**. What looked like a golden with almost no distinct values was a
golden being read 8 bits short.

The 16 genuinely flat float-Z goldens listed here are all **z16**. Those stand.

Together with the correction above, the rule for this file is now:

- colour count is a **proxy** with a false-negative mode — a single-colour
  golden still pins a value exactly if that colour is a partial mix rather
  than a clip (`Fog_coord_vec4 CoordNotSet`, which settled #42); and
- a count is only as good as the channels it was computed over — a depth
  capture scored without alpha understates its own discriminating power by a
  whole byte.

**Use this file to rank suspicion. Never to exclude a capture.** Before
discarding one, check both that its transfer function does not clip at the
value in question and that the count was taken over the channels the value
actually lives in.
