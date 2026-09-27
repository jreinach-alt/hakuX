# lane.blinx372e -- #372: Blinx's demo size flip, small to big only (one synchronous surface download fewer)

Issue: #372 (0.5, game-visible; Blinx runs 12-15 fps on the Thor, target 30). Base: origin/master @ e5db66fa37 (PR #396 folded).
Files: hw/xbox/nv2a/pgraph/vk/surface.c, docs/lanes/blinx372e/**, docs/testing/predictions/blinx372e-*.json.
       vk/surface.c was released at ready by lane.doa413b (PR #440, xemu-surf logging hunk, in audit, not folded). Before marking
       your PR ready, merge master (or lane/doa413b if it has not folded) and re-run your arm. vk/draw.c is lane.remote's: do not touch.
Needs device: yes (Thor soak for the arm; desktop for the design). Needs NDK: no.
Read first: docs/lanes/blinx372d/NOTES.md sec 1, 3, 5 and "Do not repeat"; #372's 19:20Z comment; docs/lanes/surfwatch382/NOTES.md.
Overlap: lane.slowdown462 (PR #463) measures Blinx on the Nova and lane.tbflip424 registers a Blinx leg; read, do not edit their files.

## What is settled (from blinx372d, measured on Thor)
Both of the demo's synchronous `pgraph_vk_finish(SURFACE_DOWN)` calls per frame are one D24S8 zeta surface at one address, pitch 2560,
flipping between 640x480 and 320x240 (n=993 each). Role, format, pitch, swizzle are unchanged. Those waits are `Sub` 34.5 ms of a
64-70 ms frame. PR #396's handoff covers identical geometry only, so it is inert on the demo (handoffs=0, fps 12.98 to 12.25, noise).
The 320x240 binding is the top-left quadrant of the 640x480 one in VRAM (pixel at y*2560 + x*4 in both).

## The job
1. Close or measure the CPU-write gap first: `vram_newer` is set only when a download is recorded over a shelved binding, never on
   a guest CPU write, and a clean shelved binding sheds its watch. Say whether a guest CPU write to the big binding's range while
   it sits shelved can occur in the demo (a counter on the shelved binding's range, not an assumption), and what a guard costs.
2. Then the hunk, small to big only: on the flip to 640x480, record a `vkCmdCopyImage` of the quadrant (D24S8, depth+stencil aspects)
   from the evicted 320x240 image into the unshelved 640x480 image instead of download + re-upload. Big to small stays on the old
   path (the evicted binding still owes three quadrants to VRAM and the watch does not guard a shelved owed download: sec 5).
3. Price it offline before the arm: the bound is about half of the Sub the two waits cost, not a measured value. If step 1 shows the
   gap cannot be closed cheaply, land the counter and say so; do not land an unguarded hunk.

## Falsifier and arm
Mover: sd/frame about 2 down to 1 and demo fps up from 12.5 on a same-session Thor A/B (the blinx372c 8-leg prediction is the
template); report the median from the frame counters, not a screenshot. Must-not-move: Depth buffer fixed function, every
Color_zeta_overlap and Surface_format capture, PR #387's arm, PR #396's 102-row arm (handoffs=2 stays), and every nxdk test that
binds zeta at two sizes at one address (grep `set_surface_clip` with a changed size between draws; name them before registering).
Name what would move each leg; read `status` for unreadable rows.

## Done when
NOTES.md holds the gap measurement, the priced hunk and the A/B; the prediction is registered after the last rebase; master (or
PR #440's branch) is merged and the arm re-run; PR is ready (out of draft, CI green).
