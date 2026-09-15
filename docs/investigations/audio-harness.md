# The audio measurement harness

Date: 2026-09-12. Branch: `claude/es-de-launcher-disc-error-ojnl14` (isolated
worktree, at `aeb4a096b6`).

Read `docs/investigations/audio-assessment.md` first. That document analyses the
signal path, rules out ten candidates, and closes with a submix-headroom fix
(`54a00d28fb`) whose own last section is titled **"Status: UNVERIFIED BY EAR"**.
This document is the answer to that: a capture that can be measured, and a
script that measures it.

The motivating problem in one line: *audio has no oracle*, so a gain change
lands with nothing to check it against. A level, unlike a timbre, needs no
golden reference — it needs a number. That is the whole idea here.

Claims are tagged the same way as the assessment:

- **MEASURED** — checked by reading the cited source, or by running the cited
  command and seeing the output. Re-checkable by anyone.
- **INFERRED** — needs a fact I do not have.

I did not build, did not run the emulator, and did not touch the device. The
code and the script are written and self-tested; **no baseline exists yet**, and
producing one needs the device owner. The commands are in
"Producing the baseline" below.

## 1. What was built

Two pieces plus this note.

1. **A capture**, in `hw/xbox/mcpx/apu/apu.c`. Off by default. When armed it
   writes the final APU output to a file as headerless PCM, plus a `.json`
   sidecar recording the format and the run's audio config.
2. **A measurement script**, `docs/testing/audio_measure.py`. Standard library
   only, numpy used when present purely for speed. Reports levels, clipping,
   DC, silence and an accumulator-overflow check, per channel; `--compare`
   reports the *shift* between two captures, which is the form the headroom
   prediction actually takes.

### Where it taps, and two corrections to the brief

The tap is `d->monitor.frame_buf`, immediately before `fifo8_push_all` (the
capture at `hw/xbox/mcpx/apu/apu.c:321-324`, the push at `:329`). This is the
one funnel both output paths converge on — the VP monitor mix and the GP/EP
DSP scenes both write this buffer — and everything downstream of it is SDL and
AAudio plumbing that is not under test.

I was pointed at the disabled `#if 0` block that used to sit there, and told it
was the right tap point. The location is right. Two things about it were not,
and both would have produced a broken harness:

- **MEASURED: `apu_fifo_output` does not exist.** `grep -rn apu_fifo_output hw/`
  returns exactly one line — the dead `fwrite` inside the `#if 0` itself. It is
  not a member of `MCPXAPUState` (`apu_int.h:102-110`); the buffer is
  `d->monitor.frame_buf`. That block has not compiled since the monitor struct
  was introduced. (The assessment noticed this too, at its section 5.)
- **MEASURED: the 1-in-8 gate was correct and I kept it.** I was told to
  capture every frame instead, on the grounds that 1-in-8 makes the file's
  sample rate a lie. It is the other way round. `frame_buf` holds 256 stereo
  frames and is filled in eight 32-sample slices, indexed
  `off = (ep_frame_div % 8) * NUM_SAMPLES_PER_FRAME` — at `vp.c:1885` on the
  monitor path and `dsp/gp_ep.c:465` on the GP path. `NUM_SAMPLES_PER_FRAME` is
  32 (`apu_regs.h:333`), and 8 x 32 = 256. So the buffer is complete only on
  the eighth frame, which is exactly when `(ep_frame_div + 1) % 8 == 0` fires,
  and it is zeroed right after the push (`apu.c:332`). Writing it every frame
  would emit the same 1024-byte block eight times, seven of them holding a
  partly-stale buffer, and the file would then contain 8x too many samples.
  *That* would be the lie. The existing cadence is the buffer geometry, not a
  sampling decision.

The capture therefore writes one 1024-byte block per completed buffer, which is
one block per 5.333 ms (`EP_FRAME_US`, `apu_regs.h:363`), i.e. 192 KB/s.

It sits **after** the `volume_limit` scaling (`apu.c:308-314`) so the file holds
what is actually sent to the device. A limiter below unity scales both sides of
an A/B equally and so cancels in a dB difference; its value goes in the sidecar
either way. The assessment records it as 1.0 on the owner's device, where the
`< 1` guard makes that block inert.

