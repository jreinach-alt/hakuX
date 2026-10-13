# x1port1012: X1 BOX fixes we still carry, as 0.5.1 candidates (#939, #938)
State: draft

Lane: x1port1012          Issue: #939 [#938]
Base: master @ dd5e3cb3c6
Files: docs/lanes/x1port1012/PR.md, docs/lanes/x1port1012/NOTES.md, docs/lanes/x1port1012/OUTBOX.md, hw/xbox/mcpx/apu/vp/vp.c, hw/xbox/mcpx/apu/vp/adpcm.h, hw/xbox/mcpx/apu/vp/hrtf.h, hw/xbox/mcpx/apu/apu.c, hw/xbox/nv2a/pgraph/vk/texture.c, hw/xbox/nv2a/pgraph/vk/draw.c, android/app/src/main/java/com/rfandango/haku_x/SetupWizardActivity.kt, android/app/src/main/res/values/strings.xml, docs/testing/nv2a_index.json
Prediction: none yet (Phase A ports are correctness fixes on paths the smoke batch reads by crash/hang/fps)
Needs device: yes (Nova)    Needs NDK: yes

Phase A: one commit per port from X1 BOX (izzy2lost/xemu), each credited in its
commit message, so any one can be dropped at the 0.5.1 cut. Work in progress.
