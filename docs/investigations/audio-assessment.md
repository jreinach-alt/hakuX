# Audio assessment: first pass over the MCPX APU

Date: 2026-09-12. Branch: `claude/es-de-launcher-disc-error-ojnl14` (isolated worktree).

Audio has had no attention on this project. There is no harness, no golden
reference, no tracker entry and no baseline. This document is therefore an
assessment, not a fix. It exists to make the next person's decisions cheap.

The one concrete symptom, from the device owner, verbatim:

> "Volume seems unusually low, even when turned up to max, and I do not have
> any hints as to what is causing that."

## Method and its limits

Everything below is read from source. I did not build, did not run, and did not
touch the device; I cannot hear the output and nothing here is verified by ear.

Claims are tagged:

- **MEASURED** — a property of the source that I checked by reading it, and
  that anyone can re-check from the cited lines. Symbolic gain through the
  chain counts as measured *on the source*; it says nothing about what a
  running title actually programs.
- **INFERRED** — a conclusion that needs a fact I do not have (usually: what
  value a guest title writes to a register).

Five mechanism claims were retracted on this project in two days for being
presented as fact. I have tried hard not to add a sixth. Where I do not know, I
say so and name the measurement that would settle it.

## 1. The signal path, as built

**MEASURED.** There are two output paths, selected by one config bit.

```
                                   voices (<=256)
                                         |
                        vp.c voice_process()  -- per-voice: envelope, LPF,
                                         |       HRTF, per-bin attenuation
                    +--------------------+--------------------+
                    |                                         |
        mixbins[32][32] (float)                  sample_buf[32][2] (float)
                    |                                         |
        float_to_24b -> GP DSP XRAM                  (VP monitor mix)
                    |                                         |
              GP scene, then EP scene                src_float_to_short_array
                    |                                         |
                    +--------------------+--------------------+
                                         |
                       monitor.frame_buf[256][2]  (int16, 1024 B)
                                         |
                       fifo8  ->  monitor_sink_cb  ->  SDL audio device
                                         |
                                   AAudio (Android)
```

Path selection is `mcpx_apu_update_dsp_preference()`,
`hw/xbox/mcpx/apu/dsp/gp_ep.c:25-45`:

- `use_dsp == true`  -> `MCPX_APU_DEBUG_MON_GP_OR_EP` (gp_ep.c:35). Output comes
  from the GP/EP DSP scenes the title uploads.
- `use_dsp == false` -> `MCPX_APU_DEBUG_MON_VP` (gp_ep.c:39). Output comes from
  the VP monitor mix, and the mixbins are thrown away.

**MEASURED: the device owner is on the second path.** `use_dsp` defaults to
false in three independent places:

- `config_spec.yml:316` — `use_dsp: bool`, no default, so false.
- `android/app/src/main/cpp/xemu_settings_android.cc:90` — `g_config.audio.use_dsp = false;`
- `android/app/src/main/java/com/rfandango/haku_x/SettingsActivity.kt:70` — `"use_dsp" to false`

The UI calls it "Real-time DSP processing ... experimental"
(`ui/xui/main-menu.cc:845`, `android/app/src/main/res/values/strings.xml:261`),
so leaving it off is the expected configuration, not an unusual one.

This matters more than anything else in this document: **the audible path on the
handheld is the VP monitor mix, which the code itself describes as not being how
the hardware works** (`vp.c:1488-1493`):

```c
 * TODO: Are the 2D, 3D and MP voice lists merely a DirectSound
 *       convention? Perhaps hardware doesn't care if e.g. a multipass
 *       voice is in the 2D or 3D list. On the other hand, MON_VP is
 *       not how the hardware works anyway so not much point worrying
 *       about precise emulation here. DirectSound compatibility is
 *       enough.
```

The same point is made from the other side at `gp_ep.c:522-524`: the DSP switch
exists "Until DSP is more performant". The accurate path is the one that is off
by default.

Frame geometry, for reference: `NUM_SAMPLES_PER_FRAME 32`, `NUM_MIXBINS 32`,
`MCPX_HW_MAX_VOICES 256`, `MCPX_HW_MAX_3D_VOICES 64`
(`apu_regs.h:330-334`); `EP_FRAME_US 5333` (`apu_regs.h:363`). One FIFO push is
8 VP frames = 256 stereo int16 = 1024 bytes = 5.333 ms at 48 kHz
(`apu.c:216-231`, `apu_int.h:104`).

## 2. The low-volume symptom

> **Note on the line numbers in this section.** They cite the tree as it was
> when the diagnosis was made, before the fix in section 9. The divisor
> described below at `vp.c:1509` no longer exists; the code that replaced it is
> at `vp.c:1578`. Read this section against the parent of the fix commit, and
> section 9 against the current tree.

### Candidate A — uncompensated submix headroom in the VP monitor mix

**This is the strongest candidate and the only uncompensated gain loss I can
find on the default path.**

The code, `hw/xbox/mcpx/apu/vp/vp.c:1502-1517`:

```c
        float g = 0.0f;
        for (int b = 0; b < 8; b++) {
            if (bin[b] == mp_bin && !debug_isolation) {
                continue;
            }
            float hr = 1 << d->vp.submix_headroom[bin[b]];
            g = fmax(g, attenuate(vol[b]) / hr);
        }
        g *= ea_value;
        for (int i = 0; i < NUM_SAMPLES_PER_FRAME; i++) {
            sample_buf[i][0] += g*samples[i][0];
            sample_buf[i][1] += g*samples[i][1];
        }
```

**MEASURED.** `submix_headroom` is written only from
`NV1BA0_PIO_SET_SUBMIX_HEADROOM` (`vp.c:551-557`), whose payload mask is
`0x7` (`apu_regs.h:157`), so it holds 0..7. It is reset to 0 (`vp.c:1916`).

**MEASURED.** Across the entire APU subtree, headroom is used in exactly three
places and *all three are divisions*:

