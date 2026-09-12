# Issue #19, measured: it is not a contamination problem

Run overnight 2026-09-11/12 on APK `f9b5a5df2776`, one binary for both arms.
`docs/testing/overnight_19.sh`, verdicts by `night19_report.py`.

## What #19 claimed and what the measurement says

The issue reads "328 of 864 failing tests render another test's image (two
causes)", and that number has hung a caveat over every ranking either lane has
built: if a third of failures are one test rendering another's image, then any
ranking is partly a ranking of contamination. Nobody had separated the two
causes, because by hand it is hundreds of device cycles.

Group `g0`, the 23 smaller suites #19 names, company arm and solo arm on the
same binary:

| | |
|---|---:|
| captures in the company arm | **1,291** (every suite matching its golden count) |
| accused of rendering another test's image | **54** (4.2%) |
| **contamination** — exact when run alone | **2** |
| **missing-state** — as wrong alone | **52** |
| no-run, or binary mismatch | 0 |

**Two.** Not a third of failures and not a contamination problem: 52 of the 54
are tests that are wrong *by themselves*, which means we never implement the
state bit that distinguishes each from the test it reproduces. That is the far
more actionable of the two verdicts, because each one names a feature.

The two genuine contamination cases are `Texture_render_target::TexFmt_A8` and
`TexFmt_A8_L`, both reproducing `TexFmt_DXT1` at error 67.42 in company and
**0.00 alone** — order-dependent, the #6 texture-cache family.

## The 52, and what each group names

| suite | n | renders instead | what the group says we do not implement |
|---|---:|---|---|
| `W_param` | 11 | `ff_w_zero_inf__quad_w-inf` (8) | degenerate W: zero, negative zero, denormals, ±inf all collapse to one behaviour |
| `Blend_surface` | 8 | `DstAlpha_ARGB8` | destination alpha on a surface that **has no alpha channel** |
| `ZMinMaxControl` | 8 | `CtrlFixed_WBuf_ZCLAMP_IgnW` (4) | the NEARFAR clamp mode, and the ignore-W variant |
| `Fog_gen` | 6 | each test's `-planar` sibling | **radial fog distance** — every `-radial` draws its `-planar` twin |
| `Image_blit` | 6 | `ImgBlt_Clip_0_0_640_480` (6/6) | the blit clip rectangle, ignored entirely |
| `Fog_exceptional_value` | 4 | a `NaN-`/`INF-` sibling | INF and NaN fog coordinates |
| `Bump_map` | 4 | `BumpMap_AY8_L` (2) | Y16 and the YUV pair as bump sources |
| `Specular` | 2 | `ControlFlagsLightDisable_VS` | a specular control flag under a vertex shader |
| `Surface_format` | 2 | `Fmt_A8R8G8B8` | the X and X1A7 surface formats' pad bits |
| `Texture_signed_component_tests` | 1 | `txt_A8R8G8B8_ADD` | `FUNC_ADD_SIGNED` — #43, rule already derived |

Three of these are worth calling out because the group is unusually clean:

**`Fog_gen`'s radial fog.** All six `-radial` tests render their `-planar`
sibling with an identical error alone, so the radial distance mode is not
approximated — it is not implemented, and we compute planar for both. `Fog gen`
sits second on the current target ranking at 2.19M non-precision channels, and
this says a named feature accounts for six of its captures outright.

**`Blend_surface`'s destination alpha.** Every one of the eight is a `DstAlpha`
or `1-DstAlpha` factor on an `X`- or `Z`-prefixed surface format, reproducing
the `ARGB8` variant. The surface format table in `vk/constants.h` already
carries `FIXME: Force alpha to zero` and `FIXME: Force alpha to one` on exactly
those rows; this is the measured cost of those two FIXMEs, and it is eight
tests.

**`Image_blit`'s clip rectangle.** Six for six render the unclipped
`ImgBlt_Clip_0_0_640_480`, which is about as unambiguous as this method gets:
the clip parameters reach us and change nothing.

## What this settles for both lanes

The contamination caveat on every ranking is **4.2% of captures accused and
0.15% actually order-dependent**, for these 23 suites. It can be dropped as a
qualifier on target selection. What replaces it is better: a list of ten named
features, several of them small, with the tests that prove each one.

`Depth_buffer` and `Blend_tests` are the remaining groups and are not covered
by the numbers above.

Method note: the value here came from insisting both arms run on one binary
and that every solo run prove itself `[1/1]` in its own progress log. Of the 54
solo runs, 0 failed and 0 came back on a different APK sha — which is only
knowable because the harness records the sha per row and the report refuses
rows that disagree.
