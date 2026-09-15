# The bump stage does not colour-convert a YUV source

`Bump_map`'s RGB residue survives the change of host — the device lane measures
435,201 px on Adreno with 0% within one step and 0 of 40 captures exact — so it
is real work rather than a lavapipe artefact like the alpha above it. On this
lane the same residue is 356,151 px, and **62.6% of it is two captures**:

| capture | px |
|---|---:|
| `BumpMap_YUY2_L` | 111,496 |
| `BumpMap_UYVY_L` | 111,496 |
| `BumpMap_Y16_L` / `_Y16` | 22,416 each |
| `BumpMap_X8R8G8B8_L` / `_X8R8G8B8` | 3,296 each |
| the other 32 captures together | 81,735 |

111,496 px is the whole quad. These two are not slightly wrong; they are
entirely wrong, and they were still entirely wrong after the YUV decode was
made exact (`52defa5b`) — which is what says the decode is not the problem.

## The measurement that locates it

Compare two formats *within the same image set*, which cancels out everything
about the renderer and asks only how differently that set treats YUV:

| | ours | gold |
|---|---:|---:|
| `YUY2_L` vs `A8R8G8B8_L` | 46,282 | **112,110** |
| `YUY2_L` vs `R8B8` | 55,310 | **111,722** |
| `YUY2_L` vs `UYVY_L` | 214 | 214 |

Our YUY2 result sits 46,282 px from our own RGB-format result — the distance
you would expect from a lossy RGB -> YUV -> RGB round trip. Hardware's sits
112,110 px away, the entire quad. **Hardware's YUV bump result has essentially
nothing in common with its own RGB-format result, and ours has a great deal in
common with ours.** That is not a decode precision gap; it is a different
quantity being fed to the bump stage.

(The `YUY2_L` vs `UYVY_L` row is a control: 214 px in both sets, so the two YUV
orderings agree with each other everywhere, in both ours and hardware.)

## What the numbers say is happening

`GenerateBumpMapSurface` fills an `SDL_PIXELFORMAT_RGBA8888` surface with
`colors[(y >= 2) * 2 + (x >= 2)]`, so past the first two rows and columns the
whole texture is one colour. For `Bump_map` that is `0x00804500`, which in
RGBA8888 is R = 0x00, G = 0x80, B = 0x45.

**The offsets come from blue and green, not red and green.**
`append_bump_channel()` is called with component 2 for dS and component 1 for
dT, and its `chan[] = "rgba"` makes those blue and green. So the RGB formats
feed the bump stage **(dS, dT) = (+69, -128)** — blue 0x45, green 0x80 read as
a signed byte. (An earlier revision of this document said `(0, -128)`, reading
red and green. That was wrong.)

The guest converts the same surface to YUY2 for the YUV tests, where BT.601
puts that colour near Y = 87, Cb = 121. A raw two-bytes-per-texel read gives
`(Y0, Cb)` for one texel and `(Y1, Cr)` for the next — values of a completely
different character to `(+69, -128)`, and in particular not one sign-flipped
channel and one small one. Through the test's bump matrix
(`SetBumpEnv(0.3, 0.0, 0.0, 0.5, ...)`) that is the difference between a
displacement of about `(+0.16, -0.5)` and something pointing into a different
quadrant entirely, which samples a different part of the TEX1 checkerboard at
every pixel. That is what a whole-quad difference looks like.

**Which raw byte lands in which channel is not established**, and that is the
gap between this and an implementable rule. Our converter writes R, G, B from
the decode; a hardware path that skips the conversion has two bytes per texel
to place in the channels the bump stage reads, and the goldens have not been
made to say which. Guessing costs a build and a run per variant.

We convert YUY2 to RGB at upload time, unconditionally, in
`pgraph/texture.c:475`. The shader therefore never sees the source bytes. The
hardware texture unit appears to decode YUV for a colour lookup and not for a
bump lookup.

## Status

**This is a hypothesis with a quantified case, not a derived rule.** What is
established: the decode is exact and is not the cause; hardware's YUV bump
output is unrelated to its own RGB-format output while ours is closely related
to ours; and the raw-byte reading predicts a displacement in the right
direction to explain a whole-quad difference. What is not established is the
exact channel mapping hardware uses.