| site | expression | path |
|---|---|---|
| `vp.c:1469` | `hr = 1 << d->vp.hrtf_headroom` | mixbin, 3D voices, bins 0-3 |
| `vp.c:1471` | `hr = 1 << d->vp.submix_headroom[bin[b]]` | mixbin, all other bins |
| `vp.c:1509` | `float hr = 1 << d->vp.submix_headroom[bin[b]]` | **VP monitor mix** |

There is no multiplication by `1 << headroom` anywhere under `hw/xbox/mcpx/` —
`grep -rn "headroom" hw/xbox/mcpx/apu/` returns only the three sites above plus
the register write, the reset, the two struct fields (`vp.h:85,87`) and the two
vmstate entries (`apu.c:584-585`).

**MEASURED.** In the mixbin path the division has a counterpart: the mixbins go
to the GP DSP (`gp_ep.c:440-447`), and the scene the title uploaded applies its
own gain. Whatever headroom convention the title chose, it also wrote the scene
that undoes it. In the VP monitor path there is no counterpart: `sample_buf`
goes straight to int16 and out, and the mixbins are explicitly discarded one
function later, `vp.c:1891-1892`:

```c
        memset(d->vp.sample_buf, 0, sizeof(d->vp.sample_buf));
        memset(mixbins, 0, sizeof(float[32][32]));
```

**So on the default Android path, output is attenuated by
`2^submix_headroom[bin]` and nothing ever restores it.** Because the divisor is
a power of two, the loss is exactly 6.0206 dB per unit:

| `submix_headroom` | divisor | loss |
|---|---|---|
| 0 | 1 | 0 dB (change is inert) |
| 1 | 2 | 6.02 dB |
| 2 | 4 | 12.04 dB |
| 3 | 8 | 18.06 dB |
| 4 | 16 | 24.08 dB |
| 7 | 128 | 42.14 dB |

That is precisely the "6 dB per bit" signature that reads as *unusually low*
rather than as a subtle error.

**INFERRED, and this is the gap.** I do not know what value titles write. The
reasoning that makes a non-zero value likely: the field is 3 bits wide and the
divisor is a power of two, which means the register's natural unit is 6 dB and
its range is 0..42 dB. A headroom control denominated in 6 dB steps up to 42 dB
is only useful if it is normally non-zero — its whole purpose is to reserve
range in the 24-bit GP mixbuf so that summing many voices into one bin cannot
overflow, and the Xbox APU sums up to 256 voices. I would expect the XDK to
program a non-zero default for the standard mixbins. **I have not verified
this, the evidence is not in this tree, and the fix is worthless if the value
is 0.**

**This is the single cheapest measurement in this whole document and it should
be taken before anything else is changed.** See section 4.

### Candidate B — HRTF headroom disagrees between the two paths

**MEASURED.** For a 3D voice (`v < MCPX_HW_MAX_3D_VOICES`), bins 0-3 are
overwritten with `d->vp.hrtf_submix[0..3]` (`vp.c:1375-1380`). The mixbin path
then uses `hrtf_headroom` for those bins (`vp.c:1466-1469`), but the VP monitor
mix uses `submix_headroom[bin[b]]` for *all* bins including those four
(`vp.c:1509`). The two paths therefore apply different attenuation to the same
voice, and the author flagged the uncertainty in place (`vp.c:1468`):

```c
            // FIXME: Not sure if submix/voice headroom factor in for HRTF
```

`hrtf_headroom` has the same 3-bit payload (`apu_regs.h:159`) and resets to 0
(`vp.c:1913`). HRTF is on by default (`config_spec.yml:317-319`,
`android/app/src/main/cpp/xemu_android.cpp:719-721`), so this affects the
3D voices most titles use for positional audio. Same 6 dB per unit.

### Candidate C — the per-voice headroom field is defined and never read

**MEASURED.** `NV_PAVS_VOICE_CFG_FMT_HEADROOM (0x7 << 13)` is defined at
`apu_regs.h:231` and is read nowhere: `grep -rn "CFG_FMT_HEADROOM" hw/` returns
only the definition. A third 3-bit, 6 dB-per-unit headroom control is parsed out
of the register layout and then ignored.

**INFERRED, direction unknown.** If the hardware attenuates by this field, we
are *louder* than hardware and this is not the symptom. If it is a gain, we are
quieter. I cannot tell from this tree which it is, and I am not going to guess —
but it is the third headroom control in the same register file, all three 3 bits
wide, which is at least consistent with headroom being a normal, non-zero part
of how titles drive this hardware.

### Candidate D — FIFO underrun silently zero-fills

**MEASURED.** `monitor_sink_cb` (`apu.c:277-317`) waits at most 10 x 0.5 ms
= 5 ms for the FIFO to reach the requested byte count, then fills whatever is
missing with silence, `apu.c:315-317`:

```c
    if (copied < free_b) {
        memset(stream + copied, 0, free_b - copied);
    }
```

Nothing counts how often this happens. With the Android defaults
(`apu.c:330-336`: `fifo_frames = 48`, `audio_samples = 2048`) the callback asks
for 8192 bytes at a time while the APU produces 1024 bytes per 5.333 ms, so a
callback needs 8 frames' worth of work to have completed. If the APU thread is
behind, the tail of every buffer is silence.

**INFERRED.** Persistent partial fills reduce output RMS by the duty cycle, so
this *can* present as reduced loudness — but it would normally be heard as
choppiness or crackle first, and the owner reported neither. I rate this a
secondary candidate. It is worth instrumenting regardless, because right now a
chronic underrun is completely invisible; the existing `g_dbg.utilization`
(`apu.c:184-195`) measures APU thread sleep, not output starvation, so a
utilization below 1 does not rule this out.

### Candidate E — the output volume limiter's curve (not the cause at max, but wrong)

**MEASURED.** `apu.c:216-223`:

```c
        if (0 <= g_config.audio.volume_limit && g_config.audio.volume_limit < 1) {
            float f = pow(g_config.audio.volume_limit, M_E);
```

