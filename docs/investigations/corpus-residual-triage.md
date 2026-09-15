# A quarter of the corpus residual cannot tell two wrong models apart

Measured on `5b707602`, **one binary**, OpenGL, 15 discs, 2,941 captures scored
against `/tmp/goldens/results` and classified with
`docs/testing/classify_residuals.py`. 2,640 captures carry a residual across 61
suites.

This extends `surf1-residual-triage.md` from one disc to the corpus, and the
finding holds at that scale.

## The headline

| | channels | share |
|---|---:|---:|
| total differing | 240,506,032 | |
| **flat golden -- cannot discriminate at all** | **56,698,980** | **23.6%** |
| boundary-shift -- documented precision floor | 2,931,082 | 1.2% |
| actionable (structural AND discriminating) | 174,137,753 | 72.4% |

`classify_residuals.py` records `golden_colours` -- how many distinct colours the
golden holds over the pixels where we differ -- and its own header says that
when it is one, "every wrong model scores identically ... its channel count must
never drive a ranking -- the number is the size of a region, not the size of a
defect".

**This is not an artefact of one suite.** `W_buffering` alone is 67.7% of the
corpus residual, so excluding it is the control: **21.4% flat** without it
against 23.6% with. The share barely moves.

## Concentration, which matters before reading any percentage

| rank | suite | channels | share | cumulative |
|---|---|---:|---:|---:|
| 1 | `W_buffering` | 162,886,125 | 67.7% | 67.7% |
| 2 | `Depth_buffer_fixed_function` | 9,187,640 | 3.8% | 71.5% |
| 3 | `Blend_tests` | 7,660,673 | 3.2% | 74.7% |
| 4 | `3D_primitive` | 7,254,492 | 3.0% | 77.7% |
| 5 | `Window_clip` | 6,029,312 | 2.5% | 80.3% |
| 6 | `Fog_exceptional_value` | 5,434,244 | 2.3% | 82.5% |

Six suites are 82.5% of the corpus. Any corpus-wide number is mostly a statement
about `W_buffering`.

## Ranked by what is actionable, not by what is big

| suite | total | actionable | flat golden | boundary |
|---|---:|---:|---:|---:|
| `W_buffering` | 162,886,125 | **122,287,038** | 40,060,984 | 538,103 |
| `Blend_tests` | 7,660,673 | **7,332,519** | 0 | 1,048 |
| `3D_primitive` | 7,254,492 | **6,664,407** | 0 | 590,085 |
| `Depth_buffer_fixed_function` | 9,187,640 | **5,762,100** | 3,315,954 | 76,438 |
| `Fog_exceptional_value` | 5,434,244 | **5,413,908** | 0 | 20,336 |
| `Line_width` | 4,514,611 | **4,462,131** | 0 | 52,480 |
| `Attrib_carryover` | 2,923,650 | **2,457,142** | 0 | 13,731 |
| `Bump_env_lum` | 2,268,410 | **2,120,023** | 88,560 | 90,211 |
| `Blend_surface` | 3,660,115 | **2,084,870** | 1,474,560 | 2,381 |
| `Texture_signed_component_tests` | 1,955,592 | **1,928,760** | 5,748 | 3,840 |
| `Texture_perspective` | 1,427,840 | **1,411,663** | 0 | 16,177 |
| `Material_alpha` | 1,627,304 | **1,394,304** | 766 | 86,120 |

## Suites that are mostly or entirely unable to discriminate

These can say pass or fail and nothing else, over the pixels where we currently
differ. They are **safe to verify against and unsafe to fit to**.


| suite | flat share | channels | captures |
|---|---:|---:|---:|
| `Window_clip` | **100.0%** | 6,029,312 of 6,029,312 | 84 |
| `Texture_shadow_comparator` | **93.4%** | 2,374,614 of 2,541,288 | 58 |
| `Color_zeta_overlap` | **100.0%** | 330,305 of 330,305 | 3 |
| `Fog_carryover` | **73.4%** | 262,624 of 357,848 | 8 |
| `Stencil` | **100.0%** | 90,000 of 90,000 | 2 |
| `Vertex_shader_rounding_tests` | **98.0%** | 72,116 of 73,610 | 3 |
| `2D_Lines` | **100.0%** | 9,371 of 9,371 | 12 |

`Window_clip` is the one to notice: **84 captures, 6,029,312 channels, 100%
flat.** It is the fifth-largest suite in the corpus and it cannot distinguish
between any two wrong models. A ranking by channel count puts real effort there.

`Texture_shadow_comparator` at 93.4% is worth flagging for a different reason --
it has had sustained cross-lane work (#35), and most of its residual is in
regions where the golden is flat.

## The caveat that must travel with this

`golden_colours` is a property of **(golden, our current output)**, not of the
golden alone: it counts colours over the pixels where *this* binary differs. A
different binary differs in different places and would move these numbers. So
"cannot discriminate" means "cannot discriminate between our current output and
the golden", which is exactly the question a ranking asks -- but it is not a
permanent property of the suite, and re-measuring after a large fix is right.

This is also why the single-binary constraint mattered. There are 140 older
`score_*` directories on this box spanning 2.5 days of different binaries;
mixing them would make every number here incoherent. All 15 discs above ran on
`5b707602`.

## Not a defect ranking

The actionable column says where a defect *could* be found, not that one is
there. `Line_width`'s 4.46M, for instance, is the first baseline for a disc that
aborted until this commit and has never been examined at all.

## Reproduce

    python3 docs/testing/classify_residuals.py \
        /tmp/pgraph-run/score_cx_*/*/ /tmp/pgraph-run/score_surfbase/surfbase \
        /tmp/pgraph-run/score_lfix/lfix --goldens /tmp/goldens/results --tsv out.tsv

then bucket by `golden_colours <= 1`, `class == boundary-shift`, and the
remainder.
