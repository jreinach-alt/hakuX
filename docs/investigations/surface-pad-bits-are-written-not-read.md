# The Z/O pad bits are written by the raster, not read by the texture unit (#59 follow-on)

The `X8R8G8B8` O/Z pair that the before/after corpus sweep found -- `Z` to
bit-exact and `O` tripled to 59,183 -- **is not a polarity error.** The polarity
is right. #48's pad readback is a read-side approximation of a write-side rule,
and it is exact on every pixel the GPU rendered and wrong on every pixel it did
not.

Settled offline against the goldens and two existing capture sets. **No device
run was spent.**

## Which path the capture takes: (a), and (b) is refuted for it

Two candidates were live. (a) #59 arm 2's stride-scoped pad readback in
`vk/texture.c`; (b) `check_surface_compatibility()`'s host-format-only reuse
predicate, under which a binding could answer for whichever guest format first
created it.

It is **(a)**, and the ten `Surface_format` captures refute (b) as the carrier
by themselves. The override fires only where two conditions hold, and both are
read off the **current** format through the refreshed `host_fmt`:

| capture | guest bpp | stride vs the 4-byte stage-0 texture | `sampled_pad_alpha` | override fires | moved in the sweep |
|---|---:|---|---|---|---|
| `Fmt_A8R8G8B8` | 4 | match | IDENTITY | no | no |
| `Fmt_B8` | 1 | differs | IDENTITY | no | no |
| `Fmt_G8B8` | 2 | differs | IDENTITY | no | no |
| `Fmt_R5G6B5` | 2 | differs | IDENTITY | no | no |
| `Fmt_X1A7R8G8B8_Z1A7R8G8B8` | 4 | match | IDENTITY | no | no |
| `Fmt_X1A7R8G8B8_O1A7R8G8B8` | 4 | match | IDENTITY | no | no |
| `Fmt_X1R5G5B5_Z1R5G5B5` | 2 | differs | ZERO | no | no |
| `Fmt_X1R5G5B5_O1R5G5B5` | 2 | differs | ONE | no | no |
| **`Fmt_X8R8G8B8_Z8R8G8B8`** | 4 | **match** | **ZERO** | **yes** | **yes** |
| **`Fmt_X8R8G8B8_O8R8G8B8`** | 4 | **match** | **ONE** | **yes** | **yes** |

The test samples its scratch surface through **texture stage 0 as
`LU_IMAGE_A8R8G8B8` at 640x480** (`surface_format_tests.cpp`, the
`render_result` block), so the guest stride the readback is scoped on is 4
whatever the surface format is. That is why the answer is "specific to the
8-bit pad width": the 8-bit pad formats are the only rows where a 4-byte
surface meets that 4-byte texture *and* carry a non-identity pad swizzle. The
2-byte `X1R5G5B5` pair is excluded by the stride filter #59 arm 2 added, and
the 4-byte `X1A7R8G8B8` pair by its deliberate IDENTITY.

**That table is a complete account with no exceptions**, and every condition in
it is a property of the capture's own format. Under (b) the value applied would
be a *stale* one, and the run order -- read from the arm's own
`pgraph_progress_log.txt`, which is name order, not source order -- makes that
predict something sharp:

```
[9/10]  Surface format::Fmt_X8R8G8B8_O8R8G8B8
[10/10] Surface format::Fmt_X8R8G8B8_Z8R8G8B8
```

`_Z8` runs **immediately after** `_O8`, into one 640x480 surface at one address
and pitch, and the two share `VK_FORMAT_B8G8R8A8_UNORM` -- the textbook case for
the host-format-only predicate. If the binding carried its creating draw's pad
semantics, `_Z8` would inherit `ONE` and show `_O8`'s failure: a blacked-out
background and opaque quads. It is **bit-exact**. Whatever the predicate's
alias class permits elsewhere, on this pair it delivered the current format.

