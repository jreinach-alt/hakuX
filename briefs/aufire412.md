# lane.aufire412 -- #412: 007: Agent Under Fire gameplay at a flat 16 fps on the Nova

Issue: #412. Base: origin/master @ dc38b745b8.
Files: docs/lanes/aufire412/**, docs/testing/predictions/aufire412-*.json. Any code file (hw/xbox/nv2a/**, hw/xbox/**) is
       NOT granted yet: name it in NOTES.md and on the issue once the profile shows the site, and the board grants it if free.
Needs device: yes (Nova soak of the same route). Needs NDK: no.
Read first: the issue body (run 0-0-y-1790433159-titleplay-p1-aufire in $DISPATCH_DIR/results), docs/lanes/fps382/NOTES.md
and docs/lanes/blinx372c/NOTES.md (method: gfps/timeline/phase-line readers, `Sub` vs `Fen`, vCPU and slow-store counters).

## What is settled
First mission (Trouble in Paradise), first-person on the rooftop: 16.2 fps median, 16.1 minimum over 60-frame windows,
96 of 100 frames late, worst stall 85 ms, no crash, no audio starvation. Title screen and briefing run 40-60 fps; the rate
drops to 12-20 as soon as the mission scene is on screen, even behind the pause menu, and holds at 16. A flat 16.1-16.2 in
every window reads as a steady per-frame cost, not stalls (a claim, from the issue: test it against a per-frame histogram).

## The job
1. From the run on disk, then a fresh Nova soak of the same route, take one split per frame: vCPU thread busy vs renderer
   busy (1 - Ri/G), `Sub` vs `Fen`, slow stores/s and tlb_set_dirty. The fps382 finding (guest CPU decoding into pages that
   take the notdirty slow path) and the blinx372c finding (synchronous surface downloads) are the two known shapes: say
   which, or neither, this scene is.
2. If it is one of the known shapes, name whether the landed fixes (PR #387 watch suspension, PR #396 draft) already cover
   it and what a soak on master reads. If neither, name the counter that separates it and the file that owns it.
3. Price the fix offline before any device arm. Land only what the counter supports.

## Falsifier and arm
Mover: demo fps 16 toward 30 on a same-session Nova A/B of the same route, same scene (the pause-menu-over-scene window is
the cheapest matched scene). Must-not-move: Depth buffer fixed function, Color_zeta_overlap, Surface_format, and PR #387's
arm. Name what would move each; check `status` for unreadable rows. Blinx (#372) shares vk/surface.c with PR #396: do not
touch it until that folds.

## Done when
NOTES.md holds the split, the shape named, the priced hunk or the reason none exists; a grant request on #412 if a code
file is needed; the prediction is registered after the last rebase; before marking ready merge master and re-run the arm.
