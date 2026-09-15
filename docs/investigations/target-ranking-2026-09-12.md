# What to work on next, ranked on numbers rather than on pixel counts

> **CORRECTION 2026-09-12 — the `Texture_render_target` figure in this file is
> the #27 contamination, not a measurement of the suite.**
>
> The 9,034,555-channel / 1-of-41 reading was taken from a capture set with
> `RenderTextureLoop` INCLUDED. That test runs first alphabetically and
> disables the texture stage, so the 40 format tests that never set it up
> render with no stage: each differs by exactly 81,225 px, the whole quad,
> while the loop test itself is pixel-exact. The same figure reproduces to all
> seven digits from such a set. A no-loop set of the same suite on the same
> build gives **752,908 channels, 5 exact**.
>
> This file's own staleness check compared two loop-included sets against each
> other, so they agreed by sharing the contamination.
>
> The "2.8x gap between the lanes" it records is also not a disagreement: one
> lane counted pixels and the other channels on the same captures — 3,209,634
> px and 9,034,555 channels, ratio 2.815.
>
> Do not rank on any number in this file for that suite. See
> `render-to-texture-residual.md`.

Written 2026-09-11 against the remote lane's reclassified corpus
(`run-2026-09-12-corpus-classes.tsv`, 1,444 captures), which subtracts the ±1
population and the boundary-shift band from each suite's differing channels.
Ranking by raw differing pixels put fog and bump maps near the top; they are
much smaller than they looked, and the order below is the one worth working.

| suite | captures | exact | non-precision channels | flat-golden | **ranked on** | dominant class |
|---|---:|---:|---:|---:|---:|---|
| **Blend tests** | 105 | 16 | 6,499,208 | 0 | **6,499,208** | structural (44) |
| Line width | 61 | 1 | 815,888 | 0 | **815,888** | structural (60) |
| Bump map | 38 | 0 | 780,558 | 0 | **780,558** | structural (27) |
| Texture format | 40 | 18 | 720,384 | 0 | **720,384** | exact (18) |
| Bump env lum | 40 | 0 | 657,905 | 5,064 | **652,841** | structural (32) |
| Texture DXT | 15 | 0 | 523,692 | 0 | **523,692** | one-step-lo (8) |
| Specular | 22 | 0 | 495,115 | 0 | **495,115** | structural (20) |
| Texture cubemap | 72 | 6 | 480,346 | 6 | **480,340** | structural (64) |
| Specular back | 17 | 0 | 476,338 | 0 | **476,338** | structural (15) |
| Fog exceptional value | 96 | 12 | 434,704 | 0 | **434,704** | structural (84) |
| Texture render target | 40 | 11 | 308,248 | 0 | **308,248** | boundary-shift (26) |
| Fog carryover | 11 | 0 | 356,144 | 262,144 | **94,000** | structural (11) |
| Fog gen | 60 | 4 | 2,186,712 | 2,172,192 | **14,520** | one-step-sym (43) |

**Updated 2026-09-12 with a flat-golden column, and it reorders the board.**
`flat-golden` is the part of each suite's non-precision channels sitting in
captures whose golden holds exactly **one** colour over the pixels we differ
in. Such a capture scores every wrong model identically, so it is a pass/fail
oracle and its channel count is the size of a region rather than the size of a
defect. Ranking on the remainder moves `Fog gen` from second place to last in
this table -- 2,186,712 to 14,520 -- and `Fog carryover` from twelfth to
below it. Neither is "done"; both are bounded by what the corpus can see, and
`unfalsifiable-goldens.md` has the evidence and the reverted fix that made the
case.

The column comes from `classify_residuals.py`'s `golden_colours` output, joined
in `docs/testing/run-2026-09-12-golden-discrimination.tsv`. Across the corpus
it is 2,464,510 of 15,337,853 channels, 16.1%, in 76 of 1,444 captures.

## What the top row turned out to be, and what it is now

`Blend tests` is not only first, it is first by a factor of three — and four
fifths of its sampled residual was **one bug that has nothing to do with
blending**: a render target sampled as a texture was read in the surface's
channel order instead of the texture's, so R and B came back exchanged.

