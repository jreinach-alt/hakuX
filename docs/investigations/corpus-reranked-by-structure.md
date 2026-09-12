# 57% of the corpus is one-step, and one-step can mean "not ours"

Tonight the bump suites' 6.46M px of one-step alpha turned out to be lavapipe's
blend, confirmed on Adreno with zero pixels differing. That was worth doing
again across the whole corpus, because the ranking both lanes work from counts
differing pixels without asking which of them survive a change of host.

Over all 1,444 captures (`run-2026-09-12-corpus-classes.tsv`):

| | channels | share |
|---|---:|---:|
| differing | 39,011,871 | |
| **+-1** | **22,390,421** | **57.4%** |
| not +-1 | 16,621,450 | 42.6% |

A one-step channel is not automatically a host artefact. But every host
artefact found so far has been one-step, and more than half the corpus sits in
that class, so the distinction decides where effort goes.

## Ranked on what is not one-step

| suite | total | +-1 | **not +-1** | captures |
|---|---:|---:|---:|---:|
| `Blend_tests` | 7,660,673 | 1,160,549 | **6,500,124** | 105 |
| `Fog_gen` | 4,666,628 | 2,479,868 | **2,186,760** | 60 |
| `Bump_map` | 1,068,453 | 0 | **1,068,453** | 38 |
| `Line_width` | 2,516,604 | 1,506,940 | **1,009,664** | 61 |
| `Bump_env_lum` | 2,268,382 | 1,520,266 | **748,116** | 40 |
| `Texture_format` | 2,967,977 | 2,247,528 | **720,449** | 40 |
| `Specular` | 945,290 | 398,852 | **546,438** | 22 |
| `Texture_DXT` | 1,566,774 | 1,042,252 | **524,522** | 15 |
| `Specular_back` | 670,458 | 159,201 | **511,257** | 17 |
| `Texture_cubemap` | 484,759 | 209 | **484,550** | 72 |
| `Fog_exceptional_value` | 5,435,524 | 4,980,500 | **455,024** | 96 |
| `Fog_carryover` | 357,032 | 0 | **357,032** | 11 |

Two entries move a long way against a ranking by raw size.
**`Fog_exceptional_value` falls from second-largest to eleventh** — 5.4M
becomes 455k. **`Bump_map` rises to third** on a tenth of that suite's raw
figure, because none of it is one-step. `Texture_format`'s 720,449 also
predates this session's YUV fix, which removed 273,800 px of it.

## The suites worth a single Adreno capture each

These are more than 90% one-step, which is the shape the bump alpha had before
it was shown to be the host's. If any of them behaves the same way, that
quantity leaves the board entirely:

| suite | total | one-step share | captures |
|---|---:|---:|---:|
| `Fog_exceptional_value` | 5,435,524 | 91.6% | 96 |
| `Fog_param` | 1,951,488 | **99.6%** | 54 |
| `Material_alpha` | 1,627,304 | 94.6% | 24 |
| `Lighting_normals` | 179,600 | **99.9%** | 28 |
| `Stipple_tests` | 147,202 | 95.0% | 6 |
| `Fog_vsh` | 98,556 | **99.9%** | 6 |
| `Fog` | 98,220 | **100.0%** | 6 |
| `Vertex_shader_rounding_tests` | 73,610 | 98.0% | 51 |

Together that is **8.8M channels in suites that are almost entirely one-step**,
and `Fog_exceptional_value` and `Fog_param` alone are 6.9M of it. The check is
the one that settled the bump alpha: read the same capture on a real GPU and
see whether the difference is there at all.

This does not claim any of them is host-specific. It says where the question is
worth asking, ordered by what the answer is worth.


## Answered, and mostly not the way I hoped

The device lane priced the ask within minutes of it being posted. Same measure,
different host, from the #19 sweep's fresh arm:

| suite | this lane's +-1 share | Adreno's |
|---|---:|---:|
| `Fog_param` | 99.6% | **99.6%** |
| `Fog_exceptional_value` | 91.6% | **92.6%** |
| `Fog_gen` | 53.1% | **53.1%** |
| `Bump_map` | 0% | **0%** |