### Format — MEASURED, from the source

| Property | Value | Source |
| --- | --- | --- |
| Sample type | `int16_t`, signed 16-bit | `apu_int.h:104` |
| Channels | 2 | `apu_int.h:104`, `apu.c:600` |
| Layout | interleaved L,R — channel is the *minor* index of `frame_buf[256][2]` | `apu_int.h:104` |
| Endianness | host (`AUDIO_S16SYS`); little on both ARM64 Android and x86-64 | `apu.c:599` |
| Sample rate | 48000 Hz | `apu.c:598`, `apu_regs.h:363` |
| Block | 256 frames = 1024 bytes = 5.333 ms | `apu_int.h:104`, `apu_regs.h:363` |

One consequence worth stating because it changed the script: the float-to-short
conversion clamps to `+/-1.0` and scales by **32767**
(`android/app/src/main/cpp/samplerate_stub.c:161-197`). Negative saturation
therefore arrives as `-32767`, not `-32768`. My first version of the clip test
looked for `<= -32768` and would have counted **none** of the negative
clipping — caught by the script's self-test, which is why that self-test exists.

### How it is armed

Off unless armed, and it is armed by **either** of:

- `XEMU_AUDIO_CAPTURE=1` in the environment, or
- the presence of a marker file, `audio_capture.on`, in the capture directory.

The marker exists because the environment variable is **not reachable on a
device**. **MEASURED:** on Android the env is populated from Kotlin via
`SDLActivity.nativeSetenv`, and the analogous texture-dump switch is gated on a
SharedPreference set through the settings UI
(`android/app/src/main/java/com/rfandango/haku_x/MainActivity.kt:100-112`). So
an env-only switch needs a UI toggle plus a Java change — and `MainActivity.kt`
is outside the file boundary I was given. A marker file needs neither, and can
be thrown with one `adb shell touch`. If the marker's first line parses as an
integer it overrides the size cap in MB, so a run can be bounded from adb
without rebuilding.

Everything is read **once**, in `apu_capture_init` (`apu.c:525`), called from
`monitor_init` (`apu.c:639`) after the audio device is up. The per-frame cost
when the capture is off is a single pointer test (`apu.c:321`).

### Properties it was written to have

The brief named four failure modes in the dead code. Each is addressed and
each is covered by the standalone test described in section 5:

| Dead code | This capture |
| --- | --- |
| Relative path `"ep.pcm"`; the guest's cwd is not writable on Android | Defaults to the app's external files dir (`apu.c:437`), where the pgraph harness already writes and `adb pull` reaches without root |
| `assert(fd != NULL)` — an I/O failure kills the run | Never asserts. A failed open logs and disables; a failed write logs, closes and latches off (`apu.c:255-273`) |
| `fopen`/`fclose` per frame, inside the audio path | Opened once, handle held, closed on cap or error |
| Unbounded — a forgotten flag fills the device | Byte cap, default 64 MB ≈ 341 s (`apu.c:226`), overridable |

One property I added: the file is opened `"wb"`, not the dead code's `"a+"`.
Appending would silently splice successive runs into one file whose timeline is
a lie, and a 90-second soak repeated three times would read as one 270-second
capture with two discontinuities in it.

## 2. What the script measures

Per channel, separately, plus a file-level summary:

- **Peak** in LSB and dBFS.
- **RMS** in dBFS, both raw and **with DC removed**. The AC figure is the one to
  compare; a DC offset inflates raw RMS without being audible.
- **DC offset** in LSB, as a percentage of full scale, and in dBFS.
- **Clipping**: the count and percentage of samples at or beyond full-scale
  magnitude (`abs(s) >= 32767`, per the note above).
- **Silence**: per-channel silent flag at < -90 dBFS AC RMS (about 1 LSB), plus
  leading and trailing all-zero durations, plus an all-channels-silent warning.
- **Zeros**: percentage of exactly-zero samples.
- **Per-window RMS distribution**: percentiles (p5/p25/p50/p75/p95) of AC RMS
  over 50 ms windows. This matters more than it looks — see section 4.
