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

## Measuring one absent suite immediately produces a top-three entry

Two discs already in this lane cover part of the gap, so the cheap half was
done rather than described. `iso_attr.iso`, one run, 270 captures:

| suite | captures | exact | channels | +-1 | **not +-1** |
|---|---:|---:|---:|---:|---:|
| **`3D_primitive`** | 160 | 4 | 7,287,835 | 6,160,302 | **1,127,533** |
| `Attrib_carryover` | 96 | 0 | 2,923,650 | 2,449,120 | **474,530** |
| `Attrib_float` | 12 | 3 | 610,719 | 523,023 | 87,696 |
| `Attrib_setter` | 2 | 0 | 62,728 | 58,180 | 4,548 |

**`3D_primitive`'s 1,127,533 structural channels would place it third on the
re-ranked board** -- above `Bump_map` at 1,068,453 and `Line_width` at
1,009,664 -- and it was not on the board at all. `Attrib_carryover`'s 474,530
would sit around eighth. One run, no new disc, and the ordering changes.

That is the concrete argument for rebuilding the corpus over the full golden
set: this is not a hypothetical loss of fidelity, it is a top-three item that
nobody could see.

## And the second disc puts a suite straight into second place

`iso_risk.iso`, 898 captures:

| suite | captures | exact | channels | **not +-1** |
|---|---:|---:|---:|---:|
| **`W_buffering`** | 530 | 108 | 7,867,148 | **5,553,462** |
| `Depth_buffer_fixed_function` | 80 | 6 | 981,228 | **340,726** |
| `Texture_shadow_comparator` | 288 | 260 | 26,328 | 26,328 |

**`W_buffering`'s 5,553,462 structural channels rank second on the board**,
below only `Blend_tests` at 6,500,124 and more than double `Fog_gen`'s
2,186,760. It was not on the board at all.

So two discs, both already on disk, have now produced the **second and third**
largest structural entries in the corpus:

| suite | structural channels | previously |
|---|---:|---|
| `Blend_tests` | 6,500,124 | ranked first |
| **`W_buffering`** | **5,553,462** | **invisible** |
| **`3D_primitive`** | **1,127,533** | **invisible** |
| `Bump_map` | 1,068,453 | ranked third |
| `Line_width` | 1,009,664 | ranked fourth |

`Texture_shadow_comparator` is the counter-example worth keeping: 260 of 288
exact and 26,328 channels total. Measuring an absent suite does not always
find work, which is exactly why it has to be measured rather than guessed at.

## A crash worth noting, and not over-claiming

`iso_risk.iso` -- `Texture shadow comparator`, `W buffering` (530 goldens),
`Depth buffer fixed function` (80) -- segfaulted at frame 0 on the first
attempt, 108 log lines, core dumped, no captures. A run of the same disc on
10 September produced 898 captures, so the obvious reading was a regression.

**A second attempt produced 898 captures -- the same count as 10 September.**
The crash is transient, not a reproducible regression, and the obvious reading
was wrong. Recorded because a disc that intermittently dies at startup is worth
knowing about, but not as a regression claim, which is what one run would have
supported and two did not.

A related trap cost a moment here and is now in `AGENTS.md`: `pgrep -c
qemu-system-i386` returns 0 during a live run, because Linux truncates `comm`
to fifteen characters and the process is `qemu-system-i38`. That false negative
reads as "the emulator is free" and invites starting a second one against the
one-at-a-time rule. Use `ps -eo comm= | grep qemu`.

## The sweep: previously-invisible suites hold more structural defect than the whole known corpus

Seven more discs, all already on disk, no builds. Consolidated against the
goldens, structural (non-one-step) channels:

| suite | caps | exact | channels | **not +-1** |
|---|---:|---:|---:|---:|
| **`W_buffering`** | 530 | 108 | 7,867,148 | **5,553,462** |
| **`Blend_surface`** | 32 | 3 | 3,660,115 | **2,951,816** |
| `Clear` | 32 | 25 | 1,399,512 | **1,399,512** |
| **`Texture_signed_component_tests`** | 19 | 9 | 1,475,507 | **1,285,019** |
| `Texgen_with_texture_matrix` | 66 | 30 | 1,200,238 | **1,197,530** |
| `3D_primitive` | 160 | 4 | 7,287,835 | **1,127,533** |
| `Image_blit` | 41 | 12 | 1,413,902 | **898,340** |
| `Depth_buffer_fixed_function` | 160 | 12 | 1,962,456 | **681,452** |
| `Color_zeta_overlap` | 9 | 6 | 784,268 | **632,947** |
| `Surface_format` | 10 | 0 | 520,297 | **475,458** |
| `Attrib_carryover` | 96 | 0 | 2,923,650 | **474,530** |
| `Depth_buffer` (144 of 784) | 144 | 28 | 2,846,110 | **371,928** |
| `Attrib_float` | 12 | 3 | 610,719 | 87,696 |
| `Attrib_setter` | 2 | 0 | 62,728 | 4,548 |
| `Texture_border` | 1 | 0 | 5,564 | 0 |
| **`Surface_clip`** | 47 | **47** | 0 | **0** |
| **`Stencil_func`** | 16 | **16** | 0 | **0** |

**17,141,771 structural channels, from suites that were not in the corpus at
all.** The entire previously-known corpus held 16,621,450. **Measuring what was
already on disk more than doubled the known structural defect population.**

Two entries reorder the top of the board outright: `W_buffering` at 5,553,462
sits second behind `Blend_tests`, and `Blend_surface` at 2,951,816 sits third,
above `Fog_gen`'s 2,186,760. `Texture_signed_component_tests` at 1,285,019 is
#43's own suite, and its 19 captures are a better oracle for the signed-byte
rule than the grid cells it was fitted on.

**And three suites are simply finished.** `Surface_clip` 47/47 exact and
`Stencil_func` 16/16 exact -- both from the sixteen with no scored record
anywhere -- plus `Window_clip` at 92/92. Those are not defects anyone needs to
look at again, and nobody knew.

`Texture_shadow_comparator` at 260/288 exact and 26,328 channels is the
counter-example that keeps the rest honest: measuring an absent suite does not
reliably find work. It has to be measured.

`Depth_buffer` is partial -- this disc runs 144 of its 784 goldens, which is the
subset problem the device lane found from the other direction.
