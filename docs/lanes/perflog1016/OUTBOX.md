# lane.perflog1016 OUTBOX

Edits this lane needs in files other lanes hold. Each one is a patch in this
directory, against the base named in PR.md. Apply with
`git apply docs/lanes/perflog1016/<file>.patch`. Each patch is one small
hunk group that reads a flag and does nothing else, so it can go on top of
the holder's work.

NEED: hw/xbox/nv2a/pgraph/profile.c -- REQUIRED for the button to print anything. Without it the switch flips the timers but nothing prints them. The patch defines `nv2a_perflog_poll()` (env `XEMU_PERFLOG_RT` at the first poll, then the `perflog.on` marker, level-triggered, one `hakuX-perflog: runtime tier ON|OFF (frame N, by ...)` line per flip). It also gates the every-60-frames print block (hakuX-phase, hakuX-cpu, xemu-vsync, xemu-surf, xemu-pace, xemu-work, xemu-gpu) on the run-time flag instead of `#if NV2A_PERF_LOG`, and smooths the four perf-only phase fields (Sfp/Mfp/FTx/TxH) in both builds. Patch: perflog1016/profile.c.patch
NEED: hw/xbox/nv2a/pgraph/vk/renderer.c -- REQUIRED, one call: `nv2a_perflog_poll(fdump_base_dir())` in fdump_poll_marker(). It runs on the frame dump's existing once-a-second poll, at the flip, with the directory the frame-dump marker already uses, so the perflog marker lives beside frame_dump.on and needs no new JNI or MainActivity edit. Patch: perflog1016/renderer.c.patch
NEED: hw/xbox/nv2a/pfifo.c -- coverage. It switches the hakuX-cpu timers (pusher/puller/method/lock) and the Idle(Fr/St) fields of hakuX-phase at run time. The flag is read ONCE per puller run and once per pusher pass, never per method (class B, see NOTES.md). Without it those fields print 0 under the switch, and the counts still print. Patch: perflog1016/pfifo.c.patch
NEED: hw/xbox/nv2a/pgraph/vk/surface.c -- coverage. It switches the xemu-surf timers (SURF_TIMER_* and the df flush/read timers) at run time. Without it xemu-surf prints its counts with 0 ms. Patch: perflog1016/surface.c.patch
