reportasync1010: write the occlusion report after the GPU is done, off the PFIFO thread (#433, 0.5)
State: draft

Lane: reportasync1010       Issue: #433 (umbrella), none filed
Base: master @ 9fd2608f8f
Files: hw/xbox/nv2a/pgraph/vk/reports.c, docs/testing/nv2a_index.json, docs/lanes/reportasync1010/**, docs/testing/predictions/reportasync1010-*.json
Prediction: docs/testing/predictions/reportasync1010-nfs.json @ 2201efdad090f4691ada9e2fb87d1b2fd7f1ec901de5d6fb64b221385f7b497a (race start, off/on/on/off, plain build)
Prediction: docs/testing/predictions/reportasync1010-pixels.json @ 80d0c4d86f5975df665232fa62bd64411cb9b776bdf0675790b6f0f8dc767266 (27-suite disc, must_not_move)
Needs device: yes (Nova)
Needs NDK: yes

Step 2 of docs/lanes/nfs30plan1010/PLAN.md (section 4.2): the PFIFO thread
waits 4.3-6.7 ms per frame at NFS Most Wanted's race start for the GPU to
finish so it can write the zpass report (frametrace site #54, reports.c).
This lane moves the report write to after the GPU is done, on a thread
that does not pace the frame, behind `HAKUX_REPORT_ASYNC=1` (default off),
and instruments when the guest uses the report (`HAKUX_REPORT_TRACE=1`).

Release note (none): opt-in switch, off by default

🤖 Generated with [Claude Code](https://claude.com/claude-code)
