Lane: blinx372c            Issue: #372
Base: master @ 6c25a829ef
Files: docs/lanes/blinx372c/NOTES.md, docs/lanes/blinx372c/comment-372.md, docs/lanes/blinx372c/demobound.py, docs/lanes/blinx372c/pr-body.md, docs/lanes/blinx372c/stallread.py, docs/testing/predictions/blinx372c-demo-soak.json
Prediction: docs/testing/predictions/blinx372c-demo-soak.json @ 475ff4d9502379c22b14b935554bba77e573b7379061d0a96975f0fb78399eb3   (a soak, not an A/B arm; arms.sh skips soaks)
Needs device: yes    Needs NDK: no

This PR names the SURFACE_DOWN site behind the two `Sd` finishes per frame in Blinx's attract demo: **`vk/surface.c:update_surface_part`, the incompatible-binding eviction**. They are completed by the synchronous `pgraph_vk_finish` in `pgraph_vk_surface_update`.

| result (Thor, apk 0550f75e2024) | sd/frame | cDef share | evict dl = cDef | demo fps | prediction |
|---|---|---|---|---|---|
| 1790424874-blinx372c-754046 (frames) | 2.0 | 1.00 | 120/120 on every line | 12.6 | 8/8 PASS |
| 1790425369-blinx372c-1062368 (no frames) | 2.0 | 1.00 | 120/120 on every line | 12.4 | 8/8 PASS |

- **Verdict on the falsifier:** removable in kind. It is not the guest's own readback, since pDl = 0 and dl = 0. The emulator ping-pongs two incompatible host images of one guest address through VRAM. The pixels are consumed by the stale re-upload, so the hunk must copy them on the GPU rather than skip the download.
- **Price (a bound):** the waits sit in `Sub` (qemu_event_wait), with a median of 34.5-34.8 ms per frame. Removing them with GPU work unchanged gives a GPU-bound ceiling of about 21-23 fps (`demobound.py`).
- **Hunk:** the incompatible branch of `update_surface_part` records a GPU-side copy into the next binding. It overlaps and depends on vk/surface.c's CPU-access watch (lane.surfwatch382).
- **Corrections:** P4's label passed but its stated mechanism (texture_bind) is refuted. `stallread.py`'s Fen-based price used the wrong timer.

No hw/ file is edited. Details and the do-not-repeat list are in docs/lanes/blinx372c/NOTES.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
