# lane.blinx372d -- #372: remove the two synchronous surface downloads in Blinx's attract demo

Issue: #372. Base: origin/master @ a5b5b628f2 (includes PR #387, lane.surfwatch382: the CPU-access watch suspension).
Files: hw/xbox/nv2a/pgraph/vk/surface.c, docs/lanes/blinx372d/**, docs/testing/predictions/blinx372d-*.json.
       vk/surface.c was released by lane.surfwatch382 and is free. vk/draw.c is lane.remote's (#274, PR #389 draft): do not touch it.
Needs device: yes (Thor soak for the arm; desktop for the design). Needs NDK: no.
Read first: docs/lanes/blinx372c/NOTES.md and the last comment on #372 (12:32Z), docs/lanes/surfwatch382/NOTES.md.

## What is settled
The demo's frame is Tot 64-70 ms, of which `Sub` 34.5-34.8 ms is two synchronous `pgraph_vk_finish(SURFACE_DOWN)` per
frame. Site: the incompatible-binding branch of `update_surface_part` in vk/surface.c. The guest binds a surface where a
draw-dirty binding sits, `check_surface_compatibility` fails (colour/zeta role, vk_format, pitch or size), the old binding
is deferred-downloaded and shelved, `pgraph_vk_surface_update` completes that download synchronously, and the partner
binding is unshelved stale and re-uploads what the other drew. No guest CPU access asks for these (pDl=0, dl=0). The
wait is in the phase line's Sub, not Fen. Ceiling if both waits go: about 21-23 fps at the median (bound, not a value).

## The job
1. First, one counter: which compatibility field fails on this path (role, format, pitch, size), from a Thor soak line.
   A pitch-only or size-only mismatch is a plain `vkCmdCopyImage`; a role swap (colour<->zeta) needs a conversion pass.
2. Then the hunk: record image -> buffer -> image on the GPU into the next binding instead of the host finish, leaving the
   shelved binding draw-dirty so the CPU copy happens only if the CPU touches the memory. That depends on the watch
   surfwatch382 landed being the only guard against a later CPU read of stale VRAM: say how the two interact and test it.
3. Price it offline before the arm; if only one branch of the counter is cheap, land that branch only.

## Falsifier and arm
Mover: sd/frame 2.0 -> 0 and demo fps from 12.5 toward 20 on the same-session Thor A/B (the 8-leg blinx372c prediction is
the template). Must-not-move: Depth buffer fixed function (the Z16/Z24 flips named on the branch's comment), every
Color_zeta_overlap and Surface_format capture, and PR #387's arm. Name what would move each. Check `status` for unreadable rows.

## Done when
NOTES.md holds the counter result, the interaction with the watch, the priced hunk and the A/B; the prediction is registered
after the last rebase; before marking ready merge master and re-run the arm; PR is ready.