**MEASURED: this is inert at the default.** `volume_limit` defaults to 1
(`config_spec.yml:320-322`) and to 1.0 on Android
(`android/app/src/main/cpp/xemu_android.cpp:722-724`), and the guard requires
`< 1`. So it does not explain "low even at max", and I am recording that as a
negative rather than a lead.

It is still wrong, and it will bite anyone who moves the slider off max. The
exponent is `M_E` — 2.71828 — so a slider the UI labels as a percentage
(`ui/xui/main-menu.cc:840-842` prints `volume_limit * 100` as `%d%%`) behaves as:

| slider label | actual gain | actual dB |
|---|---|---|
| 90% | 0.744 | -2.6 dB |
| 75% | 0.464 | -6.7 dB |
| 50% | 0.152 | -16.4 dB |
| 25% | 0.0231 | -32.7 dB |

A user who nudges the slider to 50% expecting half loudness gets -16 dB. If the
device owner ever moved this control, or if the launcher ever wrote a value
below 1 into `volume_limit`, that alone would produce the reported symptom.
**Worth ruling out by asking the owner what the slider reads and what
`volume_limit` is in their config**, because it costs one question and would
save the rest of this investigation. There is no principled reason for the
exponent to be `e`; a perceptual taper would use a power of 2 to 3 by
convention, or dB directly, and `e` looks like a placeholder that was never
revisited.

## 3. Negatives — things I checked that are clean

Recording these matters as much as the candidates; each one is a place the next
person does not need to look. All **MEASURED**.

| what | where | verdict |
|---|---|---|
| float -> int16 conversion | `android/app/src/main/cpp/samplerate_stub.c:161-196` | Correct. Clips to +/-1.0, scales by 32767. The 32767-vs-32768 difference is 0.0003 dB. Not a lost power of two. |
| float -> 24-bit for the GP mixbuf | `apu/fpconv.h:55-69` | Correct. `value * (8.0 * 0x100000)` is `value * 2^23`, with saturation at both ends. |
| GP monitor 24-bit -> int16 | `apu/dsp/gp_ep.c:466-473` | Correct. `l >> 8` on a 24-bit two's-complement value in a `uint32_t`, assigned to `int16_t`, yields the right signed 16-bit result (0xFFFFFF -> 0xFFFF -> -1). |
| integer -> float sample decode | `apu/fpconv.h:26-53` | Correct at full scale for u8, s16, s24, s32. `int24_to_float` relies on `<< 8` to discard the byte that `ldl_le_p` over-reads; correct, though fragile (see section 6). |
| ADPCM decode level | `apu/vp/adpcm.h:49-141` | Correct. Standard IMA/adpcm-xq step table, output clipped to the full int16 range, then `int16_to_float` (`vp.c:1037-1042`). No halving. |
| mono voices | `vp.c:1083-1085` | Correct. `samples[sample_count][1] = samples[sample_count][0]`, so a mono voice is not silently half-power on one channel. |
| worker mix accumulation | `vp.c:1612-1621`, `1744-1751` | Plain `+=` into the destination. **No divide-by-voice-count and no divide-by-worker-count anywhere.** The "over-cautious headroom divisor on a 256-voice sum" hypothesis is *not* present as a voice-count divisor; it is present only as the programmed headroom of candidate A. |
| worker count of zero | `vp.c:1802-1806` | Safe. `g_config.audio.vp.num_workers` is 0 on Android (`xemu_android.cpp:715-717`) and `voice_work_schedule` does `% vwd->num_workers` (`vp.c:1718-1719`), but `voice_work_init` clamps with `MAX(1, MIN(num_workers, MAX_VOICE_WORKERS))` at `vp.c:1806` first, so there is no division by zero. |
| per-voice volume decode | `vp.c:93-97`, `apu_regs.h:296-310` | Consistent. Fields are 12 bits; `attenuate()` treats the value as attenuation in 1/64 dB, `0` = unity, `0xFFF` = silence. Range 0 to -64 dB. |
| AC'97 codec volume | `hw/xbox/mcpx/aci.c` (whole file) | **Not in the path at all.** ACI is a thin wrapper that hands its two BARs to the generic `ac97_io_nam_ops` / `ac97_io_nabm_ops` and calls `ac97_common_init` (aci.c:43-69). It has no volume code of its own; the codec's mixer registers live in `hw/audio/ac97_int.c`. The APU never consults them — `ep_sink_samples` returns `false` for `MCPX_APU_DEBUG_MON_AC97` (`gp_ep.c:183-184`), and the APU opens its own SDL device (`apu.c:355-359`). So ACI's master/PCM volume cannot be attenuating anything. If anything this is a fidelity gap in the *loud* direction: a title that lowers AC'97 master volume is not obeyed. |
| Android platform stream attenuation | `thirdparty/SDL2/src/audio/aaudio/SDL_aaudio.c:115-124` | Clean. The builder sets sample rate, channels, device id, direction, format and performance mode, and never calls `setUsage` or `setContentType`, so AAudio uses its defaults of `AAUDIO_USAGE_MEDIA` / `AAUDIO_CONTENT_TYPE_MUSIC`. Those are the full-loudness defaults; there is no wrong stream type here. |

The last two are the ones I most expected to find a bug in, and did not. On
Android, "quiet even at max" is very often a wrong AAudio usage or a codec
mixer left at a low default. Neither applies here. That is what pushes
candidate A to the front.

## 4. What to measure, in order

The first three are cheap and answer the question. Do them before changing
anything.

1. **Read back `submix_headroom` and `hrtf_headroom` on a running title.**
   This decides candidate A outright. There is no current way to see these
   values: `grep -n "headroom" hw/xbox/mcpx/apu/apu_debug.h hw/xbox/mcpx/apu/debug.c`
   returns nothing, so the audio debug UI does not expose them. The cheapest
   instrument is a one-shot log in the register write handler at `vp.c:548-557`,
   firing only when a value changes. Expected outcome if candidate A is right:
   non-zero values on the bins the title's voices feed.
   - If all values are 0, candidate A is dead and the loudness is elsewhere.
     Record that as a finding, not a failure.