Testing it properly means uploading a YUV texture in raw form when a bump stage
consumes it, which is not a local change: the conversion happens at upload, the
texture cache is keyed without reference to the shader stage that will read it,
and the same texture could in principle be read both ways. That is a design
question, not a patch, and it belongs with the shader-side blending decision
#43 needs rather than being started unasked.

Worth roughly 223k px on this lane, and proportionally more of the 435,201 the
device lane measures.

## Tested, and the obvious channel assignment is wrong

The hypothesis was implemented and measured rather than left as a guess. A
`raw_yuv` flag was added to `TextureShape` — set when the stage after a YUV
texture is `BUMPENVMAP` or `BUMPENVMAP_LUM`, so it keys the cache and the same
texture read both ways gets both decodes — and the converter fed the stage
`(Cr, Y, Cb)` in the R, G, B positions, skipping the matrix but keeping the
channel correspondence.

The flag fired (`CONVERT fmt=0x25 raw_yuv=1`) and the output moved by 52,462 px.
**The error did not change at all: 111,496 px before, 111,496 px after.** Still
entirely wrong, differently wrong. Reverted.

The colours say why, and they are a better clue than anything above:

| | two most common quad colours |
|---|---|
| ours, baseline | `(254, 0, 0)`, `(33, 32, 32)` |
| ours, raw YUV | `(33, 32, 32)`, `(254, 0, 0)` |
| **gold** | **`(16, 84, 16)`, `(72, 255, 18)`** |

Ours is red-dominant under both decodes; hardware's is green-dominant. Both
hypotheses moved the *distribution* between two reds without ever producing a
green, so whatever the bump stage samples on hardware is not a cell our
displacement can reach — the two cells we choose between are not the two cells
hardware chooses between.

So the direction of the hypothesis (the source is not colour-converted) is
untouched by this result, but the channel assignment `(Cr, Y, Cb)` is
eliminated. Five orderings remain, at a build and a run each; the green
dominance is the thing to predict before spending them, not after.

## Sharper: hardware is not outputting TEX1 at all for a YUV bump source

The displacement framing above is wrong, and the goldens say so plainly. The
final combiner for this test is `SetFinalCombiner0Just(SRC_TEX1)`, and TEX1 is
an explicit `A8R8G8B8` checkerboard, identical in every one of the forty
captures — only TEX0's format varies.

So every capture in the suite should show TEX1's two cells. Reading the
goldens' most common colours:

| golden | two quad colours |
|---|---|
| `BumpMap_A8R8G8B8_L` | `(254,0,0)`, `(33,32,32)` |
| `BumpMap_A8Y8` | `(254,0,0)`, `(33,32,32)` |
| `BumpMap_G8B8` | `(254,0,0)`, `(33,32,32)` |
| **`BumpMap_YUY2_L`** | **`(16,84,16)`, `(72,255,18)`** |

`(254,0,0)` and `(33,32,32)` are the TEX1 checkerboard — RGBA8888 `0xFF0000FE`
and `0x7F202122` give cells `(255,0,0)` and `(127,32,33)` — and they are
exactly what we produce, for every format including the YUV pair. Hardware
produces them too, for every format **except** YUV, where it produces greens
that appear nowhere in TEX1.

A wrong displacement can only ever select a different *cell* of TEX1. It cannot
produce a colour TEX1 does not contain. So no bump offset, from any channel
assignment, explains this, which is why feeding the stage `(Cr, Y, Cb)` moved
55,000 px around between the same two reds and improved nothing.

Greens are the colour family of the bump *source* — RGBA8888 `0x007f4500` and
`0x00804500` are `(0,127,69)` and `(0,128,69)` — which is suggestive, though
neither golden colour matches one directly.

**Contamination is ruled out.** Crossmatching this golden against all 1,444
others, the nearest is its own UYVY sibling at 214 px and everything else is
111,496 or more. It is genuine hardware output.

## Revised recommendation

This is two captures in which hardware does something categorically different
from the other thirty-eight, not a rule we are getting slightly wrong. It is
223k px on this lane, but it is peculiar behaviour on a format combination no
title is likely to use, and the device lane reports its own bump RGB residual
moving between builds, so there is nothing stable to fit against yet.

