# Six suites worked end to end, and what each of them actually is

Scope: `Bump map`, `Bump env lum`, `Fog gen`, `Fog carryover`,
`Fog exceptional value`, `Texture cubemap`, measured at the merge HEAD.

The short version: **none of the six carries a landable fix**, and two of them
carry no semantic defect at all. What they do carry is one new cross-suite
defect (the YUV decode), two precisely located ones that resisted a fix, and a
lot of precision floor. Writing that down is the point -- the pixel counts make
these look like the largest targets in the corpus, and they are not.

## `Bump map`: a shared YUV decode plus the tie floor, and no bump defect

38 captures, 0 exact, 356,151 px.

- `BumpMap_UYVY_L` and `BumpMap_YUY2_L` are **111,496 px each, 63% of the suite
  in two files**. Same defect as `Texture format`'s UYVY/YUY2 -- see below.
- The other 36 captures are the boundary-shift precision floor. Direct test:
  **3,294 of 3,296** differing pixels in `BumpMap_A8R8G8B8` equal a golden
  4-neighbour, 1,688 of 1,688 in `BumpMap_A8`, 1,455 of 1,456 in
  `BumpMap_G8B8_R90`. Their differing rows sit on a period of 21.

There is no bump-mapping arithmetic defect here.

## `Bump env lum`: the same two things

40 captures, 0 exact, 1,770,536 px. The two YUV captures are 222,992 of it. Of
the remaining 1.55M, only about 63,000 channels exceed one step -- **96% of the
non-YUV error is +-1**.

## The YUV decode, which is the real find

`convert_yuy2_to_rgb` / `convert_uyvy_to_rgb` in `pgraph/util.h` use the
limited-range BT.601 integer approximation (298, 409, -100, -208, 516, with
Y - 16). Hardware differs, across three suites:

| capture | px |
|---|---|
| `Texture format` `TexFmt_UYVY_L`, `TexFmt_YUY2_L` | 136,900 each |
| `Bump map` `UYVY_L`, `YUY2_L` | 111,496 each |
| `Bump env lum` `UYVY_L`, `YUY2_L` | 111,496 each |

About 720,000 pixels over six captures. In `Texture format` the differing
region is exactly 370 x 370 -- **every pixel of the drawn quad** -- with mean
absolute deltas of 1.33, 2.08, 1.36 per channel and a maximum of 4. The bump
suites amplify the same small difference into different texel lookups, which is
why their deltas are large.

Ruled out: chroma interpolation. The error has no column parity at all
(`x mod 2` splits 68,450 / 68,450, and `mod 3` and `mod 4` are equally flat),
which a reconstruction difference between subsampled chroma pairs could not
produce.

Not derivable from these captures: `Texture format` draws the texture on a
scaled, filtered quad, so our sampled values are filtered blends of converted
texels rather than raw conversions, and an exact fit against a brute-forced
(Y, Cb, Cr) space fails for that reason -- full-range BT.601, the 359/88/183/454
integer form and a truncating variant all explain 0 of the top 400 observed
pairs. **Deriving the coefficients needs an unfiltered 1:1 capture**, which is
the next step and does not exist yet.

## `Fog gen`: radial under a programmable vertex shader

Covered in `signed-blend-equations.md`'s appendix. Six `FogGen_VS-*-radial`
captures at exactly 181,016 px each, hardware renders one constant, a fix
attempt was inert, and the next step is to dump the generated GLSL.

## `Fog carryover`: root cause known, not modellable

11 captures, 0 exact, 100% above one step, 0.9% boundary. `glsl/vsh.c`
initialises `oFog` to a constant every invocation; the test's right-hand quad
uses a program that never writes `oFog`, and hardware retains the previous
program's output register. Reproducing that needs a vertex shader output
register file, which is not something the GLSL path can express.

## `Fog exceptional value`: precision

96 captures, 12 exact, 3.66M px of which **93% is a one-step difference in a
single channel** (blue), the fog blend against hardware's fixed point. The
four fog-gen variants give identical pixel counts within each mode, so that
dimension is inert and there are really about 24 distinct cases.

## `Texture cubemap`: located, and the obvious fix is wrong

72 captures, 6 exact. **`DotSTR3D` is 290,551 of 294,933 px** -- 98.5% of the
suite in six captures -- while every other family sits at 150 to 300 px of tie
noise.

We render eight distinct face colours where hardware renders two, so our STR
vector scatters across the whole cube while hardware's stays coherent.

There is a real inconsistency in the code: `get_sampler_type` handles
`PS_TEXTUREMODES_DOT_STR_CUBE` by checking `state->tex_cubemap[i]` and
returning `samplerCube`, while `PS_TEXTUREMODES_DOT_STR_3D` -- the case
immediately above -- never checks it and falls through to `sampler2D`, because
a cube has `dim == 2`. The emission sites differ the same way. The test binds a
cubemap to that stage and its own comment says the lookup is a cube lookup.

**Making DOT_STR_3D match DOT_STR_CUBE makes it worse**: 294,933 -> 300,559 px,
five of the six captures regress, one improves by 1,009. Measured, then
reverted. So hardware's DOT_STR_3D is not a plain cube lookup with the raw dot
products either, and the inconsistency -- while real -- is not by itself the
defect. Whatever scaling hardware applies to the STR vector before the lookup
is the open question.
