# #60's fix is correct, measurably regresses, and the regression is a
# different defect

`check_surface_compatibility()` decides surface reuse on the GL view alone —
`gl_attachment`, `gl_internal_format`, `pitch` — and the guest-to-GL map is
many-to-one, so seven of the ten guest colour formats sit in a group it
cannot tell apart. A binding created as one is handed to a request for
another and keeps its creation-time `shape.color_format`, because the reuse
path is the one place that field was never reassigned. That is #60, and the
mechanism was already established.

What was not established is whether it matters. The issue says it is
latent — "not a live accuracy loss on any scored capture". **It is not
latent, and fixing it makes four captures worse.** Both halves of that are
measurements.

## It is read, 82 times on one disc

A probe recording the requested format on every binding and reporting every
consumer read where the held format differs: **178 stale reuses**, of which
**82 are read by `pgraph_gl_check_surface_to_texture_compatibility()`** —
not Android-gated, and not diagnostics. It decides whether a rendered
surface may be sampled directly as a texture.

All 82 are at `026eb000` against texture format `0x12`
(`LU_IMAGE_A8R8G8B8`):

| held | asked | result today | result on the true format | decides? |
|---|---|---|---|---|
| `7` X1A7R8G8B8_O | `6` X1A7R8G8B8_Z | false | false | no ×48 |
| `4` X8R8G8B8_Z8 | `8` A8R8G8B8 | **false** | **true** | **yes ×30** |
| `5` X8R8G8B8_O8 | `4` X8R8G8B8_Z8 | false | false | no ×2 |
| `2` X1R5G5B5_O | `1` X1R5G5B5_Z | false | false | no ×2 |

Thirty decisions a run are made on a format the surface does not have, and
for those thirty the answer we give is the opposite of the right one.

The Vulkan consumer audit in `b6239ccb` concluded its own `shape` refresh
would be pixel-inert because every vk-side reader of `shape`'s format is
diagnostics. That does not carry over. GL has twelve readers: eight are the
Android pack/unpack conversions, and two are the surface-to-texture tests.

## The fix, and what it costs

Refresh only the format field of the role being updated, from
`pg->surface_shape` rather than from `entry` — `entry->shape` is the
*colour binding's* shape entire on a zeta update, so taking `color_format`
from it there copies a stale value forward, and 10 of the 178 reuses are
exactly that shape.

Measured against the head at `d662ba2b`, over 236 captures, with a runtime
switch so every arm is one build (the off arm is byte-identical to the
head, which is what makes the rest of the table readable):

| arm | moved | verdict |
|---|---|---|
| off | 0 | control |
| zeta refresh only | 0 | inert |
| colour refresh only | **4 worse, 0 better, +31,948 px** | the regression |
| colour refresh, `X8R8G8B8_Z8` bindings only | **the same 4, same px** | it is all one pair |
| refuse the `A8R8G8B8` s2t row, no refresh | 1 better, −2,624 px | see below |
| refresh + refuse | **1 better, 0 worse, −4,672 px** | |

The regressions:

```
Blend_surface::ARGB8_Add_SrcA_1-SrcA     9,547 -> 22,910
Blend_surface::ARGB8_Add_SrcA_DstA      11,521 -> 21,402
Blend_surface::DstAlpha_XA_O1A7RGB8     81,920 -> 90,112
Surface_pitch::Swizzle                  14,848 -> 15,360
```

`DstAlpha_XA_O1A7RGB8` is the legible one: 8,192 pixels that matched the
golden at `#000000` become `#FFFFFF`, and 8,192 more move from `#555555` to
`#6C6C6C` against a golden of `#2A2A2A`. That is the signature of a
destination alpha going from 0 to 1 underneath a blend.

## The regression is a different defect, and it is already there

Restricting the refresh to the one pair that flips an s2t decision
reproduces the whole regression, so the damage is entirely those thirty
decisions taking the fast path. And the control arm settles what that
means: **refusing the `A8R8G8B8` surface-to-texture row in today's
unmodified code is itself an improvement** — `Surface_pitch::Swizzle`
14,848 → 12,224 with nothing else touched.

So the GL surface-to-texture fast path produces worse pixels than its own
guest-memory fallback for `A8R8G8B8`, today, independently of #60. #60's
stale format is currently *hiding* that by refusing the path for the wrong
reason. The alpha signature points at the pad bits being written by the
raster rather than masked — #59's subject — but that is a hypothesis here
and not a measurement.

## So #60 does not land yet

The combination that scores well — refresh the field *and* refuse the
`A8R8G8B8` row — is available and was measured at 1 better and 0 worse. It
is not landed, deliberately. The refusal was chosen after seeing which
capture regressed and disables a path on a guess about why; that is the
shape of an overfitted fix, and the surface-to-texture behaviour deserves
its own root cause rather than a blanket refusal bolted onto an unrelated
correctness fix.

The order is: fix the surface-to-texture path, then land #60's refresh,
which the table above says is then worth −2,048 px on its own.
