# lane.audio1016 NOTES -- quiet speech and movie audio (#984, #938)

Status: 2026-10-16 17:20 UTC, attempt 3.
- The mechanism is measured offline on MKSM.
- Switch v1 failed the loud-title leg on the Nova. v2 (capped) is written and passes the same
  tables offline.
- Five cutscene runs are registered in `docs/testing/predictions/audio1016-cutscene.json`
  and queued on 4d736d2b8c.

**Why attempt 2 did not finish.** It ended at 17:15 UTC on `waiting:` for the five cutscene
runs. At 17:17 all five were still queued behind two perflog1016 arms, and their ref,
4d736d2b8c, was not built yet. Ending on `waiting:` was correct under the lane role. lane.local
resumed the lane to wait inside the session instead (`tools/wait_results.sh` polls the result
dirs), read the five results, and close the PR.

**Why attempt 1 did not finish.** It did not fail: it ended correctly on `waiting:` for the five
identify runs, R1-R5. Those ran 08:46-09:38 on 10-16, and the lane was resumed for them. Their
verdicts are below. The MKSM pair never reached the cutscene, and the loud-title leg failed, so
the brief's "done" (a measured cause with a fix behind evidence) needed a second device batch.

NEED: `hw/xbox/mcpx/apu/vp/vp.c` (lane.x1port1012's file): apply
`docs/lanes/audio1016/vp.c.patch` **v2** (HAKUX_APU_MONVP_DOWNMIX with the unity cap, off by
default), once the cutscene runs pass U, S and C. It touches only the MON_VP block of
voice_process() and adds a table after attenuate(); it does not overlap x1port1012's changes.
Until then the patch is for the record, not for merging.

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

Queued 2026-10-16, release priority, pinned to the Nova:
R1 `1-1792157544-lane.audio1016-3902449`, R2 `1-1792157544-lane.audio1016-3902478`,
R3 `1-1792157545-lane.audio1016-3902507`, R4 `1-1792157545-lane.audio1016-3902536`,
R5 `1-1792157545-lane.audio1016-3902586`. Judge: `tools/mixlog_read.py` and
`tools/level_windows.py` on each run's logcat, legs V/M/S/U/H/C as registered.

### R1-R5 judged (attempt 2)

`tools/judge_identify.sh` wrote one table set per run into `runs/identify/`:
- `.mix` holds every apumix row;
- `.sum` and `.cap` hold one row per slot layout, under switch v1 and v2;
- `.lvl` holds the 5 s meter windows;
- `.meter` holds the run totals.

| leg | verdict | numbers |
|---|---|---|
| V | pass (R1, R2, R4, R5) | one `monvp_downmix:` line each, on in R2/R5; 27-37 apumix windows |
| M | pass | the intro FMV's long voice is FL/FR only at 0.0 / -9.3 dB, excess 0.0 |
| S | pass | whole run acrms R1 -19.86 / -20.25, R2 -20.05 / -20.43 dBFS: 0.2 dB apart |
| U | not reached | every window's top voice is single-bin: the FL/FR music at 0.0 or -9.3. The one +3.0 layout (v48, xFL xFR C at -10.7) plays about 1 s of 5 in windows 9-10, under that music. The cutscene is past the menus |
| H | void | R3 (Halo): see below |
| C | **FAIL** | clipped samples R4 84 / 73, R5 364,669 / 362,635; acrms R4 -14.45, R5 -7.41 dBFS (+7.0 dB) |

Leg C's cause is in R4's own table (`R4.sum.tsv`). Crimson Skies' music is voiced at full
volume in all six 5.1 bins (FL, FR, C, LFE, BL, BR at 0.0 dB). That is 42 voice-windows and
301,439 voice-frames in a 136 s run: the largest layout by frames.
Under v1 its left side sums to 1 + 0.707 + 0.707 = 2.414, which is +7.65 dB. The title's own
DSP program gives the same sum, but there the 6 dB submix headroom (h=1) leaves room for it;
on MON_VP, which dropped the divisor, it clips.

R3 (Halo) is void, not a measurement. The display was off at the end, soak_title.sh hit a
broken pipe, and the logcat tail belongs to another PID. It looks like the screen went off
mid-run. It was not re-run: a Halo run from boot reaches no speech anyway.

The four "all bins at -6 dB" voices run for the whole of every MKSM and Crimson run. These are
v64-67 in the save state, silent in its rings. Under v1 they get +10.7 dB, yet R1 and R2 stay
level, so they carry no sound. This is the measurement behind the cap's +6.0 on them being
harmless.

### Switch v2: hold the louder side to 1.0

If a voice's louder side sums above 1.0, v2 scales both sides down by the same factor, so the
louder one is exactly 1.0 and the image is kept. 1.0 is the largest gain MON_VP gives any voice
today, so no voice gets louder than today's loudest. `mixlog_read.py --cap` models it, and
`.cap.tsv` holds the per-layout result for every identify run:

| layout | title | v1 excess | v2 excess |
|---|---|---|---|
| FL FR C LFE BL BR at 0.0 (music) | Crimson | +7.65 | **+0.0** |
| FL FR at 0.0 / -9.3 (FMV, menus) | MKSM | +0.0 | +0.0 |
| FL FR BL BR at -1.8 / -7.8 | Crimson | +1.8 | +1.8 |
| xFL xBL xFR xBR C at -11.2 (v164, cutscene speech; save state) | MKSM | +7.65 | **+7.65** |
| xFL xFR C at -10.7 | MKSM | +3.0 | +3.0 |
| all 8 slots at -6.0 (silent) | both | +10.7 | +6.0 |

The cap only acts on a voice that is already loud in several bins. Speech spread at low volume
keeps its full gain.

### The faithful path: what the title's own DSP program costs

`use_dsp` (Real-time DSP processing) plays the GP/EP output instead of MON_VP. That is what the
hardware does: the title's matrix, its crosstalk, its I3DL2 reverb, and its submix headroom. It
is the option that fits the hardware, not an approximation of it. Its costs:

- **CPU.** `dsp_harness` ran MKSM's GP and EP programs on 10 s of input and took 5.79 s of CPU
  on this x86 host, about 0.58 of a core. A frame is 667 us of audio, so that is about 386 us
  of DSP time a frame. The Nova's cores are slower per clock than this host's, so the estimate
  there is 0.6-0.9 of a core, on the APU thread, on top of VP. Run D measures it.
- **Level.** With h=1, every single-bin voice plays 6 dB below today's MON_VP. The balance is
  right, and the whole mix is quieter. The player's volume covers that; clipping is not a
  risk.
- **Balance.** Offline, v164 plays 3.6-5.2 dB above a single-bin voice. v2 gives +7.65, so on
  this voice the switch overshoots the title's own mix by about 2.5-4 dB. Run D gives the
  on-device figure.

Ranking, by probability times the size of the win:
- **Faithful path:** if the Nova can afford it (P unknown until D, about 0.4 from the estimate
  above), it fixes the balance for every title and voice layout, including ones never measured
  (Shrek 2, Lemony, Halo's 3D voices), and adds the reverb MON_VP never plays.
- **Switch:** P about 0.6 that it closes most of the MKSM gap without clipping (legs U, S, C).
  The win is limited to layouts the direct weights model, and it overshoots crosstalk-routed
  voices.

The D run is in the same batch as the switch runs so that neither waits on the other. Because
the realtime GP loop runs `dsp_run` until the program idles, a Nova that cannot keep up shows it
as APU thread load near 1 and `starve:` lines, not as wrong samples.

### Cutscene runs (registered, queued)

Prediction: `docs/testing/predictions/audio1016-cutscene.json` (sha256 07a76a1f...67d1), ref
4d736d2b8c. That ref carries vp.c.patch v2 applied, plus gp_ep.c's `HAKUX_APU_USE_DSP=1` and
debug.c's `apudsp` cost line; all are off unless set. Route:
`routes/audio1016-mksm-wait.route`, which is fps1015-mksm's logos and menus up to s12, then no
input for 200 s from the cutscene's start (about 77 s in). fps1015's route pressed START through
the cutscene and skipped its speech.

| run | request id | title | s | env | what the owner hears |
|---|---|---|---|---|---|
| A | `1-1792170341-lane.audio1016-2350757` | MKSM, wait route | 290 | MIXLOG | **today's mix** (switch off) |
| B | `1-1792170345-lane.audio1016-2351225` | MKSM, wait route | 290 | MIXLOG, DOWNMIX | **switch on** (v2) |
| D | `1-1792170348-lane.audio1016-2351533` | MKSM, wait route | 290 | MIXLOG, USE_DSP | **the title's own DSP mix** |
| C1 | `1-1792170351-lane.audio1016-2352136` | Crimson Skies | 120 | MIXLOG, DOWNMIX | loud title, switch on |
| C0 | `1-1792170352-lane.audio1016-2352599` | Crimson Skies | 120 | MIXLOG | loud title, switch off |

They are queued in that order, A first. C0 is last on purpose: the dispatcher leaves the last
request's env on the device until the next request, and C0 sets no mix switch. The MKSM runs
pull the audio capture (`apu_monitor.s16le48k2ch.pcm`, 60 MB cap), so all three can be heard
afterwards from the result directories.

Judge: `tools/judge_identify.sh <results> docs/lanes/audio1016/runs/cutscene A=... B=... D=...
C1=... C0=...` writes the tables. `tools/judge_cutscene.py <results> A=... B=... D=... C1=...
C0=...` prints each leg against its registered bound. A level window counts as "cutscene" when it
starts at or after the first `cutscene` frame and ends within 10 s of the last one. A window
counts as "pre" when it ends before that frame and is above -50 dBFS.

Clocks: frames are `route-frames/HHMMSS-<shot>.png` on the logcat clock. `cutscene` is the
shot name the route gives each frame, not a classifier's label, so leg V still needs the frames
viewed by eye. Starvation is summed over the cutscene from hakuX-audiocap's `starve:` lines,
which count each 30 s interval on its own; they are not cumulative.

**Read before any result came in (17:13 UTC 10-16, all five still queued): leg Q will probably fail as registered.**
The judge, run over fps1015's run of the same s01-s12 on master (`1792168743-fps1015-1960988`),
gives a pre median of -26.59 dBFS (15 windows) and a cutscene median of -28.53 (21 windows), a
gap of 1.94 dB. This route's "pre" is the logos, title screen, menus and loading, not the intro
FMV the owner compared against (-17.7 to -22.4 dBFS). The cutscene median is the speech and
the music together, so Q does not isolate the speech. fps1015 pressed START through the lines,
so its cutscene windows include the cuts between lines. Legs L (per voice) and U (B against A
on matched windows) carry the question. A Q failure on this route is not evidence against the
cause. The prediction stays as registered.

## What the cause covers (#984, #938)

- MKSM: (a) measured offline, about 4-5 dB of the 8-12 dB gap. The rest is open.
- Shrek 2: the 7.5 dB loss is measured. (a) predicts +7.65 dB for an FL+C+BL / FR+C+BR
  layout. That layout is a guess until an apumix line or a save state shows it.
- Lemony Snicket: no data beyond the owner's report.
- Halo #938: R3 is void (screen off mid-run). Its menu voices would not have answered the
  question anyway: speech needs gameplay or a cinematic, which a run from boot without a route
  does not reach. lane.x1port1012's hrtf.h change (normalise each ear, `break` became `continue`) is
  the other live Halo candidate. Until it landed, a 3D voice whose left ear was already
  normalised kept an unnormalised right ear.
- Separate, not chased: for 3D-routed stereo voices, voice_process's `b % channels` sends
  the left channel to xFL and xFR and the right to xBL and xBR, which makes v164 mono on
  the DSP path. b >> 1 would keep the sides. Which one the hardware does is unknown.

## Tracker first steps

These are the rows' first steps as of attempt 2. The tracker itself is not edited from a lane.

- [issue.984]:
  1. Judge audio1016-cutscene's A/B/D on MKSM's cutscene, with the owner's ears on the three
     captures.
  2. If U/S/C pass, the NEED line above takes vp.c.patch v2 into x1port1012's tree, behind its
     switch.
  3. If D shows the Nova can run the title's program, the faithful path (use_dsp on) is
     screened as a default instead.
  4. Shrek 2 and Lemony need a save state each (question 1) for their layouts.
- [issue.938]:
  1. Halo speech needs a run that reaches speech: a cinematic or gameplay route, which R3 from
     boot did not have.
  2. The other live cause is lane.x1port1012's hrtf.h per-ear normalisation fix; Halo's speech
     may be 3D-routed. Once that fix lands, an owner session with `HAKUX_APU_MIXLOG=1` gives the
     voice layout.

## Do not repeat

- The whole-mix gain hunt (September) and the per-voice CFG_FMT_HEADROOM field: done, not the
  cause.
- Hypotheses (b) and (d) on MKSM: dead (PCM S16 at -17/-15 dBFS in the ring).
- The DSP harness needs the save state's own GP/EP program; the matrix for bins 0-9 is the
  same in two titles, so it is the DirectSound standard image.
- An uncapped per-side sum (switch v1): it clips any title that plays a voice at full volume
  in several bins (Crimson Skies, 84 to 364,669 clipped samples).
- An MKSM run from boot, or on fps1015's route, for this question. The first never reaches the
  cutscene. The second presses START through it and skips the speech. Use
  `routes/audio1016-mksm-wait.route`.
- Reading per-window level differences between two runs as the switch's effect without
  matching content. The same route still drifts a window or two; compare medians over windows
  set by the frames' clock.

## Questions (for the owner; nothing waits on them)

1. Could you take a save state in Shrek 2 during the DreamWorks logo (or the intro movie),
   and one in Lemony Snicket during a movie? `tools/hxs_voices.py` reads the voice layout from
   it offline, with no device time.
2. The three MKSM cutscene runs are queued in this order: A first, today's mix; B second,
   the switch on; D third, the title's own DSP program. Each pulls an audio capture. Is
   Raiden level with the music in B? In D? Does either sound wrong in another way, such as
   reverb, image, or level?
3. In the app's settings, does turning on "Real-time DSP processing" for MKSM sound right to
   you, and does the game stay smooth? That is the same path as run D. If the Nova can afford
   it, it is the fix that matches the hardware, for every title at once.

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
| mixlog_read.py | apumix lines to a per-voice table; `--summary` per layout, `--cap` models v2 |
| judge_identify.sh | runs mixlog_read and level_windows over each result, writes runs/<set>/*.tsv |
| judge_cutscene.py | scores the audio1016-cutscene legs (Q/L/U/S/DL/DC/C) from the five result dirs |
| routes/audio1016-mksm-wait.route | MKSM to the Goro's Lair cutscene, then no input |

To queue a lane route, copy it into the serving tree's `docs/testing/titles/routes/`, run
request.sh with `--route <stem>`, then move the copy aside. The route text travels inside the
request (`"route"`), so the copy is not needed after queueing.

Build the harness (one line):

    gcc -O2 -w -I docs/lanes/audio1016/tools/dspstub -I hw/xbox/mcpx/apu/dsp -o dsp_harness \
        docs/lanes/audio1016/tools/dsp_harness.c hw/xbox/mcpx/apu/dsp/dsp.c \
        hw/xbox/mcpx/apu/dsp/dsp_cpu.c hw/xbox/mcpx/apu/dsp/dsp_dma.c -lm
