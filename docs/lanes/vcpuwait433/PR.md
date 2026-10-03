# vcpuwait433: name the wait that puts Tron 2.0's vCPU to sleep in slow frames
State: draft

Lane: vcpuwait433       Issue: #433
Base: master @ 9550493846
Files: docs/lanes/vcpuwait433/PR.md, docs/lanes/vcpuwait433/NOTES.md, docs/lanes/vcpuwait433/OUTBOX.md, docs/lanes/vcpuwait433/capture_offcpu.sh, docs/lanes/vcpuwait433/waitsite.py, docs/lanes/vcpuwait433/decompose.py, docs/lanes/vcpuwait433/tron-newgame.route
Prediction: none yet: the off-CPU trace comes first. A Tron + BF2 prediction will be registered before any arm, if the trace names a removable site.
Needs device: yes (Nova; 1 host-run capture requested, 0 of 3 runs used)    Needs NDK: no

Waiting on a host-run capture: one 60 s off-CPU simpleperf trace of Tron 2.0's slow window, requested from lane.local in OUTBOX.md (2026-10-02 18:20 PDT). `capture_offcpu.sh` runs it under `hold.sh`. `waitsite.py` reads it and charges the vCPU's off-CPU time to the brief's candidate sites. On slowdown462's DOA capture it reproduces #474 (pgraph.lock 89.7%).

NOTES.md section 3 fixes, before the trace runs, which outcome leads to which fix, with P, win and cost for each. It also corrects one of near30's premises: the "read-downloads" figure was TLB dirty-reset time, so the vCPU's wait for a GPU surface download is still unmeasured.

Local checks: `bash -n capture_offcpu.sh` OK; `waitsite.py` on `perf/2026-09-26-slowdown462/doa3/doa3.data` reproduces slowdown462's table.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
