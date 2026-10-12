nfsaudio1011: NFS Most Wanted audio stutter -- the APU plays 50 ms-old audio in place of ~15% of the sound (#433, 0.5)
State: draft

Lane: nfsaudio1011      Issue: #433 (umbrella), none filed
Base: master @ aa04c62915
Files: hw/xbox/mcpx/apu/vp/vp.c, hw/xbox/mcpx/apu/apu_int.h, docs/lanes/nfsaudio1011/**, docs/testing/predictions/nfsaudio1011-*
Prediction: none yet (identify prediction to be registered before the first device run)
Needs device: yes (Nova)    Needs NDK: yes

Work in progress. Step 1, an env-gated `HAKUX_APU_VOICELOG=1` voice log and stale-read detector in vp.c (off by
default), is committed. The wake keys show the APU interrupt never wakes the guest (NOTES.md). Step 2, the identify
run, is next.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
