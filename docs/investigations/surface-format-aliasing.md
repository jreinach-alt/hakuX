# The surface reuse test compares a lossy projection of the guest format

Found while triaging #62's reading of `gl/surface.c`. It answers the question
put on #60 -- whether "a reused surface binding keeps its creation-time guest
format" was the wrong mechanism or an incomplete one. **It is incomplete**, and
what completes it is that the predicate authorising reuse is *structurally
unable* to see the difference.

## The two views of a surface's format

A `SurfaceBinding` carries the guest's format twice over:

- `shape.color_format` -- the guest view, an `NV097_SET_SURFACE_FORMAT_COLOR_LE_*`
  value. This is what the conversion paths read.
- `fmt` -- the GL view, a `SurfaceFormatInfo` looked up from
  `kelvin_surface_color_format_gl_map[]`.

`check_surface_compatibility()` decides whether an existing binding may be
reused for a new request. It compares:

```c
(s1->color == s2->color) &&
(s1->fmt.gl_attachment == s2->fmt.gl_attachment) &&
(s1->fmt.gl_internal_format == s2->fmt.gl_internal_format) &&
(s1->pitch == s2->pitch)
```

plus the dimensions. **`shape.color_format` is never compared.** The check is
made entirely on the GL view.

## The guest-to-GL map is many-to-one

That would be harmless if the map were injective. It is not:

| GL internal format | bpp | guest formats mapping to it |
|---|---:|---|
| `GL_RGBA8` | 4 | `X8R8G8B8_Z8R8G8B8`, `X8R8G8B8_O8R8G8B8`, `A8R8G8B8`, `X1A7R8G8B8_Z1A7R8G8B8`, `X1A7R8G8B8_O1A7R8G8B8` |
| `GL_RGB5_A1` | 2 | `X1R5G5B5_Z1R5G5B5`, `X1R5G5B5_O1R5G5B5` |
| `GL_RGB565` | 2 | `R5G6B5` |
| `GL_R8` | 1 | `B8` |
| `GL_RG8` | 2 | `G8B8` |

Every entry carries `GL_COLOR_ATTACHMENT0`, so the attachment discriminates
nothing. **Seven of the ten guest colour formats sit in a group the reuse test
cannot tell apart.**

So a binding created as `X8R8G8B8_Z8R8G8B8` is judged compatible with a later
request for `A8R8G8B8` -- same attachment, same internal format, same pitch --
is reused, and keeps its creation-time `shape.color_format`. Nothing detects
it, because nothing looked.

## Why it lands on the pad bits specifically

**All three Z/O pairs are inside aliased groups**: `X1R5G5B5_Z/O1R5G5B5`,
`X8R8G8B8_Z/O8R8G8B8`, `X1A7R8G8B8_Z/O1A7R8G8B8`. The Z and O spellings differ
only in what the pad bit reads back as -- `O` reads as one -- which is exactly
what `dst_alpha_is_one()` turns on in #48.

So a draw that requests an `O` format and is handed a binding created as `Z`
reads the *creating* draw's pad-bit semantics. That is the same surface the
`X_O1RGB5` captures exercise.

## #62 finding 4 is the same omission, one layer up

`compare_surfaces()` -- the `DO_CMP` list printed when a binding is evicted as
incompatible -- also omits `shape.color_format` and `shape.zeta_format`. It is
diagnostics only and cannot change an output, but it is not merely redundant
with the `fmt.*` fields it does compare: for the seven aliased formats every
compared field matches, so the trace prints nothing that names the difference.

**The trace cannot report the field the compatibility test never checked.**
Those are one omission, not two, and fixing the trace without fixing the
predicate would only make the blindness legible.

## What is not established here

- No capture is attributed to this. It is read from the source, and the
  aliasing is arithmetic on the map rather than a measurement.
- Whether adding `shape.color_format` to the predicate is the right fix is a
  separate question: it would evict bindings that today are reused, and the
  cost of that has not been measured. Some aliased pairs may be genuinely
  interchangeable for a given draw.
- The zeta side has the same shape but only two formats and no known alias.
