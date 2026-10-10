reportasync1010: write the occlusion report after the GPU is done, off the PFIFO thread (#433, 0.5)
State: draft

Lane: reportasync1010       Issue: #433 (umbrella), none filed
Base: master @ 9fd2608f8f, merged forward to master @ c829b64c8e (60a04cc81b); the step-5 pair runs on lane/reportasync1010-ts @ 3cd9d6b7e3 (this branch @ ba9a6df8fc merged with origin/lane/texscan1010 @ 227a161cc2, texscan1010 not folded)
Files: hw/xbox/nv2a/pgraph/vk/reports.c, docs/testing/nv2a_index.json, docs/lanes/reportasync1010/**, docs/testing/predictions/reportasync1010-*.json
Prediction: docs/testing/predictions/reportasync1010-nfs.json @ 04c379467242e8d95783d5a9a63042f284126da65702bba2ea5f09ddbe7f6d17 (race start, off/on/on/off, plain build, ref ba9a6df8fc)
Prediction: docs/testing/predictions/reportasync1010-pixels.json @ 1229dc96bea39ca5ea11f8ef6061611b0db3d522f0226c9ce8080db56fdc8f46 (27-suite disc, must_not_move, ref ba9a6df8fc)
Prediction: docs/testing/predictions/reportasync1010-both.json @ 6e6e5c9b2f1484437cc50f940b81619d57b64401de87e7178c50dc7ecd08b904 (HAKUX_TEXSCAN=1 + HAKUX_REPORT_ASYNC=1 vs both off, ref 3cd9d6b7e3)
Needs device: yes (Nova, used)
Needs NDK: yes

waiting: the 12 Nova requests in docs/lanes/reportasync1010/WAITING (pixel leg B/A, NFS off/on/on/off, both-switches off/on/on/off, two trace runs with texscan on). Resolved when they are DONE in the dispatch results; then the three judges in NOTES.md section 2 decide the verdicts and the default.

Step 2 of docs/lanes/nfs30plan1010/PLAN.md (section 4.2): the PFIFO thread
waits 4.3-6.7 ms per frame at NFS Most Wanted's race start for the GPU to
finish so it can write the zpass report (frametrace site #54, reports.c).
This lane moves the report write to after the GPU is done, on a thread
that does not pace the frame, behind `HAKUX_REPORT_ASYNC=1` (default off),
and instruments when the guest uses the report (`HAKUX_REPORT_TRACE=1`).

**Step 1 (pilot, trace on, `1-1791656656-reportasync1010-4183629` async,
`1-1791656657-reportasync1010-4184121` sync).** The async path survives
12 race starts. The finishing thread's report waits go from 4,114
(18.4 s) to 0, and the reader's slot gate costs 7 waits and 1.0 ms. The
write lands as soon after GET_REPORT as before (95 % within 8 ms), but
the guest flips before it on **98.8 %** of reports, which is over the
brief's 1 % line. NFS arms the status word (`0xffffffff`) before every
GET_REPORT and never reuses a report slot before the write lands.
NOTES.md section 2 has the table.

**Why this differs from pfifowait1009.** pfifowait released
`pfifo.lock` while the PFIFO thread still waited on the fence. The wait
stayed on the pacing thread, the vCPU moved on to queue on
`pgraph.lock` (doubled), and a lock dropped mid-method moved Stencil.
Here no lock is released, and the PFIFO thread does not wait. The fence
wait moves to a thread that holds no PGRAPH or PFIFO lock and touches
only the query pool, its fence and the 16 guest bytes.

Release note (none): opt-in switch, off by default

🤖 Generated with [Claude Code](https://claude.com/claude-code)
