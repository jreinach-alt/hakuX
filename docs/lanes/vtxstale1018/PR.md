# vk: bring a frame slot's vertex RAM current by page, not by span (#1049)

State: draft

Lane: vtxstale1018            Issue: #1049 #433
Base: master @ 7e00c7cf73
Files: docs/lanes/vtxstale1018/PR.md, docs/lanes/vtxstale1018/NOTES.md, docs/lanes/vtxstale1018/FINDINGS.md, hw/xbox/nv2a/pgraph/vk/vertex.c, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.h
Prediction: none: analysis-only (so far)
Needs device: yes    Needs NDK: yes
Selftest: none -- not yet written

At each frame-slot rotation, `pgraph_vk_finish()` copies the incoming slot's
vertex-RAM buffer current over one span from the lowest to the highest byte
uploaded while it was not current. On GTA III on foot that turns 129 KB/flip of
uploads into about 30 MB/flip of copy (2.19 ms/flip on the PFIFO thread). This
change tracks the stale pages per slot and copies only those.

Work in progress.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