- **Accumulator overflow check**: adjacent samples differing by more than full
  scale. This is *not* clipping. The per-voice conversion saturates, but the
  monitor mix then sums voices with `+=` into an `int16_t`
  (`vp.c:1887-1888`), and that accumulator can **wrap** rather than saturate.
  Wrapping flips the sign of a loud sample, which a band-limited 48 kHz signal
  does not do. It is a hint, not a proof — genuinely square content can trip it.
  It is in here because the headroom fix doubles the level going into that
  accumulator, which makes this failure mode strictly more likely than before.

Conventions are stated in the script's docstring because a dBFS figure without
them is meaningless: full scale is 32768, and RMS dBFS is relative to a
full-scale *square* wave, so a full-scale sine reads -3.01 dBFS.

`--compare BEFORE AFTER` reports the delta of every one of those statistics, the
mean and spread across all of them, and whether clipping or wrap suspects
appeared between the two.

## 3. Producing the baseline — what I need run

**Nothing here has been run.** I have no device, no adb and no dispatcher. This
is the part that needs the owner.

The capture file, for wiring into the dispatcher's pull step:

```
/sdcard/Android/data/com.jreinach.hakux.debug/files/apu_monitor.s16le48k2ch.pcm
/sdcard/Android/data/com.jreinach.hakux.debug/files/apu_monitor.s16le48k2ch.pcm.json
```

Please pull both. The `.json` sidecar is small and records the format and the
run's `volume_limit` / `use_dsp`, which is what keeps the PCM interpretable
later.

Arm the capture before the run, and bound it:

```sh
# 30 MB is ~160 s, comfortably more than a 90 s soak.
adb shell 'echo 30 > /sdcard/Android/data/com.jreinach.hakux.debug/files/audio_capture.on'
```

Then the soak as usual:

```sh
request.sh --who audio --title "Galleon (USA).xiso.iso" --seconds 90
```

Then measure:

```sh
python3 docs/testing/audio_measure.py apu_monitor.s16le48k2ch.pcm
```

Disarm afterwards, so a later run does not quietly write 192 KB/s:

```sh
adb shell 'rm -f /sdcard/Android/data/com.jreinach.hakux.debug/files/audio_capture.on'
```

Expect about 17 MB for 90 seconds. In logcat, tag `hakuX-audiocap`, one line at
start and one at stop; if the capture never armed there will be no lines at all,
which is the first thing to check if the pull comes back empty.

**A build caveat that decides which tree to build.** This worktree is at
`aeb4a096b6` and does **not** contain the headroom fix — `git merge-base
--is-ancestor 54a00d28fb HEAD` returns false. That is convenient rather than a
problem: the fix touches only `vp.c` and this capture touches only `apu.c`, so
the two are disjoint and the capture cherry-picks cleanly onto either side of
it. That is exactly what comparison 1 below needs. Build the capture into both
trees; do not try to infer one side from the other.

## 4. What this harness cannot tell us

This is the important section. A measurement that is trusted beyond its range
is worse than none.

- **It is not an accuracy oracle.** It says what level came out, not whether
  that level is *correct*. There is no golden PCM from real hardware, and the
  assessment explains why getting one is hard: the Xbox does not expose its
  internal mix, so a reference means recording S/PDIF off real silicon.
  Everything here is self-consistency and invariants.
- **It cannot compare a desktop capture with an Android capture.** The Android
  build substitutes a stub libsamplerate
  (`android/app/src/main/cpp/samplerate_stub.c`) which **ignores the requested
  converter type** — `src_callback_new` takes `converter_type` and immediately
  discards it (`samplerate_stub.c:22-25`), so the `SRC_SINC_FASTEST` the code
  asks for is not what runs. Desktop and device are running different
  resamplers. Captures from the two are not comparable and must never be used
  as each other's baseline. Every number in a baseline is tied to the platform
  that produced it.
