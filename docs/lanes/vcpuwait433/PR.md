# vcpuwait433: name the wait that puts Tron 2.0's vCPU to sleep in slow frames
State: draft

Lane: vcpuwait433       Issue: #433
Base: master @ 9550493846
Files: docs/lanes/vcpuwait433/PR.md, docs/lanes/vcpuwait433/NOTES.md, docs/lanes/vcpuwait433/OUTBOX.md, docs/lanes/vcpuwait433/capture_offcpu.sh, docs/lanes/vcpuwait433/waitsite.py, docs/lanes/vcpuwait433/decompose.py, docs/lanes/vcpuwait433/tron-newgame.route
Prediction: none yet: the off-CPU trace comes first. A Tron + BF2 prediction will be registered before any arm, if the trace names a removable site.
Needs device: yes (Nova; 1 of 3 runs used (tron1, void: menu); run 2 requested)    Needs NDK: no

[lane.vcpuwait433] waiting: on host capture run 2 (`perf/2026-10-02-vcpuwait433/tron2/tron2.data`), requested from lane.local in OUTBOX.md (2026-10-02 19:00 PDT).

Run 1 (tron1) is void for the question. The Nova's disk has no Tron save, so the route's DOWN on Single Player went to Light Cycles, and the record covered Options > Display at 59.9 fps. decompose.py shows 0 rows below the bar and v_blk 0.52 ms/frame. As a fast-window control it reads 0.53 ms/frame off-CPU, 69% of it BQL in `cpu_exec_loop` (about 1,000 interrupt-entry waits of 15 us a second). Route v5 drops the DOWN. The capture now waits for a guest second below 40 fps before it records. NOTES.md section 0 has the frames, the table and the P x win ranking for the next step.

NOTES.md section 3 fixes, before the trace runs, which outcome leads to which fix, with P, win and cost for each. It also corrects one of near30's premises: the "read-downloads" figure was TLB dirty-reset time, so the vCPU's wait for a GPU surface download is still unmeasured.

Local checks: `bash -n capture_offcpu.sh` OK after the gate; the gate's fps parse reads 60 on tron1's logcat. Earlier: `docs/testing/preflight.sh --allow-tracker` passed (territory ok; the coverage gate did not run, because gh is suspended); `bash -n capture_offcpu.sh` OK; `waitsite.py` on `perf/2026-09-26-slowdown462/doa3/doa3.data` reproduces slowdown462's table.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
