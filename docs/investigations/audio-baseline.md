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

### The instrument checks out against the one result it already has

Before trusting the numbers above, I re-derived the published headroom result
from the two captures on disk rather than taking it on trust:

```sh
python3 docs/testing/audio_measure.py --compare armB2.pcm armA2.pcm
```

The ten percentile shifts come out +6.17/+6.02, +6.22/+6.17, +5.98/+5.96,
+5.94/+6.20, +6.49/+6.03 — mean **+6.118 dB**, spread **0.55 dB**, exactly what
`audio-headroom-verified.md` reports. The whole-file summary line reads mean
+5.85 with a 3.06 dB spread, and the difference between those two numbers is the
censoring: the post-fix peak is pinned at 32,767, so the peak statistic cannot
show the rest of the gain and drags the summary down. Quoting the summary would
have been wrong, which that write-up also says.

So the tool, the captures and the published claim all agree, and the baseline
below rests on an instrument that reproduces a known answer.

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

## 3. Repeat-run results: the runs did not happen, and the near-miss matters more

Two soaks were queued as described. **Neither produced a capture, because the
PCM tap was not armed on the Nova** — and the first of them came back with a
24 MB PCM anyway, which measured beautifully and was not from that run.

### What came back

| | rep1 `1789274367` | rep2 `1789274376` |
|---|---|---|
| pulled PCM | 24,379,392 bytes | **nothing matched** |
| `hakuX-audiocap` lines in logcat | **0** | **0** |

`hakuX-audiocap` is in the dispatcher's `LOGCAT_SPEC`, and the capture logs one
line at start unconditionally. Zero lines in both runs, and an empty pull in the
second, is conclusive: **the marker file `audio_capture.on` is no longer on the
Nova.** It was there at 15:09 when arm A2 was taken.

### Why rep1's file was not rep1's

rep2 is what proves it, and it proves it cleanly: `soak_title.sh` deletes the
capture from the device after pulling it, so rep1's pull removed whatever was
there. rep2 could not have pulled a stale file even if it wanted to, and it
pulled nothing. The capture is off.

But the arithmetic said so first, and this is the part worth keeping, because
the file was otherwise entirely convincing:

- The capture holds **126.976 s** of audio.
- The app cannot have lived that long. Its first log line is at device time
  `21:43:25.584`; the pull completed at host time `21:45:00.68`, and the device
  clock runs 2.08 s ahead of the host (`logcat.txt` was last written at host
  `21:44:59.778` carrying a device stamp of `21:45:01.859`). Force-stop precedes
  the pull. That bounds the app's life at **about 95 s**.
- 127 s of audio does not come out of 95 s of app.

The file is a leftover from one of **eight Galleon soaks run between 15:51 and
16:48** for an unrelated CPU experiment, none of which asked for a capture and
none of which pulled one (`pull_glob` empty in all eight). Every one of them
armed the capture anyway, because the marker was still lying on the device from
the headroom A/B, and each wrote ~192 KB/s to the SD card for four minutes.

**All eight refs contain the headroom fix** (`git merge-base --is-ancestor
54a00d28fb <ref>` is true for `0bb035d89e`, `ade16fa90c`, `689a1a29b9` and
`7b63484c69`). So the file is a real post-fix Galleon capture on the Nova — just
not one whose run, build or duration can be named.

### What it says anyway, marked for what it is

Because it cannot be dated to a request, **this cannot discharge the R1-R4
prediction**, and that prediction stands unresolved. It is recorded as
corroboration of unknown provenance, not as a repeat:

| statistic | arm A2 (dated) | undated capture | Δ |
|---|---:|---:|---:|
| p50 L / R | −29.37 / −29.45 | −29.32 / −29.38 | 0.05 / 0.07 |
| p25 L / R | −32.01 / −32.05 | −32.02 / −32.07 | 0.01 / 0.02 |
| p75 L / R | −25.66 / −25.64 | −25.96 / −25.66 | 0.30 / 0.02 |
| p5 L / R | −38.00 / −38.23 | −37.96 / −38.04 | 0.04 / 0.19 |
| p95 L / R | −16.46 / −16.58 | −17.74 / −17.40 | 1.28 / 0.82 |
| peak | 32,767 / 32,767 | 32,767 / 32,767 | — |
| clipped | 36 / 16 | 28 / 12 | — |
| wrap suspects | 0 / 0 | 0 / 0 | — |
| DC %FS | −0.029 / +0.002 | −0.015 / +0.005 | — |

Every leg of R1-R4 would pass on these numbers, and the median agrees to
0.05 dB across two independent runs from different builds hours apart. That is
suggestive and it is not a measurement. It is written down so that the next
person does not have to rediscover that the two agree; it is not written down as
the repeat, because a capture that cannot be dated to the run that produced it
is exactly the thing this project has already been burned by.

### The fix, so this cannot recur