- **It cannot compare two runs sample-for-sample.** Two runs of a title are not
  deterministic, are not frame-aligned, and do not contain identical program
  material. Aggregate and distribution statistics survive that; per-sample or
  per-window-by-index comparison does not. Treat a difference under about 1 dB
  between two device runs as noise. This is also why the percentile columns
  exist: a distribution tolerates misalignment far better than a mean does, so
  a uniform gain shows up as *every percentile moving by the same amount* even
  when the two captures are not aligned.
- **It cannot measure pacing while it is capturing.** The capture writes on the
  audio thread. `/sdcard` is FUSE-backed on Android, and a stall there lands on
  that thread. The write is buffered 256 KB deep (`apu.c:225`) to keep the
  syscall rate near 4/s instead of 187/s, but this is mitigation, not immunity.
  So underrun counts and continuity measured *during a capture* describe the
  capture run, not a normal one. Candidate D in the assessment (FIFO underrun
  zero-fill) needs its own counter, not this file.
- **It cannot hear anything.** No perceptual claim follows from any of it.
  "Sounds right" is not in scope, and neither is "sounds better".
- **It says nothing about DSP scene accuracy, reverb, I3DL2, ParaEQ, HRTF
  coefficients, or envelope curve shapes.** The assessment's section 5 explains
  why each of those has no oracle; none of them is made measurable by this
  harness. A level meter cannot adjudicate a filter bank.
- **It cannot distinguish the two possible shapes of the headroom fix.** Galleon
  programs headroom = 1 on all 31 slots (MEASURED on device, per the
  assessment), so dropping the divisor and compensating after the mix give
  identical output for this title. A capture of Galleon cannot tell them apart;
  only a title that sets slots unequally could.
- **Wrap suspects are a hint.** A non-zero count is evidence of accumulator
  overflow, not proof, and a zero count does not prove the accumulator never
  wrapped — only that it left no full-scale sign flip behind.

## 5. Validation — what I actually verified

**MEASURED**, by running these here:

- `python3 docs/testing/audio_measure.py --selftest` — **51 checks, passed.**
  The oracle is arithmetic on signals whose answers are known independently: a
  full-scale square wave reads 0.00 dBFS RMS; a full-scale sine reads -3.01; a
  half-scale sine reads exactly 6.02 dB below it; clipping and DC counts are
  exact; leading/trailing silence is exact; negative saturation at -32767 is
  counted; a full-scale sign flip is flagged and a loud clean sine is not; and
  the numpy and stdlib backends agree to 1e-9, so the numbers do not depend on
  which one ran.
  - One of those checks failed on the first run. The measurement was right and
    my expected value was wrong (I wrote -9.0206 where the correct figure is
    -9.0312); I confirmed the script's number by computing it a second,
    independent way before touching anything. Recorded because "the test
    failed, so I changed the test" is the shape of a mistake, and in this case
    it happened to be the correct move for a reason that needed checking.
- The capture's C logic was compiled and run standalone against stubs, since a
  worktree cannot build the native side. Extracted verbatim from `apu.c`,
  compiled with `-Wall -Wextra -Wformat=2` with no warnings, and verified:
  off with no env and no marker; armed by a marker file; the marker's contents
  override the byte cap; the byte cap latches the capture off at exactly the
  right block; the bytes on disk match; and an unwritable path disables the
  capture without aborting.
- `python3 docs/testing/check_android_guards.py hw/xbox/mcpx/apu/` — clean, 27
  files. The `__android_log_print` in the capture's log macro is inside
  `#ifdef __ANDROID__`. This check is not optional here: the incident that
  created that script was an unguarded `__android_log_print` added for *audio*
  instrumentation, which broke the desktop link earlier today.
- A rehearsal of the real experiment on synthetic captures: a clean uniform 2x
  gain reports **+6.02 dB on every statistic, spread 0.00 dB, 0 clipped**. The
  same 2x applied to already-hot material reports **mean +5.95 dB, spread 1.00
  dB, 984 clipped**, with the peak shift held down to +5.02 by saturation while
  the quieter percentiles still move the full 6.02. The harness distinguishes
  those two outcomes, which is precisely what comparison 1 has to do.

**Not verified:** anything involving the device or a real title. No capture from
real hardware exists yet.

## 6. The first three comparisons

