coldstart1010: NFS Most Wanted's first race start after loading, census and largest fix (#433, 0.5)
State: draft

Lane: coldstart1010     Issue: #433 (umbrella), none filed
Base: master @ 9dc20e31f9
Files: hw/xbox/nv2a/pgraph/vk/draw.c, docs/lanes/coldstart1010/**, docs/testing/predictions/coldstart1010-*.json
Prediction: docs/testing/predictions/coldstart1010-depth.json @ 37d06242945828fafab2f2fd7c270ef83c05d979a6257fb45239b72be60dffad
Needs device: yes (Nova)
Needs NDK: yes

Step 1: census of NFS MW's cold race start 1 against the warm countdown, PFIFO thread's ms per frame split by
cause, with GPU busy, render passes per frame and vCPU busy. Step 2: price the remedies by probability x win and
build the top one behind a default-off switch.

Built: `HAKUX_SUBMIT_FRAMES=N` (draw.c, `xemu_set_submit_frames`) overrides the command-buffer ring depth over
the `submit_frames` pref. On the Nova that pref is 2 (the Android default), so every finish's slot rotation waits
for the command buffer submitted one finish earlier. The cold start takes about 3.8 rotations per frame, 1.2 of
them blocking for about 3.4 ms each, with pfifo.lock held. That is where the guest's 9 ms per frame of lock wait
comes from. The A/B is depth 3 against depth 2 (`coldstart1010-depth.json`). Details: `docs/lanes/coldstart1010/NOTES.md`.

Release note (none): opt-in switch HAKUX_SUBMIT_FRAMES, off by default.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
