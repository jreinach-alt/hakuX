# What to work on next, ranked on numbers rather than on pixel counts

Written 2026-09-11 against the remote lane's reclassified corpus
(`run-2026-09-12-corpus-classes.tsv`, 1,444 captures), which subtracts the ±1
population and the boundary-shift band from each suite's differing channels.
Ranking by raw differing pixels put fog and bump maps near the top; they are
much smaller than they looked, and the order below is the one worth working.

| suite | captures | exact | non-precision channels | dominant class |
|---|---:|---:|---:|---|
| **Blend tests** | 105 | 16 | **6,499,208** | structural (44) |
| Fog gen | 60 | 4 | 2,186,712 | one-step-sym (43) |
| Line width | 61 | 1 | 815,888 | structural (60) |
| Bump map | 38 | 0 | 780,558 | structural (27) |
| Texture format | 40 | 18 | 720,384 | exact (18) |
| Bump env lum | 40 | 0 | 657,905 | structural (32) |
| Texture DXT | 15 | 0 | 523,692 | one-step-lo (8) |
| Specular | 22 | 0 | 495,115 | structural (20) |
| Texture cubemap | 72 | 6 | 480,346 | structural (64) |
| Specular back | 17 | 0 | 476,338 | structural (15) |
| Fog exceptional value | 96 | 12 | 434,704 | structural (84) |
| Fog carryover | 11 | 0 | 356,144 | structural (11) |
| Texture render target | 40 | 11 | 308,248 | boundary-shift (26) |

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