2. **Ask the owner for `volume_limit` from their config, and what the slider
   reads.** One question, rules out candidate E, costs nothing.
3. **Count the underruns at `apu.c:315`.** A counter incremented when
   `copied < free_b`, plus the shortfall in bytes, surfaced next to the existing
   `g_dbg.utilization`. Decides candidate D. Expected outcome if D is not the
   cause: a near-zero count during steady playback.

## 5. The harness

Graphics accuracy works on this project because golden framebuffers dumped from
real XBOX 1.0 silicon exist, and a captured frame is a pure function of the
commands that produced it. Audio has neither property in the same degree, and
being honest about that is the point of this section.

### Where to tap

**An APU-side PCM dump, not a microphone.** Recording the handheld's speaker
would fold in the speaker response, the enclosure, AAudio's resampler, the
platform volume curve and the room; none of that is under test and all of it
moves between runs.

The tap point already exists, commented out, at `apu.c:205-212`:

```c
#if 0
        FILE *fd = fopen("ep.pcm", "a+");
        assert(fd != NULL);
        fwrite(d->apu_fifo_output, sizeof(d->apu_fifo_output), 1, fd);
        fclose(fd);
#endif
```

Note the dead symbol: `d->apu_fifo_output` (`apu.c:213`) no longer exists in
`MCPXAPUState` (`apu_int.h:73-108`) — the buffer is now `d->monitor.frame_buf`.
This block has not compiled since the monitor struct was introduced, which is
itself a small piece of evidence for how long audio has gone unexercised.

The right tap is `monitor.frame_buf` immediately before the FIFO push at
`apu.c:225-230`: one funnel, after every output path has converged, 1024 bytes
per 5.333 ms, already int16 stereo 48 kHz. Everything downstream of it is
platform plumbing we do not want in the measurement. Reopening the file per
block as the dead code did is wrong; hold the handle, and gate it on an
environment variable so a normal run pays nothing.

Cost: small — one file handle, a write of 1 KB per 5.33 ms (192 KB/s, 11.5
MB/min), and it lives entirely in `apu.c`, which this work stream owns.

### What the reference would be

This is where audio is genuinely harder than graphics, and I want to be blunt
about it rather than optimistic.

- **No reference exists today.** There is no equivalent of the framebuffer
  goldens. Producing one means capturing PCM off real hardware, and the Xbox
  does not hand you its internal mix — you would be recording its analog or
  S/PDIF output. S/PDIF is the only tap that is bit-exact in principle.
- **Even with a capture, sample-exact comparison is not available.** The DSP
  scenes are guest code; timing, frame boundaries and the resampler phase all
  differ. Any comparison has to be on aggregate or spectral properties, not
  per-sample equality. That is a weaker oracle than a framebuffer diff and it
  will not catch the class of small errors the graphics harness catches.
- **What *is* available without any hardware reference at all** is the class of
  self-consistency and invariant checks below. These have real power against
  exactly the bug class in section 2, because a gain error is visible as a
  level, and a level needs no golden.

### First three things worth measuring

Ordered by value per unit of effort, and all three have an oracle that does not
require a hardware capture:

1. **Full-scale level through the chain.** Drive one voice with a known
   full-scale signal (a synthetic S16 buffer at +/-32767, or a 1 kHz sine at
   0 dBFS) with volume registers at unity and headroom at 0, and assert the
   dumped PCM comes back at 0 dBFS within the resampler's error. **Oracle: the
   identity of the chain — full scale in, full scale out.** No hardware needed.
   This single test would have caught every power-of-two error I checked for in
   section 3, and it directly measures candidate A: run it again with headroom
   set to `n` and the output must not change if headroom is meant to be
   transparent end to end.
2. **Path agreement between VP monitor and GP/EP.** Play the same voice
   configuration with `use_dsp` off and on and compare output levels. **Oracle:
   the two paths should agree in loudness to within a dB or so for a simple
   voice.** A large systematic gap is a bug in one of them, and given section 1
   it is very likely the VP path. This is the test that turns candidate A from
   inference into a measurement without knowing anything about what titles
   write.
3. **Underrun and continuity accounting.** For a fixed-length run, assert the
   sample count out matches the wall time, and that the zero-fill at
   `apu.c:315-317` never fires during steady playback. **Oracle: arithmetic.**
   This covers candidate D and the whole class of pacing regressions, which is
   the class most likely to be silently reintroduced by the throttle logic at
   `apu.c:113-173`.

### What has no oracle, and should not be pretended into one

- **DSP scene accuracy.** The GP and EP scenes are guest DSP code run on the
  emulated 56300-family core in `dsp/dsp_cpu.c`. Correctness there is a CPU
  emulation question, not an audio question, and it wants instruction-level
  tests against the DSP's documented semantics, not PCM comparison. 73 of the
  145 flagged sites in the subtree are in that one file (section 6), and 81
  opcodes in its dispatch table are unimplemented outright.
- **Reverb, I3DL2 and ParaEQ.** Not implemented (`vp.c:1462` `// FIXME: ParaEQ`).
  There is nothing to compare.
- **HRTF filter coefficients.** `vp/hrtf.h` carries a filter bank; whether it
  matches the hardware's is not answerable without a hardware capture designed
  for it, and the parameter smoothing is an invented coefficient
  (`hrtf.h:78` `// FIXME: Match hardware parameter transition`).
- **Envelope curve shapes.** The author left explicit uncertainty in place
  (`vp.c:766-767` "This formula and threshold is not accurate, but I can't get
  it any better for now"; `vp.c:804-811`, four consecutive FIXMEs on the release
  curve). These are audible as attack/decay character. Measuring them needs a
  hardware capture of a single voice with a known envelope, which is a
  well-defined experiment but needs hardware.
- **Anything perceptual.** "Sounds right" is not a test. I cannot hear the
  device and no harness proposed here can either.

## 6. Known-issues inventory

145 sites in the subtree are flagged `FIXME`, `TODO`, `XXX` or `HACK`
(excluding the two generated DSP includes `dsp_emu.c.inc` and `dsp_dis.c.inc`,
which add 140 more). By file:

