# haloshadow1017: Halo CE's dark squares under soldiers' feet: the stock Adreno driver, not the code (#1038)

State: ready

Lane: haloshadow1017            Issue: #1038
Base: master @ 9abd80e90c (merged; branched from 8d260f39fc)
Files: docs/lanes/haloshadow1017/NOTES.md, docs/lanes/haloshadow1017/PR.md, docs/lanes/haloshadow1017/tools/chain.py, docs/lanes/haloshadow1017/tools/desk-xid-unbound.patch, docs/lanes/haloshadow1017/tools/deskbuild.sh, docs/lanes/haloshadow1017/tools/deskrun.py, docs/lanes/haloshadow1017/tools/footsq.py, docs/lanes/haloshadow1017/tools/hxsram.py, docs/lanes/haloshadow1017/tools/projgd.py, docs/lanes/haloshadow1017/tools/rbread.py, docs/lanes/haloshadow1017/tools/smap.py, docs/lanes/haloshadow1017/tools/sqcrop.py, docs/lanes/haloshadow1017/tools/syncctl.c, docs/lanes/haloshadow1017/tools/texids.py, docs/lanes/haloshadow1017/tools/tint.py, hw/xbox/nv2a/pgraph/vk/renderer.c
Prediction: none: analysis-only (the defect is the package's GPU driver; renderer.c gains frame-dump fields only)
Needs device: no    Needs NDK: no

Every sighting of the dark squares under Halo: Combat Evolved's soldiers ran on the stock Qualcomm Adreno driver. In
the morning capture, logcat line 124 says `no custom driver installed`, line 471 says `Qualcomm Technologies Inc.
Adreno Vulkan Driver` and line 518 says `[gpl569] ext=0 ... mode=0`. The owner's 13:32 retest used the same package
(the release app, uid u0a144), the same save state and the same switches, with Turnip T30 loaded (`GPU:
PurpleVK-public Adreno (TM) 740`, `ext=1 ... mode=3`). It draws a small soft shadow at each soldier's feet and no
squares. Both runs use the same projection shader key (4ab25e73) and the same draw-path pattern.

Measured by region, frame-matched (`tools/footsq.py`, aligned on a static background box):

| pair | shift, background MAD | floor inside square 1 (A/B r, g, b) | floor inside square 2 | controls |
|---|---|---|---|---|
| stock f004 / Turnip f004 (Nova) | (6,0), 2.84 | 0.751, 0.732, 0.782 (1243/1408 px darker) | 0.805, 0.734, 0.816 (1140/1440) | 0.999-1.003 |
| Turnip f004 / desktop lavapipe L4 f003 | (0,0), 0.31 | 1.000, 0.999, 0.999 (0 px) | 0.998, 0.998, 0.999 (20 px) | 0.998-1.000 |

Two conformant drivers, Turnip on the Adreno 740 and lavapipe on the desktop, agree within 0.2% inside the squares,
in different pipeline modes. Stock darkens the same floor by 18-27%, green most (the mauve tint), and draws no
silhouette. The emulator's chain is correct on both: the 128x128 targets hold the silhouette and its blur (save-state
RAM), and the desktop drew the soft shadow in every pipeline mode and draw path tried (L1-L4). Sync validation (L5)
reported no hazard, and its positive control logs one. Core validation (L6) reported no error over 218 projection
draws in the Nova's pipeline mode and draw-path pattern, and its positive control logs one. So the emulator's
stream is valid as far as the layer sees, and there is no invalid usage to fix.

`NOTES.md` section 9 accounts for every symptom and holds the closed hypothesis table. The same cause is behind
#1043 (bind pose, bindpose1017) and #1039 (Halo's rear lights; the owner confirmed them gone on Turnip). The August
video's box is a different title (UC2) and colour on a Turnip build, and it is not explained here.

## Remedies (P × win; bindpose1017's R1-R4 apply unchanged)

1. R1: Turnip T30 in the package. P 0.95, measured. Done on the owner's release app: the 13:32 retest ran it.
2. R2: Turnip by default on Adreno 6xx/7xx (a bundled driver, the menu as the override). P 0.9, every release user.
   The owner's decision; lane.local has put it to them for #1043.
3. R3: a launch guard on kgsl with no custom driver. It stops silent stock runs; moot if R2 lands.
4. R4: a stock workaround. Not chased: under the owner's 10-17 rule the stock driver is never used or tested.

## What is in the diff

`hw/xbox/nv2a/pgraph/vk/renderer.c`: frame dump schema 10, diagnostics only, armed by `XEMU_FRAME_DUMP`. The
`rttmaxNN` token reads back render targets above 64x64. Each stage records which view its descriptor names ("bv",
"pv", "tv", and a "pvi" readback for a foreign view). Each draw records "ptd". R5G6B5 and A1R5G5B5 surfaces are read
back. It adds no NV097 register sites; the index citations into renderer.c drift by lines only (preflight's index
check passes, and fold regenerates the index under `check --exact`). The rest is lane notes and tools.

Release note (none): frame-dump instrumentation only; nothing changes unless a dump is armed.

Preflight (`--allow-tracker`, 15:1x PDT) passes psh_differ, aci_vmstate, the nv2a index and board files. Two
board-side gates fail, and neither is this branch's:
- `territory`: "ui/xemu.c is listed FREE but claimed by haloship1017". This branch does not touch ui/xemu.c.
- `coverage`: #1045 has neither a lane nor a blocker. lane.xbox requested its `[lane.bootstatic1017]` row at 14:40.

Selftest fragments, chosen by reading the diff:
- `75-nv2a-index.sh` and `75-nv2a-index-drift.sh`: renderer.c moves lines that the index cites, and `check` must
  pass pure drift.
- `75-fold-exact.sh` and `90-fold-index.sh`: fold regenerates the drifted index under `--exact`.
- `98-lane-shape.sh`: the lane files are under `docs/lanes/haloshadow1017/`.
- `99-release-note-line.sh`: an emulator path changed, so the body carries the Release note line.

No fragment reads the frame-dump schema.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
