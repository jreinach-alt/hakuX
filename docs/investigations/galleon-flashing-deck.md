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

## Next measurement, not yet done

Log each texture's mip level count at upload and at bind, and correlate a
level count of one against the flash frames. If a texture is being bound with
a single level where it previously had a chain, that is the defect and the
re-upload path is where to look. If mip counts are stable, the cause is level
selection and the sampler's LOD state is where to look.