The other thirty-six captures are the better half of this target: we already
match TEX1's colours there, they are worth ~133k px on this lane, and the
device lane measures 435,201 px on Adreno with 0% of it within one step. That
is where the `Bump_map` work should go, and the YUV pair should be set aside
rather than fitted.

## The other thirty-six: a vertical-only sub-pixel displacement error

With the YUV pair set aside, the remaining 133,159 px on this lane are one
shape, and it is measurable to a fraction of a pixel.

Every non-YUV capture has **max |delta| = 221 and zero pixels at |delta| = 1**.
221 is exactly 254 - 33, the gap between the two TEX1 cell colours, so these
are pixels that landed on the wrong side of a checker boundary. Cell selection,
not precision — which is why none of it is one-step.

Whole-pixel alignment is already correct: testing integer shifts from -3 to +3
in both axes, zero shift is the best for every capture. The disagreement is
sub-pixel, and it is one-sided:

| capture | horizontal edge shift | vertical edge shift |
|---|---|---|
| `BumpMap_A8R8G8B8_L` | **0.000 px** over 2,055 edges | +0.083 px over 4,577 |
| `BumpMap_A8` | **0.000 px** over 4,692 edges | +0.082 px over 4,829 |

Horizontal is exact — every edge, every row, no exceptions. Vertical is short
by about a twelfth of a pixel, which shows up as one edge in twelve landing a
pixel out. That asymmetry is the finding: dS comes from blue and dT from green
(`append_bump_channel` components 2 and 1), and the blue path is exact while
the green path is not.

The source colour makes that suggestive. Past the first two rows and columns
the bump texture is `0x00804500`: blue `0x45` = 69, comfortably positive, and
green `0x80` = 128 — **exactly the two's-complement boundary**, the one value
where `/127`, `/128`, `/127.5` and the clamping rules all disagree. The channel
that is exact carries an ordinary value; the channel that is off carries the
boundary value.

I have not converted the 0.083 px into a coefficient. A first attempt through
the quad magnification put the implied dT error near 5e-4, which is an order of
magnitude smaller than the gap between `/127` and `/128`, so either the
magnification assumption or the model is wrong and the number should not be
quoted until it is derived properly rather than estimated.

`Y16` is not this defect. Its vertical shifts run -20 to -33 px and its
horizontal edge counts do not even match the golden's, so it is a separate and
much larger problem worth 44,832 px across its two captures.

### Facts the derivation will need

- **The plain captures read the bump channels unsigned.** `BumpMap_<format>`
  and `_L` go through `Test()`, whose only `SetFilter` call is commented out,
  so stage 0 keeps default filtering and no `BSIGNED`/`GSIGNED`. The signed
  combinations live in a separate function that sweeps `rsigned`/`gsigned`/
  `bsigned`/`asigned` over a 2x2 grid with tent filtering, and produces the
  `_B` and `_R90` names. So the 0.083 px belongs to the **unsigned** path:
  `bump_unsigned(x) = round(x * 255.0) / 255.0`.
- Green `0x80` unsigned is therefore `128/255 = 0.501961`, and with
  `bumpMat[1][1] = 0.5` the vertical displacement is `0.250980` of the
  texture, or 64.25 texels of 256.
- A hardware value of `128/256 = 0.5` exactly would put it at 64.0 texels,
  a quarter-texel away — about 0.34 screen px at this magnification, which is
  four times the 0.083 px actually measured. So that is not the rule either,
  and the remaining error is smaller than any of the obvious /255, /256,
  /127, /128 choices. That is the puzzle to solve, and it is why no
  coefficient is quoted here.

### Correction: the texture is minified, and the mean-shift estimator is unsound

Two errors in my own reasoning above, both found by measuring instead of
assuming.

**The quad minifies the texture.** Measuring the checkerboard period straight
out of the golden — the cell is 8 texels (`GenerateCheckerboardSurface`'s
default) — gives 6.07 px horizontally and 5.51 px vertically, so the
magnification is **0.76 and 0.69**, not the 1.36 I assumed from dividing the
quad's height by the texture size. The 0.083 px is therefore 0.12 texel, not
0.061, and the implied dT error is 9.4e-4 rather than 4.8e-4.

