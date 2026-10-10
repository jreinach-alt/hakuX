NFS Most Wanted race start: where the rest of the frame goes (#433, 0.5)

State: draft

Lane: nfsframe1010            Issue: #433 (umbrella; no own issue)
Base: master @ 07937793af
Files: docs/lanes/nfsframe1010/**, docs/testing/titles/routes/nfs-mw-quickrace.route
Prediction: none (telemetry) — measurement only, no A/B
Needs device: yes (Nova, queuing)
Needs NDK: no

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
--perflog` at queue time — neither of the two did. Both logged zero
`hakuX-phase`/`hakuX-cpu`/`xemu-gpu`/`xemu-surf`/`xemu-work` lines, and
`hakuX-stall` only carried the always-on `ubo_ring_grow` line, not the
perflog-gated `Finish:`/`sd[...]`/`dif[...]` counts this brief needs
(detail: docs/lanes/nfsframe1010/NOTES.md §7). Requeued the same ref,
route, title and device with `--perflog` added:
`1-1791653167-nfsframe1010-3263852` and
`1-1791653177-nfsframe1010-3266390`. `docs/lanes/nfsframe1010/WAITING` now
names these two; the first pair is kept as an always-on `hakuX-pace`
pacing cross-check (NOTES.md §8), not reused for the phase table.

Remaining: once the perflog pair lands, verify car movement from
route-frames, build the per-heavy-frame accounting table and the P×win
ranking, write the final NOTES.md section, flip this PR to ready.

Release note (none): measurement only.
