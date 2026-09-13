# Issue #74: the per-voice headroom field, and a second title's level

Date: 2026-09-12. Branch `claude/es-de-launcher-disc-error-ojnl14`, rebased at
`0499184e2d`.

Read `audio-assessment.md`, `audio-harness.md`, `audio-headroom-verified.md`
and `audio-baseline.md` first. This document picks up the single candidate they
left standing for the owner's symptom, and takes the one measurement they named
as cheapest and did not take.

> "Volume seems unusually low, even when turned up to max, and I do not have any
> hints as to what is causing that."

Where the field stands after the baseline: a **uniform** missing gain is measured
out (the output peaks at 32,767 on both channels, so further gain becomes
clipping rather than loudness), and output starvation is measured out
(0.0000% over 2,816 consecutive sink callbacks in steady state). What survives
is a **per-voice** gain, which a peak argument is precisely the wrong instrument
for, and that is #74.

Claims are tagged as in the other four:

- **MEASURED** — from a capture or a log off real hardware, or from reading the
  cited source.
- **INFERRED** — needs a fact I do not have.

## 1. What the field is, and what we do with it

**MEASURED, from source.** `NV_PAVS_VOICE_CFG_FMT_HEADROOM` is `(0x7 << 13)` at
`hw/xbox/mcpx/apu/apu_regs.h:231` — bits 13-15 of `NV_PAVS_VOICE_CFG_FMT`, the
per-voice format register. `grep -rn CFG_FMT_HEADROOM hw/` returns that one
line and nothing else. Every other bitfield in that register is read: `V6BIN`
and `V7BIN` at `vp.c:1421-1425`, `SAMPLES_PER_BLOCK`, `MULTIPASS`,
`MULTIPASS_BIN`, `LINKED`, `PERSIST`, `DATA_TYPE`, `LOOP`, `CLEAR_MIX`,
`STEREO`, `SAMPLE_SIZE`, `CONTAINER_SIZE`. `HEADROOM` alone is decoded and
discarded.

**MEASURED.** It is the third three-bit headroom control in this register file.
The other two are read, and both as *divisions*:

| site | expression | which path |
|---|---|---|
| `vp.c:1521` | `hr = 1 << d->vp.hrtf_headroom` | mixbins, 3D voices, bins 0-3 |
| `vp.c:1523` | `hr = 1 << d->vp.submix_headroom[bin[b]]` | mixbins, all other bins |

Three bits, a power-of-two divisor, so the natural unit of all three is
**6.0206 dB** over a 0-42 dB range. One of the two that *is* read turned out to
be a live, uncompensated −6.02 dB on the audible path, and fixing it
(`54a00d28fb`) measured **+6.118 dB** against a +6.02 prediction.

**MEASURED: what we do with the per-voice field today is nothing, and what the
audible path does with headroom in general is also nothing.** Since
`54a00d28fb` the VP monitor mix applies no headroom divisor at all
(`vp.c:1578`, `g = fmax(g, attenuate(vol[b]))`), and `mcpx_apu_vp_frame`
discards the mixbins outright once the monitor mix has been taken. So the two
headroom divisions above cannot reach `monitor.frame_buf` on the default
Android configuration (`use_dsp = false`).

That is the shape of the question, and it is worth stating before any run,
because it is what a measurement can be judged against:

- If the hardware's per-voice headroom is a property of the **voice→mixbin
  summation** — range reserved in the 24-bit GP mixbuf, earned back by the
  scene the title uploaded — then it belongs exactly where `submix_headroom` is
  already applied, and it is **inaudible on the monitor path by construction**,
  whatever value a title writes. #74 would then be a DSP-path fidelity item.
- If instead it is a property of the **voice's samples**, applied before the
  bin split, then the monitor mix needs it and #74 is a live per-voice gain
  error of unknown sign.

Nothing in this tree decides between those two, and the previous pass is right
that guessing the direction is how five mechanism claims were retracted here in
two days. But a cheaper question comes first and this tree *can* answer it:
**does any title write anything but 0?** If not, the direction is moot.

## 2. The instrument

