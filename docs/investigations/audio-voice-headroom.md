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

### C1-C4 — the level meter on device, registered after the capture route broke

Added after the Galleon census run came back with no PCM (section 4) and before
either of the two runs that use the meter. The capture route is blocked on a
dispatcher restart no agent may perform, so the level now comes from an
instrument inside the emulator: same tap point, same conventions, reported to
logcat.

Its agreement with `audio_measure.py` is **already established offline**, on
identical samples, by `audio_level_check.py` over the published baseline
capture: 26 of 26 statistics, every integer count exact, every percentile within
0.05 dB. So a disagreement on device is not instrument error — it is either
run-to-run variance or a real change in the level.

That makes these legs the repeat that `audio-baseline.md` section 2 registered
as R1-R4 and never got to take, and they are stated at the same tolerances:

- **C1 — level repeats.** Galleon's median active-window AC RMS from the meter
  is within **±2.0 dB** of the baseline's −29.37 / −29.45 dBFS, and p25/p75
  within **±2.5 dB** of −32.01/−32.05 and −25.66/−25.64.
- **C2 — the rails are a property of the level.** Peak reaches 32,767 on both
  channels, with a non-zero clipped count below 0.01% of samples.
- **C3 — the int16 accumulator does not wrap.** Zero wrap suspects (#73).
- **C4 — DC stays negligible.** |DC| under 0.1 %FS on both channels.

*Falsified* by any leg missing, and C1 is the consequential one: if a second
unscripted playthrough of the same title on the same device at the same ref
gives a different median, then a single soak is not a measurement of the
emulator and every audio A/B on this project — the +6.118 dB headroom result
included — rests on an assumption nobody checked.

**Not forced true by my change.** The meter observes the buffer the sink is
about to be handed and writes nothing back; the census reads one register.
Neither touches the mix, the level or the pacing.

### F1 — the instrument does not cause the defect it sits next to

Registered while the runs were still in flight and before either result
directory contained anything but a partial logcat, because it is the one way
this work could do harm and it would be easy to miss.

The meter is per-sample arithmetic **on the audio thread** — about 96,000
samples a second, a handful of integer operations each — and it sits three lines
from `monitor_sink_cb`'s zero-fill, which is #70. An instrument that costs the
APU thread its deadlines would manufacture the starvation that issue is about,
and the result would read as a finding.

- **F1 — steady-state starvation stays at zero with the meter in.** Every
  `starve:` line after the startup window reports **0.0000%** of output bytes
  zero-filled, on both handhelds, in all three runs.

*Falsified* by any non-zero steady-state figure, in which case the meter is
removed or moved off the audio thread before a single one of its numbers is
quoted. The startup window is excluded per the corrected predicate in
`audio-baseline.md` section 4a — it reads 17-27% because the guest has not
produced a sample yet, which is not starvation.

This leg costs nothing to take: the starvation counter is already permanent and
already in the same logcat.

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

### The field is 7 on a second title too

**MEASURED, on three titles now.**

| title | device | active voice-frames | at headroom 7 | at anything else | submix_headroom |
|---|---|---:|---:|---:|---|
| Galleon | Nova | 1,288,746 | **100.00%** | 0 | 1 on all 31 slots |
| Galleon (2nd run) | Nova | 1,237,181 | **100.00%** | 0 | 1 on all 31 slots |
| Dead or Alive 3 | Thor | 174,608 | **100.00%** | 0 | 1 on all 31 slots |
| Crimson Skies | Thor | 724,083 | **100.00%** | 0 | 1 on all 31 slots |

Three titles, three developers, three completely different mixes — measured
above to span 13.8 dB of median output level — and **not one voice-frame of
3,424,618 at any value but 7**, with the sibling register at 1 every time.

That matters for the reading in the section above: 7 is not one studio's
choice, it is what the runtime programs, and 1 is what it programs into the
other register. Two constants, two registers, no exceptions.

## 5. The level meter, and the second title

The capture route is blocked (previous section), so the level comes from the
in-emulator meter, calibrated offline against `audio_measure.py` on the
published baseline capture: **26 of 26 statistics agree**, every integer count
exactly, every percentile within 0.05 dB — half of its 0.1 dB bin. Re-runnable
with `docs/testing/audio_level_check.py CAPTURE.pcm`.

### C1-C4: the baseline repeats, and R1 is finally discharged

**MEASURED.** Galleon, Nova, 90 s (84.555 s of output), ref `3e15e49f4d`,
result `1789279659-audio-level-galleon-1503189`, against the pulled-capture
baseline of 92.843 s taken about eight hours earlier from a different build.

| statistic | baseline L / R | meter L / R | Δ | tolerance |
|---|---:|---:|---:|---:|
| p25 | −32.01 / −32.05 | −31.65 / −31.85 | +0.36 / +0.20 | ±2.5 |
| **p50** | **−29.37 / −29.45** | **−29.15 / −29.25** | **+0.22 / +0.20** | **±2.0** |
| p75 | −25.66 / −25.64 | −25.55 / −25.45 | +0.11 / +0.19 | ±2.5 |
| p5 | −38.00 / −38.23 | −38.05 / −38.15 | −0.05 / +0.08 | — |
| p95 | −16.46 / −16.58 | −17.55 / −17.05 | −1.09 / −0.47 | — |
| AC RMS | −23.43 / −23.50 | −23.57 / −23.25 | −0.14 / +0.25 | — |
| peak | 32,767 / 32,767 | 32,767 / 32,767 | — | — |
| wrap suspects | 0 / 0 | 0 / 0 | — | — |
| DC %FS | −0.029 / +0.002 | −0.010 / +0.003 | — | ±0.1 |

- **C1 — level repeats. PASSED, and not narrowly.** The median active window
  agrees to **0.22 dB** against a registered tolerance of 2.0 dB, p25 to 0.36
  and p75 to 0.19 against 2.5. Two unscripted playthroughs of a
  non-deterministic guest, different builds, eight hours apart, on the same
  device.
  **This is R1 from `audio-baseline.md` section 2, which has been outstanding
  since it was written**, and its consequence is the important part: a single
  soak *is* a measurement of the emulator, so the +6.118 dB headroom result and
  every other audio A/B on this project rest on something now checked rather
  than assumed.
- **C2 — the rails are a property of the level. PASSED on its first clause,
  FAILED on its second.** Peak reaches 32,767 on both channels, so the rails
  are not a one-off transient. But I registered "clipped count below 0.01% of
  samples" and it is **0.0138% (562) and 0.0176% (714)** — 1.4 to 1.8 times the
  threshold, and 16 to 45 times the baseline playthrough's 36 and 16 samples.
  The prediction is wrong, not the emulator: clipping is a count of transients,
  and two playthroughs of a title that peaks at the rails will not produce the
  same number of them. `maxjump` moved the same way, 8,970 → 13,096. **The
  honest correction is that a clipped-sample *count* is not a property of the
  level at all** — only "reaches the rails at all" is — and #72 should be read
  with that in mind.
- **C3 — no accumulator wrap. PASSED.** Zero wrap suspects, both channels,
  despite the louder transients.
- **C4 — DC negligible. PASSED.** 0.010% and 0.003% of full scale.
- **F1 — the meter does not starve the thread it sits on. PASSED.** Every
  steady-state `starve:` line in every run reads **0.0000%** — six windows
  across three soaks and both handhelds: Galleon on the Nova (0/704, 0/704),
  DOA3 on the Thor (0/704, 0/703), Crimson Skies on the Thor (0/703, 0/704).
  Not one callback short by a byte, on the densest title of the three.
  The startup windows read 17.1%, 15.0% and 55.3%, all of them *empty*
  callbacks — the guest not having produced a sample yet — which the corrected
  predicate in `audio-baseline.md` 4a excludes.

  A second, weaker corroboration from the same logs: median `gfps` on Galleon
  on the Nova is **18 without the meter** (census-only run, 22 samples) and
  **23 with it** (25 samples), and Crimson Skies with the meter medians 29 with
  a maximum of 35. Higher with the instrument in, so there is no measurable cost
  — but `gfps` swings widely run to run on a warm device and this is offered as
  "no sign of a cost", not as a measurement of one. The starvation counter is
  the leg that actually binds, because it measures the audio thread's own
  deadlines rather than the renderer's.

### T2: Dead or Alive 3, and one leg fails in the opposite direction

**MEASURED.** Dead or Alive 3, Thor, 89.643 s of output, same ref as the
Galleon meter run.

| | Galleon (baseline) | Galleon (meter) | **DOA3** |
|---|---:|---:|---:|
| peak | 32,767 (−0.00 dBFS) | 32,767 (−0.00) | **12,795 / 12,803 (−8.17 / −8.16)** |
| clipped | 36 / 16 | 562 / 714 | **0 / 0** |
| p5 | −38.00 / −38.23 | −38.05 / −38.15 | −60.05 / −58.65 |
| p25 | −32.01 / −32.05 | −31.65 / −31.85 | −39.25 / −30.35 |
| **p50** | −29.37 / −29.45 | −29.15 / −29.25 | **−23.45 / −23.65** |
| p75 | −25.66 / −25.64 | −25.55 / −25.45 | −21.25 / −21.25 |
| p95 | −16.46 / −16.58 | −17.55 / −17.05 | −19.25 / −18.55 |
| p95 − p50 | 12.91 / 12.87 | 11.60 / 12.20 | **4.20 / 5.10** |
| p95 − p5 | 21.54 / 21.65 | 20.50 / 21.10 | 40.80 / 40.10 |
| peak − p50 | 29.37 / 29.45 | 29.15 / 29.25 | **15.28 / 15.49** |
| windows counted / flat | 1677 / 179 | 1533 / 158 | **526 / 1266** |

- **T2a — DOA3's p50 more than 4 dB hotter. PASSED**, at **+5.92 / +5.80 dB**
  against the baseline and +4.30 / +4.40 against the same-ref Galleon meter run.
- **T2b — DOA3's p95 − p5 spread more than 4 dB narrower. FAILED, and in the
  opposite direction**: it is **19.26 / 18.45 dB WIDER**.

**The failed leg is my statistic's fault, and the diagnosis is in the window
counts.** DOA3's run is **1,266 flat windows against 526 counted** — 71% of the
run is exact silence, and 95% of its individual samples are zero. Ninety
seconds of DOA3 from a cold force-start is boot, load and menu, not a fight. So
its p5 of −60 dB is near-silent menu ambience, and `p95 − p5` was measuring
*how much near-silence a run contains* as much as *how wide the mix's dynamics
are*. Those are different questions and I registered a statistic that mixes
them.

**The statistic that does answer the question is `peak − p50`, and it is the one
that is not censored here.** Both Galleon figures sit against a peak pinned at
32,767, so they are lower bounds. DOA3's peak is **8.17 dB below full scale**,
so its crest is exact — and it is **13.9 dB narrower** than Galleon's censored
*lower bound*. `p95 − p50` says the same with no reference to the peak at all:
**4.2 / 5.1 dB for DOA3 against 11.6 / 12.9 for Galleon.**

### Crimson Skies is the dense, loud title the question actually needed

**MEASURED.** `Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso`,
Thor, 87.451 s of output, ref `25e5192856`, binary `b0f5b50d191e`, result
`1789280122-audio-level-crimson-1590751`. Queued after JSRF failed to boot, and
chosen because it is the one other title any document records as running on a
handheld (`crimson-skies-performance.md`), so it was known to boot rather than
hoped to.

It is also the case the baseline asked for and neither of the first two titles
provided: **1,665 counted windows against 84 flat** — continuously scored, 5% of
the run silent, against DOA3's 71%.

| title | ch | AC RMS | p50 | Δp50 | p95−p5 | p95−p50 | peak−p50 |
|---|---|---:|---:|---:|---:|---:|---:|
| Galleon (capture) | L | −23.43 | −29.37 | — | 21.54 | 12.91 | 29.37 |
| Galleon (capture) | R | −23.50 | −29.45 | — | 21.65 | 12.87 | 29.45 |
| Galleon (meter) | L | −23.57 | −29.15 | +0.22 | 20.50 | 11.60 | 29.15 |
| Galleon (meter) | R | −23.25 | −29.25 | +0.20 | 21.10 | 12.20 | 29.25 |
| DOA3 | L | −28.45 | −23.45 | +5.92 | 40.80 | 4.20 | 15.28 |
| DOA3 | R | −28.22 | −23.65 | +5.80 | 40.10 | 5.10 | 15.49 |
| **Crimson Skies** | L | **−14.00** | **−15.95** | **+13.42** | 22.30 | 6.50 | 15.95 |
| **Crimson Skies** | R | **−13.98** | **−15.65** | **+13.80** | 22.20 | 6.20 | 15.65 |

- **T2a — p50 more than 4 dB hotter. PASSED, by 13.4 / 13.8 dB.** Whole-file AC
  RMS is **9.4 dB hotter** than Galleon's, on a run that is 95% non-silent.
  Peak reaches 32,767 on both channels with 84 and 73 clipped samples —
  0.0020%, a tenth of what the louder Galleon playthrough produced.
- **T2b — p95 − p5 spread more than 4 dB narrower. FAILED again**, at 0.76 /
  0.55 dB *wider*. **That leg has now failed on both titles, in opposite
  directions, and the statistic is the reason.**

### T2b failed twice, and the fault is the statistic I registered

DOA3 came in 19 dB wider, Crimson Skies 0.6 dB wider, and I predicted both to
be 4 dB narrower. The prediction was not unlucky; `p95 − p5` cannot answer the
question I asked it. It spans from a run's quietest non-silent window to its
loudest, so it measures **how much quiet passage a playthrough happens to
contain** at least as much as how wide the mix's dynamics are. DOA3's run is
71% exact silence with near-silent menu ambience either side of it; Crimson
Skies is continuously scored but still has a quiet moment somewhere in 87 s.
Neither fact is about gain.

**Two statistics do discriminate, and both are in the table above.**

| | Galleon | DOA3 | Crimson Skies |
|---|---:|---:|---:|
| loud-half spread `p95 − p50` | 12.9 / 12.9 | 4.2 / 5.1 | 6.5 / 6.2 |
| crest `peak − p50` | 29.4 / 29.5 | 15.3 / 15.5 | 16.0 / 15.7 |

Both other titles sit at roughly **half** Galleon's loud-half spread and
**14 dB** below its crest — DOA3 −14.1/−14.0, Crimson Skies −13.4/−13.8, which
is close agreement between two unrelated titles. And DOA3's crest is **not
censored**: its peak is 8.17 dB below full scale, so that figure is exact where
Galleon's 29.4 dB is a lower bound. Censoring was the trap that nearly sank the
+6 dB headroom result, and it is the reason `peak − 23.4 dB` was never quoted as
the headline here.

### So: is the −23 dBFS, wide-crest shape ours or Galleon's?

**Galleon's, and the third title makes it emphatic.** That is the question this
section existed to answer:

- One binary, one hour, three titles. **Crimson Skies runs at −14.00 / −13.98
  dBFS AC RMS with its median active window at −15.95 / −15.65 — 9.4 dB and
  13.4 dB hotter than Galleon** — and reaches full scale with a tenth of
  Galleon's clipping. DOA3 sits between them in median and **never gets within
  8 dB of full scale, clipping nothing at all**.
- Their loud-half spreads differ by a factor of two to three and their crests by
  14 dB.
- A shape imposed by our mix could not do that. A gain error common to all three
  would move them together and leave the shapes alike; what is here is three
  different shapes from one binary, spanning 13.8 dB of median level.

**For the owner's symptom this is the reassuring direction and it is worth
stating plainly: the same build that puts Galleon's median active window 29 dB
below full scale puts Crimson Skies' at 16 dB below, and leaves 8 dB of headroom
entirely unused on Dead or Alive 3. That is what per-title content does. It is
not what a missing gain does — a missing gain cannot be missing from one title
and not another.** Combined with #74 measured out by arithmetic, the
uniform-gain hypothesis closed by the peak, and starvation at 0.0000% on both
handhelds, **there is no measured defect left that makes the output quiet, and
there is now a positive demonstration that the output can be loud.**

Galleon — the title the complaint was made against — is a wide-dynamic mix whose
median active window sits 29 dB below full scale while its peaks hit the rails.
A mix shaped like that is quiet most of the time even with its gain exactly
right, and a listener with no meter cannot tell that from a gain error. That is
the answer to "volume seems unusually low, even at max": **on this title, at
this configuration, the level is correct, and here are the measurements.**

### JSRF did not boot, which is recorded rather than retried away

`JSRF - Jet Set Radio Future (USA).xiso.iso`, Thor, 90 s, result
`1789279799-audio-level-jsrf-1542565`: `guest never appeared in 90s -- title did
not boot`. Forty-seven log lines, no level report at all (the APU frame loop did
not reach 7,500 frames), and one `voice_headroom: FIRST ... headroom=7` line
from whatever ran before the guest failed. No level from it, and it is not
evidence about audio. It is a title-compatibility data point for whoever owns
that, and the reason the third title below is Crimson Skies instead.

### Finding an exact title name cost five device claims, and now costs none

Worth recording because it was pure waste. A soak names a title by exact
filename and **nothing in this repository could tell you one**; the libraries
are the owner's, and the naming follows from nothing checked in. Five guesses
missed in a row — `Dead or Alive 3 (USA).xiso.iso`, the same with `.iso`, the
same bare, JSRF, Psychonauts, Panzer Dragoon Orta — each costing a queue claim,
an install and an ERROR. The real name is `Dead or Alive 3 (USA) (En,Ja).xiso.iso`,
which no amount of guessing reaches.

`devices.sh titles [label]` now lists them. It is `ls` and nothing else: no
lease, no install, no `am start`, no input injection, so it cannot disturb a run
in progress.

## 6. What this cannot do, and the least certain thing in it

Carried forward, because each still binds:

- **Not an accuracy oracle.** No golden PCM from real silicon exists, so no
  title's level can be called correct — only compared with another title's.
- **A desktop capture is not comparable**: the Android build substitutes a stub
  libsamplerate that resamples linearly rather than `SRC_SINC_FASTEST`.
- **The tap cannot see underrun**, because it is on the producing side of the
  FIFO. That mechanism is measured separately and reads 0.0000% in steady state
  on both handhelds.
- **It cannot hear anything.** No perceptual claim follows from any of it.

### The least certain point

**That `CFG_FMT_HEADROOM` is a headroom field at all.**

Everything above survives either way, because the loudness argument runs on the
measured level rather than on the field's meaning: a 42 dB gain is excluded by
arithmetic whatever the bits are called. But the *forward-looking* half of #74 —
that this is the voice-into-bin reserve and our mixbins are consequently 36 dB
hot on the DSP path — rests on `apu_regs.h:231` being right about bits 13-15,
and the census gives a reason to hold that loosely.

A three-bit field that reads **0b111 on every voice of every title** is equally
consistent with two readings:

1. every voice reserves the maximum 42 dB — which is arithmetically sensible,
   since 16-bit voices summed 256-deep into a 24-bit mixbuf need about seven
   bits of room, so 7 is the number the hardware would want; or
2. bits 13-15 are not this field. They could be reserved-and-set, or the low end
   of a wider field. The header leaves **bits 10-12 undefined** immediately
   below them, which is exactly the shape of a bit assignment that was guessed
   once and never checked, and `NV_PAVS_VOICE_CFG_FMT_SAMPLES_PER_BLOCK` and
   `_MULTIPASS_BIN` are already aliased onto the same `0x1F << 16` in that
   header, so it is not a document that has been audited.

Nothing in this tree separates those, and I did not try to: the experiment that
would is a hardware capture of one voice with the field written and cleared, and
that does not exist here. The consequence for anyone acting on #74 is concrete —
**do not change the mixbin divisor on the strength of this number alone.** The
value 7 is measured; that it means 42 dB of voice headroom is inferred, and the
inference is the weakest link in this document.

A cheaper partial check, now that a level costs a grep rather than a pull: log
the whole `CFG_FMT` word for one voice and read the *other* fields against what
the title must be doing — sample size, container, stereo, loop. If those decode
sensibly the header is broadly trustworthy in that region; if any of them is
nonsense the bit map is suspect and 7 means nothing. That is one log line and
one soak, and it is the next thing I would do.
