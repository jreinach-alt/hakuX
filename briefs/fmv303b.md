# lane.fmv303b -- #303: Spikeout's FMV green blocks, the CPU-side discriminator

Issue: #303. Base: origin/master @ a5b5b628f2. Continues lane.fmv303 (PR #317, merged): read docs/lanes/fmv303/NOTES.md sections 4 and 5 first.
Files: docs/lanes/fmv303b/**, docs/testing/predictions/fmv303b-*.json. NO hw/, target/, accel/ or android/ file is held.
       If a hunk is implicated, name it in NOTES and board-request it; do not edit it.
Needs device: yes (Thor soak, hands-off, `HAKUX_FMV303_PROBE=1` already in master, inert by default). Needs NDK: no.

## What is settled (do not re-measure)
The FMV is a CPU-written linear A8R8G8B8 texture on stage 0, 640x368, double-buffered at 0x307d000 / 0x3163000. The green
(Cr=0 with Y and Cb intact) is ALREADY in that guest buffer: 435 frames, 374 more than 10% tinted, mean 0.66; the screen
reads 0.63 in the same run (run 1790389079-fmv303-1248256). Display, texture upload and PVIDEO are exonerated. The tint
switches clean/tinted 63 times within shots, and two runs of one binary differ (0.41 vs 0.66): timing-dependent, CPU side.

## The job
1. Run the discriminator NOTES s5 names: the same Thor soak with the tier1 JIT tier OFF, metered per frame by
   docs/lanes/fmv303/guest_tint.py on the probe's `tint` line (no screen capture needed). The threshold setter is
   accel/tcg/cpu-exec.c:68-87 (g_tier1_threshold, 0x7FFFFFFF = off); find how a soak sets it (pref or env) and say how.
   Run tier1 ON in the same session as the control, at least two runs per arm (the ON arm itself varies 0.41-0.66).
2. Tint mean about 0.6 with tier1 off: the JIT tier is not the cause. Look for a DMA or surface write-back landing in the
   decoder's planar buffers (start from the buffers' addresses in the probe line; who writes them, and when).
   Tint drops to 0: bisect the tier1 MMX/SSE saturating ops (packuswb, paddsw, pmulhw) used by IDCT / colour conversion,
   with a guest-side falsifier per op, not a screen read.

## Falsifier and arm
Registered before the run: "with tier1 off the tint mean is within 0.2 of the tier1-on mean of the same session" (JIT tier
not the cause) versus "below 0.1" (tier1 is). A reading of `unreadable`, or fewer than 100 lit frames in an arm, is no
reading; check `status` before believing a mean. Must-not-move: no code changes unless a hunk is granted.

## Done when
NOTES.md holds the tier1-off table (both arms, run ids, apk_sha per row), which branch of step 2 it selects, and either
the named hunk with its file holder or the next discriminator. PR is ready; docs-only, so no audit is needed beyond CI.