`mcpx_apu_vp_frame` walks the three voice lists once per 32-sample VP frame and
enqueues the voices that are `ACTIVE_VOICE`. A census sits in that loop: read
the voice's `CFG_FMT_HEADROOM`, bucket it, and report the histogram every 7,500
frames — 5 s at 48 kHz, the cadence `apu.c`'s starvation counter already uses.

Two properties are deliberate:

- **Weighted by what is audible.** Voices are counted when they are active and
  about to be mixed, not when they are configured. A voice programmed and never
  played cannot move a level, and counting register writes would let one
  initialisation burst outvote a whole soak.
- **It speaks when the answer is all zeros.** A census that reported only
  non-zero findings would be indistinguishable from one that never ran, and
  that exact ambiguity has already cost this campaign two arms.

It is `#ifdef __ANDROID__` throughout, because an unguarded `__android_log_print`
in this same file broke the desktop link on 2026-09-12 while the Android build
passed. `check_android_guards.py` is clean.

## 3. Predictions, registered before the runs

Committed before either request was queued. Two soaks, both at the ref carrying
the census:

```sh
docs/testing/request.sh --who audio74-galleon --device nova \
    --title "Galleon (USA).xiso.iso" --seconds 90 \
    --audio-capture 30 --pull 'apu_monitor.s16le48k2ch.pcm*' ...

docs/testing/request.sh --who audio74-title2 --device thor \
    --title "Dead or Alive 3 (USA).xiso.iso" --seconds 90 \
    --audio-capture 30 --pull 'apu_monitor.s16le48k2ch.pcm*' ...
```

### H1 — the instrument is alive (a control, not a result)

At least one `voice_headroom:` line appears in each soak's logcat, and its
`window` count of active voice-frames is non-zero.

*Falsified* by zero lines. That is a diagnosis — the build lacks the census, or
the tag is being filtered — and it invalidates H2 rather than answering it. It
is written down separately for the reason S1 was: a silent instrument and a
clean result are the same log.

### H2 — Galleon programs a non-zero per-voice headroom, and the value is 1

**My call is non-zero**, and I am registering it as such rather than hedging.
The reasoning: the sibling register `submix_headroom` measured exactly 1 on all
31 slots on this same title (three independent runs), the two fields are the
same width with the same unit in the same register file, and a headroom control
denominated in 6 dB steps is only useful if it is normally non-zero.

Concretely: **cumulative non-zero > 0 over the soak, and the modal non-zero
value is 1.**

*Falsified* if the cumulative non-zero count is 0 for the whole run — in which
case #74 closes as **measured-inert on this title**, the direction question
never has to be answered, and that is a clean result rather than a failure.
*Also falsified* if the modal non-zero value is anything but 1.

**Not forced true by my change.** The census reads a register only the guest
writes; nothing in this commit writes it, and nothing in it changes the level.

### H3 — either way, #74 is not the owner's symptom

This is a source claim carried into the run so that H2 cannot be over-read.
Whatever H2 returns, `CFG_FMT_HEADROOM` cannot change the level on the audible
path **as the code stands**, because there is no expression anywhere under
`hw/xbox/mcpx/` that carries a headroom value into `monitor.frame_buf`: the
monitor mix applies no divisor, and the mixbins that do carry one are
`memset` to zero in the same function.

*Falsified* by exhibiting a path from `CFG_FMT_HEADROOM` to `monitor.frame_buf`.

#### H3 as first written is too broad, and I falsified half of it myself

Recorded as a correction rather than an edit, and timestamped by being committed
while both soaks were still queued — **no number from either run existed when
this was written**, so it is a source claim revised against source, not a
prediction widened against results.

The clause "there is no expression anywhere under `hw/xbox/mcpx/` that carries a
headroom value into `monitor.frame_buf`" is **false**. There are exactly four
`1 << <headroom>` expressions in the tree (`vp.c:586`, `:1316`, `:1521`,
`:1523`), and the second of them is on the monitor path by construction:

```c
    float mp_gain = 1.0f;
    if (d->monitor.point == MCPX_APU_DEBUG_MON_VP) {
        mp_gain = 1 << d->vp.submix_headroom[mp_bin];
    }
```