**The estimate is still not trustworthy, for a better reason.** Reading a
sub-pixel offset out of a mean of per-edge shifts only works when the edges'
sub-pixel phases are uniformly distributed. Here the pattern is periodic at
5.5 px, so the phases take a handful of values and repeat; the mean of the
0/1 shifts is not the offset. Any coefficient derived this way, including the
9.4e-4, is an artefact of that distribution as much as of the defect.

So the honest state is narrower than it looked: what is measured is that
**horizontal edges match exactly and vertical edges are displaced in one
direction on about 8% of crossings**. The size of the underlying offset is not
established, and none of `/255`, `/256`, `/127`, `/128` sits at a plausible
distance from it under either magnification.

**Minification is itself a lead worth taking first.** At 0.69 the sampler is
minifying, so filter choice and LOD selection apply, and a bias there would
show up exactly like this — one-sided, sub-pixel, and larger on the axis with
the smaller scale factor (0.69 vertical against 0.76 horizontal, and vertical
is the axis that is wrong). That should be checked before any more effort goes
into the bump channel arithmetic, which is where I had been looking.

## Correction: it is not a sub-pixel shift. It is whole lines on a period of 21.

Everything above about a "vertical sub-pixel displacement" is wrong, and the
mistake was in the instrument rather than the data.

Counting where the wrong pixels actually are, rather than inferring an offset
from edge positions:

| capture | px | rows > 100 px | cols > 100 px | on those lines | scattered |
|---|---:|---|---|---:|---:|
| `BumpMap_A8R8G8B8_L` | 3,296 | 76, 97, 118, 139, 256, 277, 298, 319 | 188, 193, 236, 246, 257, 368, 373, 416, 426, 437 | **3,296** | **0** |
| `BumpMap_A8` | 1,688 | the same eight | none | **1,688** | **0** |
| `BumpMap_G8B8` | 3,296 | the same eight | the same ten | **3,296** | **0** |

**Every wrong pixel is on a whole row or a whole column, and none is anywhere
else.** The rows are identical across formats and spaced **21 px** apart in two
groups of four. Formats differ only in whether they also carry the columns:
`A8` has the eight rows and nothing more at 1,688 px, and the formats at 3,296
add the ten columns.

That is the shape the corpus classifier already reported — "isolated rows on a
period of 21" — and I should have started from it instead of re-deriving.

**Why the earlier measurement misled.** Comparing edge positions row by row and
averaging the 0/1 shifts assumes the defect is spread across rows. Eight wrong
rows out of 338 produce a small non-zero mean, which reads exactly like a
uniform sub-pixel offset and is nothing of the kind. The mean was real; the
interpretation was invented. Combined with the periodic-phase problem already
noted above, that estimator produced two wrong readings in a row and should not
be used on this suite again.

So the open question changes shape entirely. It is not "what coefficient is a
hair off" but "what recurs every 21 px vertically", with a structure that is
format-independent in its rows and format-dependent in its columns. Nothing
about bump channel arithmetic explains a period, and the `bump_signed` /
displacement work above, while correct as description, was aimed at the wrong
question.

### And the source is not uniform across the quad

One more assumption of mine that the test source contradicts. I wrote above
that "past the first two rows and columns the whole texture is one colour",
which is true of the texture and irrelevant to what is sampled. The draw sets
TEX0's coordinates to span **texels 1 to 3** in both axes (`1.0f / w` to
`3.0f / w`, or 1.0 to 3.0 unnormalised for the linear formats), so the quad
samples a 2x2 texel region and straddles the `(x >= 2)` boundary of
`GenerateBumpMapSurface`.

Across that boundary the bump colours are `0x007f4500` and `0x00804500`: blue
is `0x45` throughout, and **green steps 0x7f -> 0x80** — the two sides of the
two's-complement boundary. Through `bump_signed` that is +127/128 = +0.992 on
one side and (128-256)/128 = -1.0 on the other, a full-scale sign flip at the
quad's midline. Testing exactly that transition is evidently the purpose of
the test, and the constant-source reasoning earlier in this document was built
on sand.

It does not by itself explain the period of 21 — the 0x7f/0x80 step is a single
vertical boundary, and the defect is eight horizontal rows plus ten columns —
so this sharpens the question rather than answering it. But any model of this
suite has to start from a source that changes sign across the quad, not a
constant one, and blue being constant at `0x45` while green flips is consistent
with the horizontal axis being exact and the vertical not.
