# lane.nfs30plan1010: what has to be reworked for NFS Most Wanted's race start to hold 30 fps -- analysis and remediation plan (#433, 0.5)

State: ready

Lane: nfs30plan1010          Issue: none (#433 umbrella; owner's escalation 10-10 ~09:10 PDT)
Base: master @ 07937793af
Files: docs/lanes/nfs30plan1010/PR.md, docs/lanes/nfs30plan1010/NOTES.md, docs/lanes/nfs30plan1010/PLAN.md, docs/lanes/nfs30plan1010/briefs/reportasync1010.md, docs/lanes/nfs30plan1010/briefs/drawrec1010.md, docs/lanes/nfs30plan1010/briefs/placement1010.md, docs/lanes/nfs30plan1010/briefs/gpupass1010.md, docs/lanes/nfs30plan1010/nfs-mw-quickrace.route, docs/lanes/nfs30plan1010/startread.py, docs/lanes/nfs30plan1010/vcpuread.py, docs/lanes/nfs30plan1010/phaseread.py, docs/lanes/nfs30plan1010/ftwin.py, docs/testing/predictions/nfs30plan1010-idlehalt.json
Prediction: docs/testing/predictions/nfs30plan1010-idlehalt.json @ 41bed95f5c8d3e2b2fe9cb718df5d7f87b133191bdbebcaf42ddea7073e38986 (telemetry probe, judged: V PASS, H PASS, F FAIL on both B runs; placement is not on the path, NOTES 5.6)
Needs device: yes (Nova, used)    Needs NDK: no
Release note (none): analysis and plan

Analysis-only lane: no emulator code. Four measurement runs on the Nova (two perflog + frametrace + PMU + census
runs of the race-start route; two plain-build `HAKUX_IDLE_HALT=1` probe runs), all DONE, read against
lane.nfsframe1010's two plain-build runs and lane.texscan1010's census run and NFS A/B.

**What the frame is** (PLAN.md 2-3). The PFIFO thread is the critical path and does everything in series: method
parsing, ~1,900 draw recordings at 11.9 us each, and three GPU waits per frame. On the plain build the countdown
is 56-62 ms cold, 41-42 ms warm, 40.0 post-GO; 30 fps is every frame in 2 emulated VBLANKs (33.3 ms) without the
VBLANK deferral. The GPU is busy 13-22 ms and the guest needs 24-29 ms of vCPU per frame; neither paces today.

Heavy cold-start frame, PFIFO thread, instrumented build (ms): `38.0 on CPU + 17.3 cube-face finish waits + 6.7
report fence + 12.6 VBLANK grid + 0.9 runqueue = 75.5`; warm `30.4 + 10.1 + 4.3 + 11.0 + 0.6`.

| step | lane | removes (plain, cold / warm) | expected period after (model) cold / warm | P |
|---|---|---|---|---|
| 1 | texscan1010 (built, ready, default-off; **A/B read**) | cube-face waits 17.3 / 10.1 + ~6 / ~4 CPU, **only together with step 2**; alone it MEASURED +2.6 ms over the start, +7 at the countdown | with 2: 35-40 / **33.3** | 0.7 copy / 0.5 pair |
| 2 | reportasync1010 (**dispatched**, pilot pair queued) | report fence 6.7 / 4.3, and the GPU work step 1 pushes onto it | alone: 50-55 / 37-38; lands first | 0.6 |
| 3 | drawrec1010 (**dispatched**, census running) | -30% recording: 5.5 / 4 | **33.3 at p50** / margin | 0.5 |
| 4 | placement1010 (**dropped**: probe F failed) | measured +2 to +4 with the X3 freed | | <= 0.2 |
| 5 | gpupass1010 (brief, with the step 1+2 pair) | GPU busy 21.7 -> ~13 (margin); 18 ms instr. with the copy on | unchanged | 0.6 / 0.2 |
| 6 | vcpuplan's items | guest 27.4 -> 19-21, co-critical after step 3 | holds the cold start | per item |

The one structural finding the order turns on: draws are submitted to the GPU only at a finish, and the cube-face
finishes are what submit mid-frame. Remove them alone and the report fence waits for the whole frame's GPU work.
texscan1010's A/B confirmed it in full (NOTES 5.7): `Sub` 10.8 -> 0.2 ms, the fence's remainder 4.1 -> 17.8, and
the period went UP (+2.6 over the start, +7 at the countdown, GPU 13.4 -> 18.0 instr.), where the model had said
-4 to -8. So steps 1 and 2 are one step, landed as 2 then 1, and the copy stays default-off until the pair's A/B.
Drastic measures (recorder thread, JIT backend, Turnip fork, draw batching, unlock) are priced in PLAN.md 6: the
recorder thread is step 3's fallback; the JIT backend and the driver fork are not on this scene's path and are
not scheduled.

The placement probe (NOTES 5.6): with the vCPU halting instead of spinning, its on-CPU share fell ~50 points and
the X3 was free a third of wall time, and the countdown pace read 43.5 / 43.7 ms/frame against 41.7 pooled plain
(bound 0.92 x A; post-GO 44.0 vs 40.0). Freeing the core does not shorten the FIFO thread's frame here; the
halted guest does its own work 3 ms/frame slower. Step 4 is dropped, its brief not dispatched, and NFS gets no
idle-halt title entry.

Verdicts on the NFS lanes (PLAN.md 1): texscan1010 done, ready, default-off, never on alone; nfsframe1010 ready
(its runs are the baseline); perdrawon1010 folded; forzasurf1010 finish for Forza only. reportasync1010 and
drawrec1010 are dispatched from this plan's briefs; placement1010 is not.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