| file | flagged sites |
|---|---|
| `apu/dsp/dsp_cpu.c` | 73 |
| `apu/vp/vp.c` | 53 |
| `apu/dsp/dsp_dma.c` | 6 |
| `apu/vp/vp.h` | 4 |
| `apu/apu.c` | 3 |
| `apu/apu_regs.h` | 2 |
| `apu/vp/hrtf.h`, `apu/dsp/dsp.c`, `apu/dsp/gp_ep.c`, `aci.c` | 1 each |

The distribution is itself the headline: half the flags are in the emulated DSP
core, and the next largest group is the voice processor. Detail follows in the
order a reader should care about it.

### On the hot path — affects every sample

- `vp.c:1468` — `// FIXME: Not sure if submix/voice headroom factor in for HRTF`.
  Candidate B above. Affects every 3D voice, every frame.
- `vp.c:1462` — `// FIXME: ParaEQ`. The parametric EQ stage is absent. `fmode`
  values 2 and 3 select ParaEQ (`vp.c:1425-1432`) and those voices simply get no
  EQ at all.
- `vp.c:1409-1410` — `// FIXME: If phase negations means to flip the signal
  upside down / we should modify volume of bin6 and bin7 here.` Bins 6 and 7
  carry a phase-negation semantic that is not implemented.
- `vp.c:1435` — `// FIXME: Cutoff modulation via NV_PAVS_VOICE_CFG_ENV1_EF_FCSCALE`.
  The low-pass cutoff is taken straight from `NV_PAVS_VOICE_TAR_FCA_FC0`;
  envelope modulation of it is dropped.
- `vp.c:868` — `NV_PAVS_VOICE_CFG_FMT_LINKED); /* FIXME? */`. The `linked` flag
  is read and pushed to the debug struct (`vp.c:901`) but **never acted on**.
  Linked voices are effectively unimplemented.
- `vp.c:1162-1167` — the resampler note: "Unsure about hardware's actual
  interpolation method; it could just be linear, in which case using this
  resampler is overkill", plus `// FIXME: Don't do 2ch resampling if this is a
  mono voice`.
- `apu_regs.h:336` — `#define ADPCM_SAMPLES_PER_BLOCK 64 // FIXME: Should be 65?
  Check interpolation`. Used at `vp.c:1011-1012` to derive `block_index` and
  `block_position` for every ADPCM sample; note `vp.c:886` sizes its decode
  buffer as `adpcm_decoded[65*2]`, so the two numbers already disagree. If 65 is
  right, every ADPCM voice is mis-indexed.
- `apu_regs.h:81` — `NV_PAPU_GPOFBASE0_VALUE 0x00FFFFFF // FIXME: Use ffff00
  mask but shift appropriately`. This one constant governs every GP and EP FIFO
  base/end/cur access (`gp_ep.c:148-162`, `:203-217`), i.e. where every output
  frame is placed.
- `apu_regs.h:231` — `NV_PAVS_VOICE_CFG_FMT_HEADROOM` defined, never read.
  Candidate C above.
- `hrtf.h:78` — `// FIXME: Match hardware parameter transition`, on a one-pole
  glide with an invented coefficient, re-evaluated for all 32 HRIR taps on every
  sample of every 3D voice (`hrtf.h:94-99`).

### Envelope generator — audible character, nine unresolved questions

All in `vp.c`, all on the hot path for any voice with an envelope. This is the
densest cluster of admitted guesswork in the tree:

- `vp.c:689` — `// FIXME: Confirm this?` on forcing level to 0 in DELAY.
- `vp.c:709-711` — `// FIXME: [division by zero] / Got crackling sound in
  hardware for amplitude env.` Attack rate 0 is clamped to full level.
- `vp.c:716-718` — `// FIXME: Overflow in hardware / The actual value seems to
  overflow, but not sure how.`
- `vp.c:722` — `// FIXME: Comparison could also be the other way around?! Test
  please.` The attack-to-hold transition test; an off-by-one here shifts every
  envelope.
- `vp.c:728-729` — `// FIXME: Skip next phase if count is 0? [other instances too]`
- `vp.c:761` — `// FIXME: Decay should return a value no less than sustain`, and
  a decay rate of 0 returns `value = 0.0f`, i.e. one frame of full silence
  before the state machine advances to sustain.
- `vp.c:766-767` — `// FIXME: This formula and threshold is not accurate, but I
  can't get it any better for now`, above a magic-constant curve fit
  `255.0f * powf(0.99988799f, ...)`.
- `vp.c:772` — `// FIXME: Should we still update lvl?`
- `vp.c:787` — `// FIXME: is this only set to 0 once or forced to zero?`
- `vp.c:804-811` — four consecutive FIXMEs on the release curve: unsure about
  the actual curve, unsure whether it is based on sustain level or current
  level, unsure whether to update level, and (`vp.c:815`, echoing `vp.c:277`)
  unsure whether the count ascends or descends. The chosen approximation is
  `powf(M_E, -6.91*pos)*lvl`, a T60 decay.

### Registers written by the guest and silently dropped

These are the ones that worry me most after the loudness question, because a
dropped write is invisible:

- `vp.c:454-460` — `NV1BA0_PIO_SET_OUTBUF_BA` x4. The entire body is a
  `DPRINTF` inside `#ifdef DEBUG_MCPX`, so in a normal build this is
  `case ...: break;`. Carries `//assert(false); //FIXME: Enable assert! no idea
  what this reg does`.
- `vp.c:462-468` — `NV1BA0_PIO_SET_OUTBUF_LEN` x4, same pattern, same comment.
- `vp.c:655-656` — `vp_write` `default: break;` for every unlisted VP method.
- `vp.c:583-585` — `NV1BA0_PIO_FREE` returns a constant `0x80`:
  "we don't simulate the queue for now, pretend to always be empty". The FE
  method FIFO is not modeled, so the guest never sees backpressure. The
  counterpart is `vp.c:645` `/* TODO: these should instead be queueing up fe
  commands */`.
