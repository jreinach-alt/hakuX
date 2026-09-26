# lane.blinx372c -- Blinx: name the surface-download site behind the demo wait (#372)

Issue: #372 (game-visible: Blinx: The Time Sweeper's attract demo runs ~16 fps on the Thor, floor is 20). Base: master c481e893ad.
Files: docs/lanes/blinx372c/**, docs/testing/predictions/blinx372c-*.json. No hw/ file is granted: a hunk is NAMED, not edited.
Needs device: yes (Thor). Needs NDK: no (master apk; perflog build as lane.fps382 used).

## What is known
lane.blinx372 (PR #374, docs/investigations/perf-blinx-372.md): renderer thread 96-98% busy; 32 ms of a 68 ms guest frame is
two synchronous GPU-completion waits in pgraph_vk_finish (Sd2, St1 = surface download). Ceiling near 27 fps if both go.
lane.blinx372b (PR #381, folded) added `hakuX-stall`, `hakuX-rpbrk`, `hakuX-cpu`, `xemu-gpu`, `xemu-sfp` to the dispatcher's
logcat allow-list (docs/testing/dispatcher.sh) and left tools docs/lanes/blinx372b/sites.py and workread.py.
Related but a different mechanism: lane.surfwatch382 (#382) works vk/surface.c's CPU-access watch; do not edit that file here.

## Goal
1. Confirm the dispatcher snapshot that will run your soak carries the new allow-list: the result's `logcat.spec` must show
   `hakuX-stall`. A merged dispatcher fix is not live until the dispatcher tree is updated (host-tools/dispatcher_update_window.sh,
   the host's). If the spec lacks the tag, say so on #372 and stop the soak half; do not burn a run.
2. One perflog soak of the attract demo on the Thor (240 s hands-off), master apk. Rerun once if the fps is off the ~16 median.
3. Read the per-site `hakuX-stall` counters (sites.py, workread.py): which draw/surface/call site fires Sd2 and St1, how often per
   frame, ms per stall. Name the site as file:function.
4. Name a hunk and price it (bound, not value); say whether it overlaps vk/surface.c's watch code.

## Falsifier (register before the soak)
"The waits are the demo's own readback" -- if the Sd2 site is a guest-requested surface read that reads back through VRAM the
guest then uses, no hunk removes it. "Removable" is the reverse: the download is a conservative flush (draw_dirty on a surface
the CPU never reads back). State which, with the site.

## Done when
NOTES.md in docs/lanes/blinx372c/ with the site, counters and verdict; finding posted on #372; PR (out of draft, CI green) with
notes, prediction and scripts. A named site with no safe hunk is a result.
