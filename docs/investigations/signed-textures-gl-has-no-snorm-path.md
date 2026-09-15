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

## Ownership

**`gl/texture.c` is `[lane.remote]`** -- this is the first defect in five suites
whose primary site is a file this lane holds. A GL equivalent of
`texture_wants_snorm()` belongs there.

The format entry it would select, however, lives in `gl/constants.h`, which
`gl/*.c` does not match and which is **not granted**. So the decision is
this lane's and the table is not.

Nothing is edited here.

## Not established

- That an SNORM upload is the right fix for GL rather than an extension of the
  shader path. Vulkan's comment says the sampler can only sign the whole texel;
  whether desktop GL and GLES have the same constraint is unchecked.
- Why `txt_A8R8G8B8_ADD` differs.
- Whether the one-step floor on signed alpha shares a cause with the 0x000F
  shortfall or is separate.

`docs/testing/signed_texture_pivot.py` reproduces every table above.
