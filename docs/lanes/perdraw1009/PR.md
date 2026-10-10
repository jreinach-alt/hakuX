# perdraw1009: cut the renderer's per-draw CPU cost (NFS Most Wanted, ~11 us per draw) (#433, 0.5)

State: draft

Lane: perdraw1009          Issue: none (#433 umbrella)
Base: master @ 39379dafdd
Files: docs/lanes/perdraw1009/PR.md, docs/lanes/perdraw1009/NOTES.md, docs/lanes/perdraw1009/OUTBOX.md, hw/xbox/nv2a/pgraph/vk/shaders.c, hw/xbox/nv2a/pgraph/vk/renderer.c, hw/xbox/nv2a/pgraph/vk/renderer.h, docs/testing/titles/routes/nfs-mw.route, docs/testing/predictions/perdraw1009-*.json
Prediction: not yet registered
Needs device: yes (Nova only)    Needs NDK: yes

Work in progress: reading `flush_draw_one_pass` and its callees against lane.local's
10-09 NFS profile; NOTES.md first.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
