# A measured baseline for the audio output

Date: 2026-09-12. Branch `claude/es-de-launcher-disc-error-ojnl14`, rebased at
`7821f995b5`.

Read `audio-assessment.md`, `audio-harness.md` and `audio-headroom-verified.md`
first. Those three establish the signal path, build the PCM tap and the
measurement script, and verify one gain fix. What none of them contains is the
thing the owner's symptom actually needs: **a number for what the output level
is**. The headroom work measured a *shift* between two arms. A shift says the
change did what it claimed; it does not say whether the result is right.

This document is the level itself, and what follows from it.

Claims are tagged the same way as the other three:

- **MEASURED** — from a capture off real hardware, or from reading the cited
  source. Re-checkable.
- **INFERRED** — needs a fact I do not have.

## 1. The baseline

**MEASURED.** Galleon, Retroid Pocket Nova, 92.843 s of captured APU output,
`volume_limit = 1.0`, `use_dsp = false` — so the VP monitor path, which is the
one the handheld is listening to. Capture ref `36bbdd2c84`; its audio code is
byte-identical to the current tip (`git diff 36bbdd2c84 HEAD -- hw/xbox/mcpx/`
is empty), so this measures the shipping path and not a side branch. The
submix-headroom fix is in.

    dispatch/results/1789250713-audio-armA2-2406731/pulled/
        apu_monitor.s16le48k2ch.pcm      17,825,792 bytes

| | L | R |
|---|---:|---:|
| peak (LSB) | 32,767 | 32,767 |
| peak dBFS | −0.00 | −0.00 |
| AC RMS dBFS, whole file | **−23.43** | **−23.50** |
| DC offset (LSB) | −9.44 | +0.50 |
| DC offset dBFS | −70.8 | −96.4 |
| clipped samples | 36 | 16 |
| clipped % | 0.0008 | 0.0004 |
| wrap suspects | 0 | 0 |
| largest adjacent jump | 8,970 | 6,974 |

Per-window AC RMS, 50 ms windows, silent windows excluded (1,677 of 1,857
windows counted):

| percentile | L dBFS | R dBFS |
|---|---:|---:|
| p5 | −38.00 | −38.23 |
| p25 | −32.01 | −32.05 |
| p50 | **−29.37** | **−29.45** |
| p75 | −25.66 | −25.64 |
| p95 | −16.46 | −16.58 |

Conventions, restated because a dBFS figure without them is meaningless: full
scale is 32,768, and RMS dBFS is relative to a full-scale *square* wave, so a
full-scale **sine** reads −3.01 dBFS. Subtract 3.01 from every RMS figure above
to read it sine-referenced, which is what most meters show.

### The zeros are not a dropout

**MEASURED.** The headline "9.78% of samples are exactly zero" decomposes
completely, and benignly:

| component | frames | duration |
|---|---:|---:|
| leading silence before the guest produces audio | 156,128 | 3.253 s |
| one contiguous silent stretch | 276,480 | 5.760 s |
| 1,383 isolated zero runs, 1,363 of them a single frame | ~1,400 | ~0.03 s |

That is the whole of it. The run-length distribution is p50 = 1, p95 = 1,
p99 = 2, max = 276,480 — one long stretch and a scatter of zero crossings. Run
starts are uniform modulo 32 and modulo 256, so nothing is aligned to the
32-sample VP slice or the 256-frame output block; exactly one run of 1,383 has
a length that is a multiple of 32, which is what chance gives. 1,079 blocks are
wholly zero and they are contiguous.

**So there is no periodic APU-side dropout, and the frame-buffer slicing is not
leaving holes.** This is a negative worth recording because "9.78% zeros" reads
alarming and is the first thing anyone will point at. It is silence in the
program material, not a defect. (Analysis: `docs/testing/audio_zero_structure.py`.)

### What this says about the owner's symptom

> "Volume seems unusually low, even when turned up to max, and I do not have any
> hints as to what is causing that."

**MEASURED: the digital output now reaches full scale.** Both channels peak at
32,767 and 52 samples clip. Before the headroom fix the same title peaked at
17,296 / 22,092, i.e. −5.55 / −3.42 dBFS, with 0 clipped samples
(`audio-headroom-verified.md`).

**INFERRED, and this is the load-bearing inference in this document: there is no
uncompensated gain left to recover on this path.** Any further uniform gain
turns into clipping rather than loudness, because the signal is already at the
rails. A second missing power-of-two, of the kind candidate A turned out to be,
would have to hide somewhere that does not touch the peak, and there is no such
place in a chain whose last stage is a clamp to ±1.0.

