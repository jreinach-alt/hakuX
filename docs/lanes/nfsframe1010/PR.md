NFS Most Wanted race start: where the rest of the frame goes (#433, 0.5)

State: ready

Lane: nfsframe1010            Issue: #433 (umbrella; no own issue)
Base: master @ 07937793af
Files: docs/lanes/nfsframe1010/**, docs/testing/titles/routes/nfs-mw-quickrace.route
Prediction: none (telemetry)
Needs device: yes (Nova, used)
Needs NDK: no
Release note (none): measurement only.

Measurement-only lane, no behaviour change. Answering three open questions
left by lane.local's read of perdrawon1010's race-start runs: the ~12ms gap
between phase-line `Tot` and the real frame period, whether the ~10ms
post-flip PFIFO idle (`Fr`) is a real guest wait or an idle-looping guest,
and which finishes make up the ~5-6ms of `Sub`.

Progress so far (docs/lanes/nfsframe1010/NOTES.md has detail):
- Confirmed `hakuX-stall`'s `g_opt_stats` counters are 60-guest-frame-window
  deltas (memset after each log), not cumulative — so per-frame reason
  rates are a straight divide by 60.
- Confirmed `armread.py`'s row-keying (`hakuX-perf` ... `gfps=`) matches
  real captured logs 1:1 against `hakuX-pace` (309/309) — the copied
  reader chain works as-is on this build's logs.
- Identified `hakuX-rr425w` (always-on, tag `hakuX` WARN) as the compliant,
  already-present instrument for Q2 (vCPU idle-loop vs real-work
  attribution by waking interrupt vector) — no new device time needed for
  that question specifically.
- perdrawon1010's two existing race-start runs are at ref `4ad1154e55`,
  which is not an ancestor of `origin/master`; the only non-doc diff is
  perdraw1009's own (default-off) per-draw-switch code, not present on
  master. Queuing this lane's own 2 runs on master's actual head so the
  deliverable's numbers are this lane's, on an unambiguous ref.

Queued this lane's first 2 runs on master's head (07937793af), no env, same
route: `1-1791649039-nfsframe1010-2037292` and
`1-1791649724-nfsframe1010-2219502`. Both landed DONE, and turned out to be
telemetry-blind for this brief: the Draw/Fin/Sub/Idle/Fr/GPU phase
breakdown (`nv2a_profile_get_phase_timing_str`, profile.c:896) is compiled
out unless the build carries `-Pperflog=true`
(`android/app/src/main/cpp/CMakeLists.txt`), which needs `request.sh
--perflog` at queue time — neither of the two did (detail:
docs/lanes/nfsframe1010/NOTES.md §7). Requeued the same ref/route/title/
device with `--perflog` added.

Before the requeue ran, lane.local escalated this brief's three open
questions to lane.nfs30plan1010 (Fable), which answered all three from its
own instrumented runs and this lane's two plain runs as its baseline, and
told this lane to stop after those two runs — no further device time.
lane.local withdrew the perflog requeue to `dispatch/queue/withdrawn/`
before it ran.

**Final state (NOTES.md §9-11):**
- §10: the deliverable table — pace/vblank-histogram/gfps per window
  (cold start, warm restarts, post-GO) from the two plain runs' always-on
  `hakuX-pace`/`hakuX-perf` lines. Draws/frame is confirmed unavailable on
  this build (perflog-gated, same as the phase lines), not a reading gap.
- §11: the brief's three open questions, answered in
  `docs/lanes/nfs30plan1010/PLAN.md` section 1 (verdict) and section 4.3 /
  NOTES.md §5.4-5.5 (mechanism and measurement) — cited there, not
  re-measured by this lane, since this lane's own runs cannot see the
  phase/thread breakdown those answers are built from.

No P×win ranking or "move 3 vblanks to 2" naming from this lane: that
ranking is PLAN.md section 0's job (it already did it, across the four
NFS lanes), and this lane's own instruments cannot see the phase/thread
split a removability ranking needs.
