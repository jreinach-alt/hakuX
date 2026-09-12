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
