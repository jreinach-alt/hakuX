reportasync1010: write the occlusion report after the GPU is done, off the PFIFO thread (#433, 0.5)
State: ready

Lane: reportasync1010       Issue: #433 (umbrella), none filed
Base: master @ 9fd2608f8f, merged forward to master @ c829b64c8e (60a04cc81b), to master @ d758e39a59 (f111e7227d), to master @ c271f515b4 (a21a3361d9) and to master @ 071aea27ff (140930dc16). The NFS A/B and pixel leg ran on ba9a6df8fc; the armed gate is 477893cdbf; the addendum-2 frametrace pair runs on a21a3361d9 (the gate merged with master, no emulator-code change). The step-5 pair ran on lane/reportasync1010-ts @ 3cd9d6b7e3: this branch @ ba9a6df8fc merged with origin/lane/texscan1010 @ 227a161cc2, because texscan1010 had not folded when it was queued.
Files: hw/xbox/nv2a/pgraph/vk/reports.c, docs/testing/nv2a_index.json, docs/lanes/reportasync1010/**, docs/testing/predictions/reportasync1010-*.json
Prediction: docs/testing/predictions/reportasync1010-nfs.json @ 04c379467242e8d95783d5a9a63042f284126da65702bba2ea5f09ddbe7f6d17 (race start, off/on/on/off, plain build, ref ba9a6df8fc): FAIL, 5 of 6
Prediction: docs/testing/predictions/reportasync1010-pixels.json @ 1229dc96bea39ca5ea11f8ef6061611b0db3d522f0226c9ce8080db56fdc8f46 (27-suite disc, must_not_move, ref ba9a6df8fc): FAIL, 8 of 1,060, all in the known-flaky rows; the runs=3 determinism check reads every mover as flicker, none as the switch
Prediction: docs/testing/predictions/reportasync1010-both.json @ 6e6e5c9b2f1484437cc50f940b81619d57b64401de87e7178c50dc7ecd08b904 (HAKUX_TEXSCAN=1 + HAKUX_REPORT_ASYNC=1 vs both off, ref 3cd9d6b7e3): FAIL, 4 of 8
Prediction: docs/testing/predictions/reportasync1010-gate-zpass.json @ 6caa5cf7036eefcc5a873b308592a13ca6764ec1f805009f328e71cb8efe1083 (armed gate, ZPass suite on vs off, ref 477893cdbf): PASS, 72 of 72
Prediction: docs/testing/predictions/reportasync1010-ftpair.json @ 775e0c127fc5596d7bd7a68eb9d725b8484cf301560f3240703e8f888767cc29 (addendum 2: NFS race-start frametrace, FRAMETRACE alone vs + REPORT_ASYNC + TEXSCAN, perflog, ref a21a3361d9): FAIL, 4 of 5 (F: the rule's context also holds the slot rotation fence, draw.c:5234; the report-fence sites are gone from B's pacing thread)
Needs device: yes (Nova, used)
Needs NDK: yes

Step 2 of docs/lanes/nfs30plan1010/PLAN.md (section 4.2). At NFS Most Wanted's race start, the PFIFO thread
(which paces the frame) waits 4.3-6.7 ms per frame for the GPU to finish, so that it can write the zpass report.
This lane moves that wait and the 16-byte write to a reader thread, `nv2a.vk.reports`, behind
`HAKUX_REPORT_ASYNC=1` (default off). It keeps #804's guarantee: each batch reads only its own frame slot's
queries, after that slot's fence. `HAKUX_REPORT_TRACE=1` instruments when the guest uses the report. Only
reports whose status word the guest armed are deferred. A guest that leaves the status at 0 has nothing to poll,
so the finish still writes its reports, after the batch's own slot fence (477893cdbf).

**Results** (every figure is from this lane's runs; NOTES.md section 2 has the per-run tables):

**Once the report wait is gone, the pacing thread's own CPU work is over half the race start's period: 58 % of a heavy warm frame (`p_run` 27.5 of 47.3 ms, `1-1791671434-reportasync1010-3857196`). Recording is about half of that.**

| | off | on | registered | |
|---|---|---|---|---|
| NFS warm countdown | 41.5 ms | 38.2 ms | on <= 38.0 | FAIL by 0.2 ms |
| NFS warm on - off | | -3.3 ms | <= -2.5 | PASS |
| NFS cold start 1 | 60.0 ms | 51.6 ms | on <= 55 | PASS |
| NFS warm v2 share | 53 % | 72 % | +10 points | PASS |
| NFS post-GO warm (not registered) | 39.45 ms (25.3 fps) | 35.35 ms (28.3 fps) | | |
| both switches, warm countdown | 41.0 ms | 37.5 ms | on <= 34 | FAIL |
| both switches, post-GO warm | 40.3 ms | 35.2 ms | on <= 34 | FAIL |
| both switches, v2 share | 55 % | 70 % | +15 points | FAIL by 0.2 |
| ZPass_pixel_count, 72 captures | | byte-identical | must not move | PASS |

- NFS runs: `1-1791659702-reportasync1010-546475`, `-547266`, `-547898`, `-548438`. Both switches:
  `1-1791659722-reportasync1010-552321`, `-552662`, `-552924`, `-553359`. Pixel leg:
  `1-1791659700-reportasync1010-546194` (A), `1-1791659693-reportasync1010-543406` (B).
- The pixel leg's 8 movers are Stencil_REPLACE_ST_DT(_ZB) (30,000 -> 0) and six GeometrySuperscreen captures
  (285-800 px). The prediction names both rows as known to flicker within one state, and requires a runs=3
  determinism check before a mover is read as the switch. That check (`1-1791667080-reportasync1010-2775483` A,
  `1-1791667081-reportasync1010-2775900` B) moves nothing outside its band: each mover takes both values within
  one arm, or the six runs agree and only the pixel leg's single run differed. Flicker, not the switch.
- The armed gate: its ZPass prediction PASSES, 72 of 72 byte-identical, with every report of the unarmed test
  written synchronously (`1-1791667685-reportasync1010-3048190` A, `1-1791667684-reportasync1010-3047961` B). On
  NFS (`1-1791667691-reportasync1010-3049912`, trace on, not scored) the finishing thread makes 0 report waits
  over 4,583 reports and 12 valid starts; 38.1 ms warm, 36.0 ms post-GO, the same as the ungated async runs.
- The `s*-g11` frames show a moving player at every scored start. No frame shows a missing car or a popping prop.

**The addendum (texscan on).** On texscan's configuration, the synchronous report wait is 14.5 ms per report,
50.6 s over the 12 starts (`1-1791659729-reportasync1010-554366`). With async it is 0 on the finishing thread,
plus 285 slot-gate waits totalling 22 ms (`1-1791659727-reportasync1010-553973`). Async removes it.

**Step 5 decides texscan's default: it follows this switch.** With async on, texscan adds no cost and gains at
most 0.7 ms, which is inside pair noise. Without async, it loses about 5 ms. Together the two switches do not
reach the plan's 34 ms. Something else holds the race start at about 37 ms.

**Addendum 2: where the period goes once the report wait is gone.** Two NFS race-start frametrace soaks
(perflog, ref a21a3361d9): A `HAKUX_FRAMETRACE=1` alone (`1-1791671433-reportasync1010-3857080`), B with
`HAKUX_REPORT_ASYNC=1 HAKUX_TEXSCAN=1` added (`1-1791671434-reportasync1010-3857196`). Both 12 of 12 marks, 0 bad
starts, a moving car in all 24 `s*-g11` frames. Registered first as `reportasync1010-ftpair.json`:

| check | registered | measured (warm countdown, all frames) | |
|---|---|---|---|
| V | 12 marks, >= 10 valid starts, >= 300 warm frames, env, perflog | 12 / 12, 0 / 0 bad, 721 / 859 frames | PASS |
| F | `p_c_rep` A >= 2.5, B <= 0.5 ms | A 4.43, B 0.92 | FAIL |
| U | `unhooked` A - B >= 4.0 ms | 9.64 - 2.49 = 7.14 | PASS |
| P | period B - A <= -2.5 ms | 53.60 -> 44.81, -8.78 | PASS |
| R | B `p_run` / P >= 50 % | 27.08 / 44.81 = 60 % | PASS |

F fails on what its row counts: every hooked wait in the `pgraph_process_pending_reports` context. On B that
context holds one site, the slot rotation fence (`pgraph_vk_finish+0x1330`, draw.c:5234), at 0.92 ms. Neither
report-fence site (`pgraph_vk_process_pending_reports_internal+0xd54`, `+0xc8c`) appears on B's pacing thread.
The verdict stands as registered.

Per heavy frame (3+ VBLANKs), ms (`ftpair.py`, `ftbuckets.py`; share = B's share of its period):

| row | A warm | B warm | B share | A post-GO | B post-GO | B share |
|---|---|---|---|---|---|---|
| P, the period | 53.68 | 47.34 | 100 % | 48.88 | 42.43 | 100 % |
| `p_run`, pacing thread on CPU | 28.18 | 27.48 | **58 %** | 24.84 | 24.12 | **57 %** |
| `pidle`, waiting for the guest's next push | 10.66 | 15.21 | 32 % | 10.51 | 15.27 | 36 % |
| `p_c_rep`, hooked waits in pending_reports | 4.44 | 1.06 | 2 % | 4.74 | 0.93 | 2 % |
| `unhooked` (sd finishes on A; `wait_frame_submitted`, gate) | 9.64 | 2.76 | 6 % | 8.18 | 1.24 | 3 % |
| `p_rq` + `p_oth_hk` | 0.76 | 0.83 | 2 % | 0.61 | 0.88 | 2 % |
| guest vCPU: `lockw`, waiting for `pfifo.lock` to store DMA_PUT | 0.09 | 7.31 | | 0.08 | 5.57 | |
| GPU busy | 13.04 | 19.36 | 41 % | 11.78 | 16.08 | 38 % |

The brief's four buckets, B per heavy warm frame [post-GO]:

- recording and the rest of the pacing thread's CPU work (`p_run`): 58 % [57 %]. Recording (phase `Draw`) is
  about 14.1 ms [10.6] of it; the rest is method parsing, `Surf` and finish CPU work.
- vblank quantization and waiting for the guest (`pidle`): 32 % [36 %]. 12.1 of its 13.2 ms phase-line `Idle` is
  after a flip.
- cube faces: 0 %. B has no sd finishes (90 per 60 frames on A).
- other fences and waits: 8 % [5 %]. Of that, the rotation fence is 2 % and `wait_frame_submitted` plus the gate
  is 6 % [3 %].

`p_run`'s share is an upper bound for the plain build, because the perflog clock reads run on the pacing thread.
If the whole ~4 ms perflog gap (41.7 against 37.5 ms warm, `-552662` / `-552924`) came out of `p_run`, it would
still be 56 %.

The next limit is on the guest side too. On B the vCPU waits 7.3 ms per heavy warm frame for `pfifo.lock` to
store DMA_PUT (user.c:92-95), against 0.09 on A; perflog's `hakuX-cpu` `Lw` agrees (6.6 ms on B, 0.0 on A). The
guest is busy past 2 VBLANKs on 58 % of B's heavy warm frames, and on 8 % without that wait. Frametrace names no
holder for it. The PFIFO thread holds the lock while it parses the pushbuffer (pfifo.c:2133), in
`pgraph_process_pending` (2125) and in the end-of-frame finish (2163). Which of the three costs the guest is the
next measurement, and is outside this lane's files (NOTES.md section 4).

**Recommendation: default-on, with the armed gate.** The three checks it waited on hold: the determinism check,
the gate's ZPass PASS, and 0 report waits on the gated NFS run. The reason is the step-1
table (pilot `1-1791656656-reportasync1010-4183629` async / `1-1791656657-reportasync1010-4184121` sync):

| per GET_REPORT, race starts | sync | async |
|---|---|---|
| reports written | 4,114 | 3,787 |
| queued -> written, < 8 ms | 95.6 % | 94.2 % |
| `late`: written after a flip the hand-off preceded | 0 % | 98.8 % |
| `armed`: status word nonzero at GET_REPORT | 100 % | 99.9 % |
| `reuseb4w`: slot reused before the write landed | 0 | 0 |
| finishing thread: report waits | 4,114, 18,352 ms | 0 |
| finishing thread: slot-gate waits | 0 | 7, 1.0 ms |

`late` is far over the brief's 1 % line, so the switch needs `done` honoured. NFS honours it:

- it arms the status word before GET_REPORT;
- it never reuses a slot early;
- the async write puts the status word last, after a write barrier.

So a late write shows NFS "in progress" for one more frame, never a wrong count. With the gate, the deferral
applies only to guests that arm the status word. Not covered: a guest that arms it and then reads the count
without polling. Only NFS has been traced. The flip belongs in its own PR, after two or three more titles are
traced.

**Why this differs from pfifowait1009.** pfifowait released `pfifo.lock` while the PFIFO thread still waited
on the fence. The wait stayed on the pacing thread, the vCPU's `pgraph.lock` wait doubled, and a lock dropped
mid-method moved Stencil_ZERO. Here no lock is released, and the PFIFO thread does not wait for an armed report.
The fence wait moves to a thread that holds no PGRAPH or PFIFO lock, and touches only the query pool, its fence
and the 16 guest bytes. Stencil_ZERO did not move.

Release note (none): opt-in switch, off by default

🤖 Generated with [Claude Code](https://claude.com/claude-code)