- `vp.c:590` — `vp_read` returns a constant 0 for every other VP address.
- `apu.c:93-97` and `apu.c:56-58` — writes at offset >= 0x20000 are dropped and
  reads return 0, with no log.
- `gp_ep.c:341-342`, `:382-384`, `:426-427` — GP and EP register writes outside
  the known windows are stored into a raw byte-indexed array and never
  interpreted; reads come back from the same array unvalidated.
- `dsp.c:112-136` — `write_peripheral` has no `default:`; unknown DSP peripheral
  writes vanish. `dsp.c:80` — `read_peripheral` likewise has no `default:` and
  returns the magic value `0xababa`.

### Structural and lifecycle

- `aci.c:77` — bare `// FIXME` inside `vmstate_mcpx_aci`, whose field list is
  `VMSTATE_PCI_DEVICE` and nothing else. **The embedded `AC97LinkState` is not
  migrated**, so save/load silently corrupts AC'97 state.
- `apu.c:424` — `// FIXME: Reset DSP state`. `mcpx_apu_reset` zeroes `d->regs`
  and the two `pram_opcache` arrays but does **not** reset the GP/EP DSP core
  registers, XRAM/YRAM/PRAM or DMA state. A guest reset leaves stale DSP state
  still feeding the output path.
- `apu.c:419` — `// FIXME: Can fail if thread is pegged, add flag` on the mutex
  acquire in `mcpx_apu_reset`. A reset while the APU thread is saturated can
  block.
- `apu.c:205-212` — the dead PCM dump block referencing the removed
  `d->apu_fifo_output`. Does not compile if enabled. See section 5.
- `apu.c:355-359` — `SDL_OpenAudioDevice` is called with
  `SDL_AUDIO_ALLOW_FORMAT_CHANGE` and `obtained_audio_spec.format` is never
  checked. Because the change is *allowed*, SDL installs no converter; if the
  backend returned `AUDIO_F32SYS`, the int16 bytes in `frame_buf` would be
  reinterpreted as floats. **Not the reported symptom** — misread int16 pairs
  become huge floats that clip, so it would be loud noise, not quiet — but it is
  an unchecked assumption on the output format. Either drop the flag so SDL
  converts, or assert the obtained format. In practice
  `SDL_aaudio.c:119-122` requests `AAUDIO_FORMAT_PCM_I16` and AAudio honours
  I16 universally, so the hazard is latent rather than live.
- `apu.c:358-361` — `sdl_audio_dev` is a local and is never stored, so the audio
  device is never closed or paused on teardown.
- `apu.c:53` — `r = qemu_clock_get_ns(QEMU_CLOCK_VIRTUAL) / 100; //???`. The
  `NV_PAPU_XGSCNT` global sample counter is synthesized from the QEMU virtual
  clock with a guessed divisor rather than derived from frames actually
  produced. Guest timing code reads this.
- `gp_ep.c:424` — `d->ep_frame_div = 0; /* FIXME: Still unsure about frame sync */`.
  `ep_frame_div` decides which frames run the EP DSP (`gp_ep.c:480`) and where
  monitor samples land (`gp_ep.c:466`), so a wrong reset point shifts the EP/GP
  phase for all subsequent output.
- `gp_ep.c:168-172` vs `:232-238` — the GP side **asserts** `cur < end` while
  the EP side wraps with `cur = cur % (end - base)`. Two different guesses at
  the same hardware behaviour, in the same file.
- `vp.c:528-529` — `// FIXME: Entries are 64b, assuming they are stored / like
  this <[offset,length],...>`. The SSL segment table layout is a guess, decoded
  at `vp.c:953-961` for every streaming voice segment.
- `vp.c:971` — `ebo = seg_len - 1; // FIXME: Confirm seg_len-1 is last valid
  sample index`. Off-by-one risk at every SSL segment boundary.
- `vp.c:1020` — `// FIXME: Use idiomatic DMA function`; the streaming ADPCM
  block read is a raw `memcpy` from `d->ram_ptr`, bypassing the QEMU DMA API and
  its bounds and dirty-tracking checks.
- `vp.c:1006` — `// FIXME: Restructure this loop`, on the main per-sample decode
  loop itself.
- `vp.c:1141-1146` — resampler starvation silently substitutes a frame of zeros
  ("Starvation causes SRC hang on repeated calls. Provide silence.").
- `vp.c:1686-1700` — a `TODO` block documenting three assumptions about
  multipass submix scheduling that are enforced by `assert()` rather than
  handled: MP bin constant, MP voice always clears MP bin, MP source voices
  ordered consecutively. A title violating any of them aborts the emulator
  rather than mis-mixing.
- `vp.h:82`, `:94`, `:101`, `:102` — four `// FIXME: Where are these stored?` /
  `// FIXME: Stored in RAM` notes. `ssl_base_page`, the whole `ssl[]` array,
  `hrtf_headroom`, `hrtf_submix[]`, `submix_headroom[]`, the HRIR coefficient
  table and the inbuf/outbuf SGE handles all live in host-side struct fields
  because their real guest location is unknown. **Note that this includes both
  headroom values from candidate A and B** — they are invisible to the guest and
  only partly covered by savestates.
- `fpconv.h:52` — `int24_to_float` calls `ldl_le_p` (a 4-byte load) on a 3-byte
  container at `vp.c:1067-1068`, reading one byte past the sample. The `<< 8`
  discards it, so the value is correct, but the read itself is out of bounds by
  one byte at the end of a buffer.

### Emulated DSP core

73 flagged sites in `dsp/dsp_cpu.c`, 6 in `dsp/dsp_dma.c`, 1 in `dsp/dsp.c`.
**This subtree only matters when `use_dsp` is on, which is not the default on
any platform** (section 1), so it is lower priority than `vp.c` despite having
more flags. The two findings worth carrying forward now:

