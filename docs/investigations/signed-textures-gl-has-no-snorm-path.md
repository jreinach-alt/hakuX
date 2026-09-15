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

---

# Proposed change, ready to apply — and the one line that needs a grant

Written out rather than applied, because exactly **one line** of it is in a file
this lane does not hold. Nothing here is built or measured yet.

## Verified before proposing

- **`GL_RGBA8_SNORM` is available.** `0x8F97` in `/usr/include/GL/glcorearb.h:1406`
  and in `/usr/include/epoxy/gl_generated.h:5684`, which is what this renderer
  includes via `gloffscreen.h`. That was listed as unverified in the previous
  section; it is now checked.
- **`generate_texture` and `upload_gl_texture` are both `static` inside
  `gl/texture.c`** (`:462`, `:999`), so threading the filter register through
  them touches nothing outside this lane.
- **`filter` is already read in the caller** at `gl/texture.c:700`, four lines
  above the `NV2A_UNIMPLEMENTED` warnings.
- **The cache key needs no new machinery.** It is `memset` to zero
  (`gl/texture.c:866`), hashed with `fast_hash(..., sizeof(key))` (`:877`) and
  compared with `memcmp(..., sizeof(TextureKey))` (`:1480`), so a new field
  participates automatically.

## The one line outside this lane

`hw/xbox/nv2a/pgraph/gl/renderer.h:148`:

```diff
 typedef struct TextureKey {
     TextureShape state;
     hwaddr texture_vram_offset;
     hwaddr texture_length;
     hwaddr palette_vram_offset;
     hwaddr palette_length;
+    uint32_t signed_channels; /* NV_PGRAPH_TEXFILTER0_[ARGB]SIGNED bits */
 } TextureKey;
```

This is the GL renderer's own private header, and `[lane.remote]` holds
`gl/*.c`, which matches no header. Vulkan already carries the equivalent --
`TextureKey` at `vk/renderer.h:716` embeds the whole `uint32_t filter` -- so
this is bringing GL level with a decision already taken on the other backend,
not a new design.

`territory.toml`'s own preamble says the mechanism for this case is a grant:
*"When a finished fix spans two territories, GRANT one lane the other's file
rather than waiting for both to free. Waiting serialises on the slower lane for
no benefit."* Asking rather than editing, and asking for one field rather than
the file.

## The rest, all inside `gl/texture.c`

Helpers, next to the existing format conversion:

```c
/* The sampler has to sign the texel BEFORE filtering. The bump maps hold 0x7f
 * and 0x80 in adjacent quadrants -- neighbouring values unsigned, +127 and -128
 * signed -- so converting after the fetch saturates to +/-1 at every boundary
 * instead of sweeping through zero. That is measurable: every mask containing
 * signed alpha differs from hardware by exactly one step
 * (Texture_signed_component_tests). vk/texture.c:112 takes the same route; a
 * PARTIAL set of flags is still fixed up per channel in glsl/psh.c, which is
 * why only the all-four case needs this.
 */
static const uint32_t kAllSignedChannels =
    NV_PGRAPH_TEXFILTER0_ASIGNED | NV_PGRAPH_TEXFILTER0_RSIGNED |
    NV_PGRAPH_TEXFILTER0_GSIGNED | NV_PGRAPH_TEXFILTER0_BSIGNED;

static bool texture_wants_snorm(uint32_t filter, unsigned int color_format)
{
    return (filter & kAllSignedChannels) == kAllSignedChannels &&
           pgraph_color_format_has_signed_variant(color_format);
}

static GLint gl_internal_format_to_snorm(GLint gl_internal_format)
{
    switch (gl_internal_format) {
    case GL_RGBA8: return GL_RGBA8_SNORM;
    case GL_RG8:   return GL_RG8_SNORM;
    case GL_R8:    return GL_R8_SNORM;
    default:       return 0;   /* leave the format alone */
    }
}
```

Then three edits:

1. **Key** (`:866`): `key.signed_channels = filter & kAllSignedChannels;`
2. **Thread** `filter` into `generate_texture` and `upload_gl_texture` -- both
   static, both called only from within this file.
3. **Upload** (`:1051-1053`): where `tex_ifmt` is already a local that Android
   overrides via `android_prepare_tex_upload`, override it too:

   ```c
   if (texture_wants_snorm(filter, s.color_format)) {
       GLint snorm = gl_internal_format_to_snorm(tex_ifmt);
       if (snorm) {
           tex_ifmt = snorm;
       }
   }
   ```

   Returning 0 and leaving the format alone matters: a format with no SNORM
   counterpart must keep the current behaviour rather than fail, and
   `pgraph_color_format_has_signed_variant()` and this switch are two different
   lists that could disagree.

**`gl/constants.h` is not touched** -- the mapping stays local, which both keeps
it in-lane and avoids claiming the table is complete.

## What it should be measured against

Before building, register a prediction with numbers. The targets from the
baseline above:

- `0x000F` is **342,060** differing channels at mean 96.37. If the SNORM upload
  is the whole story it should fall to roughly the level of its neighbours --
  a few thousand at a one-step floor.
- The **seven ±1-floor masks must not get worse.** They go through the
  per-channel shader path and this change must not touch them; any movement
  there is a regression and means the key change altered bindings it should
  not have.
- The **eight byte-exact masks must stay byte-exact.** That is the sharpest
  regression test in the suite.
- `SADD`/`SREVSUB`/`ADD` (73.7% of the suite) are a different defect and should
  not move at all.

## Risks worth stating

- **An SNORM image reinterprets the same bytes**, so every consumer of that
  binding sees signed data. The per-channel shader fix-up in `glsl/psh.c` must
  not then *also* apply to the all-four case, or the conversion happens twice.
  `psh.c` is not this lane's to read closely, and this is the first thing a
  reviewer should check.
- **Cache pressure.** A texture used both signed and unsigned now occupies two
  entries. The cache is 512 entries (`gl/texture.c:1488`); this test uses one
  texture, a real title might not.
- **Unbuilt and unmeasured.** No arm has been run. Every number above is a
  target, not a result.
