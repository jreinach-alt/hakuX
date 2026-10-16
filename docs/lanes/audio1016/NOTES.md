# lane.audio1016 NOTES -- quiet speech and movie audio (#984, #938)

Status: 2026-10-16 18:30 UTC, attempt 3. Done: PR ready.
- **Measured cause, MKSM (#984).** Today's monitor mix (MON_VP) under-plays a voice spread over
  several speaker bins. It gives such a voice the gain of its loudest bin, while the title's own
  DSP program sums the bins.
  On the Nova, in the Goro's Lair cutscene:
  - Raiden's line (v164: xFL, xBL, xFR, xBR and C at -11.2 dB) plays level with the idle
    gameplay after it (-29.34 vs -29.10 dBFS).
  - The title's own DSP program puts the same speech 4.49 dB above that gameplay.
  - Switch v2 (`HAKUX_APU_MONVP_DOWNMIX=1`, vp.c.patch) puts it 7.46 dB above, at -22.15 dBFS,
    with menus and gameplay within 0.5 dB of today.
  - The loud title (Crimson Skies) is unchanged: clipped 84 / 73 both ways, acrms +0.02 dB.
- The title's own DSP path (`use_dsp`) runs on the Nova at 286 us of 667 per frame, with no
  starvation and no fps change. Two measured blockers keep it from being the fix today:
  - the whole mix is 4-6 dB quieter;
  - Raiden's stereo line plays in mono (L/R correlation 0.99, against 0.65 on MON_VP).
- Verdicts, coverage and ranking: "Cutscene runs judged (attempt 3)" below.

**Why attempt 2 did not finish.** It ended at 17:15 UTC on `waiting:` for the five cutscene
runs. At 17:17 all five were still queued behind two perflog1016 arms, and their ref,
4d736d2b8c, was not built yet. Ending on `waiting:` was correct under the lane role. lane.local
resumed the lane to wait inside the session instead (`tools/wait_results.sh` polls the result
dirs), read the five results, and close the PR.

**Why attempt 1 did not finish.** It did not fail: it ended correctly on `waiting:` for the five
identify runs, R1-R5. Those ran 08:46-09:38 on 10-16, and the lane was resumed for them. Their
verdicts are below. The MKSM pair never reached the cutscene, and the loud-title leg failed, so
the brief's "done" (a measured cause with a fix behind evidence) needed a second device batch.

NEED: `hw/xbox/mcpx/apu/vp/vp.c` (lane.x1port1012's file when this lane was briefed): apply
`docs/lanes/audio1016/vp.c.patch` **v2** (HAKUX_APU_MONVP_DOWNMIX with the unity cap, off by
default). It touches only the MON_VP block of voice_process() and adds a table after
attenuate().
- Evidence: the [frames] reading and legs S and C below. Leg U as registered failed on its
  window rule, not on the switch.
- x1port1012 has folded (3c2338eb2b), and territory.toml no longer names vp.c.
- `git apply --check docs/lanes/audio1016/vp.c.patch` passes on master 4bf47129b1.
- The 4d736d2b8c run build carried the same change.

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

Ranking, by probability times the size of the win, as of attempt 2. Run D has since measured
it; the current ranking is under "Cutscene runs judged":
- **Faithful path:** if the Nova can afford it (P unknown until D, about 0.4 from the estimate
  above), it fixes the balance for every title and voice layout, including ones never measured
  (Shrek 2, Lemony, Halo's 3D voices), and adds the reverb MON_VP never plays.
- **Switch:** P about 0.6 that it closes most of the MKSM gap without clipping (legs U, S, C).
  The win is limited to layouts the direct weights model, and it overshoots crosstalk-routed
  voices.

The D run is in the same batch as the switch runs so that neither waits on the other. Because
the realtime GP loop runs `dsp_run` until the program idles, a Nova that cannot keep up shows it
as APU thread load near 1 and `starve:` lines, not as wrong samples.

### Cutscene runs (registered; ran on the Nova 10-16 from 10:28 PDT)

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

**Read from run A's frames, before any level in A, B or D was read (17:40 UTC 10-16).** Run A
(`...2350757`) reached the cutscene at 10:30:07 device clock. Its frames, viewed by eye:
- 103007-103101: letterboxed, Raiden and Kung Lao speaking, 26-37 fps.
- 103113 onward: no bars, the LIU KANG health bar is up at 59 fps, and Liu Kang stands idle.

Run without input, the Goro's Lair cutscene lasts about 55-65 s, not the >= 120 s leg V
assumed. Under the registered rule A's "cutscene" windows are therefore about 60 s of speech
plus 140 s of idle gameplay. The registered legs are scored as written. Next to them,
`judge_cutscene.py` prints a reading labelled `[frames]`:
- `speech` windows: inside the leading run of letterboxed `cutscene` frames, detected from
  the pixels (rows 60-160 and 800-960 near black), plus 5 s.
- `idle` windows: from 12 s after the last letterboxed frame to the end.

The rule depends only on the frames, and it was fixed before any level was read. It is not a
registered leg, and NOTES and PR.md say so wherever they quote it.

### Cutscene runs judged (attempt 3)

All five ran on one binary, 4d736d2b8c. Each MKSM run has one `monvp_downmix:` line (A off, B
on, D none, since D plays the DSP output) and a letterboxed span of 45-55 s. The two Crimson
runs held 120 s, with one PID each in the logcat. Outputs are in `runs/cutscene/`:
- `judge.out.tsv`: judge_cutscene.py, every leg;
- `fps.out.tsv`: fps_spans.py;
- `<run>.{mix,sum,cap,lvl,meter,dsp}.tsv`: judge_identify.sh.

**Registered legs** (audio1016-cutscene.json, scored as written):

| leg | bound | measured | verdict |
|---|---|---|---|
| Q | A: pre - cutscene >= 6 dB | +2.31 | FAIL. Expected before results: this route's "pre" is menus, not the intro FMV |
| L | a voice in >= 4 bins with excess >= +5 dB | 54 spread voice-windows. The judge's pick is the silent all-bins group (+10.67); v164 (5 bins, +7.65) meets the bound on its own | PASS |
| U | cutscene B - A in [+3, +8.5] | +1.03 | FAIL: the window holds 55 s of speech and 140 s of idle play; see [frames] |
| S | pre \|B - A\| <= 1.5 | -0.05 | PASS |
| DL | pre D - A in [-8, -4] | -4.07 | PASS |
| DL | cutscene D - A in [-4, +1] | -4.63 | FAIL, by 0.63; idle play dominates the window |
| DL | balance gain D over A in [+2, +7] | -0.56 | FAIL: same window |
| DC | gp_us + ep_us/8 in [250, 700] | 286 | PASS |
| DC | D starve - A >= 1 point | 0.00 vs 0.00 % | FAIL: the Nova kept up |
| C | L: clipped C1 <= 2 x C0 + 100 per window; acrms within 1.5 dB | 84 vs 84; -14.06 vs -14.08 | PASS |
| C | R: same | 73 vs 73; -14.06 vs -14.08 | PASS |

Leg V's ">= 120 s of cutscene" was wrong: the cutscene is 55-65 s (see above). U and both
DL windows are about 70% idle gameplay, so they measure the gameplay, not the speech.

**[frames] reading** (not registered; the rule was fixed from A's frames before any level
was read). Medians of the 5 s logcat meter windows, dBFS:

| | speech (letterboxed) | idle (after) | pre (menus) | speech above idle |
|---|---|---|---|---|
| A, today (switch off) | -29.34 (11 windows) | -29.10 (27) | -26.83 (16) | **-0.24** |
| B, switch v2 on | -22.15 (11) | -29.61 (27) | -26.88 (16) | **+7.46** |
| D, title's DSP | -30.45 (9) | -34.94 (28) | -30.90 (18) | **+4.49** |
| B - A | +7.19 | -0.51 | -0.05 | +7.70 |
| D - A | -1.11 | -5.84 | -4.07 | +4.73 |

What it says:
- Today the speech has no lift over the gameplay. The title's own program gives it +4.49 dB.
  The offline harness predicted +3.6 to +5.2 dB for v164 over a single-bin voice, so the
  device confirms the mechanism, hypothesis (a). Every speech window in A, B and D carries the
  v164 layout (xFL xBL xFR xBR C at -11.2, excess +7.65; `speech voices` rows in
  judge.out.tsv).
- Switch v2 lifts the speech by 7.19 dB and leaves the menus (-0.05) and gameplay (-0.51)
  where they were. It overshoots the title's own balance by 7.70 - 4.73 = **3.0 dB**, inside
  the 2.5-4 dB predicted offline for flat weights on a crosstalk-routed voice.
- B's speech lands at -22.15 dBFS, at the quiet end of the intro FMV's -17.7 to -22.4 in the
  owner's 10-14 logcat (the reference the owner heard). A's -29.34 matches the owner's
  -28 to -31.
- The capture agrees. Speech is 80-150 s into each capture: A -28 to -31 dBFS per 5 s window,
  B -20 to -23, peaks -4.4 dBFS at worst.
  - A and B both reach 0 dBFS at 215 s, in the gameplay, so that peak is in the game's own
    content and not the switch.
  - At 185 s and 270 s a hot effect that A plays on both sides plays mostly on the right in B.
    That is the image change: a single-side voice stays on its side.

**The DSP path's two blockers, both measured:**
1. Level. With submix headroom h=1, everything single-bin is 4-6 dB quieter than today (pre
   -4.07, idle -5.84), and the speech is no louder in absolute terms (-1.11). The owner's
   complaint is "too quiet even at max volume", so on its own this path makes it worse.
2. Image. In the speech span (capture 90-150 s) the L/R correlation is 0.99 in D, against 0.65
   in A and 0.59 in B. In D's idle span (0.69) it is normal. voice_process feeds slot b from
   channel `b % channels`. For v164's hrtf_submix order (xFL, xBL, xFR, xBR) that sends the left
   channel to both front bins and the right channel to both back bins, and the downmix sums
   them to near mono. dsp_route_compare.py predicted this offline (dsp_b%2 L = R), and D
   confirms it on the device. Which rule the hardware uses is not known: `b >> 1` would keep
   v164 stereo but would put Top Spin's FL/FR pairs in mono.

**DSP cost on the Nova (run D, cutscene windows):**
- gp_us 263, ep_us 186, vp_us 154; gp_cyc 13158 against A's 418.
- APU thread util 0.68 (max 0.74), against A's 0.26 (max 0.35).
- Starve 0.0%.
- The MKSM program fits with about 25% of the thread to spare. That is one title; a heavier
  GP program (I3DL2-heavy titles) is not measured.

**fps** (hakuX-perf gfps, over the same spans):

| run | speech median / p10 / min | idle median / p10 / min |
|---|---|---|
| A | 33 / 23 / 18 | 59 / 59 / 59 |
| B | 32.5 / 22 / 7 | 59 / 59 / 59 |
| D | 33 / 25 / 24 | 59 / 59 / 44 |

B's 7 is one sample 12 s into the speech, at the same scene cut where A dips to 18 at 11 s.
The switch adds 2 us of vp_us, so it does not explain the dip. The DSP path costs no frames on
this title.

**Ranking, by probability times the size of the win:**
- **Switch v2 as the default**, through the default-on screen. P about 0.75 that it closes the
  owner's MKSM complaint: it is measured here at +7.2 dB on the speech, with no change to menus,
  gameplay, the loud title or CPU. The win is medium: every title whose quiet voice is
  spread over several bins at low volume. MKSM is measured; Shrek 2 is predicted (+7.65 dB
  against a measured 7.5 dB loss). Its costs:
  - it plays crosstalk-routed voices about 3 dB hotter than the title intends;
  - single-side voices stay on their side, which is the direction the hardware goes.
- **The title's own DSP path as the default.** P about 0.3 today. It needs a makeup gain equal
  to the submix headroom, with its own clipping check, and it needs the slot-to-channel rule
  settled (blocker 2). The win is large: every title and every layout, including the reverb
  MON_VP never plays, and it is the path that fits the hardware.
  Its cost is now measured as affordable on one title. It should start as its own lane now,
  not wait for the switch to fold.

## What the cause covers (#984, #938)

- MKSM: (a) measured on the device (above). Today the cutscene speech plays 4.7 dB under the
  title's own balance. Switch v2 restores that and adds 3 dB more. The owner's logcat put the
  speech 8-12 dB under the intro FMV. Of that gap, 4.7 dB is (a). The other 3-7 dB remains
  even in the title's own mix, so it is the title's mastering. With the switch on, the speech
  reaches the quiet end of the FMV's range.
- Shrek 2: the 7.5 dB loss is measured. (a) predicts +7.65 dB for an FL+C+BL / FR+C+BR
  layout. That layout is a guess until an apumix line or a save state shows it.
- Lemony Snicket: no data beyond the owner's report.
- Halo #938: R3 is void (screen off mid-run). Its menu voices would not have answered the
  question anyway: speech needs gameplay or a cinematic, which a run from boot without a route
  does not reach. The hrtf.h per-ear normalisation fix is now on master (d88374737c, 0.5.1 A8),
  the other live Halo candidate. Until it landed, a 3D voice whose left ear was already
  normalised kept an unnormalised right ear. Whether it fixes #938 needs an owner session.
- Separate, not chased: for 3D-routed stereo voices, voice_process's `b % channels` sends
  the left channel to xFL and xFR and the right to xBL and xBR, which makes v164 mono on
  the DSP path. b >> 1 would keep the sides. Which one the hardware does is unknown.

## Tracker first steps

These are the rows' first steps as of attempt 3. The tracker itself is not edited from a lane.

- [issue.984]:
  1. Apply vp.c.patch v2 (the NEED line), off by default.
  2. Screen `HAKUX_APU_MONVP_DOWNMIX=1` as a default in the next default-on screen. Measured on
     MKSM, safe on Crimson Skies. The owner's ears on the three WAVs (question 2) are the
     check the meter cannot make.
  3. Start a lane on the faithful path (use_dsp as the default). Its two blockers are above:
     - a makeup gain for the submix headroom, with its own clipping check;
     - the slot-to-channel rule for stereo voices with an hrtf_submix order.
     Its instrument is in this PR: `HAKUX_APU_USE_DSP=1` plus debug.c's `apudsp` line and the
     capture's L/R correlation.
  4. Shrek 2 and Lemony need a save state each (question 1) for their layouts.
- [issue.938]:
  1. Halo speech needs a run that reaches speech: a cinematic or gameplay route, which R3 from
     boot did not have.
  2. The other live cause is the hrtf.h per-ear normalisation fix, on master since
     d88374737c; Halo's speech may be 3D-routed. An owner session on a build with that fix and
     `HAKUX_APU_MIXLOG=1` gives the voice layout and says whether #938 is still there.

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
- A cutscene window set by "first to last route frame". Without input MKSM's Goro's Lair
  cutscene lasts 45-55 s and gameplay follows, so such a window is mostly gameplay (legs U and
  DL failed on it). Use the letterboxed span (`judge_cutscene.speech_span`).
- Expecting the DSP path to starve on the Nova for MKSM: it does not (util 0.68, 0 starve).
- Judging use_dsp on level alone: it also collapses v164 to mono. Check the L/R correlation
  of the capture over the speech.

## Questions (for the owner; nothing waits on them)

1. Could you take a save state in Shrek 2 during the DreamWorks logo (or the intro movie),
   and one in Lemony Snicket during a movie? `tools/hxs_voices.py` reads the voice layout from
   it offline, with no device time.
2. The three MKSM cutscene captures are in `D:\hakux-staging\audio1016\`. Each is the same
   105-110 s of the Nova's output: the end of the menus, loading, the Goro's Lair cutscene
   (Raiden and Kung Lao, from about 20 s in), then Liu Kang idle.
   - `MKSM-cutscene-A-today-switch-off.wav`: **switch off**, today's mix.
   - `MKSM-cutscene-B-switch-on.wav`: **switch on** (HAKUX_APU_MONVP_DOWNMIX=1).
   - `MKSM-cutscene-D-title-dsp.wav`: the title's own DSP program (use_dsp on, switch off).
     It is quieter overall, and the speech is near mono.

   Is Raiden at the right level against the gameplay in B? Is anything off in B, such as an
   effect now heard on one side only? The full captures are in each result's
   `pulled/apu_monitor.s16le48k2ch.pcm`.
3. In the app's settings, does turning on "Real-time DSP processing" for MKSM sound right to
   you, and does the game stay smooth? That is the same path as run D. The Nova affords it on
   MKSM (run D). Its quieter mix and its mono speech are the two things to fix before it can
   be the default.

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
| judge_cutscene.py | scores the audio1016-cutscene legs (Q/L/U/S/DL/DC/C) from the five result dirs, plus the [frames] speech/idle reading |
| fps_spans.py | hakuX-perf gfps median/p10/min over the [frames] speech and idle spans |
| pcm_wav.py | cuts a capture to a WAV for listening |
| wait_results.sh | polls dispatch result dirs until each request is DONE |
| routes/audio1016-mksm-wait.route | MKSM to the Goro's Lair cutscene, then no input |

To queue a lane route, copy it into the serving tree's `docs/testing/titles/routes/`, run
request.sh with `--route <stem>`, then move the copy aside. The route text travels inside the
request (`"route"`), so the copy is not needed after queueing.

Build the harness (one line):

    gcc -O2 -w -I docs/lanes/audio1016/tools/dspstub -I hw/xbox/mcpx/apu/dsp -o dsp_harness \
        docs/lanes/audio1016/tools/dsp_harness.c hw/xbox/mcpx/apu/dsp/dsp.c \
        hw/xbox/mcpx/apu/dsp/dsp_cpu.c hw/xbox/mcpx/apu/dsp/dsp_dma.c -lm
