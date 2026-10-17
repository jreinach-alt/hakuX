# #938 Halo CE (4D530004) opening cinematic: quiet speech under loud music -- offline research

(Subagent report, 2026-10-16 22:40 PDT, saved by the lane. Unverified by the lane where marked
"agent"; the lane's own checks are in ../../NOTES.md.)

Scope: tree b12a313033 (0.5.1-rc1); `git diff --stat b12a313033 HEAD -- hw/xbox/mcpx/apu` is empty, so
every line ref holds on the lane head (141d3b9916). Nova config use_dsp=false, renderer vulkan. Inputs:
the owner's states slot0 (21:51:42, start of the cinematic), slot1 (21:52:20), slot2 (21:52:51); voice
registers and rings read from the decompressed .hxs streams; Halo's GP/EP programs run in a
`dsp_harness` on slot1. No device touched. (Large artefacts moved to /mnt/d/hakux-staging/halo1016/audio-scratch/.)

## 0. Result

- Speech vs music: MON_VP plays Halo's 2D speech (v65) and 2D music (v85/v86/v88) at exactly the ratio
  in their volume registers: speech +4.1 dB over music at slot0, +1.0 dB at slot1.
- The bed: the rest of the mix is a 3D bed of low-frequency voices (centroids 136-258 Hz) through the
  HRTF. About speech level at slot0/1, about 12 dB over everything at slot2. The HRTF's scale relative to
  hardware is unknown.
- Faithful DSP: Halo's own DSP program would play that bed +4.65 dB louder relative to speech than MON_VP
  does today. Neither the faithful path nor the MKSM downmix lowers it; both raise it.
- Max-over-bins is real but not this bug: every audible Halo voice has equal volume on the slots it uses.
- Top hypotheses: H2 title mix reproduced faithfully (P 0.30); H1 HRTF scale leaves the bed louder than
  hardware (P 0.20).

## 1. The symptom in the code (use_dsp=false path)

| step | where | Halo fact |
|---|---|---|
| use_dsp=false selects MON_VP | gp_ep.c:58-69 (`HAKUX_APU_USE_DSP` at gp_ep.c:41) | rc1 has use_dsp=false |
| register to gain `powf(10, vol/(64*-20))`; 0xFFF = mute | vp.c:450-454 | 1/64 dB per step |
| mono voice copied to channel 1 | vp.c:1740-1741 | v65 and every 3D voice are mono |
| a paused voice returns early | vp.c:1982-1984 (VOICE_PAUSE vp.c:667) | v65 paused at slot2 |
| 3D voices: slots 0-3 forced to hrtf_submix | vp.c:2057-2062 | hrtf_submix = [6,8,7,9] = xFL,xBL,xFR,xBR |
| I3DL2 filter (fmode 3) not run on 3D voices | vp.c:2103-2114 (only fmode 1 runs the LPF) | every Halo 3D voice has fmode 3 |
| HRTF FIR on 3D voices | vp.c:2135-2142; taps L1-normalised in hrtf.h set_target_params | HRIRs not in the save state (1.4) |
| DSP mixbins, discarded under MON_VP | vp.c:2146-2159 | `samples[i][b % channels]` at vp.c:2157 |
| MON_VP mix: g = max over slots of attenuate(vol[b]), skipping MP bin; no headroom divisor (comment 2191-2207); g*ea added to L and R | vp.c:2186-2214 | hrtf_headroom 0; submix_headroom 0; no MP voices; eg/lvl off/255 |
| float to int16, clip at +-1 | vp.c:3336-3340 | |
| volume_limit is a static gain (inert at 1), not a limiter; capture taken after it | apu.c:723-764, 797-802 | nothing in hakuX ducks speech |
| `level` line (peak, acrms, clipped) | apu.c:663-671 | instrument for section 5 |

### 1.1 Max-over-bins: verified, not the cause

vp.c:2208 takes the per-voice max. For Halo this loses nothing: v65 uses bins 0/1 at -13.4/-13.4 dB;
music voices are FL/FR pairs at equal volume; 3D voices use [6,8,7,9] at one volume. A 2D voice on FL/FR
at gain g plays g per side under both max and any downmix, so A1 is refuted for 2D voices. For 3D voices
the max does under-play the four slots (1.3).

### 1.2 What each voice puts into the mix

Contribution = volume register + RMS of the voice's whole source buffer. 3D figures assume 0 dB HRTF gain;
under L1 normalisation |H(f)| <= 1, so 3D figures are upper bounds, not values.

| moment | speech v65 | 2D music | 3D bed | speech-music dB | speech-rest dB |
|---|---|---|---|---|---|
| slot0 | -13.4 + -16.4 = -29.8 (pauses 0.11, centroid 901 Hz, speech band 0.57) | v85 -35.7, v86 -38.5; sum -33.9 | v4/v5/v6 share one buffer (source -26.7, 136 Hz) at -11.1/-12.3/-10.3; v10, v0, v2 below -44; sum <= -32.7 (-28.4 coherent) | +4.1 | +0.5 (-2.5 coherent) |
| slot1 | -13.4 + -21.8 = -35.2; -32.2 while active (pauses 0.50, 580 Hz) | v85 -34.2, v86 -39.9; sum -33.2; v75 paused | 8 live (v0,4,5,6,7,8,16,18), 140-234 Hz; sum <= -33.4 | +1.0 | -1.9 |
| slot2 | paused (source -16.3, band 0.69; -29.7 if playing) | v85 -31.1, v86 -50.9, v88 -37.9; sum -30.2 | v15 -7.0 + -11.3 = -18.3 (pitch 18.4 kHz, band 0.00, 258 Hz); v5 -28.6; sum <= -17.9 | +0.5 (if played) | -12.0 (if played) |

Reading: the registers put speech at or slightly above the music, so "music is loud" can only mean bed
plus music. The bed is LF rumble, about equal to speech at slot0/1 and dominant at slot2.

### 1.3 What the title's own DSP would do (dsp_harness on slot1, 997 Hz, through Halo's EP/GP)

| bin | to L dB | to R dB |
|---|---|---|
| 0 (FL) | -6.6 | < -30 |
| 1 (FR) | < -30 | -6.6 |
| 2 (C) | -9.6 | -9.6 |
| 6 (xFL) | -6.6 | -31.0 |
| 8 (xBL) | -9.6 | -34.0 |
| 10 (reverb) | -10.3 | -13.8 |

Bins 4/5 -9.6 (EP only). GP flat (0.0 dB at 150/997/3000 Hz); crosstalk -24.4 dB. EP bin-0 sweep
non-monotonic (0 dB at 100/1500/3000/6000/12000 Hz, -3..-8 between): taken as a harness artefact,
unresolved. A 3D voice feeds two left bins with the same ear signal (b>>1): xFL -6.6 + xBL -9.6 =
0.468+0.331 = 0.799 amplitude = +4.65 dB over a single-FL voice; MON_VP's max gives +0. So today's MON_VP
plays the bed 4.65 dB quieter relative to speech than Halo's DSP would (1.8-4.65 under b%2). A2 refuted in
the direction that matters.

### 1.4 Save-state hazard (every 3D A/B)

Saved: hrtf_submix and headrooms (vmstate apu.c:1342-1360). Not saved: `vp.hrtf.entries` (vp.h:92-99,
"FIXME: Stored in RAM") and `vp.filters[v].hrtf`. After a .hxs load, 3D voices run through zero or stale
HRIRs until the guest re-sends SET_HRIR (vp.c:770-794) and SET_VOICE_TAR_HRTF (vp.c:708-724).

### 1.5 X1 BOX 1.2.9 (tag x1box-1.2.9 in ~/hakuX)

MON_VP identical except `g = fmax(g, attenuate(vol[b]) / hr)`, hr = 1 << submix_headroom; Halo's headroom
is 0, so a port changes nothing for Halo (MKSM, h=1, would lose 6 dB). hrtf.h: same L1 normalisation,
`break` where rc1 has `continue` (when the left ear sums to 0 or 1 the right ear is not normalised).
5681bf2fc9 changes timing, not level. Nothing in 1.2.9 worth porting for #938.

## 2. Hypotheses (P sums to 1.00)

| id | hypothesis | P | win | HIT | MISS |
|---|---|---:|---|---|---|
| H2 | faithful: hakuX plays Halo's mix as programmed; quiet speech = title's LF bed + music on the Nova speaker | 0.30 | none from the emulator | owner's Xbox, same cinematic and speaker: speech as buried; Nova leg A speech-music within 1 dB of +4.1/+1.0 | speech plainly over the bed on the Xbox, or leg C/R/H hits |
| H1 | HRTF scale: hrtf.h L1 normalisation leaves the bed louder than hardware | 0.20 | 3 dB slot0/1, up to 12 dB where the bed dominates | `apuhrtf` l1<1 for bed voices (v4/5/6, v15); leg C or R puts `apumeter 3d=` >=3 dB under A, raises speech-rest median 3 dB, clips no more | l1>=1 on bed voices, or `3d=` within 1 dB across A/C/R |
| H3 | speech stream starves under the sub-30 fps cinematic (#1018) | 0.12 | speech gaps filled | `apuvoice sslempty v=65` (vp.c:1322) > 0 in leg A, or `pause=65:n` mid-sentence | zero sslempty v=65 and pause=65 only at line ends, both runs |
| A2 | the title's DSP balance favours speech | 0.06 | - | leg D raises speech-rest >=3 dB over A | (predicted) all -6.6 dB, speech-bed ~4.6 dB lower |
| A6 | I3DL2 (fmode 3) not emulated on 3D voices (vp.c:2108-2110), ParaEQ FIXME vp.c:2144 | 0.05 | 0-6 dB on the bed | FCA/FCB coefficients from the .hxs show a cut >=3 dB on the bed | pass-through coefficients |
| A4 | volume decode error | 0.04 | - | `apumix` volume disagrees with soloed level | match within 1 dB |
| A1 | MON_VP max-over-bins under-plays speech | 0.03 | - | `apumix` shows v65 on unequal or extra bins | v65 on bins 0/1 at one volume (already true at all three slots) |
| - | other (ADPCM decode level of dialogue, Nova output path, owner's reference) | 0.20 | | | |

The real Xbox decides H2 vs H1; the Nova A/B can size the HRTF lever but not which scale hardware uses.

## 3. HAKUX_APU_MONVP_DOWNMIX and Halo

Not in rc1 (audio1016 vp.c.patch v2). Weights FL/xFL 1; BL/xBL 0.707; C 0.707 both; LFE 0; sums over a
voice's slots, caps the louder side at 1.0. Halo 2D voices (speech, music) on FL/FR: 0.0 dB change. Halo 3D
voices xFL+xBL / xFR+xBR at g -> 1.707g per side = +4.65 dB (cap acts only above -4.65 dB; bed voices at
-7.0..-12.3, uncapped; v19 at -1.4 dB paused, would be capped to +1.4). Net for #938: speech-rest +0.5 ->
-2.75 dB at slot0, -1.9 -> -4.8 at slot1: 3.2-4.65 dB worse (though it matches Halo's own DSP sum under b>>1).
Default-on risk: every DirectSound3D voice on the standard four-slot crosstalk layout gets +4.65 dB against
2D music and speech, in every 3D title; none screened. If #984 needs it, gate out 3D voices (R2); MKSM's quiet
voice v164 is 2D (index >= 64) and keeps +7.46 dB.

## 4. Remedies by P x win

- R1 `HAKUX_APU_HRTF_NORM` = l1 (default, today) | cap (divide only when sum|c| >= 1) | raw (int8/128 taps as
  sent) | off (skip the FIR, = audio.hrtf=false). Log `hrtf_norm: <mode>`. Code: meter_plus_norm.diff
  (switch + meter), hrtf_norm_switch.diff (switch alone). Default stays l1 until A/B and Xbox reference agree.
  Risk: changes every 3D voice in every title. P x win 0.20 x 3-12 dB.
- R2 keep the downmix off 3D voices, only if HAKUX_APU_MONVP_DOWNMIX goes default-on for #984:
  `if (monvp_downmix_on() && v >= MCPX_HW_MAX_3D_VOICES && ...)`, opt-in HAKUX_APU_MONVP_DOWNMIX_3D=1. Guard, not fix.
- R3 the #1018 fps fix, only if H3 hits; judged by `sslempty v=65` and `pause=65`.
- Not recommended: use_dsp default-on (speech -6.6 dB, bed +4.65 relative; audio1016's blockers; NEW third
  blocker: a mono 3D voice sends only the left-ear HRTF output to all four crosstalk bins,
  `samples[i][b % channels]` vp.c:2157 with channels=1); an X1 BOX port; the downmix as it stands.

## 5. Nova A/B

Build: b12a313033 + meter_plus_norm.diff (passes `git apply --check`, not compiled by the agent). New lines
(tag hakuX-audio): `apu_meter: on`, `hrtf_norm: <mode>` once; every 5 s `apumeter w= 3d= 2d= top=v:dBFS,...
pause=v:n,...` (MON_VP only); `apuhrtf v= h= l1=L/R l2=L/R dc=L/R itd=` on a voice's first HRTF bind per
window and every 50th.

| leg | env (all + HAKUX_APU_MIXLOG=1 HAKUX_APU_METER=1 HAKUX_APU_VOICELOG=1) | for |
|---|---|---|
| A | - | baseline; bed HRIR scale; H3 |
| C | HAKUX_APU_HRTF_NORM=cap | H1 |
| R | HAKUX_APU_HRTF_NORM=raw | H1 |
| H | HAKUX_APU_HRTF_NORM=off | upper bound of the HRTF lever |
| D | HAKUX_APU_USE_DSP=1 | A2 prediction (`apudsp`, `level`) |

Load slot0.hxs, run ~80 s through slot1 (+38 s) and slot2 (+69 s); two runs per leg. Validity: `apu_meter:
on` and `hrtf_norm:` present; `apuhrtf` lines for v4/5/6 by window 1; `3d=` above -45 dBFS; if the guest
never rebinds HRIRs (1.4) every 3D leg is void (would need a from-boot route); drop windows before the first
`apuhrtf`. Read: meter_read.py; audio1016's method via lvl_tt.py on `level L/R:` (medians of 5 s windows,
energy-differenced from cumulative acrms, speech span vs reference span); `grep 'apuvoice sslempty v=65'`.

Desktop (hakux-desktop.service, xemu GL): .hxs already gives the voice layout; a desktop run adds only the
`apuhrtf` numbers and needs DC_BASE_ISO -> Halo ISO, a route or desktop-loadable state, HAKUX_APU_* passed
through desktop_channel.sh (passes only HAKUX_RENDERER today, :620-642), stderr captured, > DC_TIMEOUT 420 s.

## 6. Shared with MKSM #984 and others

Same code, opposite effect: MKSM's quiet voice is multi-bin speech (v164 xFL,xBL,xFR,xBR,C at -11.2 dB)
under-played 7.65 dB by the max; in Halo the multi-bin voices are the bed. The fix for one is the
regression for the other. MKSM h=1, Halo h=0. Halo's hrtf_submix [6,8,7,9] = L,L,R,R supports b>>1 over
vp.c:2157's b%2 (DSP path only). Save-state HRIR loss affects every save-state A/B of a 3D title (and users
loading a state). One flat downmix table cannot fit every title.

Owner question (not blocking): on the real Xbox, same speaker or headphones, does Keyes/Cortana sit clearly
over the ship hum in this cinematic?
