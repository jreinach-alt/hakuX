# halo1016: Halo CE cutscenes on the Nova -- quiet speech under loud music (#938), cinematic at 8-19 fps (#1018)

State: draft

Lane: halo1016            Issue: #938, #1018
Base: master @ 61ae61dd91
Files: docs/lanes/halo1016/**, docs/testing/predictions/halo1016-*.json, hw/xbox/mcpx/apu/vp/hrtf.h, hw/xbox/mcpx/apu/vp/vp.c, hw/xbox/nv2a/pgraph/vk/surface.c
Prediction: docs/testing/predictions/halo1016-cinesplit.json @ 88edbbdfa3e0c12241ab27e0191bd39169bc5f22821408686c6415fdc40d92b8 (judged), docs/testing/predictions/halo1016-speech.json @ 397046c508a1ef966ecbbf8a9f7cd1742d5e156d6af31b3e196a9624ba56d04e (judged), docs/testing/predictions/halo1016-census.json @ 1cb4052f9a4ef54af2a29497ca18fb5144a7f7119a26f556014e9737b40fe179 (queued)
Needs device: yes    Needs NDK: yes

Release note (none): instrumentation only. An off-by-default APU per-voice mix meter (HAKUX_APU_METER) and HRIR scale switch (HAKUX_APU_HRTF_NORM), and an overlap-eviction census line ([ovl1018]) in the Vulkan surface cache; nothing a player sees or hears changes.

This is a deep dive into two defects in Halo: Combat Evolved's opening cinematic on the Nova,
targeting 0.5.2. The owner hit both while playing 0.5.1-rc1 by hand: the dialogue is quiet under
loud music (#938), and a ~47 s stretch runs at 8-19 fps (#1018). Each symptom's account, the
hypothesis tables and the remedies are in `docs/lanes/halo1016/NOTES.md`.

## #1018: what the cinesplit A/B found (judged by cineread.py, committed before either arm landed)

| leg | claim | result |
|---|---|---|
| S | the PFIFO thread is on-CPU for most of the plateau | MISS (the threshold was mis-scaled; see NOTES) |
| G | the GPU is the bottleneck (gpu/P high) | MISS: gpu/P 0.17 |
| W | the off-CPU time is synchronous SURFACE_DOWN finishes | HIT: 61.17 sdown/f, 33.01 ms/f |
| P | sysmem-backed surfaces shorten the period | MISS: period ratio 0.96 |

On the plateau, the draw thread spends ~33 ms a frame blocked in `pgraph_vk_finish(SURFACE_DOWN)`,
at 61 to 129 calls a frame. The guest sits in its idle loop while it waits, and the GPU's own time
is small.

Same-address incompatible evictions (`[evict372]`) are flat over the plateau. The only earlier
perflog soak of the title puts all of its downloads on overlap eviction, at 1/30 of the plateau's
rate. The census pair (`halo1016-census.json`) measures the plateau itself with a new
`[ovl1018]` counter. It splits the downloads between overlap eviction, the texture path and CPU
reads, and tests `HAKUX_S2T_CVT` against them.

## #938: what the speech legs found (judged by speechread.py, committed before either leg ran)

| leg | claim | result |
|---|---|---|
| B | speech sits over music in hakuX, as the registers at two state moments put it | MISS: median -4.3 dB |
| L | the guest's HRIR taps sum under 1, so today's L1 division raises the 3D bed | MISS: l1 ~13 |
| N | the raw HRIR scale lowers the bed 3 dB and lifts speech | MISS: bed 20 dB louder, clips |
| S | the dialogue stream starves in the slow shots | MISS: 0 sslempty |

The HRIR scale and stream starvation are refuted. The music, not the 3D bed, is what sits over
the speech, and hakuX plays it at the title's own registers:
- through the same ADPCM decoder as the speech;
- on the same bins;
- with no filter or envelope on either voice.

The dialogue's margin is +2 dB in the first two minutes and -2 dB in the score's swells. This
PR proposes no #938 change. A hardware listen at the named times decides what is left.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
