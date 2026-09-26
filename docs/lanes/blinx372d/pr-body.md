Lane: blinx372d            Issue: #372
Base: master @ a5b5b628f2
Files: hw/xbox/nv2a/pgraph/vk/surface.c, docs/lanes/blinx372d/NOTES.md, docs/lanes/blinx372d/pr-body.md
Prediction: pending (docs/testing/predictions/blinx372d-*.json, registered after the last rebase)
Needs device: yes    Needs NDK: no

Removes the two synchronous `pgraph_vk_finish(SURFACE_DOWN)` calls per frame in Blinx's attract demo. They come from the incompatible-binding branch of `update_surface_part`. Work in progress.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
