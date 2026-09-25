# #277: DMA corruption around surfaces -- a file read into a bound surface keeps the old colour

Lane: dmasurf277           Issue: #277 (xemuReadFromFileIntoSurface, 90,912 px, one capture, whole region wrong)
Base: origin/master @ fab230935e (rebase to the tip before you register anything).
Files: docs/lanes/dmasurf277/**, docs/testing/predictions/dmasurf277-*.json
       (LOCATE-FIRST. The issue's guess is vk/surface.c:3406-3422, which is lane.remote's (#109); vk/draw.c is
       lane.vtxarr262's. Name the function and the hunk; ask by board-request for the path.)
Needs device: yes for the arm; the analysis is desktop. Needs NDK: no.

## The defect
Silicon shows the file's white after the read; we still show the dark colour from before it. Same family as
#184/#262 (a write the surface cache does not notice). Related #85. Games: medium.

## Read first; the location is a claim
1. Read the test source (nxdk_pgraph_tests, xemuReadFromFileIntoSurface): what is drawn, what memory the file
   read targets, and whether the target is a surface's backing memory or a texture.
2. Trace how a guest write into a bound surface's memory reaches the surface cache: which dirty/notify path
   exists for CPU writes (memory-region dirty, surface_dirty, download/upload check) and why this write does not
   trip it. Read #262's and #184's NOTES.md before you write "nobody has looked"; they name the same gap.
3. Score by region against the golden across all runs on disk (dates, both devices) so a stale capture is not
   read as a live defect; check the scores `status` for `unreadable`.

## The arm (register after the last rebase, bound to the function you name)
must_move: xemuReadFromFileIntoSurface -> exact or a stated residual.
must_not_move: Surface format, Clear, Surface-as-vertex-array, every capture that never writes a bound surface
from the CPU. Name the change that would move each.

## Done when
NOTES.md names the mechanism, the per-capture priced result and the exact hunk with its holder; the arm is
registered; the PR is ready. Analysis plus a named hunk is a complete outcome; the board grants files as
holders fold.
