# The submix-headroom fix, verified by measurement

2026-09-12. Two soaks of Galleon on the Nova, 92.843 s of captured APU output
each, through the PCM tap at `monitor.frame_buf` and `audio_measure.py`. No
listening involved, which was the point: audio had no oracle and the fix was
sitting unverifiable.

    arm A   ref 51aa3f9d0e   the fix in   (54a00d28fb)
    arm B   ref 8254d88ebc   the fix reverted, harness identical

Both captures 17,825,792 bytes, s16 stereo interleaved at 48 kHz,
`volume_limit=1.0`, `use_dsp=false` — so the monitor path, which is the path
the divisor was being applied on.

## The prediction, made before the measurement

A uniform **+6.02 dB**, from removing an uncompensated `2^submix_headroom`
divisor where Galleon programs headroom = 1 on all 31 mixbin slots (itself
measured on device). Uniform is the operative word: a level change moves every
statistic together, while a change of *shape* would not.

## The result

Per-window AC RMS percentiles, 50 ms windows, silent windows excluded, both
channels:

| statistic | L shift | R shift |
|---|---:|---:|
| p5 | +6.17 | +6.02 |
| p25 | +6.22 | +6.17 |
| p50 | +5.98 | +5.96 |
| p75 | +5.94 | +6.20 |
| p95 | +6.49 | +6.03 |

**Mean +6.118 dB over those ten statistics, spread 0.55 dB, against a predicted
+6.02 — a deviation of +0.098 dB.** The harness's own guidance is to treat
anything under about 1 dB as noise between two non-sample-aligned runs of a
non-deterministic guest, so this is as close to the prediction as the
instrument can resolve, and the tight spread is what says it is a level change
rather than a shape change.

## The predicted side effect also appeared

| | arm B | arm A |
|---|---|---|
| peak L / R | 17,296 / 22,092 | **32,767 / 32,767** |
| peak dBFS | −5.55 / −3.42 | −0.00 / −0.00 |
| clipped samples | **0** | **52** (0.0012%) |
| accumulator overflow jumps | 0 | 0 |

Clipping goes from none to 52 samples of 4,456,448. That was called in advance:
past full scale the extra gain becomes distortion instead of loudness. It is
small enough not to argue against the fix and large enough to say a limiter is
worth considering.

**Read the peak row with care.** R's peak appears to shift only +3.42 dB, which
looks like a failure of the prediction and is not — arm A's peak is pinned at
32,767, so the statistic is censored and cannot show the rest of the gain. That
is exactly why the percentile columns exist, and why the whole-file `--compare`
summary reports a 3.06 dB spread while the percentiles alone spread 0.55 dB.
Quoting that summary spread as the result would have been wrong.

## What this does not establish

- **Not accuracy.** It says the level moved as predicted; it does not say the
  new level is what an Xbox produces. No hardware audio golden exists.
- Galleon programs all 31 slots equally, so this capture cannot distinguish
  dropping the divisor from compensating after the mix — the two shapes differ
  only when slots differ.
- Desktop captures are not comparable: the Android build substitutes a stub
  libsamplerate that resamples linearly instead of the requested
  `SRC_SINC_FASTEST`.

## Getting the capture at all took three attempts

Worth recording, because two of the three failures were mine and both were
silent. The first pair of arms produced a **0-byte PCM** with a correct
430-byte sidecar. The capture's own diagnostics would have said why
immediately, and they were being filtered out: `logcat` tag filters are
**exact matches, not prefixes**, so `hakuX-audio:I` never matched the tag
`hakuX-audiocap`. And the serve loop was running a copy of the dispatcher from
before the `--pull` wiring existed, so even a good capture would have stayed on
the device.
