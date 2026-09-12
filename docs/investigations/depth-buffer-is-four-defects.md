# `Depth_buffer` is sixteen cells, eight of them redundant, and four defects

The corpus held 144 of this suite's 784 goldens, the largest partial on the
board. The goldens were captured from a test list that emits 49 depth cutoffs
per cell; the current `nxdk_pgraph_tests` tree emits 9 of those 49, which is
where the 144 came from. Rebuilding the 2025-03-14 tree as `iso_olddepth.iso`
and running `--suite "Depth buffer"` produces all 784, and every one of them
matches a golden by name.

Provenance, because I have twice quoted capture sets without it: captures are
`/tmp/pgraph-run/score_olddepth/olddepth`, written 2026-09-12 13:41 by the
current `build/qemu-system-i386` from `iso_olddepth.iso` built the same hour.
Where the run overlaps the 2026-09-07 sweep it agrees in shape and to within
0.05% on the fixed-point cells (78,047 px against 78,051 on the largest). It
disagrees sharply on float Z, where the sweep has whole-frame failures
(307,168 px) against thousands now -- that is the F16/F24 encoding work landing
since, not a measurement discrepancy.

## Compression is not a variable

Every test runs twice, with Z compression off (`Cn`) and on (`Cy`). Over 196
pairs:

| | golden `Cn` == golden `Cy` | ours `Cn` == ours `Cy` |
|---|---:|---:|
| depth dumps | **196/196** | **196/196** |
| colour frames | 0/196 | 0/196 |

The depth buffers are bit-identical across the compression setting on silicon
*and* here. The colour frames differ by exactly 36 pixels in a 14x7 box at rows
52-65, cols 90-96 -- the one glyph of the printed test name that spells `n`
instead of `y`, in the goldens as much as in our output.

So the suite's 16 cells are 8. Anyone working #16 can halve the space before
starting.

## The eight remaining cells hold four different defects

`Cn` only, since `Cy` is proven identical. `+1` is ours above silicon. The
depth rows count PNG channels of a *packed* word, so a `max` of 255 there is a
byte carry, not a large error -- see defect 2 for the decoded figures.

| format | kind | caps | exact | channels | ours +1 | ours -1 | \|d\|>1 | max |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Z16 fixed | depth | 49 | **49** | **0** | 0 | 0 | 0 | 0 |
| Z24 fixed | depth | 49 | 1 | 155,906 | **146,739** | 7,065 | 2,102 | 255 |
| F16 float | depth | 49 | 0 | 469,927 | 0 | 0 | **469,927** | 255 |
| F24 float | depth | 49 | 1 | 96,736 | 1,915 | 95 | 94,726 | 238 |
| Z16 fixed | colour | 49 | 1 | 1,382,062 | 677,049 | 635,551 | 69,462 | **2** |
| Z24 fixed | colour | 49 | 1 | 1,385,255 | 680,578 | 635,215 | 69,462 | **2** |
| F16 float | colour | 49 | 0 | 858,372 | 372,783 | 425,897 | 59,692 | 128 |
| F24 float | colour | 49 | 1 | 277,604 | 116,280 | 157,376 | 3,948 | 68 |

**1. Z16 fixed depth is already exact.** 49 of 49 captures bit-identical, zero
differing channels. The device lane reported 98/98 on Adreno; this is the same
result on a second rasteriser, which makes it a property of the emulator rather
than of either host.

**2. Z24 fixed depth is one unit, and it is directional.** The table above
counts PNG channels, which flatters and then libels this cell: the `_ZB` dumps
are the raw zeta word saved as ARGB8888, so depth is `A<<16 | R<<8 | G` and
stencil is `B`. A one-unit error that carries across a byte boundary shows up
as a 255 in the channel view. Decoding the word instead:

| | |
|---|---:|
| pixels differing, 49 captures | 154,855 |
| **max \|error\|** | **1 depth unit** |
| ours one *above* silicon | 147,790 (95.44%) |
| ours one *below* | 7,065 (4.56%) |

