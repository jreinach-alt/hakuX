# Signed textures: the GL backend never asks the question Vulkan asks

Measured on `5b707602`, OpenGL, the 19 captures in
`/tmp/pgraph-run/score_cx_signed`, scored against
`/tmp/goldens/results/Texture_signed_component_tests`. 1,955,592 differing
channels.

`texture_signed_component_tests.cpp:84-87` names the mask bits: `0x01` is
**signed alpha**, `0x02` red, `0x04` green, `0x08` blue, fed to
`NV097_SET_TEXTURE_FILTER`'s `[ARGB]SIGNED` bits. The suite enumerates all
sixteen combinations plus three blend captures.

## Fifteen of sixteen masks are exact or a one-step floor

| mask | A | R | G | B | differing | mean \|d\| | max |
|---|---|---|---|---|---:|---:|---:|
| 0x0000 | – | – | – | – | **0** | – | 0 |
| 0x0002 | – | R | – | – | **0** | – | 0 |
| 0x0004 | – | – | G | – | **0** | – | 0 |
| 0x0006 | – | R | G | – | **0** | – | 0 |
| 0x0008 | – | – | – | B | **0** | – | 0 |
| 0x000A | – | R | – | B | **0** | – | 0 |
| 0x000C | – | – | G | B | **0** | – | 0 |
| 0x000E | – | R | G | B | **0** | – | 0 |
| 0x0001 | A | – | – | – | 5,748 | 1.00 | 1 |
| 0x0003 | A | R | – | – | 3,844 | 1.00 | 1 |
| 0x0005 | A | – | G | – | 3,812 | 1.00 | 1 |
| 0x0009 | A | – | – | B | 3,840 | 1.00 | 1 |
| 0x0007 | A | R | G | – | 1,908 | 1.00 | 1 |
| 0x000B | A | R | – | B | 1,936 | 1.00 | 1 |
| 0x000D | A | – | G | B | 1,904 | 1.00 | 1 |
| **0x000F** | **A** | **R** | **G** | **B** | **342,060** | **96.37** | **221** |

**Every mask without signed alpha is byte-exact. Every mask with it differs by
exactly one step -- except the all-four case, which is catastrophic.** 0x000F is
93.7% of the entire sixteen-mask residual.

## The control: are those eight exact because we are right, or because the test cannot tell?

A byte-exact capture means nothing if the flag changes no pixels. Comparing each
mask against `0x0000` **in the image area only** (excluding the top 40 rows,
where the test prints the flags into its own label):

| flag | golden moves | ours moves |
|---|---:|---:|
| `0x0001` A | 114,028 | **114,028** |
| `0x0002` R | 79,674 | **79,674** |
| `0x0004` G | 79,849 | **79,849** |
| `0x0008` B | 79,684 | **79,684** |
| `0x000F` ARGB | **114,047** | **51,437** |

Each flag on its own moves about 80,000 channels of real image, and **ours moves
by the identical count**. So per-channel signedness is genuinely reproduced, not
merely undetectable. The label band accounts for only 98-130 channels and was
excluded rather than assumed away.

**At 0x000F the hardware moves 114,047 and we move 51,437 -- we under-react by
55%.**

## Why: Vulkan asks a question the GL backend does not

`pgraph_color_format_has_signed_variant()` (`texture.c:114`) has exactly **two**
consumers in the tree:

- `vk/texture.c:122`, inside `texture_wants_snorm()`, whose own comment names
  this suite:

  ```c
  /* The sampler can only sign the whole texel.  A partial set of flags
   * is applied per channel in the pixel shader after the fetch instead
   * (Texture_signed_component_tests). */
  return (filter & any_signed) == any_signed &&
         pgraph_color_format_has_signed_variant(color_format);
  ```

- `glsl/psh.c:331`, which applies a **partial** set per channel after the fetch
  (`psh.h:51`, `uint32_t tex_signed[4]`).

So the design is explicit: **all four flags together means sample an SNORM
texture; anything less is fixed up in the shader.** The shader half is shared,
which is why the partial masks work in both backends.

**The GL backend has no SNORM path at all** -- `grep -ri snorm hw/xbox/nv2a/pgraph/gl/`
returns nothing. It uploads unsigned RGBA8 whatever the flags say, so the
all-four case has nothing to reproduce it with, and the per-channel shader
fix-up alone does not get there. That is the 55% shortfall.

