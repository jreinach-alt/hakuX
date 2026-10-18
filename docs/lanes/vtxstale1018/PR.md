# vk: bring a frame slot's vertex RAM current by page, not by span (#1049)

State: draft

Lane: vtxstale1018            Issue: #1049 #433
Base: master @ 7e00c7cf73
Files: docs/lanes/vtxstale1018/PR.md, docs/lanes/vtxstale1018/NOTES.md, docs/lanes/vtxstale1018/FINDINGS.md, hw/xbox/nv2a/pgraph/vk/vertex.c, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/buffer.c, hw/xbox/nv2a/pgraph/vk/vtxstale.h, docs/testing/jobs/selftest.d/99-vtxstale-pages.sh
Prediction: none: no arm -- the change is byte-identical by construction and by the selftest; the device number is a [dipwin] perflog run on the before run's build plus this change (request 1792342997-vtxstale1018-1009067)
Needs device: yes    Needs NDK: yes
Selftest: 99-vtxstale-pages

Each frame slot keeps its own copy of the guest's vertex RAM. When a slot
comes back into use, `pgraph_vk_finish()` brought it current with one copy
from the lowest to the highest byte uploaded while it was out of use. Uploads
are scattered, so on GTA III on foot 129 KB/flip of uploads became about
30 MB/flip of copying, 2.19 of the 2.36 ms/flip the PFIFO thread spends at
frame end.

Each slot now keeps a bitmap of the 4 KB pages uploaded while it was out of
use (the same geometry as `uploaded_bitmap`). An upload marks its pages in
every other slot, and the rotation copies only the marked runs and clears
them. The slot that is not rotated in keeps its marks, so an upload still
reaches every slot of the ring (#39).

| | before (span) | after (pages) |
|---|---|---|
| selftest, 3000 random rotations: bytes copied | 891,623,514 | 118,468,608 |
| selftest: slot bytes different from current at rotation | 0 | 0 |
| GTA III on foot, `[dipwin]` stale ms/flip | 2.19 | pending |
| GTA III on foot, `Fen:` ms/flip | 2.36 | pending |

Release note (performance): less time spent at the end of each frame keeping vertex data in step between frames in flight; measured on GTA III on foot.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
