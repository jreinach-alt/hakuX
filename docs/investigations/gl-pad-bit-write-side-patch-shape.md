# The GL-side pad-bit fix: exact patch shape, and the one thing not to do

Answers `briefs/158.md` (cloud, analysis only, no device, no code change).
Base `4eb641e7`, merged. Files edited: this one. **Neither `glsl/psh.c` nor
`vk/draw.c` is touched** — they are held by #138 and PR #148 respectively.

#158 measured the gap: GL trails Vulkan by 413,790 px across eleven captures,
where eight days ago the two renderers were byte-identical on ten of them. This
says what the GL-side edit is, site by site, so that whichever of #138 or #148
clears first the fix is a known-shape dispatch rather than fresh investigation.

## The headline: do NOT port the readback column

The obvious move — give `gl/constants.h` a `sampled_pad_alpha` column beside the
Vulkan one — **is wrong, and the Vulkan tree says so in its own words.** That
override is **withdrawn**, not active (`vk/texture.c:1367`):

> `#59. WITHDRAWN, not deleted, once the raster actually stamps the constant
> into memory. This override is a READ-SIDE approximation of a WRITE-SIDE rule.
> It is exactly right while the bytes in memory are wrong, and it becomes a
> second correction stacked on a corrected value the moment psh.c stamps and
> vk/draw.c stops the blend unit overwriting the stamp.`

and it is **actively wrong** in a case the write side fixes (`:1378`): a 1555
surface sampled through an 8888 view reads two 1555 words as one texel, so the
alpha byte is the high byte of the *second word*, not a pad bit at all. Forcing
it to the format's constant substitutes a value for a channel that never held
one.

So Vulkan's current correctness on these captures comes from the **write side**,
and the read-side column survives only as the fallback for a part without
`dualSrcBlend`. **Porting it to GL would port a retired approximation**, and on
the 1555 formats it would be a fresh defect. This is the single most valuable
line in this document, because the column is the first thing a reader reaches
for: it is the visible difference between the two backends' tables.

## What `glsl/psh.c` needs: one term, at three sites

The write side is fully implemented and backend-neutral in substance. What
excludes GL is **one conjunct**, repeated:

| site | current | note |
|---|---|---|
| `psh.c:2000` | `(ps->opts.vulkan && g_dual_src_pad_supported) ?` | declares `layout(location = 0, index = 0/1)` outputs |
| `psh.c:3550` | `if (ps->opts.vulkan && g_dual_src_pad_supported) {` | emits `fragColorSrc1 = fragColor;` then stamps `fragColor.a` |
| `psh.c:3841` | `g_dual_src_pad_supported ? … : PSH_PAD_ALPHA_NONE` | **already backend-neutral** — stages the uniform |

The third site does not mention `opts.vulkan` at all, which is the shape the
other two want. The edit is to replace `ps->opts.vulkan &&` with the capability
the term stands in for, leaving `g_dual_src_pad_supported` as the sole gate at
all three, exactly as the uniform site already does.

`layout(index = 1)` is core GLSL 3.30 (`ARB_blend_func_extended`), and
`common.c:133` emits `#version 400` for desktop GL, so the qualifier is
available there with no extension string. **GLES is the exception and must be
excluded**: `EXT_blend_func_extended` is not core in GLES 3.0, and
`common.c:112-14` emits `#version 300 es` by default. That is the same
desktop-GL-versus-GLES split #72's grant was conditioned on, and the same
failure mode — a shader that does not compile.

## Who sets the flag, and where

`pgraph_glsl_set_dual_src_pad_supported()` is called once, from
`vk/instance.c:978`, after the device feature is known. GL needs the same call
at renderer init, gated on desktop GL with `ARB_blend_func_extended` present and
GLES excluded. `gl/renderer.c:196` already probes with
`epoxy_gl_version() >= 30`, so the idiom exists in the file; the sibling check
is `epoxy_has_gl_extension("GL_ARB_blend_func_extended")`.

Absence is a refusal to enable, never a failure to start (`psh.h:182`). On a
part without it, GL stays exactly as it is today — which is the current,
measured state — so the change cannot regress a part that lacks the feature.

## The blend side

`vk/draw.c` names the SRC1 factors so the blend unit reads the combiner's alpha
from index 1 rather than the stamped index 0. GL's equivalent is
`glBlendFuncSeparate` with `GL_SRC1_ALPHA` / `GL_ONE_MINUS_SRC1_ALPHA`, in
`gl/draw.c`.

**One interaction to get right, and it is already in the file.**
`gl/draw.c:351` folds a known `Ad = 1.0` into the blend factors via
`surface_color_format_dst_alpha_is_one()`, keyed on
`pg->surface_shape.color_format`. With the stamp live, the blend unit no longer
needs that fold for the four stamping formats — the stamped alpha *is* the
value. The Vulkan side's most recent commit here (`77bd2977`, *"the clear's pad
alpha follows the shape, not the last draw"*) is precisely about keeping those
two halves answering from one state. The GL port must decide the same question,
and `gl/draw.c:107` records the fold's one deliberate exclusion —
`X1A7R8G8B8`, whose seven alpha bits are real data — which matters below.