`get_multipass_samples`, `vp.c:1313-1316`. A multipass sub-voice reaches the
output only through this read — the monitor mix skips its direct contribution to
avoid double-counting — so its content is scaled by `2^submix_headroom[mp_bin]`
on the way to `sample_buf` and then to `monitor.frame_buf`. That is a
*compensation* for the divisor those samples were written into the bin with, not
a loss, and it is the right thing; but it does mean headroom reaches the audible
output, and I said it could not.

**What survives, and it is the part H3 was actually for:** `CFG_FMT_HEADROOM`
specifically is read by nothing — `grep -rn CFG_FMT_HEADROOM hw/` returns only
its definition — so *that* field cannot reach `monitor.frame_buf` whatever a
title writes into it. The narrowed claim is the one to judge the run against.

**And the over-broad version was hiding something worth having.** If silicon
applies per-voice headroom as a voice→mixbin attenuation, then implementing it
means the multipass read above must earn back **both** headrooms, not just the
submix one — otherwise multipass content alone would sit `2^voice_headroom`
below everything else on the monitor path. That is the same class of defect as
the one `54a00d28fb` fixed, and it would be introduced *by* the fix for #74.
Written down now so that whoever implements the direction, once it is known,
does not have to rediscover it.

So a non-zero H2 does **not** license adding a gain to the monitor path. It
licenses exactly one thing: the direction question in #74 becoming live for the
DSP path, with a hardware capture as the only instrument that can settle it.

### T1 — the second title's capture is that run's (a control)

The captured duration does not exceed the app's lifetime, and the run's logcat
contains `hakuX-audiocap` lines.

*Falsified* by either failing — in which case the PCM is a leftover from another
experiment and must not be measured, which is exactly what a 24 MB file did on
2026-09-12. It was caught by arithmetic: 126.976 s of audio cannot come out of a
95 s app lifetime.

### T2 — the discriminator: is the −23 dBFS / 23 dB-crest shape ours or Galleon's?

Galleon's measured baseline, 92.843 s on the Nova: whole-file AC RMS
−23.43/−23.50 dBFS, median active 50 ms window −29.37/−29.45, p5 −38.00, p95
−16.46, peak pinned at 32,767 both channels.

**Crest factor is the wrong statistic to compare and I am not going to use it as
the headline.** Both titles will almost certainly pin their peak at 32,767, and
crest against a censored peak is just AC RMS with the sign flipped — so
"hotter with a narrower crest" would be one claim dressed as two. The
censoring-free statistics are the window percentiles, which is what the headroom
result already turned on.

**My call: Dead or Alive 3 lands materially hotter and materially narrower.**
It is a fighting game with continuous music and dense impact material;
Galleon's first 90 s from a cold start is a boot-logo-and-intro sequence with
sparse content.

- **T2a — level.** DOA3's median active-window AC RMS (p50) is **more than 4 dB
  hotter** than Galleon's −29.37/−29.45, i.e. **above −25.4 dBFS** on both
  channels.
- **T2b — shape.** DOA3's p95 − p5 spread is **more than 4 dB narrower** than
  Galleon's 21.54 dB (L) / 21.65 dB (R), i.e. **below 17.5 dB** on both
  channels.

*Falsified, and this is the interesting outcome,* if DOA3's p50 lands **within
2 dB** of Galleon's and its p95 − p5 spread **within 2 dB** of Galleon's. That
would say the level and the dynamic shape are properties of **our mix** rather
than of one game's content, and it would reopen the owner's symptom with a
mechanism the baseline could not name.

An in-between result — hotter but not by 4 dB, or hotter without narrowing — is
reported as in-between. It is not folded into whichever leg it is closest to.

**Not forced true by my change.** The census does not touch the mix, the level,
or the pacing; it reads one register and counts.

## 4. Results

Filled in when the runs land.

## 5. What this cannot do

Carried forward, because each still binds:

- **Not an accuracy oracle.** No golden PCM from real silicon exists, so neither
  title's level can be called correct — only compared.
- **A desktop capture is not comparable**: the Android build substitutes a stub
  libsamplerate that resamples linearly rather than `SRC_SINC_FASTEST`.
- **A capture cannot see underrun**, because the tap is on the producing side of
  the FIFO. That mechanism was measured separately and reads 0.0000% in steady
  state.
- **It cannot hear anything.** No perceptual claim follows from any of it.
