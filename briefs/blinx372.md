# #372: where does Blinx's in-engine attract demo spend its frame, and what is the cheapest lever

Lane: blinx372          Issue: #372 (Blinx: The Time Sweeper, ~16 fps on the Thor in the attract demo; game-visible)
Base: origin/master @ 6550967a5e (rebase to the tip before you register anything).
Files: docs/lanes/blinx372/**, docs/investigations/perf-blinx-372.md, docs/testing/predictions/blinx372-*.json
       LOCATE-FIRST for any source change: name the hunk and its file on #372 and `board-request` it; do not edit hw/ or
       target/ unasked. Read-only use of docs/testing/perf/*.sh, soak_title.sh, dispatcher.sh (lane.titlerun's, released
       at ready in PR #307); edit none of them.
Needs device: yes, the **Thor** (bdc158a5) for the reproduction and the profile; hands-off soaks through the dispatcher,
holds at most 60 minutes. Needs NDK: only if a hunk is approved.

## What is known (the issue; run 0-0-y-1790405024-titlebench-2, ref 6561442869, apk 290cba668b65)
Title 4D530013. gfps 59 through the menus, then ~116 s in, when "Demo play" starts (a courtyard, Blinx behind a spiked
gate, a large green hand in the foreground), it drops to 10-22 and holds at 12-19 to 240 s. It renders correctly and
never crashes: slow only. The perf line is emitted more often when frames are fast, so read the TIME-weighted median,
not the per-line one. Unattended run: the attract demo, not gameplay.

## The job, in order
1. Reproduce on today's master with the same title bench (soak_title.sh through the dispatcher), twice; record the
   gfps windows, the `hakuX-pace` line (PR #310 folded it), and the prefs each run used. State the spread.
2. Profile the slow window: `docs/testing/perf/profile_guest.sh` (simpleperf, guest thread) and `loadsample.sh` for the
   thread split. Answer ONE question: is the frame bound by the guest CPU (translation-cache churn, softmmu slow
   paths), by the GPU/Vulkan side (draw count, a shader compile stall, a surface-copy), or by a single guest wait
   (a stalled flip, a voice/audio lock)? Report the top 20 self symbols and the split. Count `report-sample` records,
   not rounded percentages (host memory: simpleperf rounding inflates the JIT).
3. If GPU-side: capture one slow frame's draw list and name the costliest state (huge draw count, per-draw pipeline
   creation, a readback). If CPU-side: run `tcg_pages.py` counters and say whether TLB flushes or dirty-page
   invalidation dominate (that is lane.perfarch's #68 territory: name it, do not fix it).
4. Write `docs/investigations/perf-blinx-372.md` and post the finding on #372. If one lever is small and local, name
   the hunk and its prediction (a gfps floor over the demo window) and board-request the file.

## Falsifier
The claim to break: "the slow window is guest-CPU bound". Break it by reading the GPU-busy share and the flip-wait
share in the same window, on both runs. If the guest thread is under 60% busy in the slow window, the CPU is not the
wall and the cause is elsewhere; say so and follow the wait.

## Done when
#372 carries the measured split with both runs' raw logs kept under /home/justin/hakux-work/perf/2026-09-26/, the doc is
on a ready PR, and either one named lever (with a registered prediction) or an explicit "no lever found, bound is X".
Do not edit the board files. Do not trigger CI as a self-check.
