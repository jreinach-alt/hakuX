# fpsnext1019: GTA III driving, Blinx 2 and Fable toward 30 fps (#433)

State: draft

Lane: fpsnext1019            Issue: #433
Base: master @ 5dc1218a8f (+ merge of lane/fpsdata1018 @ 0fd255d991, mid-fold; dropped once it lands)
Files: docs/lanes/fpsnext1019/NOTES.md, docs/lanes/fpsnext1019/PR.md, docs/lanes/fpsnext1019/FINDINGS.md, android/app/src/main/cpp/xemu_android.cpp, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/texture.c
Prediction: none: measurement first (frame trace and render-mode A/B on the owner's scenes); a prediction is registered before any build
Needs device: yes    Needs NDK: yes

Measures where the frame goes in GTA III's in-car scene and Blinx 2's gameplay, and lands the levers that move them
toward 30 fps. Detail in `docs/lanes/fpsnext1019/NOTES.md`; per-title table in `FINDINGS.md`.

Release note (none): measurement only so far.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