That is not the same as saying the level is *correct* — accuracy needs a
hardware reference and none exists — but it does close the specific hypothesis
that the symptom is a missing gain stage in the emulated APU.

**What the number does say, and it is the more interesting half:** the crest
factor is 23.4 dB (peak 0 dBFS against −23.43 AC RMS), and the median 50 ms
window sits 29.4 dB below full scale. A mix that peaks at 0 dBFS while
averaging −29 dB *is* quiet most of the time, and that is a faithful rendering
of wide-dynamic-range content, not a bug. If the owner still reports low volume
after the headroom fix, the two remaining explanations are perceptual (the mix
is genuinely wide and the handheld's speaker has no headroom to spare) or
**downstream of the tap** — and there is exactly one unmeasured mechanism
downstream, filed as an issue below.

### The tap cannot see the last stage, and that is where the remaining risk is

**MEASURED, from source.** The capture taps `d->monitor.frame_buf` immediately
before `fifo8_push_all` (`hw/xbox/mcpx/apu/apu.c:321-329`). Everything after
that is the FIFO and `monitor_sink_cb` (`apu.c:376-420`), which on a short read
does this and nothing else (`apu.c:415-417`):

```c
    if (copied < free_b) {
        memset(stream + copied, 0, free_b - copied);
    }
```

Nothing counts it. **A chronic partial fill would reduce loudness at the
speaker by its duty cycle while leaving every number in section 1 unchanged**,
because the capture is taken on the producing side of the FIFO. That is the one
mechanism that survives this baseline and still explains the owner's report, and
it is invisible to the instrument that produced the baseline. See issue below.

## 2. What was predicted before the repeat runs

Stated here, and committed, before the requests were queued. Three captures of
the same title on the same handheld from the same audio code — arm A2 above,
plus two fresh 90 s soaks at `7821f995b5` — should agree if the baseline is a
property of the emulator rather than of one playthrough.

**None of these legs is forced true by anything I changed, because I changed
nothing in the audio path to take them.** The runs are unscripted, the guest is
not deterministic, and the three captures will contain different program
material. The reason to expect agreement is that Galleon's first 90 s from a
cold force-start is a scripted boot-logo-intro sequence, and *that assumption is
precisely what is under test*.

- **R1 — level repeats.** Median active-window AC RMS agrees across all three
  captures to within **±2.0 dB**, and p25 and p75 to within **±2.5 dB**.
  - *Falsified* if any pair differs by more than that on p50. The consequence
    would be severe and is the reason to take this measurement at all: a single
    soak would then not be a measurement of the emulator, and every audio A/B on
    this project — the +6.118 dB headroom result included — would rest on an
    assumption nobody had checked.
- **R2 — the rails are a property of the level, not of one transient.** Peak
  reaches 32,767 on both channels in every run, with a non-zero clipped count
  below 0.01% in each.
  - *Falsified* if a run peaks well below full scale. That would make arm A2's
    clipping a one-off transient rather than a property of the post-fix level,
    and would reopen the "no gain left to recover" inference in section 1.
- **R3 — the int16 accumulator does not wrap.** Zero wrap suspects in every run.
  - *Falsified* by any non-zero count, which would be a defect introduced by the
    headroom fix doubling what is summed into `int16_t` at `vp.c:1887-1888`.
- **R4 — DC stays negligible.** |DC offset| under 0.1% of full scale on both
  channels in every run.
  - *Falsified* by a larger or a growing offset, which would point at a
    truncation bias rather than at program material.

Results are recorded in section 3 when the runs land.

## 3. Repeat-run results

*(Pending. Two soaks queued: Galleon, Nova, 90 s, ref `7821f995b5`.)*

## 4. What this baseline cannot do

Carried forward from `audio-harness.md` section 4, because each still binds:

- It is **not an accuracy oracle**. No golden PCM from real silicon exists.
- A **desktop capture is not comparable**: the Android build substitutes a stub
  libsamplerate that resamples linearly regardless of the requested
  `SRC_SINC_FASTEST`.
- It **cannot see underrun**, per section 1.
- It **cannot measure pacing while it is capturing** — the capture writes on the
  audio thread to FUSE-backed storage.
- It **cannot hear anything**. No perceptual claim follows from any of it.