The marker being persistent device state is the whole problem, and it failed in
both directions on the same day: present when nobody wanted it (eight runs), and
absent when someone did (these two). Arming is now **per request**:

- `request.sh --audio-capture MB` sets an `audio_capture` field;
- `dispatcher.sh` passes it as `AUDIO_CAPTURE_MB`;
- `soak_title.sh` writes the marker before `am start`, **deletes any existing
  capture first**, verifies the marker read back, and removes the marker in its
  `release()` trap so an interrupted run cannot leave it armed.

Deleting the old capture first is the load-bearing half. A stale PCM that
measures well is indistinguishable from a good measurement; an absent one is an
obvious failure. `request.sh` also refuses `--audio-capture` outright when the
*serving* dispatcher does not implement it, rather than letting the flag be
ignored and the stale file be filed as the answer — the same guard, and the same
reasoning, as the existing `--skip-tests` one.

**This needs the orchestrator to merge and restart the serving dispatcher before
any further capture can be taken.** Until then the immediate unblock is one
command per handheld:

```sh
adb -s ee317437 shell 'echo 30 > /sdcard/Android/data/com.jreinach.hakux.debug/files/audio_capture.on'   # nova
adb -s bdc158a5 shell 'echo 30 > /sdcard/Android/data/com.jreinach.hakux.debug/files/audio_capture.on'   # thor
```

and any capture taken that way must be dated against its run before it is
believed. The arithmetic that catches it is: **captured seconds must not exceed
the app's lifetime**, and `audio_measure.py` prints the first number while the
soak's own timestamps give the second.*

## 4. The starvation measurement, predicted before the run

The capture being unarmed is, for this one question, a gift. The harness
write-up warns that starvation measured *during* a capture describes the capture
run and not a normal one, because the capture writes to FUSE-backed storage from
the audio thread. With the marker gone, a soak now yields the clean figure.

The counters need no marker and no pull — they report through logcat, which the
dispatcher already captures with `hakuX-audiocap:I` in its `LOGCAT_SPEC`.
Queued: Galleon, 120 s, at the commit carrying the counter.

**Two arms, on both handhelds, and the reason is worth recording.** The first
was pinned to the Nova to match the baseline's device. It sat unclaimed: the
Nova worker's last log line is at 21:43 and every request since has been served
by the Thor, so a nova-pinned request waits indefinitely. A second arm was
queued to the Thor rather than unpinning the first, because an unpinned request
would land on whichever device is idle and the result would not record which —
soak results do not carry `device_label`, only disc runs do.

The pin exists to stop a *level* being compared across handhelds. This is not
that: it is a fresh pacing measurement, not a comparison against the Nova
baseline, so either device answers S1-S3. If both arms run, the pair is a free
cross-device check — and worth having, because `devices.sh` is explicit that
the two are "NOT interchangeable until proven so" and the pairing has not yet
been verified.

- **S1 — the instrument is alive.** At least one `starve:` line appears.
  - *Falsified* by zero lines. That would mean the build lacks the counter or
    the report is not reached, and it would invalidate S2 rather than answer it.
    This leg exists because a silent instrument and a clean result are the same
    log, and that ambiguity has already cost this campaign two arms.
- **S2 — starvation does not explain the owner's symptom.** Over the run,
  zero-filled bytes are **under 1.0%** of output bytes, and **no single 5 s
  interval reports more than 5%**.
  - *Falsified* by a larger figure, in which case the handheld is losing that
    fraction of its output to invented silence, no PCM capture can see it, and
    the symptom is reopened with a mechanism the baseline could not reach.
  - **This is not forced true by the change.** The counter does not touch the
    FIFO, the watermarks or the pacing; it only observes. And the Android
    defaults are exactly the shape that starves: the sink asks for 8192 bytes at
    a time while the APU produces 1024 bytes per 5.333 ms, so a callback needs
    eight production units to have completed, and `monitor_sink_cb` waits at
    most 10 × 0.5 ms = 5 ms — less than one frame period — before giving up and
    filling with zeros. A run that starves is entirely plausible a priori; that
    is why this is worth measuring rather than asserting.
- **S3 — the figure is uncontaminated.** The line reads `capture off`.
  - This is a control on an assumption, not an independent prediction. If it
    reads `ARMED`, someone re-armed the marker between now and the run, the
    capture is writing on the audio thread, and S2's number describes that
    rather than a normal run — in which case S2 is void, not falsified.

## 5. What this baseline cannot do

Carried forward from `audio-harness.md` section 4, because each still binds:

- It is **not an accuracy oracle**. No golden PCM from real silicon exists.
- A **desktop capture is not comparable**: the Android build substitutes a stub
  libsamplerate that resamples linearly regardless of the requested
  `SRC_SINC_FASTEST`.
- It **cannot see underrun**, per section 1.
- It **cannot measure pacing while it is capturing** — the capture writes on the
  audio thread to FUSE-backed storage.
- It **cannot hear anything**. No perceptual claim follows from any of it.
