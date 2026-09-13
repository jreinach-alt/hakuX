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

## 4. Results: every active voice carries headroom = 7, and that settles it

**MEASURED.** Galleon, Retroid Pocket Nova, 90 s held, ref `8d96196c71`, binary
`2413de7c33ad`, result `1789278817-audio74-galleon-1188071`. App lifetime
22:55:29.661 → 22:57:01.456 device time = 91.8 s; eighteen census windows of
5 s = 90 s of censused frames, which is the run.

    voice_headroom: FIRST active voice with headroom=7 -- voice 64.
    ...
    voice_headroom: window 107467 active voice-frames  hr0..7 =
        0 0 0 0 0 0 0 107467   cumulative 1288746 nonzero of 1288746

| headroom value | active voice-frames | share |
|---|---:|---:|
| 0 | 0 | 0.00% |
| 1 | 0 | 0.00% |
| 2-6 | 0 | 0.00% |
| **7** | **1,288,746** | **100.00%** |

Eighteen windows, every one of them 100% at 7, from the first active voice to
the last. Window totals run 28,171 → 37,500 → 117,073 as the title's voice count
grows (a window is 7,500 frames, so that is about 4 active voices at the start
and 15 by the end). **Not one voice-frame of 1,288,746 carried any other
value.**

The same run re-confirms `submix_headroom[0..30] = 1`, all 31 slots — a fourth
independent observation, and the first on the Nova at today's tip.

### Verdict against the predictions

- **H1 — the instrument is alive. PASSED.** Eighteen report lines plus one
  first-sighting line, on clean 5 s intervals.
- **H2 — non-zero. PASSED. Modal value 1. FAILED.** I predicted 1, by analogy
  with the sibling register. It is **7**, the maximum the three-bit field can
  hold, on every voice. Recording the failed leg rather than restating the
  prediction: the reasoning that produced "1" — *the sibling is 1, the fields
  are the same width, so they will hold the same value* — was an analogy, and
  the measurement says the two registers hold different quantities, which is
  more interesting than if I had been right.
- **H3 (narrowed) — `CFG_FMT_HEADROOM` reaches nothing. PASSED**, by grep, and
  the correction to its over-broad first wording is recorded above.

### Why 7 closes the owner's symptom, by arithmetic rather than by assumption

**This is the load-bearing result of this document.** The direction of the field
is still not known from source. It does not need to be, because one of the two
directions is now excluded by the level we already measured.

Suppose `CFG_FMT_HEADROOM` were a **gain** we are failing to apply — the only
direction that could make us too quiet. It is 7 on 100% of voice-frames, so the
whole mix would move together, by `2^7` = **+42.14 dB**. Against the measured
baseline (`audio-baseline.md` section 1):

| statistic | measured today | + 42.14 dB |
|---|---:|---:|
| peak | −0.00 dBFS | +42.1 dBFS |
| AC RMS, whole file | −23.43 / −23.50 dBFS | **+18.7 dBFS** |
| median active 50 ms window | −29.37 / −29.45 dBFS | **+12.8 dBFS** |
| p5 active window | −38.00 dBFS | +4.1 dBFS |

Every one of those is above full scale. A correct level in which the *fifth
percentile* of active windows sits 4 dB into the rails and the median sits 12.8
dB into them is not a mix any title ships; it is permanent gross clipping. **So
the field is not an unapplied gain, and #74 cannot be "volume seems unusually
low".**

The other direction survives and points the opposite way: as an *attenuation*
we would be too loud, not too quiet — and on the audible path we apply it
nowhere, which is the same reasoning `54a00d28fb` already settled for the
submix headroom.

**MEASURED OUT: #74 is not the owner's symptom.** That is the third and last of
the three candidates the baseline left standing — a uniform missing gain, output
starvation, and a per-voice missing gain — and all three are now measured out.

### What 7 and 1 together say, which is new

The two registers hold **different** values on the same title: `submix_headroom`
is 1 everywhere, `CFG_FMT_HEADROOM` is 7 everywhere. That is evidence they are
two different quantities rather than two names for one reserve, and it makes a
coherent model available for the first time:

