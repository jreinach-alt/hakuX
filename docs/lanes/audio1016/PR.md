# audio1016: quiet speech and movie audio on the Nova (#984, #938)

State: ready

Lane: audio1016         Issue: #433 #984 #938
Base: master @ 4bf47129b1
Files: docs/lanes/audio1016/**, hw/xbox/mcpx/apu/debug.c, hw/xbox/mcpx/apu/apu_debug.h, hw/xbox/mcpx/apu/dsp/gp_ep.c, docs/testing/predictions/audio1016-identify.json, docs/testing/predictions/audio1016-cutscene.json
Prediction: docs/testing/predictions/audio1016-cutscene.json @ 07a76a1f4f7004ccaf6a63264f7287854ef75c4a4d83654c8f7383ca7e0d67d1 (judged; earlier: audio1016-identify.json @ 4f98e09fca360bdd6279896f767bb9c35cf903f16113d634b3a7b79ab6322bd4, judged)
Needs device: no    Needs NDK: yes

Release note (none): HAKUX_APU_MIXLOG (a per-voice mix and cost log) and HAKUX_APU_USE_DSP (plays the title's DSP program, as the Real-time DSP setting does), both off by default.

**Cause, measured on the Nova (MKSM, #984).** With the title's DSP program off (MON_VP, the Android default), each
voice plays at the largest of its eight slot volumes. The title's own GP/EP program adds the voice's speaker bins into
each output side instead. MKSM's cutscene voice (Raiden, v164) sits at -11.2 dB in five bins: xFL, xBL, xFR, xBR and C.
In the Goro's Lair cutscene, medians of the 5 s level meter, dBFS:

| run (4d736d2b8c) | speech | gameplay after | menus before | speech above gameplay |
|---|---|---|---|---|
| A: today, switch off | -29.34 | -29.10 | -26.83 | -0.24 |
| B: switch v2 on | -22.15 | -29.61 | -26.88 | **+7.46** |
| D: the title's own DSP program | -30.45 | -34.94 | -30.90 | **+4.49** |

The title's program lifts the speech 4.5 dB over its gameplay; today's mix does not lift it at all. The offline
harness, which runs the title's program from the owner's save state, predicted +3.6 to +5.2 dB.

These speech and gameplay spans are not registered legs. They are the letterboxed frames, a rule fixed from run A's
frames before any level was read. The registered legs were scored as written:
- PASS: L (a voice in 4 or more bins), S (menus unchanged by the switch, -0.05 dB), DC cost (286 us of 667), and C on
  both channels.
- FAIL: U, both DL windows and Q. The registered "cutscene" window was about 70% gameplay, because the cutscene is
  45-55 s, not the assumed 120 s or more. Q's "pre" was menus, which NOTES said before the results came in.
- FAIL: DC starve. The Nova kept up.

The full table is in NOTES.md.

**Switch, in `docs/lanes/audio1016/vp.c.patch` (v2), not in this diff.** `HAKUX_APU_MONVP_DOWNMIX=1` sets each side's
gain to the voice's speaker-bin gains weighted by the DSP matrix's direct terms, with the louder side held to 1.0.
On the Nova:
- Speech +7.19 dB, menus -0.05, gameplay -0.51.
- About 3 dB hotter than the title's own balance, as predicted for flat weights on a crosstalk-routed voice.
- Crimson Skies (loud title): clipped samples 84 / 73 with and without it, acrms +0.02 dB.
- No fps or CPU change: vp_us 156 vs 154.

The patch applies cleanly on master 4bf47129b1. vp.c was lane.x1port1012's file when this lane was briefed; that lane
has since folded. NOTES.md carries the NEED line.

**The faithful path (use_dsp) is affordable but not yet the fix.** MKSM's GP/EP program costs 263 + 186 us per frame
on the Nova, with APU util 0.68 (max 0.74), no starvation and no fps change. Two measured blockers remain:
- The whole mix is 4-6 dB quieter (submix headroom), and the speech is no louder (-1.1 dB).
- v164's stereo speech plays as mono: L/R correlation 0.99, against 0.65 today. voice_process's `b % channels` feeds
  both front crosstalk bins from the left channel.

Ranking, probability times win:
- Switch v2 as the default (P about 0.75, medium win), through the default-on screen.
- The faithful path as its own lane, started now (P about 0.3 today, largest win): a makeup gain and the
  slot-to-channel rule.

**Coverage.**
- MKSM: measured.
- Shrek 2: predicted. Its measured 7.5 dB loss matches an FL+C+BL layout's +7.65, but the layout is unseen.
- Lemony Snicket: no data. Neither title has a profile, so each needs an owner save state or a MIXLOG session.
- Halo #938: open. The identify run was void. The hrtf.h per-ear fix (d88374737c) is the other candidate and needs an
  owner session.

Listening copies for the owner are in `D:\hakux-staging\audio1016\`: A (switch off), B (switch on), D (title DSP).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
