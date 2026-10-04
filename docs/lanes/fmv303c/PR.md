# #303: surface write-back probe for Spikeout's FMV green blocks (lane.fmv303c)
State: draft

Lane: fmv303c            Issue: #303
Base: master @ 7e6a4ac88a (origin/master merged at cf328d86f7)
Files: hw/xbox/nv2a/pgraph/vk/surface.c, docs/lanes/fmv303c/NOTES.md, docs/lanes/fmv303c/wb_judge.py, docs/lanes/fmv303c/PR.md, docs/lanes/fmv303c/OUTBOX.md, docs/testing/predictions/fmv303c-wb-probe.json
Prediction: docs/testing/predictions/fmv303c-wb-probe.json @ 6b933f6193d59eb8770b1478c64deeefa84bde70d663aa2d05dfa6fbdc318cd6
Needs device: yes (Thor)    Needs NDK: yes

This is step 2a of docs/lanes/fmv303b/NOTES.md s5. A probe that is off by
default (`HAKUX_FMV303_PROBE=1` turns it on) logs every nv2a surface
write-back that lands in guest RAM, with the guest flip count. It covers the
sync copy in `download_surface_to_buffer()` and each staged or deferred copy
in `pgraph_vk_complete_staged_downloads()`. It also logs one cumulative `wbc`
counter line per flip stall, so a zero count is an observed zero.
`docs/lanes/fmv303c/wb_judge.py` joins these lines to the fmv303b tint lines
from the guest buffer. The question: does a write-back land in
0x3000000..0x3400000 before tinted frames and not before clean ones?

Arm: two Thor soaks on cf328d86f7, Spikeout USA disc (re-registered
2026-10-04 before any run: the first two requests named the Europe disc and
were refused before start, display-covered). Run ids and results are in
docs/lanes/fmv303c/NOTES.md.

Territory: `hw/xbox/nv2a/pgraph/vk/surface.c` is held by lane.async794. This
lane's hunk was committed before that grant, under fmv303c's original grant,
and the fold needs a shared grant for it (see OUTBOX.md).

Local checks: wb_judge.py fixtures give none=EXONERATED, onbuf=HIT,
otherbuf=UNORDERED, all=UNORDERED, outside=VOID on the merged tree. The surface.c diff
against origin/master only adds lines.

Release note (none): diagnostic probe, off unless HAKUX_FMV303_PROBE=1.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
