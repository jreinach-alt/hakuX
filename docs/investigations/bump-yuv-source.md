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

The bump stage reads those channels as signed offsets, so the RGB formats feed
it **(0, -128)**. The guest converts the same surface to YUY2 for the YUV
tests; BT.601 puts that colour at roughly Y = 87, U = 121. Read as raw bytes
those are **(+87, +121)**.

Through the test's bump matrix (`SetBumpEnv(0.3, 0.0, 0.0, 0.5, ...)`) the two
give displacements of about `(0, -0.5)` and `(+0.21, +0.48)` in texture
coordinates — opposite corners. A displacement that different samples a
different part of the TEX1 checkerboard at every pixel, which is what a
whole-quad difference looks like.

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
