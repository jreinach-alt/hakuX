# halo1016: Halo CE cutscenes on the Nova -- quiet speech under loud music (#938), cinematic at 8-19 fps (#1018)

State: draft

Lane: halo1016            Issue: #938, #1018
Base: master @ 61ae61dd91
Files: docs/lanes/halo1016/**, docs/testing/predictions/halo1016-*.json, hw/xbox/mcpx/apu/vp/hrtf.h, hw/xbox/mcpx/apu/vp/vp.c
Prediction: docs/testing/predictions/halo1016-cinesplit.json @ 88edbbdfa3e0c12241ab27e0191bd39169bc5f22821408686c6415fdc40d92b8 (judged), docs/testing/predictions/halo1016-speech.json @ 397046c508a1ef966ecbbf8a9f7cd1742d5e156d6af31b3e196a9624ba56d04e (queued)
Needs device: yes    Needs NDK: yes

Release note (none): an off-by-default APU per-voice mix meter (HAKUX_APU_METER) and HRIR scale switch (HAKUX_APU_HRTF_NORM); nothing changes for a player yet.

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
at 61 to 129 calls a frame. The guest sits in its idle loop while it waits. The GPU's own time
is small. The next measurement is a perflog census that names the caller and the
surface-to-texture refusal reason behind those downloads.

## #938

The speech legs (`halo1016-speech.json`: HRIR scale l1 against raw, plus the per-voice meter) are
queued on the Nova. Until they land, nothing in this PR changes what a player hears.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