Never more than one, anywhere, and directional. The device lane's "one unit
high on 96/98" reproduces here with its sign. (The decode checks out against
the geometry: the big quad ramps 12,030,660 at row 100 to 14,826,862 at row
300, and the frame runs 789 to 16,777,215.)

It is also a clean function of the depth cutoff the test writes:

| cutoff | +1 channels | | cutoff | +1 channels |
|---|---:|---|---|---:|
| `0x00000f` | **0** | | `0x800007` | 1,392 |
| `0x10000e` | 89 | | `0xb00004` | 1,408 |
| `0x20000d` | 213 | | `0xc55558` | 3,974 |
| `0x40000b` | 584 | | `0xe55556` | 10,297 |
| `0x600009` | 998 | | `0xffffff` | 16,349 |

Zero at cutoff zero, monotone to the top of the range, in steps rather than a
straight line. That is the shape of a relative error of about one part in 2^24:
invisible at 16 bits, exactly one unit at 24. The Z16 result above is
consistent with it -- the same relative error is a 256th of a unit there and
rounds away.

The scale convention is already deliberate (`glsl/psh.c` around the `z24_open`
ULP nudge, `vk/surface-compute.c` `DEPTH_SCALE`, `PGRAPHState::zeta_stored_as_float`),
and a previous investigation left a comment there costing exactly one unit
*uniformly*. This is not that: it is zero at the bottom of the range and one at
the top. I have not tested a candidate fix, so this paragraph is where the
lead is, not the answer.

**3. Float Z depth is structural, not rounding.** On F16 all 469,927 differing
channels are more than one step -- **not one of them is one-step** -- and the
encoding is a different shape, not a nearby value: ours reads `[0,0,156]`,
`[0,0,205]`, `[0,0,255]` where the golden reads `[16,0,16]`, `[16,0,32]`,
`[16,0,65]`. This has nothing to do with defect 2 and should not be worked as
if it did.

F24 decodes, and says the same thing more sharply. 49,380 pixels differ, only
4.07% of them by one unit, and the rest cluster on a handful of magnitudes that
appear in near-equal positive and negative counts:

| error | pixels | | error | pixels |
|---:|---:|---|---:|---:|
| +12,584 | 10,368 | | -12,584 | 8,640 |
| +787 | 4,913 | | -786 | 4,733 |
| +2,360 | 2,090 | | -2,359 | 2,098 |

Matched pairs of one magnitude are what a boundary in the wrong place looks
like: on one side of it a pixel takes the neighbouring quad's depth and on the
other side the reverse. The magnitudes are quad-to-quad depth steps, not
arithmetic drift. This is a question about which fragment wins, not about how
precisely its depth was computed.

**4. The colour error is not caused by the depth error.** This is the
result I did not expect. In the two fixed-point cells the channels wrong by
more than one are **the same 69,462, in the same places, in all 49
index-paired tests**, and 16 of the 49 pairs have a bit-identical signed
difference -- even though the Z16 depth buffer underneath is bit-perfect and
the Z24 one is not. The whole fixed-point colour error is within 2.

A colour defect that is identical whether the depth buffer beneath it is
correct or one unit high is not downstream of the depth write. It is its own
thing, it is small, and it is the reason the suite reports 1 exact colour
capture in 49 in every cell including the cells where the depth is perfect.

## What the board entry should say

Not "`Depth_buffer`, 340,726 channels". Four entries:

| | size | shape |
|---|---:|---|
| Z16 fixed depth | 0 | **done** |
| Z24 fixed depth | 154,855 px | **exactly** one unit, 95% of it upward |
| Float Z depth | 566,663 ch | structural: a boundary in the wrong place |
| Colour, all cells | 3,903,293 | <=2 in fixed cells, format-independent |

and the compression axis deleted.
