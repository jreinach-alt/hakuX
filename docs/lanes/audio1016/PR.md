# audio1016: quiet speech and movie audio on the Nova (#984, #938)

State: draft

Lane: audio1016         Issue: #433 #984 #938
Base: master @ 15a72e10dc
Files: docs/lanes/audio1016/**, hw/xbox/mcpx/apu/debug.c, docs/testing/predictions/audio1016-identify.json
Prediction: docs/testing/predictions/audio1016-identify.json @ 4f98e09fca360bdd6279896f767bb9c35cf903f16113d634b3a7b79ab6322bd4
Needs device: yes    Needs NDK: yes

Release note (none): HAKUX_APU_MIXLOG, a per-voice mix log that is off by default.

**Mechanism, measured offline on MKSM.** When the title's DSP program is off (MON_VP, the Android default), each
voice is played at the largest of its eight slot volumes. The title's own GP/EP program instead adds the voice's
speaker bins into each output side. The program was run on the host from the owner's save state, and its matrix for
bins 0-9 matches Top Spin's. A voice spread over several speaker bins therefore comes out quieter than a voice in
FL/FR alone, relative to how the title mixes it. MKSM's cutscene voice v164 sits at -11.2 dB in xFL, xBL, xFR, xBR
and C. The DSP plays it 3.6-5.2 dB above a single-bin voice at the same volume; MON_VP plays it level with one. That
covers about 4-5 dB of the owner's 8-12 dB gap. Shrek 2's measured 7.5 dB loss fits an FL+C+BL layout (+7.65 dB),
but that layout is not yet measured: there is no Shrek 2 save state and no profile.

| hypothesis | MKSM |
|---|---|
| (a) MON_VP takes the max over bins, not the per-side sum | measured: 4-5 dB |
| (b) PCM decoded low / wrong format | dead (S16 at -17/-15 dBFS in the ring) |
| (c) per-voice headroom field | not supported |
| (d) voice volume envelope stuck low | dead |

**Fix, behind a switch, not in this PR's diff.** `docs/lanes/audio1016/vp.c.patch` adds `HAKUX_APU_MONVP_DOWNMIX=1`:
each side's gain becomes the sum of the voice's speaker-bin gains, weighted by the measured direct terms of the
DSP matrix (front 1, C and back 0.707, LFE 0). It equals the title's downmix for standard 2D layouts and overshoots
v164 by 0-4 dB. vp.c belongs to lane.x1port1012, so the patch is a NEED line in NOTES.md. The registered runs use
a048589ff0, which carries it.

**Instrument.** `HAKUX_APU_MIXLOG=1` (debug.c) logs one `apumix` line per active voice per 5 s window.
`tools/mixlog_read.py` prints each voice's slots, today's gain and the switch's per-side gains.

**Runs registered** (Nova, a048589ff0, 1230 s): MKSM with and without the switch, Halo (#938), and Crimson Skies
with and without the switch (clipping check on a loud title). Legs and probabilities are in the prediction.

Not covered: Lemony Snicket and Shrek 2 have no profile, so the gate refuses runs on them. Their voice layouts need a
save state from the owner (`tools/hxs_voices.py` reads it offline) or an owner session with `HAKUX_APU_MIXLOG=1`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
