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