## Is `gl/renderer.h`'s missing `host_fmt` the blocking gap?

**No. It is a consequence of the read-side design, and the write side does not
need it.** `vk/constants.h:449` says to take the readback value from a binding's
`host_fmt` and never from `shape.color_format`, because at *texture-bind* time
the register has been restored to `A8R8G8B8` by the suite
(`RenderToSurfaceEnd`, `nv2astate.cpp:1684`) and an override keyed on the
register would be dead code.

The write side has the opposite timing. It runs at **draw** time, when the
surface in question *is* the current one, and the same comment says so
explicitly: `pg->surface_shape.color_format` *"is the right source for the BLEND
half of #48, where the surface in question IS the current one, and the wrong one
here."* `psh.c:3841` already keys on exactly that register.

So `host_fmt` is a separate gap — real, and the reason GL could never host the
read-side override — but **not blocking this fix**. Recording it that way
matters: a dispatch that starts by adding `host_fmt` to GL's `SurfaceBinding`
would be building the foundation for the approximation this document says not to
port.

## The falsifier, and it bites

The brief asks that the proposed gate be checked against the eleven captures'
formats, and that a gate not covering all of them is a wrong shape.
`pgraph_glsl_surface_pad_alpha_mode()` (`psh.c:236-248`) covers exactly four
formats: `X1R5G5B5_Z` and `X8R8G8B8_Z` to `ZERO`, `X1R5G5B5_O` and
`X8R8G8B8_O` to `ONE`, everything else `NONE`.

| # | capture | surface format | covered? |
|---|---|---|---|
| 1 | `1-DstAlpha_X_O1RGB5` | `X1R5G5B5_O` | yes |
| 2 | `1-DstAlpha_X_ORGB8` | `X8R8G8B8_O` | yes |
| 3 | `DstAlpha_X_O1RGB5` | `X1R5G5B5_O` | yes |
| 4 | `DstAlpha_X_ORGB8` | `X8R8G8B8_O` | yes |
| 5 | `DstAlpha_X_ZRGB8` | `X8R8G8B8_Z` | yes |
| 6 | `Fmt_X8R8G8B8_Z8R8G8B8` | `X8R8G8B8_Z` | yes |
| 7 | `Fmt_X8R8G8B8_O8R8G8B8` | `X8R8G8B8_O` | yes |
| 8 | `Fmt_X1R5G5B5_Z1R5G5B5` | `X1R5G5B5_Z` | yes |
| 9 | `Fmt_X1R5G5B5_O1R5G5B5` | `X1R5G5B5_O` | yes |
| 10 | `Surface_pitch::Swizzle` | n/a | **no — not a pad capture** |
| 11 | `DstAlpha_XA_O1A7RGB8` | `X1A7R8G8B8_O` | **no — excluded by design** |

**Nine of eleven, and the two exclusions are individually correct rather than
gaps in the shape:**

- **`Swizzle` is not in this family at all.** #158's own text says *"every
  capture but `Swizzle` is a pad format"*; it is #87's layout question plus the
  guest/pgraph race, and it entered the eleven because that list was *every
  capture where GL trails*, not *every pad capture*. It must not be counted for
  or against this fix.
- **`X1A7R8G8B8_O` is excluded deliberately, on both backends.** Its seven alpha
  bits are **real data**, so a constant stamp would destroy them —
  `gl/draw.c:107` excludes it from the blend fold for the same reason, and
  `vk/constants.h:437` says the format's readback *"is not a constant and so
  cannot be expressed as a swizzle"*. This is the capture #60 re-measured, and
  its 8,192 px are a **third** mechanism: neither the write-side stamp nor the
  readback column can address it, and no proposal here should claim it.

**So the expected yield is 9 captures and roughly 397,000 px**, not 413,790.
Stating that before anyone registers an arm is the point of the exercise: an
arm predicting all eleven would fail on two captures it was never going to move,
and the failure would read as a broken fix rather than a mis-scoped prediction.

## Summary for dispatch

| question | answer |
|---|---|
| gate `psh.c` needs | drop `ps->opts.vulkan &&` at `:2000` and `:3550`, leaving `g_dual_src_pad_supported` alone as `:3841` already does; exclude GLES |
| new constants-table column? | **no** — the Vulkan column is withdrawn and wrong on 1555; do not port it |
| `gl/renderer.h`'s `host_fmt` | separate gap, **not blocking**; the write side keys on the register at draw time |
| who sets the flag | `gl/renderer.c` at init, desktop GL with `ARB_blend_func_extended`, GLES excluded |
| blend side | `gl/draw.c`, `GL_SRC1_ALPHA` factors, and reconcile with the `:351` fold as `77bd2977` did for Vulkan |
| expected yield | **9 of 11 captures, ~397,000 px**; `Swizzle` and `X1A7R8G8B8_O` are out of scope |

No code change, no PR, no device time, per the brief.
