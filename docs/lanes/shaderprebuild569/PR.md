# lane.shaderprebuild569: P3, pre-build known pipelines on a compile pool; save the pipeline cache during play (#569)
State: draft

Lane: shaderprebuild569       Issue: #569, for #433
Base: master @ 2c59b7bbba
Files: docs/lanes/shaderprebuild569/PR.md, docs/lanes/shaderprebuild569/NOTES.md, hw/xbox/nv2a/pgraph/vk/compile_worker.c, hw/xbox/nv2a/pgraph/vk/shaders.c, hw/xbox/nv2a/pgraph/vk/renderer.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/draw.c
Prediction: none yet (to be registered before any device run)
Needs device: yes    Needs NDK: yes

Work in progress. P3 of `docs/lanes/shaderplan569/NOTES.md`: item 5 (is the pipeline cache saved
on Android), then a compile pool, persisted pipeline keys and a background pre-build at title
boot, then keeping `spv_cache/` across a driver-identity change.

Release note (performance): a game you have played before no longer freezes the first time a scene loads.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