### And a warning that is actively misleading

`gl/texture.c:708-711` prints `NV2A_UNIMPLEMENTED` for each of the four signed
flags. **Three of the four are in fact reproduced exactly**, through `psh.c`.
Read literally, that warning would have sent someone looking for four missing
features when only one case is missing. It was nearly what sent *me* the wrong
way -- the measurement said otherwise.

## The other 81% is the signed blend equations again

| capture | differing | share of suite |
|---|---:|---:|
| `txt_A8R8G8B8_SADD` | 732,972 | 37.5% |
| `txt_A8R8G8B8_SREVSUB` | 707,706 | 36.2% |
| `txt_A8R8G8B8_ADD` | 149,862 | 7.7% |

`SADD` and `SREVSUB` are the same `FUNC_ADD_SIGNED` /
`FUNC_REVERSE_SUBTRACT_SIGNED` pair parked in
`blend-tests-is-two-signed-equations.md`, aliased to their unsigned
counterparts in both backends. `txt_A8R8G8B8_ADD` differing at all is **not**
explained by that and is not explained here either -- plain `ADD` was within
+/-2 throughout `Blend_tests`. Unmeasured.

## The +/-1 floor and the 55% shortfall are ONE defect

`vk/texture.c:92-100` documents why the conversion has to happen **in the
sampler, before filtering**:

> the bump maps hold 0x7f and 0x80 in adjacent quadrants, which are neighbouring
> values unsigned but +127 and -128 signed. Interpolating unsigned and
> converting afterwards **saturates to +/-1 at every boundary instead of
> sweeping through zero**.

That is exactly the floor measured above: every mask containing signed alpha
differs by **exactly one step, maximum 1**, on 1,904 to 5,748 channels. The
comment predicts that artefact for a post-fetch conversion, and GL does the
conversion post-fetch.

So this closes a question left open earlier in this document. **The one-step
floor and the all-four shortfall are the same root cause** -- GL applying
signedness after the fetch instead of in the sampler. The floor is that
approach's documented saturation artefact; the 55% shortfall is the same
approach failing outright when there is no partial set to fix up.

## Why GL cannot simply copy the Vulkan fix

`TextureShape` (`texture.h`) carries `cubemap, dimensionality, color_format,
levels, width/height/depth, border, mipmap levels, pitch` -- **and no
signedness**. The GL texture cache is keyed on that shape, and the filter
register is applied afterwards as *sampler* state (`gl/texture.c:546-580`:
min/mag filter, LOD bias). That is correct for filter modes and wrong for
signedness, because signedness needs a **different uploaded image**.

Vulkan solved it structurally: `TextureKey` (`vk/renderer.h:709-720`) embeds
`uint32_t filter`, so, in its own words, *"a texture bound with different
signedness gets its own cache entry and its own image"*, and `vk/texture.c:612`
picks the SNORM format at upload.

**A GL fix needs the same move** -- the signed bits into the GL texture cache
key -- not a local override at the `glTexImage2D` site. The upload site does
hold `tex_ifmt` in a local that Android already overrides
(`android_prepare_tex_upload`), so the override itself is easy; **the cache key
is the real work**, and without it a texture uploaded unsigned would be reused
for a signed binding.

## Ownership

**`gl/texture.c` is `[lane.remote]`** -- this is the first defect in five suites
whose primary site is a file this lane holds. A GL equivalent of
`texture_wants_snorm()` belongs there.

The format entry it would select, however, lives in `gl/constants.h`, which
`gl/*.c` does not match and which is **not granted**. So the decision is
this lane's and the table is not.

Nothing is edited here.

## Not established

- Whether desktop GL and GLES both offer the needed SNORM internal formats.
  `GL_RGBA8_SNORM` is core in GL 3.1+ and GLES 3.0+, but that is read from the
  specification, not verified against this renderer's context.
- Why `txt_A8R8G8B8_ADD` differs.
- How much of the residual a GL SNORM path would actually remove. The two
  effects share a cause, but "same cause" is not a predicted number, and no arm
  has been run.

`docs/testing/signed_texture_pivot.py` reproduces every table above.