**Identical to a tenth of a percent on three of four.** These are not the
bump-alpha case. Two independent hosts agreeing that closely is strong evidence
of a shared precision floor rather than a software-rasteriser artefact, so the
8.8M channels stay on the board: ours to fix or ours to accept, but ours.

The hypothesis was worth testing and it was cheap to test. It was wrong.

## And the top entry is not what it says either

`Blend_tests`' 6,500,124 is not a blend investigation. The device lane
recovered the retired 1,568-test oracle and scored the 1,120 unsigned tests:
**4,480 of 4,480 quads match silicon at their centres** — every equation, every
source and destination factor. The blend arithmetic is exonerated by
measurement rather than by argument.

What fails is the **fifth quad**, which is issued with the first draw's source
colour: our quad 5 equals our own quad 1 on 1,119 of 1,120 tests, and nothing
else is wrong anywhere. Where a test happens to want the same colour twice the
capture is exact. `MIN` and `MAX` ignore the factors and behave identically, so
it sits upstream of blending — a draw-state or draw-queue defect.

So the entry should read: **one draw-state bug plus #43**, not 6.5M px of blend
work.

## Two suites this table does not rank

Measured on Adreno, from the same sweep:

| suite | captures | exact | differing | +-1 share |
|---|---:|---:|---:|---:|
| `W_param` | 110 | 32 | **5,136,387** | 45.2% |
| `Texture_render_target` | 41 | 1 | **3,209,634** | **0.0%** |

`Texture_render_target` at zero percent one-step and one capture exact in
forty-one is a pure structural block larger than anything this table ranks
except `Blend_tests`. This lane's corpus puts it at 563,668 differing channels,
so the two lanes disagree by a factor of six and that gap needs explaining
before either number is used.


## The table's own data is wrong for one suite, and it is the biggest one

`Texture_render_target` is not 563,668 channels. Measured directly on the
current build, 41 captures from `iso_rtt.iso`:

| | |
|---|---:|
| captures exact | **1 of 41** |
| differing channels | **9,034,555** |
| of those +-1 | 14,255 (**0.2%**) |

That is **sixteen times** what the corpus TSV records, and it puts the suite
**first on the structural axis** -- above `Blend_tests`' 6,500,124, which is
itself now known to be one draw-state bug plus #43 rather than blend work.

The error is in the TSV, not in the run. Checking it row by row against direct
reads of current captures:

| suite | TSV total | direct | rows differing |
|---|---:|---:|---|
| `Texture_DXT` | 1,566,774 | 1,566,774 | **none** |
| `Volume_texture` | 655,209 | 655,209 | **none** |
| `Bump_env_lum` | 2,268,382 | 2,268,410 | 2 of 40, 28 channels total |
| `Line_width` | 2,516,604 | 2,516,892 | 54 of 61, 288 channels total |
| `Texture_format` | 2,967,977 | 2,191,677 | 2 of 40 -- this session's YUV fix |
| **`Texture_render_target`** | **563,668** | **9,034,555** | **40 of 40** |

So the file is trustworthy everywhere else: two suites match to the channel,
two differ only by run-to-run noise, and `Texture_format`'s gap is a fix landing
after the file was written. `Texture_render_target` is wrong on every row --
claiming `TexFmt_A1R5G5B5` and `TexFmt_A8` are exact where they differ by
235,980 and 243,675 channels.

It is not a stale-capture problem either, which was my first guess: captures
from two days ago give 9,192,290, so this suite was never near-exact and the
TSV never reflected a real measurement of it.

**Corrected ranking head:**

| suite | structural channels |
|---|---:|
| `Texture_render_target` | **~9,020,000** |
| `Blend_tests` | 6,500,124 (one draw-state bug plus #43) |
| `Fog_gen` | 2,186,760 |
| `Bump_map` | 1,068,453 |

The device lane measures `Texture_render_target` at 3,209,634 on Adreno, also
0.0% one-step. Both are direct measurements and they are 2.8x apart, which is
its own question and has to be settled before either is used as a target size.
