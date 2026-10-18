# gta3drive1017: Grand Theft Auto III drops into the teens while driving (#433)

State: draft

Lane: gta3drive1017            Issue: #433
Base: master @ afde9a4677
Files: hw/xbox/nv2a/pgraph/vk/texture.c, docs/lanes/gta3drive1017/PR.md, docs/lanes/gta3drive1017/NOTES.md, docs/lanes/gta3drive1017/owner_play.tsv, docs/lanes/gta3drive1017/pilot343857_waits.tsv, docs/lanes/gta3drive1017/pilot343857_waits.bands, docs/lanes/gta3drive1017/pilot346093_waits.tsv, docs/lanes/gta3drive1017/pilot346093_waits.bands, docs/lanes/gta3drive1017/tools/owner_play.py, docs/lanes/gta3drive1017/tools/drive_split.py, docs/lanes/gta3drive1017/tools/ft_waits.py, docs/lanes/gta3drive1017/tools/route_gate.py, docs/lanes/gta3drive1017/tools/drive_judge.py, docs/lanes/gta3drive1017/tools/pixel_noise.py, docs/lanes/gta3drive1017/tools/capture_history.py, docs/lanes/gta3drive1017/routes/gta-3-drive.route, docs/lanes/gta3drive1017/routes/refs/gta-3-drive/enter-help.png, docs/lanes/gta3drive1017/routes/refs/gta-3-drive/fist-hud.png, docs/lanes/gta3drive1017/routes/refs/gta-3-drive/at-kuruma.png, docs/testing/predictions/gta3drive1017-drive.json, docs/testing/predictions/gta3drive1017-pixels.json
Prediction: docs/testing/predictions/gta3drive1017-drive.json @ 678376d73ae12a502e32b2079d10ac680cd01658309ee58d817c08adc077104f, docs/testing/predictions/gta3drive1017-pixels.json @ 01b0fd3bb866e23cf7692e74d6f355715f8806ec6e9abe5109b519460bc1bda6
Needs device: yes    Needs NDK: yes
Selftest: none -- the emulator change (texture.c) is built by CI and pixel-judged by the pgraph suite arms; the lane files and the two prediction files are read by no fragment (the fragments that parse predictions, 40-arms-refusal, 92/94/99-arms-*, 98-lane-shape, build their own fixtures).

GTA III (5454000E) is rated Playable on the Nova from an on-foot route. The owner's 10-17 play on 0.5.2-rc1 (Turnip,
mode 3) dips into the teens while driving. This lane located the wait and removes it.

**The wait** (NOTES.md 6.2, pilot 1-1792275531-...-343857, perflog + FRAMETRACE on Turnip). In the driving windows
under 26 fps, the PFIFO thread sleeps 14.3 ms/frame in vkWaitForFences. 11.6 ms/flip of that is create_texture's
#474 drain (`pgraph_vk_flush_all_frames`) ahead of the surface-to-texture copies: 72 drains and 73 copies a flip,
against 2 and 2 at 30 fps. The GPU is busy 21.9 ms of the 47 ms frame. The vCPU then waits 7.5 ms/flip for
pgraph.lock, which the drain holds.

| band (pilot 1) | windows | fps | faf ms/flip | faf n/flip | PFIFO fence ms/frame | vCPU lock ms/frame | GPU ms/frame |
|---|---|---|---|---|---|---|---|
| >= 28.5 | 78 | 29.9 | 2.5 | 2.0 | 2.4 | 1.5 | 14.1 |
| 26-28.5 | 31 | 27.5 | 7.4 | 13.0 | 8.5 | 3.5 | 16.2 |
| < 26 | 111 | 21.2 | 11.6 | 71.9 | 14.3 | 7.5 | 21.9 |

**The change** (texture.c). A plain colour copy (vkCmdCopyImage) no longer drains the in-flight frames first. The
copy is recorded in the frame's own command buffer. Its barrier out of SHADER_READ_ONLY (image.c, srcStage
FRAGMENT_SHADER) has every earlier submission on the one VkQueue in its first scope, and frames are submitted in
recording order. So the copy cannot overwrite the node while an earlier frame still samples it. This is the same
argument as texscan's copy, and the same path a node older than three submits already takes.

Unchanged: zeta copies, HAKUX_S2T_CVT's converting copy, and upload copies keep the drain. `HAKUX_S2T_DRAIN=1`
restores the old drain, which is the A arm. A run prints `[s2tdrain] first skip` once, the first time a copy skips a
drain it would have had.

**Arms** (queued by the lane; one build, env A/B):

- gta3drive1017-pixels.json: drain474's seven surface-as-texture pgraph suites.
- gta3drive1017-drive.json:
  - two runs per arm on the driving route (`routes/gta-3-drive.route`, gated on the scene beside the Kuruma. The
    help-box gate voided the first pair: NOTES.md 8.2);
  - then one per arm on the on-foot gta-3 route.
- The bar: B's driving at >= 28.5 fps for >= 90% of the moving window, with on foot not regressed.

**Pixel suites** (B 1-1792280141-...-1361822, A 1-1792280164-...-1362137; NOTES.md 8.1). Neither arm reached the
changed branch: no `[s2tdrain]` line in either run, and the switch's only reader sits on that branch. So the same code
ran in both. ab_compare's 33 movers are run-to-run variance:
- 31 shadow_comparator captures at +-80/86 px. Same-ref pairs at the base move 20 and 37.
- CPUWriteIgnoresSurfaceConfig: a stripe race already seen in two runs from before this change.
- FramebufferNotModifiedBySurfaceState: one pixel.

Suite totals match between arms. The skip's pixels are judged on GTA III's drive frames.

Release note (performance): Grand Theft Auto III no longer stalls its renderer on every render-to-texture copy, the
cause of the drops into the low 20s and teens while driving.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