### 1. The headroom fix: is it +6.02 dB, uniformly, and does it clip?

The fix predicts (assessment, section 9) a uniform **+6.02 dB** with no other
level change, no frequency-response or balance change, and a warning that dense
mixes may now clip where they previously had 2x of margin.

Capture Galleon for 90 s on the device from two builds — the same tree with and
without `54a00d28fb`, the capture cherry-picked onto both — then:

```sh
python3 docs/testing/audio_measure.py --compare before.pcm after.pcm
```

What each outcome means:

- **All statistics shift ~+6.02 dB, small spread, no new clipping** →
  prediction confirmed, on the measurement rather than by ear.
- **Shift near zero** → the fix is inert on this title, contradicting the
  measured `submix_headroom[0..30] = 1`. Believe the capture and re-open the
  question.
- **Shift well under 6 dB *with* new clipping** → the fix works and saturation
  is eating the difference. The assessment already calls this outcome the change
  working and needing a limiter, not the change being wrong. The clip count and
  the held-down peak column are what tell the two apart.
- **Large spread across the statistics** → the change altered the signal's
  shape, not just its level, and "2x louder" is the wrong description of it.
- **Wrap suspects appearing only in the *after* capture** → the doubled level is
  overflowing the `int16_t` accumulator at `vp.c:1887`. That is a new defect
  introduced by the fix, distinct from clean clipping, and it is the reason that
  check is in the script.

Run the capture **twice per side**. A lone anomalous run on this device has
been a one-off band before; two runs per side costs four soaks and removes
that whole class of doubt.

### 2. Full scale in, full scale out

The assessment's highest-value test, and the only one here with a real oracle
that needs no hardware: drive one voice with a known full-scale signal, volume
registers at unity and headroom at 0, and assert the captured PCM comes back at
0 dBFS. **Oracle: the identity of the chain.** Then repeat with headroom set to
`n` — if headroom is meant to be transparent end to end, the output must not
move.

This would have caught every power-of-two error the assessment went looking for,
and unlike comparison 1 it does not depend on what a title happens to program.
It needs a way to drive a synthetic voice, which does not exist yet; that is the
next thing worth building, and it is a bigger job than this harness was.

### 3. Path agreement: VP monitor versus GP/EP

Capture the same title with `use_dsp` off and on and compare levels. **Oracle:
the two paths should agree in loudness to within a dB or so for simple content.**
A large systematic gap is a bug in one of them, and per the assessment's section
1 the VP monitor path — the one the owner is actually listening to, and the one
the code itself says is "not how the hardware works" — is the likely culprit.

This turns candidate A from an inference about register values into a
cross-check between two independent implementations of the same mix, without
needing to know anything about what titles write. Note that the DSP path is
experimental and may not survive a 90-second soak; if it does not, that is a
finding about the DSP path, not a failure of the harness.

## 7. Boundary notes

Files changed here: `hw/xbox/mcpx/apu/apu.c`, plus the two new files
`docs/testing/audio_measure.py` and this document. Nothing else was touched.
`hw/xbox/mcpx/aci.c` and the rest of the APU subtree are within the boundary I
was given but needed no changes.

I read but did not modify `vp.c`, `dsp/gp_ep.c`, `apu_int.h`, `apu_regs.h`,
`android/app/src/main/cpp/samplerate_stub.c`,
`android/app/src/main/java/com/rfandango/haku_x/MainActivity.kt`, and
`hw/xbox/nv2a/pgraph/vk/texture_dump.c` (for the env-var and dump-path
conventions this capture follows).

Not done, as instructed: no build, no device, no push, no CI, no issue edits.
`docs/testing/nv2a_issues.toml` untouched — audio still has no tracker entry,
and this harness does not create one.

One thing I could not do from inside the boundary: give the capture a settings
UI toggle the way the texture dump has one. That needs `MainActivity.kt` and
`SettingsActivity.kt`. The marker file is the workaround and it is arguably
better for harness work anyway — no rebuild to toggle — but if audio capture
ever becomes a routine user-facing feature it should get the same treatment as
the texture dump, and the env-var path is already in place for it.
