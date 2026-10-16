# audio1016: quiet speech and movie audio on the Nova (#984, #938)

State: draft

Lane: audio1016         Issue: #433 #984 #938
Base: master @ 15a72e10dc
Files: docs/lanes/audio1016/**, hw/xbox/mcpx/apu/debug.c, hw/xbox/mcpx/apu/apu_debug.h, hw/xbox/mcpx/apu/dsp/gp_ep.c, docs/testing/predictions/audio1016-identify.json, docs/testing/predictions/audio1016-cutscene.json
Prediction: docs/testing/predictions/audio1016-cutscene.json @ 07a76a1f4f7004ccaf6a63264f7287854ef75c4a4d83654c8f7383ca7e0d67d1 (earlier: audio1016-identify.json @ 4f98e09fca360bdd6279896f767bb9c35cf903f16113d634b3a7b79ab6322bd4, judged)
Needs device: yes    Needs NDK: yes

Release note (none): HAKUX_APU_MIXLOG (a per-voice mix and cost log) and HAKUX_APU_USE_DSP (plays the title's DSP program, as the Real-time DSP setting does), both off by default.

**Mechanism, measured offline on MKSM.** When the title's DSP program is off (MON_VP, the Android default), each
voice is played at the largest of its eight slot volumes. The title's own GP/EP program instead adds the voice's
speaker bins into each output side. The program was run on the host from the owner's save state, and its matrix for
bins 0-9 matches Top Spin's. A voice spread over several speaker bins therefore comes out quieter than a voice in
FL/FR alone, relative to how the title mixes it. MKSM's cutscene voice v164 sits at -11.2 dB in xFL, xBL, xFR, xBR
and C. The DSP plays it 3.6-5.2 dB above a single-bin voice at the same volume; MON_VP plays it level with one. That
covers about 4-5 dB of the owner's 8-12 dB gap.

| hypothesis | MKSM |
|---|---|
| (a) MON_VP takes the max over bins, not the per-side sum | measured offline: 4-5 dB |
| (b) PCM decoded low / wrong format | dead (S16 at -17/-15 dBFS in the ring) |
| (c) per-voice headroom field | not supported |
| (d) voice volume envelope stuck low | dead |

**Switch, not in this PR's diff.** `docs/lanes/audio1016/vp.c.patch` adds `HAKUX_APU_MONVP_DOWNMIX=1`, which sets
each side's gain to the sum of the voice's speaker-bin gains, weighted by the DSP matrix's direct terms. vp.c belongs
to lane.x1port1012, so the change is a NEED line in NOTES.md.
- **v1 failed the loud-title leg.** Crimson Skies' music plays at full volume in all six 5.1 bins and summed to
  +7.65 dB: clipped samples rose from 84 to 364,669, and acrms from -14.45 to -7.41 dBFS.
- **v2 holds a voice's louder side to 1.0,** today's largest gain, and scales the other side with it. Offline on the
  same tables, Crimson's loud layouts move +0.0 dB while v164 keeps its +7.65.

**Runs on the Nova.**
- **Identify, judged** (a048589ff0): MKSM with and without v1, Halo, and Crimson with and without v1.
  `runs/identify/` holds the tables. The MKSM runs reached only the intro FMV and the attract loop, not the cutscene.
  The Halo run is void.
- **Cutscene, registered** (4d736d2b8c, 1560 s):
  - MKSM through the Goro's Lair cutscene with no input, three ways: today's mix, v2 on, and the title's own DSP
    program (`HAKUX_APU_USE_DSP=1`), with audio captured;
  - Crimson with and without v2.

  Legs and probabilities are in the prediction. The DSP run also measures whether the Nova can run the title's
  program: debug.c's new `apudsp` line gives GP/EP time per frame and APU thread load.

Not covered: Lemony Snicket and Shrek 2 have no profile, so the gate refuses runs on them. Their voice layouts need a
save state from the owner (`tools/hxs_voices.py` reads it offline) or an owner session with `HAKUX_APU_MIXLOG=1`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