- `dsp_cpu.c:181-335` — **81 opcode table rows have `NULL, NULL` for their
  disassemble and emulate handlers**, i.e. wholly unimplemented instructions
  (`brclr`/`brset`/`bsclr`/`bsset` in all forms, `bscc`, `eor #xxxx,D`,
  `jclr`/`jset`/`jsclr`/`jsset` qq forms, `lra`, `maci`, `macri`, `mpyri`,
  `plockr`, `punlockr`, and others). The dispatcher at `dsp_cpu.c:631-635` logs
  under `DPRINTF` and then calls `emu_undefined`, which burns 100 fake cycles
  and continues. In a release build that is **completely silent**, and any
  shipped microcode using one would quietly mangle audio from then on.
- `dsp_cpu.c:957` — `return 0x00FFFFFF; // FIXME: What does the DSP actually do
  in this case?` An out-of-bounds X-space read prints to stderr and hands the
  DSP a placeholder. On the hot path for every DSP memory operand.

Enumerating the remainder is a separate exercise and should be scoped as its own
issue rather than folded into the loudness work.

## 7. Recommendation

> **Superseded by section 9.** Candidate A was confirmed on hardware and the fix
> has since landed. This section is kept as written, because the prediction it
> makes is what section 9 is measured against.

No code change is made in this commit. Candidate A is the best-supported
explanation of the symptom, and the mechanism is measured, but it turns on one
fact I do not have — the value titles write to `SET_SUBMIX_HEADROOM` — and if
that value is 0 the fix is inert. Changing gain in the dark, on a symptom I
cannot hear, against no baseline, is how the retracted mechanism claims on this
project happened.

The order I would take it:

1. Instrument the two headroom registers (section 4, item 1) and read them on a
   real title. One log line in `vp.c:548-557`, inside files this stream owns.
2. Confirm `volume_limit` is 1.0 on the owner's device (section 4, item 2).
3. If headroom is non-zero, remove the `/hr` from the VP monitor mix at
   `vp.c:1509` only, leaving the mixbin path at `vp.c:1466-1476` untouched
   because the DSP scene compensates there.

**Falsifiable prediction for that change, stated now, before any measurement.**
If the title programs `submix_headroom = H` on the bins its voices feed, then
removing the divisor at `vp.c:1509`:

- raises output amplitude by exactly `2^H`, i.e. 6.0206 x H dB, uniformly
  across all content;
- changes no frequency response, no timing, and no relative balance between
  voices that share a headroom value;
- changes relative balance *between* bins only where those bins were given
  different headroom values;
- is bit-identical to today's output if H is 0 for every bin in use;
- may introduce clipping at `samplerate_stub.c:168-185` in dense mixes that
  previously had `2^H` of margin. If the symptom becomes distortion rather than
  quietness, that is this change working and needing a limiter, not this change
  being wrong.

Also worth filing independently of the loudness work, because each is a defect
on its own terms: the `pow(x, M_E)` volume curve (candidate E), the missing
underrun accounting (candidate D), the unmigrated ACI state (`aci.c:77`), the
DSP state not reset on guest reset (`apu.c:424`), the silently dropped
`SET_OUTBUF_BA`/`SET_OUTBUF_LEN` writes (`vp.c:454-468`), the unchecked SDL
output format (`apu.c:355-359`), and the never-closed audio device.

## 8. Boundary notes

This stream owns `hw/xbox/mcpx/apu/**` and `hw/xbox/mcpx/aci.c`. Findings that
point at files it does not own were deliberately left as reports:

- `android/app/src/main/cpp/samplerate_stub.c` — the Android build substitutes a
  stub libsamplerate. `src_callback_read` (line 94) is **linear interpolation**,
  not the `SRC_SINC_FASTEST` that `vp.c:1166` asks for; the `converter_type`
  argument is discarded at `samplerate_stub.c:25`. This is a resampling-quality
  difference, not a loudness one — linear interpolation of a pitched voice adds
  aliasing and a slight high-frequency roll-off. It means desktop and Android
  do not resample identically, so **any audio golden captured on one platform is
  not valid for the other**. That constrains the harness in section 5 and should
  be recorded before anyone captures a reference.
  `src_float_to_short_array` in the same file is correct (section 3).
- `android/app/src/main/cpp/xemu_android.cpp:715-724` and
  `xemu_settings_android.cc:90` — where the Android audio defaults
  (`num_workers = 0`, `use_dsp = false`, `hrtf = true`, `volume_limit = 1.0`)
  are actually set.
- `thirdparty/SDL2/src/audio/aaudio/SDL_aaudio.c:115-124` — checked and clean;
  no `setUsage`/`setContentType` call, so AAudio's MEDIA/MUSIC defaults apply.
- `ui/xui/main-menu.cc:840-842` — the volume slider that feeds candidate E's
  `pow(x, M_E)` curve, and where the misleading `%d%%` label is printed.
- `hw/audio/ac97_int.c` — where the AC'97 codec's own volume registers live.
  Section 3 establishes they are not in the output path, so no change is
  proposed, but this is the file anyone chasing codec volume should open.

`ui/sdl2.c` was **not** implicated: the APU opens its own SDL audio device at
`apu.c:355-359` and does not route through the UI's audio path at all.

## 9. Resolution: candidate A confirmed and fixed

### The measurement that closed the gap

**MEASURED, on hardware, not by me.** The coordinator added the one-shot log
proposed in section 4 at the `SET_SUBMIX_HEADROOM` write site and booted Galleon
for 90 seconds on the Nova:

```
submix_headroom[0..30] = 1
```

All 31 slots written, every one of them 1, set once at startup, no slot left at
zero. That is the fact section 2 was missing. The divisor at the monitor mix was
live at exactly 2x, i.e. **−6.02 dB uniformly**, and the fix is not inert.

The coordinator separately confirmed that `volume_limit` is 1.0 and that the
`< 1` guard makes `apu.c:218` genuinely inert at maximum volume, so candidate E
is excluded at max rather than merely unlikely. With the ten negatives of
section 3 standing, there is no second uncompensated divisor competing for the
explanation.

### What changed, and what deliberately did not

Two sites, both confined to the monitor path:

1. **`voice_process`, the monitor mix** — the `/hr` divisor is **dropped**, so
   the per-bin selection is now `g = fmax(g, attenuate(vol[b]))`.
2. **`get_multipass_samples`** — the mixbin read is **compensated** by
   `1 << submix_headroom[mp_bin]`, guarded on
   `monitor.point == MCPX_APU_DEBUG_MON_VP`.

**Why drop at site 1 rather than compensate after the mix.** The coordinator
asked for the shape that stays correct if slots are ever set unequally, and
these differ exactly there. The attenuation is applied per voice and per bin, so
its inverse belongs in the same place. A single post-mix scale would have to
pick one headroom value for a sum that may draw on bins carrying different ones,
and there is no correct choice of scalar in that case — max, min and mean are
all wrong for some voice. Galleon sets all slots equal, so this capture cannot
distinguish the two shapes; dropping is the one that remains right when a title
does not. Dropping also restores the intent of the `fmax`, which is to pick the
loudest bin a voice actually uses: with the divisor in place, a quieter bin could
win the selection merely by having less headroom.

**Why site 2 was needed at all.** This is a residual that only appears once site
1 changes, and it is the reason the fix is two lines rather than one. Multipass
sub-voices are deliberately skipped in the monitor mix to avoid double-counting
them; their audio reaches the output *only* by being read back out of
`mixbins[mp_bin]` by the destination voice. That mixbin was filled by the
mixbin loop, which still divides. So had site 1 changed alone, direct content
would have risen 6.02 dB while multipass-routed content stayed put — a 6 dB
shift in the balance between dry and submixed audio, which is a new defect, not
a fix. Compensating at the read follows the hardware's own convention, that
whoever reads a submix earns the headroom back, and it uses that bin's own
value, so it too stays correct when slots differ.

**`vp.c:1521` and `:1523` are deliberately unchanged, and should stay that way.**
Asked explicitly: **only the monitor-path sites should change.** Those two lines
feed `mixbins[]`, which is the sole input to the GP DSP, and on that path the
scene the title uploaded earns the divisor back when it reads the bin. Removing
them would double the level going into the 24-bit mixbuf and risk overflowing it
— which is the exact failure headroom exists to prevent. `:1521` (the HRTF
divisor) additionally carries an unresolved question of its own, recorded as
candidate B, that this change does not touch and does not depend on.

### Evidence that the change cannot reach the DSP path

Asked for as evidence bar item 2. For site 1 this is a containment proof, not an
argument:

- The edited statement's only effect is the value of `g`, which is used only at
  the two `sample_buf[i][...] +=` lines immediately below.
- `d->vp.sample_buf` is written in exactly two places, both inside
  `monitor.point == MCPX_APU_DEBUG_MON_VP` guards (the per-voice mix, and the
  worker accumulation in `voice_worker_thread`), and **read in exactly one**:
  `src_float_to_short_array` in `mcpx_apu_vp_frame`, also inside that guard.
  `grep -n "sample_buf" hw/xbox/mcpx/apu/vp/vp.c` enumerates every reference.
- The GP DSP's sole input is `mixbins[]`, written to DSP XRAM via
  `float_to_24b` in `mcpx_apu_dsp_frame` (`gp_ep.c:446`).
- `sample_buf` and `mixbins` are disjoint buffers, and the mixbin loop is not
  touched.

So no value the DSP consumes can change. Site 2 is different and needs the
guard rather than a proof: `get_multipass_samples` writes `samples[][]`, which
*does* feed the mixbin loop and therefore the DSP, so the compensation is
explicitly conditioned on the monitor point. That guard is load-bearing, not
cosmetic — without it this edit would alter the DSP path.

Note that the correct gate is `monitor.point`, not `use_dsp`: the desktop debug
UI can force a monitor point directly via `mcpx_apu_debug_set_monitor`
(`ui/xui/debug.cc:206`, `debug.c:61-63`), so a build with `use_dsp` on can still
be listening to the VP monitor mix. Both sites key off `monitor.point`, so both
behave correctly in that configuration too.

### Prediction

Stated before any listening, as evidence bar item 1. With all 31 slots at 1:

- The monitor mix comes out **2x louder, +6.02 dB**, uniformly across all
  content — dry and multipass alike, since site 2 keeps them in step.
- **No other level in the chain moves.** The DSP path, the GP and EP monitor
  taps, and the AC'97 path are all untouched, per the containment proof above.
- No change to frequency response, timing, stereo balance, or the relative
  balance between voices.
- Bit-identical output for any title that leaves every slot at 0.
- Relative balance between bins changes only if a title sets slots unequally,
  which Galleon does not.
- Dense mixes may now clip at the `+/-1.0` clamp in
  `src_float_to_short_array`, having previously carried 2x of margin. **If the
  symptom becomes distortion rather than quietness, that is this change working
  and needing a limiter, not this change being wrong** — and the right response
  is a limiter or a headroom-aware master scale, not restoring the divisor.

### Status: UNVERIFIED BY EAR

**This has not been listened to, and I cannot listen to it.** It is not built,
not run, and not heard; I have no device access and no audio oracle. What is
verified is the source reasoning and the register capture. The only oracle
available until the PCM-tap harness of section 5 exists is a human listening to
the device, and that has not happened yet.

Two further caveats worth holding onto:

- Multipass (site 2) is the less-exercised path, and I do not know from the
  capture whether Galleon uses multipass voices at all. If it does not, site 2
  is inert for that title and untested by the listening check — it is there so
  that titles which *do* use it are not left 6 dB out of balance.
- The compensation at site 2 uses `submix_headroom[mp_bin]`. For a 3D voice
  whose bins 0-3 are remapped to `hrtf_submix[]`, the mixbin loop attenuates by
  `hrtf_headroom` instead (`vp.c:1521`), so if an HRTF submix bin were ever also
  used as a multipass bin the two would disagree. DirectSound puts the multipass
  bin at 31 and the HRTF submixes elsewhere, so this does not arise in practice,
  but it is the seam to look at first if multipass audio comes out wrong.