- **Per-voice headroom 7 = 42 dB = seven bits** is the reserve for *summing*.
  The GP mixbuf is 24-bit and a voice is 16-bit, so shifting each voice down by
  7 leaves room to sum on the order of 128-256 voices into one bin without
  overflowing — and the Xbox APU sums up to 256. Seven is not an arbitrary
  value; it is the number of bits the arithmetic needs.
- **Submix headroom 1 = 6 dB** is a much smaller reserve at the bin *output*,
  which is the stage the uploaded GP scene reads.

**INFERRED, and it is the live part of #74 now.** If that model is right, then
`vp.c:1521-1523` divides the voice by the wrong register: it uses
`2^submix_headroom[bin[b]]` = 2 where the hardware would use
`2^voice_headroom` = 128. Our mixbins would then be **64x = 36.1 dB hotter**
than silicon's, which on a 24-bit saturating mixbuf is a real overflow hazard —
on the **DSP path only**.

That is worth stating precisely, because it is the part that is *not* closed:

- On the **monitor path** (`use_dsp = false`, the handheld's default and the
  owner's configuration) this is **inert**. The mixbins are discarded; the
  monitor mix applies no headroom; the one place headroom reaches the audible
  output, the multipass read at `vp.c:1316`, divides and multiplies by the
  *same* `submix_headroom[mp_bin]` and is therefore self-consistent whatever
  the true convention is.
- On the **DSP path** (`use_dsp = true`, off by default, labelled experimental)
  it would be a 36 dB error into a saturating fixed-point buffer.

**No fix is being made, and that is deliberate.** Changing the divisor from 2 to
128 on a guess would move the DSP path by 36 dB in a direction nothing has
measured, on a path this harness cannot capture: the PCM tap reads
`monitor.frame_buf`, and `use_dsp` is a config toggle no soak can set. That is
precisely how a measured chain acquires an unmeasured stage. #74 stays open with
its value now known and its blast radius now bounded.

### The capture did not arm, and the reason is a harness bug worth more than the capture

**The run pulled no PCM.** `run.log` reads `PULL: nothing matched`, and every
`starve:` line reads `capture off`, so this is an honest empty result and not a
stale file — the failure mode the previous pass engineered for.

The request asked for it: `"audio_capture": "30"` is in `request.json`, and
`request.sh`'s guard passed because it checks
`${DISPATCH_TREE}/docs/testing/dispatcher.sh`, which does support the field.
**But that is not the script that serves the request.** The worker execs a
snapshot in `$DISPATCH_DIR/bin`, and that snapshot is from 22:16 and has neither
`audio_capture` in `dispatcher.sh` nor `AUDIO_CAPTURE_MB` in `soak_title.sh`.
So the field was accepted, recorded, and dropped.

The snapshot cannot refresh itself, and that is the actual defect:

```sh
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"          # dispatcher.sh:36
...
now_hash="$(cat "$HERE"/dispatcher.sh "$HERE"/soak_title.sh ...)"   # :537
if [ "$now_hash" != "$DISPATCH_SRC_HASH" ]; then ... exec bash "$SNAP/dispatcher.sh"
```

Once a worker has re-execed into `$SNAP`, `$HERE` **is** `$SNAP`, so it hashes
the snapshot against itself. The hash can never change again and the re-exec can
never fire a second time. The mechanism added at `689a1a29b9` to pick up script
changes works exactly once per worker lifetime.

This blocks every audio capture on the project, not just this one, and it will
silently swallow any future change to `dispatcher.sh`, `soak_title.sh`,
`run_disc.sh`, `score_sweep.py`, `affinity.py`, `captures.py`,
`make_test_iso.py` or `extract_results.py`. **The serving dispatcher needs
restarting**; that is the orchestrator's to do, and no agent may do it from
here.

I have not touched `dispatcher.sh`. Hashing the source tree instead of `$HERE`
is the obvious repair and it is *not* safe to apply blind: `build_ref` detaches
that same tree for the length of every build, so a source-tree hash would flap
mid-build and re-exec a worker into whatever dispatcher a foreign ref carries —
which is the failure the comment at `:540-559` was written about, and which
killed the Nova worker for twenty-five minutes on 2026-09-12. What I have done
instead is make the refusal honest: `request.sh` now checks the snapshot that
will actually run.

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
