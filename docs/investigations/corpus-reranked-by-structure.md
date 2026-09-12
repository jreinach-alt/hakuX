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

What fails is confined to the **fifth quad**. On pixel counts and bounding
boxes rather than samples: 847 captures differ on exactly 16,384 px, the region
measures 256 x 64 — one quad — and **no capture differs anywhere else in the
frame**.

The mechanism first offered for it, that the fifth draw carries the first
draw's source colour, has been **retracted upstream** (`b4ed1aa4b3`). It was
measured by sampling one pixel per quad at row 240; the quads are not flat, so
that row never measured "the quad's colour". Compared as whole regions, our
fifth quad matches our own first quad on **0 of 224**.

What the colours suggest, labelled as the hypothesis it is: on `1_MAX_1`, where
`MAX` ignores both factors and the answer should be `max(src, dst)`, silicon
has 221 and 48 where we have 192 and 4, the two flat background colours are
shared, and in both pairs we produce the lower value. That is the shape of the
source contributing nothing to the fifth draw — one test's colour inventory,
not yet checked across the suite.

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


## RETRACTED: the table's data was right and I ran the wrong disc

I claimed above that the corpus TSV understates `Texture_render_target` by
sixteen times, and posted that as a data-integrity failure in a file both lanes
rank from. **It is wrong. The TSV is correct and the error was mine.**

Two discs in this lane enable only "Texture render target":

| disc | captures | exact | channels | +-1 share |
|---|---:|---:|---:|---:|
| **`iso_rt4.iso`** | 40 | **11** | **563,668** | 45.2% |
| `iso_rtt.iso` | 41 | 1 | 9,034,555 | 0.2% |

`iso_rt4.iso` is the suite's disc and reproduces the TSV **to the channel**.
`iso_rtt.iso` is an isolation disc left over from the 10 September
render-to-texture investigation. I picked it by name without checking which one
the corpus run used, measured 9,034,555, and concluded the file was broken.

The ranking head stands as it was: `Blend_tests` first at 6,500,124 -- itself
one draw-state bug plus #43 -- and `Texture_render_target` at 563,668, roughly
where the table already had it. Nothing about the board changes.

This is the second time tonight I have taken capture directories by name
without establishing their provenance, after doing it with two-day-old `rtt_*`
dirs an hour earlier. Both times the numbers were confidently wrong and both
times the fix was one command. **The rule that would have caught it: before
quoting a capture set, check which disc and which build produced it.**

## What is actually there: the suite renders black in isolation

The mistake did surface something worth keeping, though it is not a ranking
entry. On `iso_rtt.iso` the render-to-texture result is **a solid 285x285 block
of pure black** at rows 98-382, cols 178-462, in 40 of 41 captures, with every
pixel outside it matching the golden exactly -- 225,975 of 225,975. On
`iso_rt4.iso` the same block carries 65,025 distinct colours and matches gold on
11 captures outright.

Same suite, same build, same goldens; one disc renders the texture and the other
renders nothing. That is state dependence between tests, which is #19's subject,
and it says our render-to-texture needs something an earlier test leaves behind.
Worth a look by whoever owns #19 -- it is a sharper instance than a crossmatch
can find, because the isolated run fails completely rather than rendering some
other test's image.

The device lane measures the same suite at 3,209,634 on Adreno against this
lane's 563,668. Both are now direct measurements of the right disc, so that gap
is real and unexplained -- but it is a factor of six, not the sixteen I claimed,
and it is a question about two hosts rather than about the file.
