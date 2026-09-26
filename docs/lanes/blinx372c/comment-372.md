[lane.blinx372c] Found the site behind the demo's two Sd waits: `vk/surface.c:update_surface_part`, the incompatible-binding eviction. These downloads are not the guest's own readback, so a hunk can remove them in principle.

Two 240 s perflog soaks of the attract demo on the Thor, master 6c25a829ef (apk 0550f75e2024). Both `logcat.spec`s name `hakuX-stall`:

| result | frames | sd/frame | cDef share | evict dl = cDef | demo fps | prediction |
|---|---|---|---|---|---|---|
| 1790424874-blinx372c-754046 | every 30 s | 2.0 | 1.00 | 120/120 on every line | 12.6 | 8/8 PASS |
| 1790425369-blinx372c-1062368 | none | 2.0 | 1.00 | 120/120 on every line | 12.4 | 8/8 PASS |

On all 48 demo lines, per 60 flips: `sd[dl0 cDef120 cDefC0 pDl0 dDl0]`, all `dif` fields 0, and `evict[dl:120 stale:120]`.

**How the two waits happen**
- The guest binds a surface at an address where a draw-dirty binding already sits.
- `check_surface_compatibility` fails, on the color/zeta role, vk_format, pitch or size.
- The old binding is deferred-downloaded and shelved.
- `pgraph_vk_surface_update` then completes that download with a synchronous `pgraph_vk_finish(SURFACE_DOWN)`.
- The partner binding is unshelved as stale and re-uploads from VRAM what the other one drew.
- Two such switches happen per frame.

**Verdict on the falsifier**
- pDl = 0 and dl = 0, so no guest CPU access requests these downloads. VRAM is only the emulator's transfer medium between two host images of one guest surface.
- The pixels are consumed by the stale re-upload, though. So the hunk must copy them on the GPU; it cannot just skip the download.

**Price (a bound, not a value)**
- The wait sits in the phase line's `Sub`, not `Fen`. A pfifo-thread finish waits in `qemu_event_wait` inside `finish_submit`.
- Median over the demo: Tot 64-70 ms, Sub 34.5-34.8 ms (an upper bound on the waits), GPU 42-45 ms.
- With the waits removed and GPU work unchanged, the frame is GPU-bound. The ceiling is **about 21-23 fps** at the median (`demobound.py`), just over the 20 floor, and the real gain could be less.
- A GPU-side copy would also cut the download half of the transfer time. That is bounded by 1000/(Tot - Sub), about 30 fps.

**Hunk, named here and not edited**
- Where: the incompatible branch of `update_surface_part`.
- What it does: records image -> buffer -> image on the GPU into the next binding. The shelved binding stays draw-dirty, so the CPU copy happens only if the CPU touches the memory.
- **It overlaps vk/surface.c's CPU-access watch (surfwatch382), and depends on it.** The watch becomes the only guard against a later CPU read of stale VRAM.
- The golden to watch is Depth buffer fixed function (Z16/Z24 flips), per the comment on that branch.
- Cheapest next step: one counter saying which compatibility field fails. A pitch-only or size-only mismatch is a plain `vkCmdCopyImage`; a role swap needs a conversion pass.

**Corrections**
- The registered P4 passed on its label (cDef), but its mechanism (the texture_bind range path) is refuted.
- `stallread.py`'s Fen-based `ms_per_wait_upper` measures the wrong timer.

Notes: docs/lanes/blinx372c/NOTES.md on PR #388.
