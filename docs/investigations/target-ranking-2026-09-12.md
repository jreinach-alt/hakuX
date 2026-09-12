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

## What the top row turned out to be

`Blend tests` is not only first, it is first by a factor of three — and four
fifths of its sampled residual is **one bug that has nothing to do with
blending**: a render target sampled as a texture is read in the surface's
channel order instead of the texture's, so R and B come back exchanged. Filed
as issue 44, fix written, measurement pending. See
`blend-render-target-channel-order.md`.

That matters for how this table is read. `Fog gen`'s 2.19M is 43 of 60
captures classified `one-step-sym`, which is a rounding rule; `Line width`'s
816k is 60 of 61 `structural`, which is a missing or wrong rule; and the same
number in two different classes is not the same amount of work. Rank by class
first and size second.

## The suites issue 44 could also be carrying

Anything that samples a render target through a texture format of a different
channel order is exposed to the same bug, and four of them are in this table:
`Texture render target` (by definition), `Blend surface`, `Surface format`,
`Image blit`. None of them is confirmed yet — the A/B of `apk-chanorder.apk`
against `apk-night.apk` is what will say, and it costs one device run per
suite. Do that before opening any of them as separate work.

## The ordering caveat that outranks all of this

Issue 19 says a third of failing tests render *another test's* image. Until the
isolation sweep has said which captures are affected, every row above is partly
a ranking of contamination rather than of emulator faults — both lanes' rankings
are, including this one. That is why the sweep runs first.