**Fixed and measured** by the remote lane as `a8f2454a` while this table was
being written: 5,893,287 differing pixels down to 3,562,479, exact 1/105 to
16/105, 79 captures better and none worse, with all fifteen MAX captures
byte-exact — VK_BLEND_OP_MAX was right all along and the channel order was
hiding it. Both lanes reached the same diagnosis and very nearly the same
function independently; theirs carries the measurement, so theirs is what
landed. `surface-as-texture-decode.md`.

**A correction to my own inference.** From 10,026/18,000 on Adreno against
16,625 on lavapipe I read host dependence. That was wrong: the lavapipe number
was taken on a branch that already had the fix, so the two numbers differ by
branch state, not by host. The genuinely host-shaped part is what is left after
the fix — every one of the desktop lane's remaining 1,375 misses is
`|delta| = 1`, where nothing in the Adreno set was off by a single step.
Re-measuring the Adreno arm on one binary is what closes that, and it is the
first thing the fresh `Blend tests` arm is for; the prediction to test is
10,026 + 6,353 = **16,379**, with the residue collapsing to one step.

So this row's remaining 3.56M px is the real target, and 30 of the 105
captures (`SADD`/`SREVSUB`) are #43, whose rule the remote lane has since
closed: the source is read as a signed byte, `signed(S) = S − 256 if S ≥ 128`,
both factors ignored, fitting 3600/3600.

That matters for how this table is read. `Fog gen`'s 2.19M is 43 of 60
captures classified `one-step-sym`, which is a rounding rule; `Line width`'s
816k is 60 of 61 `structural`, which is a missing or wrong rule; and the same
number in two different classes is not the same amount of work. Rank by class
first and size second.

**`Line width` is not the open target it looks like here, and I had it wrong.**
`4ed3a55ea6` landed the register on 2026-09-11 and the width now tracks
silicon to within 4% at every width from 1.25 px up. What is left splits three
ways, none of it a missing rule: the device's own minimum and granularity
below 1.25 px (silicon draws a sub-pixel line as *dashes*, which no line
rasteriser will do), a 3-4% shortfall at every width that is the line ends,
and the colour interpolated along the line. I reached the opposite conclusion
by measuring against a capture set four days older than the fix; the
correction and what is genuinely left are in `line-width-residual.md`.

## Two rows re-measured on Adreno, because this table is not from this lane

Every figure above comes from the remote lane's corpus, which is lavapipe. That
matters for the bump rows: their 6.46M px alpha block in those suites turned
out to be lavapipe's own blend, with alpha byte-identical to silicon on Adreno
across three formats and three capture sets. So the question is whether the
`structural` figures here survive the change of host.

`Bump map` does, measured on the #19 sweep's own fresh arm (APK
`f9b5a5df2776`, 40 captures, correctly dated against the binary):

| | |
|---|---:|
| captures exact | **0 of 40** |
| RGB pixels differing | **435,201** |
| of those, within one step | **0 (0%)** |
| alpha pixels differing | 283,097 |

Zero one-step pixels, so none of it is a precision floor, and for most formats
the RGB and alpha counts are *identical* (35,106/35,106, 22,374/22,374,
3,895/3,895) — the same pixels are wrong in both, which is a whole-texel
disagreement rather than an alpha defect. This row is real work on the host
that ships.

Two of the forty are the YUV pair (`BumpMap_YUY2_L`, `BumpMap_UYVY_L`, 111,496
px each) and predate the YUV decode fix in this tree, so they will move on
their own.

`Bump env lum` is **not yet re-measured here** — it was not in the sweep's
group, and the Adreno captures I have for it are from 09-11, before two fixes
landed. One disc settles it and it should be settled before the row is trusted
in either direction.

## The suites the channel order could also have been carrying: none

The obvious next thought was that every suite sampling a render target through
a different format was exposed to the same fault — `Texture render target` by
definition, plus `Blend surface`, `Surface format` and `Image blit`. It is not
so: a disc of the fourteen surface- and texture-path suites, 236 captures, is
byte-identical either side of the fix, as are the 91 lighting captures that
share the blend disc. `Texture render target` cannot see the defect at all
because its display quad resets the stage to A8R8G8B8, and `Texture format`
cannot because SDL converts the source to whatever is declared. So this was one
suite's bug, and the four rows above keep their own numbers.

## The ordering caveat that outranks all of this

Issue 19 says a third of failing tests render *another test's* image. Until the
isolation sweep has said which captures are affected, every row above is partly
a ranking of contamination rather than of emulator faults — both lanes' rankings
are, including this one. That is why the sweep runs first.
