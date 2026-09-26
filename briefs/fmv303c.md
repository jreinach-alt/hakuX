# lane.fmv303c -- #303: Spikeout's FMV green blocks, the surface write-back probe

Issue: #303. Base: origin/master @ 7e6a4ac88a. Continues lane.fmv303b (PR #398, merged): read docs/lanes/fmv303b/NOTES.md sections 4 and 5 and docs/lanes/fmv303b/board_request_surface.md first.
Files: hw/xbox/nv2a/pgraph/vk/surface.c (PROBE HUNK ONLY, granted), docs/lanes/fmv303c/**, docs/testing/predictions/fmv303c-*.json.
       PR #396 (lane.blinx372d, ready) also touches surface.c and released it at ready: before marking your PR ready, merge master
       (or origin/lane/blinx372d if #396 has not folded) and re-run your arm. PR #387 (folded) changed the CPU-access watch in the same file.
Needs device: yes (Thor soak, hands-off, HAKUX_FMV303_PROBE=1). Needs NDK: yes (one hunk). Touches hw/: the PR needs audit.

## What is settled (do not re-measure)
The FMV is a CPU-written linear A8R8G8B8 texture, 640x368, double-buffered at 0x307d000 / 0x3163000. The green (Cr=0, Y and Cb intact) is
already in that guest buffer; display, upload and PVIDEO are exonerated. Tier1 on/off does not move it (0.688 vs 0.680, 2+2 Thor runs): do
NOT re-run that A/B. The tint switches clean/tinted 63 times within shots and differs between runs of one binary: timing-dependent, CPU side.

## The job
1. Add the default-inert probe hunk NOTES s5 specifies, gated on the existing HAKUX_FMV303_PROBE=1: at every point a downloaded surface's bytes
   are copied into d->vram_ptr + surface->vram_addr (download_surface_to_buffer, pgraph_vk_complete_staged_downloads; find them by name, the
   line numbers moved) log `[fmv303] wb addr=%08x len=%x color=%d fmt=%d` with the display frame counter, plus one per-frame counter line so a
   zero is an observed zero.
2. Thor soak, hands-off, two runs, apk_sha per row; join the wb lines to the `tint` lines (docs/lanes/fmv303/guest_tint.py) by frame.
   Question: does a write-back land in 0x3000000..0x3400000, and does it precede tinted frames and not clean ones?
3. Hit: name the stale binding and why it is still dirty, and fix it in surface.c (a second hunk; register it before you measure).
   Zero over >= 100 lit tinted frames with the counter showing write-backs elsewhere: surface write-back is exonerated; probe the APU and IDE DMA
   landing sites next, then step 2b of NOTES s5.

## Falsifier and arm
Registered before the run: "no write-back lands in the FMV region on tinted frames" versus "a write-back lands in the region within 2 frames before
a tinted frame and not before clean ones". A reading of `unreadable`, or fewer than 100 lit frames in an arm, is no reading; read `status` first.
Must-not-move: with HAKUX_FMV303_PROBE unset the hunk changes no behaviour (pgraph suites, Surface_* rows).

## Done when
PR ready, CI green, arm verdict posted, docs/lanes/fmv303c/NOTES.md with the per-run table (run ids, apk_sha) and the branch it selects.
