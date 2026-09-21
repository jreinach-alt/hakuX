# Gap list B, worked against the emulator

The three "behaviour that provably differs" entries in
`nv2a-hardware-gap-list.md` were each measured on the console *and* on a
desktop build of this tree, one single-test disc per case, identical config.

**Two of the three reclassify.** "Our hardware disagrees with the golden" was
the wrong reading for both.

| capture | emulator vs golden | emulator vs **our hardware** | our hardware vs golden | verdict |
|---|---:|---:|---:|---|
| `TexFmt_R6G5B5` | 134,902 px | **identical** | 134,902 px | **the golden is the outlier** |
| `-NaNs_NaNs` | 14,697 px | 14,637 px | **60 px** | **emulator defect** |
| `WBuf24F_FloorQuad_V0_ZB0_ZS1` | 59,888 px | 59,888 px | **identical** | emulator defect, confirmed |
| ” `_ZB` (depth) | **307,200 px** | **307,200 px** | **identical** | every pixel differs |

## `TexFmt_R6G5B5` — the golden, not the console

The emulator and this V1.1 console produce **byte-identical** output, and both
differ from the published golden by 134,902 px (43.9% of the frame).

Two independent implementations agreeing against a reference is evidence about
the reference. The earlier reading — a V1.1-versus-1.0 silicon difference, or a
golden from a different suite build — can now be narrowed: a silicon difference
would not be reproduced by an emulator that models neither revision. **The
golden is stale or came from a different build of the test suite.**

Consequence: any score quoting `Texture_format::TexFmt_R6G5B5` against this
golden is measuring the golden, not the renderer.

## `-NaNs_NaNs` — an emulator defect, not a hardware difference

Our console differs from the golden by **60 px**; the emulator differs from
both by about **14,700 px**. The 60 px is noise beside that.

This was listed as a hardware/golden disagreement. It is not: hardware
essentially agrees with the golden and **the emulator is the outlier** on
signalling-NaN vertex attributes.

Note the neighbouring test is `-NaN to +NaN (quiet)` → `-NaNq_NaNq`. The two
differ only in signalling versus quiet, so a comparison that mixes them looks
plausible and means nothing. The first run of this did exactly that.

## `WBuf24F_FloorQuad_V0_ZB0_ZS1` — #31 confirmed, and quantified

Our hardware is **byte-identical to the golden**, colour and depth. The
emulator differs from both: 59,888 px on colour and **307,200 px on the depth
capture — every pixel in the frame**.

That anchors #31 to this project's own console rather than to a published
golden, and gives the slope-offset defect a figure: the depth buffer is wrong
everywhere, not in a region.

## A trap worth recording: golden filenames are sanitised

`desktop-runs.md` says to take the test name from the goldens directory rather
than from an issue. That is necessary and not sufficient — **the goldens
directory holds sanitised filenames, not test names**:

| golden filename | actual test name |
|---|---|
| `-NaNs_NaNs.png` | `-NaN to +NaN (signalling)` |
| `-NaNq_NaNq.png` | `-NaN to +NaN (quiet)` |
| `-MaxSN_MaxSN.png` | `-Max (subnormal) to +Max (subnormal)` |

A name the XBE does not recognise is ignored silently: the run completes, the
log says `Testing completed normally` with no `Starting` line, and nothing is
captured. That happened here and produced a clean-looking empty run.

**The authoritative source is the progress log of a run that executed the
test.** `grep "^Starting"` gives exact names.

## What produced these

One single-test disc per case via `make_test_iso.py`, run on
`build-desktop/qemu-system-i386` with `DISPLAY=:0` (WSLg), MCPX and flash
configured, each into its own hdd image so runs cannot contaminate each other.
Hardware captures come from the calibration run
(`xbox-calibration-2026-09-20.md`), which is 3,374/3,379 bit-identical to the
goldens overall — so a disagreement on these specific captures is not a
question about the console's general fidelity.
