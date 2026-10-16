# lane.audio1016 NOTES -- quiet speech and movie audio (#984, #938)

Status: 2026-10-16. Mechanism measured offline on MKSM; fix written behind a switch
(`vp.c.patch`); five Nova runs on one binary registered in
`docs/testing/predictions/audio1016-identify.json` and queued.

[lane.audio1016] waiting: the five audio1016-identify runs on the Nova (request ids under
"Runs" below). Resolves when their results are in; then judge the legs and mark ready.

NEED: `hw/xbox/mcpx/apu/vp/vp.c` (lane.x1port1012's file): apply
`docs/lanes/audio1016/vp.c.patch` (HAKUX_APU_MONVP_DOWNMIX, off by default). It touches only
the MON_VP block of voice_process() and adds a table after attenuate(); it does not overlap
x1port1012's changes.

## The question

The whole mix is at a normal level (MKSM session acrms -25 dBFS, peak -0.5), but some voices
are quiet: movie audio and speech. The September work (audio-assessment.md, audio-harness.md,
audio-baseline.md, audio-headroom-verified.md, audio-voice-headroom.md,
audio-savestate-and-monitor-accumulator.md) looked for a gain missing from the whole mix and
did not look per voice. That work is not redone here.

On Android the default is `use_dsp = false`. What the player hears is the VP monitor mix
(`MON_VP`, `vp.c` voice_process, after the mixbin loop): per voice,
`g = max over the voice's 8 bin slots of attenuate(vol[b])`, times the envelope, into L from
channel 0 and R from channel 1. There is no headroom divisor, which September removed after
measuring +6.02 dB on Galleon. The mixbins are computed, and the GP/EP DSP program that would
mix them is not run for output.

## Measured

### Shrek 2 (41560037): DreamWorks logo movie vs the disc source

Emulator output (owner run, logcat level meter, plus the movie's PCM pulled off the disc with
`tools/xiso_ls.py` and `tools/pcm_windows.py`), aligned windows:

| Segment | Source L / R (dBFS RMS) | Emulator L / R (dBFS RMS) | Loss (dB) |
|---|---|---|---|
| 0-4.5 s | -37.7 L | -45.16 / -48.33 (13.7% of samples zero-fill) | ~7.5 |
| 4.5-9.5 s | -34.4 / -37.2 | -41.98 / -44.57 | 7.6 / 7.4 |

Peaks are about 6 dB down too. Menu music in the same run plays at -20 dBFS. Both channels
lose the same amount, so the loss is a gain and not a dropped channel.

### MKSM (4D570029): the owner's save state in the Goro's Lair cutscene

`/mnt/d/hakux-staging/ownerplay-1014/mksm-state/slot0.hxs`
(sha256 d493eba3...ab83) is the scene the owner complained about (Raiden's voice).
`tools/hxs_unpack.py` unpacks it and `tools/hxs_voices.py` walks the voice lists in guest RAM.
Five voices are active:

| v | list | fmt | type | Hz | eg | bin slot: vol (dB) | MON_VP g (dB) | source RMS / peak L, R (dBFS) |
|---|---|---|---|---|---|---|---|---|
| 64-67 | 2D | mono B16/S16 | loop, 32 frames | 48000 | off | all slots -6.0 | -6.0 | silent |
| 164 | 2D | stereo B16/S16, spb 2 | loop, 16384 frames (a streamed ring) | 48000 | off / 255 | 6:-11.2 8:-11.2 7:-11.2 9:-11.2 2:-11.2 11:off 0:off 1:off | -11.2 | -17.0 / -5.4, -15.3 / -4.4 |

v164 is the cutscene voice. It has fmode 0 and no HRTF handle. APU state: hrtf_submix
[6, 8, 7, 9], hrtf_headroom 0, submix_headroom 1 for every bin except 31.

The owner's logcat from the same session (level meter, dBFS):

| Time | Content | Level (dBFS) |
|---|---|---|
| 22:32:58-22:33:18 | intro FMV (59 fps) | -17.7 to -22.4 |
| 22:33:23 | (transition) | -43 |
| 22:33:28 on | in-engine cutscene, Raiden (21-23 fps) | -28 to -31 |

MON_VP's prediction for v164 is the -17 dBFS source minus 11.2 dB, about -28 dBFS. That matches
what the device played. So the emulator does what vp.c says; the question is what the hardware
does with a voice spread over five bins.

### The title's own DSP program, run offline

`tools/hxs_dsp_export.py` pulls the GP and EP state (registers, P/X/Y memory, peripheral
registers, the APU's DSP-related registers, guest RAM) out of the save state.
`tools/dsp_harness.c` builds the emulator's own `dsp.c`, `dsp_cpu.c` and `dsp_dma.c` against
small stubs (`tools/dspstub/`), restores both DSPs, and runs the title's GP and EP programs
frame by frame. It writes chosen signals into the GP mixbin buffer (X:0x1400 + 32*bin, 24-bit,
as `mcpx_apu_dsp_frame` does) and records the EP's output FIFO 0, which is what the AC97 plays
when `use_dsp = true`.

Checks: GPRST and EPRST are both 0x3 in the state. With silence in, the GP goes idle within
13199 instructions a frame and the EP within 7119. The only FIFO traffic is EP output index 0,
1024 bytes (256 stereo frames) every 8 frames. The GP uses no FIFO; GP to EP goes through
shared scratch memory.

Gain from each mixbin to the EP output, sine at -20 dBFS, 997 Hz (`tools/dsp_gain_matrix.py`),
in dB. "-" means below -80 dB:

| bin | name | to L | to R | note |
|---|---|---|---|---|
| 0 | FL | 0 | - | |
| 1 | FR | - | 0 | |
| 2 | C | -3 | -3 | |
| 3 | LFE | - | - | |
| 4 | BL | -3 | - | |
| 5 | BR | - | -3 | |
| 6 | XTLK FL | 0 | -8 | |
| 7 | XTLK FR | -8 | 0 | |
| 8 | XTLK BL | -3 | -11 | |
| 9 | XTLK BR | -11 | -3 | |
| 10 | I3DL2 | -9 | -12.2 | reverb send; Top Spin -9 / -29.4 |
| 26 | FX | -2 | -2 | MKSM only |
| 11-25, 27-31 | | - | - | |

The cross terms of the crosstalk bins depend on frequency; the direct terms do not:

| bin -> other side | 211 Hz | 997 Hz | 4013 Hz |
|---|---|---|---|
| 6 -> R | -2.5 | -8 | -18.7 |
| 8 -> R | -5.6 | -11 | -21.7 |

The MON_GP tap (X:0x1400 and X:0x1420 after the GP) carries only bins 0, 1, 6 and 7, and 10
faintly. So the GP does the crosstalk and the EP does the 5.1-to-stereo downmix (center and
surrounds at -3 dB). The program does not compensate for submix headroom: bin 0 to L is 0 dB.
So on the DSP path a title with submix_headroom 1 plays its voices 6 dB below one with
headroom 0.

The same check on Top Spin (4d530035, from the owner's 10-14 state) gives the same matrix for
bins 0-9. Top Spin's submix_headroom is 0 everywhere; MKSM's is 1.

### v164 through the DSP program vs through MON_VP

`tools/dsp_route_compare.py` with v164's own source ring (dumped from RAM) and its slot
volumes, the -6.02 dB headroom divisor applied to every DSP route as voice_process does. AC
RMS of the second half, dBFS:

| path | L | R | what it is |
|---|---|---|---|
| monvp | -29.43 | -27.30 | MON_VP today: max slot gain, no divisor |
| dsp_b%2 | -29.37 | -29.37 | the DSP program, slot b fed from channel b % 2 (voice_process today) |
| dsp_b>>1 | -27.05 | -27.01 | the DSP program, slot b fed from channel b >> 1 |
| ref_0/1 | -34.60 | -32.95 | the same source at the same max gain in bins 0/1 only |

Source: -16.97 / -15.27 dBFS, L/R correlation 0.716.

What this says:

- Through the title's DSP program, v164 is **5.2 dB (L) / 3.6 dB (R) louder than a plain
  front-left/front-right voice at the same register volume** (dsp_b%2 vs ref_0/1); 7.6 / 5.9
  dB under b>>1. On MON_VP the two play at the same level, because the max over slots counts
  one bin no matter how many the voice is spread over.
- So MON_VP under-plays a voice spread over several speaker bins, relative to everything else,
  by about 4-5 dB for this voice. That is hypothesis (a) as a measured mechanism. It covers
  about half of the 8-12 dB FMV-to-cutscene gap in the owner's logcat. The rest of the gap may
  be the content (the FMV is mastered hotter than the cutscene dialogue); no hardware
  recording of this scene exists to say.
- In absolute terms MON_VP and the DSP path give about the same level for v164 (-29.4 vs
  -29.4 L), because MON_VP also drops the 6 dB headroom divisor. What MON_VP gets wrong is the
  balance: everything that sits in one bin (music, effects) is 6 dB louder than on the DSP
  path, and v164 is not.
- A flat-weight model with no crosstalk filter overestimates the multi-bin gain: the whole
  ring with flat weights (b%2, with headroom) is -26.59 dBFS vs monvp -28.17. The crosstalk
  filter's phase takes some of the coherent sum away.

### Which channel feeds which slot

Top Spin's 2D stereo voices use slot pairs [0: FL, 1: FR] and [4: BL, 5: BR], so b % channels
is right for 2D voices (b >> 1 would put L in both FL and FR). For voices routed through
hrtf_submix [6, 8, 7, 9], b % 2 sends the left channel to XTLK FL and XTLK FR, and the right to
XTLK BL and XTLK BR. That collapses v164 to mono (dsp_b%2 L = R above). b >> 1 would send L to
6 and 8 (left front and back) and R to 7 and 9. Which one the hardware does is not known. It
does not change the level finding much (b%2 and b>>1 both beat ref_0/1 by 4-8 dB). It may be a
separate stereo-image defect on 3D-routed voices; noted, not chased.

## Hypotheses

| | hypothesis | MKSM | Shrek 2 | Lemony | Halo (#938) |
|---|---|---|---|---|---|
| (a) | MON_VP loses the multi-bin sum and the DSP balance | **measured mechanism, ~4-5 dB on v164** | open (7.5 dB loss measured; voice layout unknown) | open | open |
| (b) | format or container scaling | dead: v164 is PCM S16 at -17 / -15 dBFS | open | open | open |
| (c) | volume register width or sign | not supported: volumes decode to normal DSound values (-11.2, -6.0, 0.0, -7.9, -8.4 dB) | open | open | open |
| (d) | software movie decoder writes small samples | dead: the ring the game writes is at -17 / -15 dBFS | open | open | n/a |
| (e) | other | -- | -- | -- | HRTF normalisation; x1port1012 territory |

What a hit for (a) looks like on Shrek 2 or Lemony: the movie voice has its slots spread over
several speaker bins (for example FL, C, BL and FR, C, BR), and the gain the DSP matrix gives
that spread, relative to its max slot, is close to the measured loss. For FL + C + BL that is
1 + 0.707 + 0.707 in amplitude for a coherent signal, +7.65 dB, against the 7.5 dB measured on
Shrek 2. This is a prediction from the matrix, not a measurement: there is no Shrek 2 or
Lemony save state.

## The fix, behind a switch: HAKUX_APU_MONVP_DOWNMIX=1 (vp.c.patch)

MON_VP keeps its "no headroom divisor" rule. Instead of one gain per voice (the largest slot
volume), it gives each voice one gain per side: the sum over its speaker-bin slots (bins 0-9)
of the slot gain times the bin's weight to that side. The weights are the direct terms of
the matrix above: FL, xFL to L and FR, xFR to R at 1; C to both at 0.707; BL, xBL to L and
BR, xBR to R at 0.707; LFE 0. The crosstalk cross terms are left out (they depend on
frequency). A voice with no speaker-bin slot (FX sends only) keeps the max. The source
channel is kept as today (L from channel 0, R from channel 1), so stereo voices keep their
image. A voice panned to one side now stays on that side; today it plays on both.

For every standard 2D layout (FL/FR, FL/FR/BL/BR, with or without C) this equals the
title's DSP downmix, except that C takes its own side's channel. For v164 it gives +7.65 dB
on both sides over today. The DSP program gives +3.6 to +5.2 dB under voice_process's b % 2
channel rule, and +5.9 to +7.6 under b >> 1. So the flat weights overshoot by 0-4 dB on this
3D-routed stereo voice. That is the known bias.

Instrument: `HAKUX_APU_MIXLOG=1` (debug.c, my territory, off by default) logs one
`apumix` line per voice active in each 5 s window: its eight slots (bin:volume) and frame
count. `tools/mixlog_read.py` turns that into a table with today's gain and the switch's
per-side gains. **What a hit looks like:** a voice with excess +3 dB or more on both sides is
one today's mix under-plays relative to single-bin voices. If the quiet voice (movie,
speech) shows an excess near the measured loss (MKSM ~4-8 dB, Shrek 2 7.5 dB) and the music
and effects show ~0, (a) explains that title. If the quiet voice shows ~0, (a) is dead for
that title.

## Runs (Nova, ref a048589ff0, one binary)

Shrek 2 and Lemony Snicket have no profile, and the profile gate refuses both
(`titlestate.py admit`: "no profile (no golden) and no route-finding"). A blind route-finding run is
not what that path is for, so neither is in this set. Their layouts need a profile, or the
owner's save state taken in the movie (as for MKSM), or an apumix line from an owner session
with `HAKUX_APU_MIXLOG=1` in env_vars.

| run | title | s | env | for |
|---|---|---|---|---|
| R1 | MKSM 4D570029 | 180 | MIXLOG | layout of every voice from boot; baseline |
| R2 | MKSM 4D570029 | 180 | MIXLOG, DOWNMIX | the switch leaves single-bin voices alone |
| R3 | Halo 4D530004 | 180 | MIXLOG | #938: which Halo voices are multi-bin |
| R4 | Crimson Skies 4D530021 | 120 | MIXLOG | clipping baseline, loud title |
| R5 | Crimson Skies 4D530021 | 120 | MIXLOG, DOWNMIX | clipping with the switch |

## What the cause covers (#984, #938)

- MKSM: (a) measured offline, about 4-5 dB of the 8-12 dB gap. The rest is open.
- Shrek 2: the 7.5 dB loss is measured. (a) predicts +7.65 dB for an FL+C+BL / FR+C+BR
  layout. That layout is a guess until an apumix line or a save state shows it.
- Lemony Snicket: no data beyond the owner's report.
- Halo #938: R3 gives the menu voices. Speech needs gameplay, which a run from boot without a route does not
  reach. lane.x1port1012's hrtf.h change (normalise each ear, `break` became `continue`) is
  the other live Halo candidate. Until it landed, a 3D voice whose left ear was already
  normalised kept an unnormalised right ear.
- Separate, not chased: for 3D-routed stereo voices, voice_process's `b % channels` sends
  the left channel to xFL and xFR and the right to xBL and xBR, which makes v164 mono on
  the DSP path. b >> 1 would keep the sides. Which one the hardware does is unknown.

## Tracker first steps

- [issue.984]: read R1-R2's apumix table; get Shrek 2 and Lemony layouts as above; judge
  the switch on MKSM's cutscene with the owner (it is past a menu, which no run reaches).
- [issue.938]: R3's table; the hrtf.h fix in x1port1012; a gameplay route for Halo speech.

## Do not repeat

- The whole-mix gain hunt (September) and the per-voice CFG_FMT_HEADROOM field: done, not the
  cause.
- Hypotheses (b) and (d) on MKSM: dead (PCM S16 at -17/-15 dBFS in the ring).
- The DSP harness needs the save state's own GP/EP program; the matrix for bins 0-9 is the
  same in two titles, so it is the DirectSound standard image.

## Questions (for the owner; nothing waits on them)

1. Could you take a save state in Shrek 2 during the DreamWorks logo (or the intro movie),
   and one in Lemony Snicket during a movie? `tools/hxs_voices.py` reads the voice layout from
   it offline, with no device time.
2. Once the switch is judged: would you play MKSM's Goro's Lair cutscene once with
   `HAKUX_APU_MONVP_DOWNMIX=1` and say whether Raiden is now level with the music?

## Tools (docs/lanes/audio1016/tools/)

| tool | what it does |
|---|---|
| xiso_ls.py | lists and extracts files from an XISO image |
| level_windows.py | per-window RMS/peak of the logcat level meter lines |
| pcm_windows.py | per-window RMS/peak of raw PCM |
| hxs_unpack.py | HXS1 save state to a migration stream (zstd via ctypes) |
| hxs_voices.py | per-voice table from the stream: format, bins, volumes, envelope, source level |
| hxs_dsp_export.py | GP/EP state and guest RAM from the stream, for dsp_harness |
| dsp_harness.c | runs the title's GP/EP programs on the emulator's own DSP core |
| dsp_gain_matrix.py | per-bin gain to the EP output |
| dsp_route_compare.py | one voice through the DSP program vs MON_VP |

Build the harness (one line):

    gcc -O2 -w -I docs/lanes/audio1016/tools/dspstub -I hw/xbox/mcpx/apu/dsp -o dsp_harness \
        docs/lanes/audio1016/tools/dsp_harness.c hw/xbox/mcpx/apu/dsp/dsp.c \
        hw/xbox/mcpx/apu/dsp/dsp_cpu.c hw/xbox/mcpx/apu/dsp/dsp_dma.c -lm
