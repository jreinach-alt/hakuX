# x1port1012: X1 BOX fixes we still carry, as 0.5.1 candidates (#939, #938)
State: draft

Lane: x1port1012          Issue: #939 [#938]
Base: master @ dd5e3cb3c6
Files: docs/lanes/x1port1012/PR.md, docs/lanes/x1port1012/NOTES.md, docs/lanes/x1port1012/OUTBOX.md, docs/lanes/x1port1012/ccheck.py, hw/xbox/mcpx/apu/vp/vp.c, hw/xbox/mcpx/apu/vp/adpcm.h, hw/xbox/mcpx/apu/vp/hrtf.h, hw/xbox/mcpx/apu/apu.c, hw/xbox/nv2a/pgraph/pgraph.c, hw/xbox/nv2a/pgraph/vk/texture.c, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/instance.c, android/app/src/main/java/com/rfandango/haku_x/SetupWizardActivity.kt, android/app/src/main/res/values/strings.xml
Prediction: none: the ports are correctness fixes judged by a smoke batch (crash, hang, fps against each title's ledger reading), not an A/B on pixels
Needs device: yes (Nova)    Needs NDK: yes

Release note (stability): bad audio data in a game no longer closes the emulator (the voice is skipped); a texture pointing outside video memory draws blank instead of aborting or reading past it; ADPCM audio with an out-of-range step index plays instead of producing noise; a corrupt pipeline cache is discarded instead of crashing at start; no audio device is no longer fatal; the setup wizard rejects a file that is not a 256 KB, 512 KB or 1 MB BIOS.

Phase A of lane.x1port1012: one commit per port from X1 BOX (izzy2lost/xemu), each credited in its
commit message, so any one can be dropped at the 0.5.1 cut.

| commit | change | source |
|---|---|---|
| 81b542ca3e | vp: bad guest voice data skips the voice instead of aborting | X1 BOX c59b1a7ba7, 51e16997ff |
| de06bd39e3 | vk: a texture outside VRAM binds the dummy texture | X1 BOX 39435acbc7, 71604431d6 |
| 79981e045c | vp: ADPCM step index is clamped, not a refused block | X1 BOX d8d73ed85b |
| cbda0e85fd | vk: EDS1 core names alias the EXT ones; a NULL command is refused | X1 BOX d5d64b9dc3, e3c1927bdf |
| d0eb2410b2 | setup: the flash ROM must be 256 KB, 512 KB or 1 MB | X1 BOX a7765290d1 |
| 10c83bfa06 | apu: HRTF history cleared on voice start; no audio device is not fatal | X1 BOX 55262dde6d (two hunks) |
| d4d292c9ca | vk: staging flushed before its copy; UBO barrier reaches the fragment stage | X1 BOX 3d3515faad (flush); fragment stage ours |
| d88374737c | vp: HRTF normalisation skips one channel, not both | ours (X1 BOX has the same bug) |
| 172d94de1f | vk: a rejected pipeline cache file starts an empty cache | X1 BOX 1d10f6cb2a / 67fe8d7b2e |
| 4f0111232c | nv2a: a DMA_VERTEX change bumps vertex_attr_gen | X1 BOX b4999f2e97 (pgraph.c hunk) |

What each port took and left out, and the regression check, are in `docs/lanes/x1port1012/NOTES.md`.
nv2a_index.json is not in this PR: `check` passes and `check --exact` shows only moved lines.

Smoke batch on the Nova (Halo, GTA: Vice City, Crimson Skies against their ledger readings): queued,
results in NOTES.md when judged. Phases B to D (#939, #938, Fable) continue on `lane/x1port1012-halo`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
