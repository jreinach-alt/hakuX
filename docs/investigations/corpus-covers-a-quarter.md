# Every ranking we have is built on a quarter of the oracle

The device lane found that `Blend tests` runs 105 of its 1,673 goldens and
`Depth buffer` 72 of 784. That is not two suites with a problem. Counting the
whole golden set against the corpus both lanes rank from:

| | |
|---|---:|
| golden suites | **100** |
| golden captures | **5,608** |
| suites in `run-2026-09-12-corpus-classes.tsv` | **40** |
| rows in it | **1,444** |
| **coverage** | **25.7%** |

**Sixty suites with goldens are absent from this corpus entirely** -- not
partially measured, not scoring zero: absent from the file, so absent from
every ranking built on it.

**Corrected, and the correction matters.** An earlier revision of this page
said those 4,164 captures "have never been compared against anything". That is
false. The device lane counted it properly: their own tonight's scoring covers
24 suites, so the union of what current rankings actually see is **50 of 100**,
and a further 29 of the 60 appear in the 2026-09-08 full sweep (79 suites) even
though they are not in either current corpus. `W_buffering`, `Shade_model`,
`3D_primitive`, `Depth_buffer` and `W_param` are all in
`docs/investigations/sweeps/` -- measured, then dropped out of the working set.

**Sixteen suites have no scored record in any of the three** (240 golden
entries): `Texgen_with_texture_matrix` 66, `Surface_clip` 47, `Depth_Clamp` 40,
`Clear` 32, `Stencil_func` 16, `Texture_Matrix` 11, `Color_zeta_overlap` 9,
`SetVertexData` 7, `Texture_BRDF` 3, `Depth_function` 2, `Zero_stride` 2, and
five suites of one capture each. Even that is about the *systematic* record:
`v0.4.0-j1`'s notes quote figures for `Surface_clip` and `Clear`, so individual
runs happened outside these files.

The largest:

| suite | goldens |
|---|---:|
| `Depth_buffer` | 784 |
| `W_buffering` | **530** |
| `Shade_model` | **168** |
| `3D_primitive` | **160** |
| `W_param` | 110 |
| `Attrib_carryover` | 96 |
| `Depth_buffer_fixed_function` | **80** |
| `ZPass_pixel_count` | 78 |
| `Texgen_with_texture_matrix` | **66** |
| `Surface_clip` | **47** |
| `Image_blit` | 42 |

Of the 40 suites that *are* measured, five have fewer rows than goldens, and
only one materially: `Blend_tests` at 105 rows against 1,673, which is the gap
the device lane found. The other four are off by one or two.

## Why this went unnoticed

Both lanes rank by differing pixels within the corpus, and a suite that is not
in the corpus has no row, no score, and no place in any ranking. It does not
appear as a zero -- it does not appear. The failure is invisible to every
process built on top of it, which is how a 530-capture suite like
`W_buffering` stays unexamined while we argue about the ordering of items an
order of magnitude smaller.

It also explains an observation from the device lane that had no explanation at
the time: **`W_param`, the largest differing population they measure on Adreno
at 5,136,387 channels, "isn't ranked by your table".** It is not ranked because
it is not in the corpus. The same is true of `Image blit`, where their method
log found the NV clip-rectangle class dropped entirely.

## What it does and does not invalidate

It does not make the measured numbers wrong. `Bump_map`'s 1,068,453 structural
channels are still 1,068,453, and the YUV decode fix still removed 273,800 px.
Every measurement stands.

What it invalidates is **ordering**. "The biggest remaining defect" has been
asserted repeatedly tonight -- by me, most recently -- on a ranking that cannot
see three quarters of the evidence. No claim of the form "X is the largest
remaining target" should be made again until the corpus is rebuilt over the
full golden set.

## The cheap part

Most of the absent suites need only a disc and a run; `docs/testing` already
has `make_test_iso.py` and the scoring harness. The expensive part is not
measurement, it is that nobody knew it was missing.
