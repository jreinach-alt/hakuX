# lane.perflog1016 OUTBOX

Edits this lane needed in files other lanes held. Each was a patch in this
directory. As of 10-18 the three tree NEEDs are closed and the fourth is
dropped. The one open NEED is lane.local's own scratchpad file, and it does not
block the PR.

APPLIED (10-18, ce91b11b74; granted to this row by lane.local 10-16 09:49 PDT): hw/xbox/nv2a/pgraph/profile.c -- the implementation (`#define NV2A_PERFLOG_RT_IMPLEMENTATION` before its first include), the every-60-frames print block on `nv2a_perflog_on()`, the four Sfp/Mfp/FTx/TxH fields in both builds. Patch: perflog1016/profile.c.patch
APPLIED (10-18, ce91b11b74; same grant): hw/xbox/nv2a/pgraph/vk/renderer.c -- the one poll, `nv2a_perflog_poll(fdump_base_dir())` in fdump_poll_marker(). Patch: perflog1016/renderer.c.patch
APPLIED (10-18, ce91b11b74; same grant): hw/xbox/nv2a/pfifo.c -- the hakuX-cpu timers and the Idle(Fr/St) split on the switch. The flag is read once per pfifo_run_puller() call, which is once per method command (class A, beside four atomics; corrected from "never inside the method loop"), and once per pusher pass. CBL stays a perflog build's. Patch: perflog1016/pfifo.c.patch
DROPPED (10-18): hw/xbox/nv2a/pgraph/vk/surface.c -- lane.gta3instr1018 holds it. Not asked for. Under the switch, xemu-surf prints its counts with 0 ms timers. The patch stays here for the file's next holder: perflog1016/surface.c.patch

NEED (lane.local, not a tree file): the owner-play recorder's logcat filter. `ownerplay.py` in lane.local's scratchpad, `LOGCAT_SPEC` at line 35 as read 10-16, keeps hakuX-perf, hakuX-route and hakuX:W. So an owner session keeps the switch's flip line, the Mark lines and `[tcg787]`. It drops all seven tags the switch's every-60-frames block prints. To capture what the button turns on, add `hakuX-phase:I hakuX-cpu:I xemu-vsync:I xemu-surf:I xemu-pace:I xemu-work:I xemu-gpu:I` before `*:S`. With the switch OFF those tags print nothing, so the capture is unchanged until the owner presses the button. The 10-12 capture unit `hakux-ownerplay-perf` had the same gap (its log holds only hakuX-perf/pace/stderr/unhandled/build). The dispatcher's spec (dispatcher.sh:2516) keeps all of them except xemu-vsync and xemu-pace. The ON proof this lane queued reads hakuX-phase, hakuX-cpu and `[tcg787]`, so it is not affected.
