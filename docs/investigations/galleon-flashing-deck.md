# Galleon's flashing deck texture

Observed 2026-09-11 on a Retroid Pocket Nova, Turnip T30, build `d191c1877c`.
Reported as a long-standing defect and visible in third-party video of this
emulator, so it is not a regression from recent work.

The scene was driven by hand while a capture script took 40 consecutive frames
and injected no input. Evidence in `images/`: `galleon-deck-normal.png` (frame
38), `galleon-deck-flash.png` (frame 39), and the crops in `leftdeck.png` and
`trio.png`.

## What it is

Intermittent, roughly one frame in forty in this scene, and stronger on the
left of the deck than the right. On a flashing frame the deck is brighter and
**loses its smooth mid-distance blend for a hard high-frequency stipple.**

Left-deck crop, same region, consecutive frames:

| frame | mean luminance | local contrast (std) |
|---|---|---|
| 38 | 92.2 | 24.2 |
| **39 (flash)** | **112.9** | **29.4** |
| 40 | 90.1 | 24.2 |

## Why the numbers matter more than the appearance

The first guess from a thumbnail was that a detail or dirt layer drops out,
leaving a lighter base wood. **The contrast figure rules that out.** Losing a
modulating layer would raise the mean and *lower* local contrast, because the
surface would flatten. Here the mean rises by 21 and the contrast rises too,
and the crop shows an aliased crosshatch appearing rather than detail
disappearing.

Brighter, sharper and aliased at mid distance is the signature of **sampling a
level of the mip chain that is too detailed for the distance**: no
minification averaging, so the texture both aliases and reads lighter. The two
candidate causes are mip level selection, and a texture being re-created or
re-uploaded without its full mip chain so only the top level exists until it is
rebuilt.

The second is the more interesting one here, because it would explain the
intermittency directly: a texture re-uploaded on the frame the guest touched it
would flash for exactly as long as it took to repopulate. This emulator polls
the dirty bitmap before every draw and re-binds on any hit, which gives such a
re-upload plenty of opportunities.

It is **not** lighting. A lighting or vertex-colour change brightens without
introducing high-frequency detail.

## Scene diagnostics during the capture

| | |
|---|---|
| guest frame rate | 14 fps, 71-75 ms |
| VBLANKs per flip | 4.3 |
| renderer idle | 46-49 ms of the frame |
| dirty-bitmap queries | ~1,200 per frame |
| slow stores into code pages | ~38,000 per 120 frames, one page taking 25,000 |

Worth recording that Galleon leans on the retranslation loop far harder than
Fuzion Frenzy did, roughly five times the slow-store rate, which is consistent
with it running at 14 fps.

## Revised: it is the stride, not the mip level

The mip reading above is **wrong**, and two pieces of evidence killed it.

First, the report from someone watching it live: the glitched patch cycles
through several different patterns and lighting, then sweeps across to the
right of the screen before the cycle restarts. A mip level cannot do that. A
wrong level gives one consistently wrong appearance, not a sequence.

Second, cropping the same deck patch out of all 40 frames and tiling them
(`images/galleon-deck-cycle.png`) shows what the sequence is: **fine diagonal
hatching, coarse diagonal hatching the other way, smooth plain wood, and a
strong crosshatch weave, in rotation.** The pattern's *direction* changes
between frames.

That direction change is the diagnostic part. Mip selection cannot rotate a
pattern. Reinterpreting the same texture memory with the wrong row stride can,
and does: a stride mismatch shears the image diagonally, and the shear angle
is set by how far wrong the stride is. A stride that differs frame to frame
gives a rotating set of shear angles, and content that walks sideways, which is
exactly the reported sweep to the right.

So the working diagnosis is **the deck texture being sampled with an incorrect
and varying row stride or tiling interpretation.** The candidates, in the order
worth checking:

1. Swizzled versus linear confusion. The NV2A stores most textures swizzled,
   and un-swizzling with the wrong assumption produces precisely this kind of
   diagonal shear.
2. Pitch read from the wrong register, or from a surface's pitch rather than
   the texture's.
3. A colour surface sampled as a texture where the two disagree about pitch.
   Related to, but distinct from, the channel-order case the desktop lane
   fixed in `a8f2454a`; that one swaps colours, this one shears geometry.

Recording the churn honestly: this defect has now had three readings from me.
A dropped detail layer, from thumbnails. A wrong mip level, from luminance and
contrast. And now a stride mismatch, from the pattern rotating. Each revision
came from evidence the previous one could not explain, and the first two were
stated too confidently for what they rested on.

## Stride is ruled out. It is the coordinate side.

Measured 2026-09-11 on the live scene, build `865d829fe2`, logging each
texture stage's format, dimensions, level count, pitch and swizzled flag
whenever any of them changes. 22,493 transitions over about 45 seconds of
deck gameplay.

| | |
|---|---|
| distinct texture addresses | 115 |
| **addresses whose geometry ever changed** | **0** |
| pitch values seen | 0 (swizzled), 512 and 2560 (the 93 linear ones) |
| swizzled vs linear | 22,400 vs 93, never flipping for one address |
| stages in use | 0, 1 and 2, so this is multi-textured |

**Not one of the 115 textures ever changed its format, size, level count,
pitch or swizzled flag.** So the memory is not being reinterpreted at a
varying stride, and the shear cannot be coming from the texture side. The
stride reading is dead, on the same criterion this document set for it before
the measurement: if all five are stable across a flash, the cause is the
coordinate side.

That fits the reported behaviour at least as well. A wrong texture matrix
shears and rotates the sampled pattern, and a matrix left over from a
different material would give a rotating set of wrong appearances as materials
cycle -- "a few different patterns and lighting" -- with content walking
sideways. Three active stages means a detail or light-map stage with its own
generated coordinates is a candidate for carrying stale state.

So the next measurement is the texture matrix and coordinate generation mode
per stage, logged on change in the same way. Worth noting that the texture
matrix data is one of the fields an audit of the threaded-draw snapshot flagged
as uncaptured, which is at least a hint that this state is handled less
carefully than the rest.

### A note on the instrumentation itself

Logging every transition produced about 500 lines a second, which flooded the
logcat ring and **evicted the frame-pacing lines from the same capture** -- 1
survived where a dozen were expected. The geometry answer was unaffected
because it only needed the transitions, but a measurement that destroys the
other measurements in the same window is a bad trade. The next version should
emit a per-frame summary rather than a line per bind.

## Next measurement, not yet done

Log the texture matrix and the coordinate generation mode for each active
stage, on change, and as a per-frame summary rather than a line per bind. If a
stage's matrix or texgen mode differs between a clean frame and a flashing one
for the same material, that is the defect. Three stages are active, so include
which stage.