So on the Vulkan side `host_fmt` is being refreshed correctly on the reuse path
(`b6239ccb87`, #55) and the plumbing delivered the right format at the right
time. What is wrong is the *model*, not the predicate.

## The model: the pad bits are physically in the surface's memory

The decisive evidence is a difference between two **goldens**, and it needs
nothing of ours at all.

`Surface_format` draws its result twice: the top half with the sampled surface
alpha as coverage, the bottom half with **alpha forced opaque by the combiner**.
A read-side alpha swizzle cannot reach the bottom half, and cannot reach a
colour channel. Yet:

| golden pair | differing px | top half | bottom half |
|---|---:|---:|---:|
| `X1R5G5B5_O` vs `X1R5G5B5_Z` | 32,806 | 16,422 | **16,384** |
| `X1A7R8G8B8_O` vs `_Z` | 32,806 | 32,806 | 0 |
| `X8R8G8B8_O` vs `_Z` | 32,805 | 32,805 | 0 |

The 5551 pair's 16,384 bottom-half pixels differ **in the green channel only,
by exactly +128, with R, B and A bit-identical.** The guest code for the two
tests is the same but for the format register, so those bytes differ because
**the raster wrote them differently**. A 1555 word's pad bit is bit 15 -- the
high bit of the word's second byte -- and two such words are reinterpreted by
the `A8R8G8B8` stage-0 read as one texel whose byte 1 is green. Setting the pad
bit is green `+128`. Exactly that, on exactly 16,384 px, in the half where
alpha is forced.

The 4-byte pairs show 0 bottom-half difference for the same reason read the
other way: there the surface stride equals the texture stride, so the pad byte
lands in the texel's alpha and nowhere else.

`docs/testing/surface_pad_write_side.py` re-derives this from the goldens and
exits non-zero if the read-side model survives -- its failure condition is "the
O and Z goldens agree in the alpha-forced half", which is exactly what a
readback constant predicts. Pointed at the 4-byte pair, whose bottom half
cannot differ under either model, it fails, so it is answering rather than
agreeing. It currently reports **16,384 of 16,384** bottom-half differences as
a clean green `+128`.

So the rule is:

> **The raster writes the format's pad constant into the pad bits: 0 for a `Z`
> suffix, all-ones for an `O` suffix. The texture unit then reads the stored
> bytes plainly.**

Two things already in the tree agree and were not read across:

- `constants.h`'s `X1A7R8G8B8` derivation, `sampled alpha = (X << 7) |
  (stored_alpha >> 1)`, measured over 32,755 invertible px. That is a
  **stored-bits** model with the X bit in place, not a readback constant.
- The test's own documentation: `_Z8` says "no quads should appear in the top
  half", and its golden's top half **is** the bare checkerboard. Nothing forced
  0 on readback; the raster stored 0 and the quads became invisible.

## Why this produced a "swap" that looks like a polarity error

`surface_format_tests.cpp` `memset`s the whole 640x480x4 scratch region from
the CPU, renders **two 128x128 quads** into it, and then samples the whole
640x480 back. So 88% of what is sampled is CPU-written zeros that the raster
never touched.

* A read-side constant is right on the 12% the GPU drew and wrong on the 88% it
  did not.
* For `O` the wrong constant is 1 where the stored byte is 0, so the
  never-rendered background goes opaque black instead of letting the test's
  `0xFF202020`/`0xFF000000` checkerboard through. Measured: **58,159 of the
  59,183 differing pixels are outside the quad rectangles, all of them the one
  transition `(32,32,32,255) -> (0,0,0,255)`** -- a single colour pair, a single
  distinct combination over the whole set.
* Inside the quad rectangles the same change took `O` from **16,382 differing
  to 1,024**, and `Z` from 32,743 to **0**. The readback constant is doing its
  job where it applies.
* `Z` is bit-exact because 0-everywhere and 0-on-written-pixels coincide when
  the unwritten memory is a `memset` to zero. **That is the third time in this
  issue that the `Z` variant has passed by luck** -- #48 recorded it once, #59
  arm 2 again, and here again.

A polarity swap is refuted outright rather than left as an alternative: giving
`Z` the `ONE` swizzle would black out its background *and* make its quads
opaque, where the golden wants both transparent.

## What the write-side rule predicts, simulated from measured pixels

Composite each capture from the arm that has the right answer in each region --
the post-#59 arm inside the two quad rectangles (where a write-side force and
the read-side swizzle agree), the pre-#59 arm outside them (stored bytes) --
and score against the golden:

| capture | `fb4dfafc6d38` | `553cfffc73d3` | write-side simulation |
|---|---:|---:|---:|
| `Fmt_X8R8G8B8_O8R8G8B8` | 16,382 | 59,183 | **0** |
| `Fmt_X8R8G8B8_Z8R8G8B8` | 32,743 | 0 | **0** |

**Both bit-exact, max delta 0 in every channel, residual 0.** Not an estimate:
it is measured pixels scored against the hardware golden.

## The same defect, measured on a capture the readback never reached

`Fmt_X1R5G5B5_{O,Z}1R5G5B5` are byte-identical across the two arms because the
stride filter excludes them -- and they carry the write-side defect in the open,
in the alpha-forced bottom half where only stored bytes can be seen:

| capture | differing | green exactly +128 | green exactly -128 |
|---|---:|---:|---:|
| `Fmt_X1R5G5B5_Z1R5G5B5` | 29,881 | **10,776** | 0 |
| `Fmt_X1R5G5B5_O1R5G5B5` | 16,096 | 0 | **3,681** |

One-directional in both, and in opposite directions: we set the pad bit where a
`Z` surface must clear it and clear it where an `O` surface must set it, because
we store the combiner's alpha instead of the format's constant. Nothing else in
the corpus reads those bytes as colour, which is why this went unseen.

## Where the fix goes, and why it is not in this stream's files

Alpha enters a colour surface's image in four places. Three are in
`vk/surface.c`; the one that matters most is not.

1. **Draws** -- the fragment shader's alpha output. This is the site for the
   quads, and forcing a constant 1 is not expressible in
   `VkPipelineColorBlendAttachmentState`: `result.a = src.a*Fs + dst.a*Fd`
   admits 0 (both factors `ZERO`) but no constant 1, and `VK_BLEND_OP_MIN/MAX`
   ignore the factors. So it needs `glsl/`.
2. **Clears** -- `Blend_surface` clears its surface to `0xFF555555` and then
   samples regions the geometry never covered, so the clear must stamp the pad
   constant too or that suite regresses where #59 arm 2 repaired it.
3. **VRAM uploads** -- must *not* stamp anything. This is the case
   `Surface_format`'s background is, and stamping it is the bug being fixed.
4. **Blits and surface-to-surface copies** -- same rule as uploads.

And the read-side swizzle in `vk/texture.c` comes out in the same change, or
the two corrections stack on the rendered pixels.

`glsl/` and `vk/texture.c` are both outside this stream's file set, so this is
handed over rather than attempted. Landing only the `vk/surface.c` half would
change the clear path with nothing consuming it.

## Must not move, named as a whole suite rather than as the pair being changed

#59 arm 2's guard list was assembled around `X_O1RGB5` because that was the
regression in front of it, and this is what it missed. So:

**Genuinely inert -- no pad bits, or a real alpha channel:**
`Surface_format/Fmt_A8R8G8B8` (0), `Fmt_B8` (16,144), `Fmt_G8B8` (32,552),
`Fmt_R5G6B5` (0). And the whole `Surface_clip` suite at **0**, which #59 took
there from 1,175,741 and which uses no pad format.

**Expected to move, and registering them at today's value would be wrong.** A
write-side force changes the stored bytes, and these read them:

* `Fmt_X1R5G5B5_Z1R5G5B5` (29,881) and `Fmt_X1R5G5B5_O1R5G5B5` (16,096) --
  should shed the 10,776 and 3,681 pad-bit pixels above. Direction only; both
  carry other residual.
* `Blend_surface`'s `X_{O,Z}1RGB5` and `XA_{O,Z}1A7RGB8` rows -- their texture
  stage format matches their surface format, so the sampled alpha should be
  unchanged, but the claim is that they are **inert**, not that they improve,
  and it is a claim to check rather than assume.

**Deliberately out of scope:** `Fmt_X1A7R8G8B8_{Z,O}1A7R8G8B8` (32,743 /
16,383). Their X bit is one bit of a field whose other seven are real data that
we store at 8-bit precision, so forcing the pad bit without the 7-bit
requantisation `constants.h` already measured would be half a fix. Hold them at
today's values.

## The clear stamps it too -- SETTLED, and the instrument was already in the corpus

This section used to read "Least certain point: whether the **clear** stamps
the pad constant on hardware", and proposed inferring it from
`Blend_surface/DstAlpha_X_O1RGB5`, where the answer would have been ambiguous
because that suite draws a full-surface background quad and so has no
clear-only region at all.

The decisive test was one suite away. **`Clear::TestSurfaceFmt` clears a
128x128 surface to each of six clear colours, draws only a 4x4 black centre
mark, and samples the whole surface back** through an `LU_IMAGE_A8B8G8R8`
stage with `SetFinalCombiner1Just(SRC_TEX0, true)` -- alpha taken from TEX0.
So the displayed alpha over the cleared area **is** the pad byte, over an area
the geometry provably never touched, and the two variants' guest code differs
only in the format register.

In the **goldens**:

| golden pair | differing px | what differs |
|---|---:|---|
| `SCF_X8R8G8B8_O8R8G8B8` vs `_Z8R8G8B8` | 98,342 | **RGB bit-identical**, alpha 255 against 0, 16,368 px per clear colour across all six |
| `SCF_X1R5G5B5_O1R5G5B5` vs `_Z1R5G5B5` | 49,274 | every difference exactly **+128** in the byte carrying bit 15 of a 1555 word |

The clear values are arbitrary and the difference is the **same constant for
all six**, which is what refutes the memset reading outright: under it the two
variants hold identical bytes and the goldens would agree.

> **The clear writes the format's pad constant, exactly as the raster does.**

**And our own output already said so, in the open.** Measured on the #59
baseline arm at `23be8223f5` (`1789359225-padwrite59-base-1009294`, thor):

    Clear/SFC_X1R5G5B5_Z1R5G5B5   49,152 px   R and B BIT-IDENTICAL
                                              green 49,152 px at max delta 128
                                              alpha 49,104 px
    Clear/SCF_X1R5G5B5_O1R5G5B5        0 px   bit-exact

`pgraph_get_clear_color()` hands **every** pad format alpha 1.0. That is the O
constant by coincidence -- which is why the O twin is bit-exact and has been
all along -- and the wrong constant for Z, which is the whole of that 49,152.
It is the same green `+128` signature the draw side was derived from, in a
capture no draw reaches.

**A fourth Z-passes-by-luck, and this one is the O passing by luck instead.**
Worth naming because the pattern in this issue has been Z coinciding with the
truth; here it is O.

**The 4-byte pair is not a second instance of this, and the difference is worth
recording.** `Clear/SCF_X8R8G8B8_{Z,O}8R8G8B8` both sit at 81,840 px against
their goldens with **zero differing alpha pixels in either** -- their stride
matches the sampling stage's, so #48's readback swizzle was firing there and
delivering the right alpha for the wrong reason. Their entire residual is RGB,
max delta 158/159/204, an unrelated clear-colour defect. So removing the
readback without fixing the clear makes the **Z** member of that pair worse and
leaves the O member alone, which is exactly the half-done shape this issue has
carried as "two of four would regress eight bit-exact captures".
