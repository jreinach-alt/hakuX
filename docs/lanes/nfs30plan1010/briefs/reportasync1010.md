# lane.reportasync1010 -- write the occlusion report from the render thread after the fence, not from the PFIFO thread before it (#433, 0.5)

Opus (engineering, per the 10-10 model table; Sonnet when usage is Low). Issue: none (dispatched directly by lane.local,
#433 umbrella; step 2 of docs/lanes/nfs30plan1010/PLAN.md). Nova only.

## Why
- **NFS Most Wanted race start** (lane.nfs30plan1010's runs `1-1791649387-nfs30plan1010-2138210` and
  `1-1791649388-nfs30plan1010-2138879`, frametrace, NOTES.md 5.5): the PFIFO thread, which paces the frame, blocks
  **6.7 ms/frame cold, 4.3 warm, 1.0 times per frame** at frametrace site `#54` (`p_fence`) inside
  `pgraph_vk_process_pending_reports_internal` (hw/xbox/nv2a/pgraph/vk/reports.c:213), under `pfifo.lock`
  (called from pfifo.c:2163). That is the #804 wait on every submitted frame fence (reports.c:257-262) plus
  `vkGetQueryPoolResults` with WAIT_BIT, followed by `pgraph_write_zpass_pixel_cnt_report` (pgraph.c:5610-5631)
  writing 16 bytes into guest RAM.
- **It grows when texscan1010 lands.** Draws reach the GPU only at a finish; today the cube-face finishes (`sd` 90
  per 60 frames) submit mid-frame and the report fence finds the GPU nearly done. With `HAKUX_TEXSCAN=1` nothing
  submits before the end-of-frame STALLED finish, and this fence waits for the whole frame's GPU work (12.8 ms warm,
  21.7 cold, NFS GPU busy). PLAN.md section 3 ("one structural fact") and 4.2. So this is the lane that makes
  texscan1010's win real: together, the warm race start and post-GO fit in 2 VBLANKs (30 fps).
- **The report write today is `timestamp, result, done=0`** (pgraph.c:5625-5629, "FIXME: Check"). The guest cannot
  be polling `done`; it reads `result` some time after GET_REPORT. The hardware writes the report when the GPU
  reaches it in the stream. Doing the same removes the wait from the pacing thread without changing what the
  guest sees, as long as the guest reads after the GPU is done.
- **What the corpus says** (nfs30plan1010 NOTES 2.3): seven finish-deferral attempts. Those that moved a wait to
  another PFIFO-thread site lost fps (SURFSPLICE 22.1 -> 19.9, STALLFIN=reports 30.3 -> 25.8). The one that let
  the GPU run while the PFIFO thread went on (`g_sg_held`, SURFGPU) won +18-24 gfps on NBA. This design is the
  second kind: the PFIFO thread never waits; the render thread, which already waits on this fence (render_thread.c
  :157/:163), does the write.

## The job
1. **Instrument first: when does the guest consume the report?** Default off (`HAKUX_REPORT_TRACE=1`), on the
   plain build at the race start: per GET_REPORT, log the time it was queued, the time its fence passed, and the
   time of the next flip (FLIP_STALL) and of the next GET_REPORT at the same offset. If the guest flips before the
   result would have landed on >1% of reports, say so in NOTES.md: the async write then needs `done` honoured by
   the guest, or stays opt-in. One table.
2. **Build the async write behind `HAKUX_REPORT_ASYNC=1`, default off.** Design in PLAN.md 4.2:
   - at finish time, snapshot the pending reports into the `RenderCommand` (renderer.h:778-791): host pointer
     from `nv_dma_map(pg->dma_report)` + offset taken on the PFIFO thread, query index, frame slot; clear
     `report_queue`/`num_queries_in_flight` on the PFIFO side;
   - in `process_finish` (render_thread.c:116-171), after `vkWaitForFences` on this command's fence, read the query
     pool for the snapshotted indices (fences on one `VkQueue` signal in submission order, so #804's wait on every
     earlier frame is implied) and write `result` then `done=1` with a release store;
   - `pgraph_vk_process_pending_reports_internal` keeps its bookkeeping and stops waiting.
   Keep #804's guarantee: the count written must be this frame's, never the previous frame's. Say in NOTES.md how
   the design keeps it.
3. **Pixel check before any fps claim.** The "ZPass pixel count" suite (nv2a_issues.toml:843, 2963) on vs off,
   then the 27-suite disc. Rows byte-identical or explained region by region. Then NFS race-start frames at the 12
   marks on vs off, region-compared: a wrong report shows as a car or prop missing or popping.
4. **Register the prediction first**, in docs/testing/predictions/reportasync1010-*.json: NFS race start, switch on
   vs off, plain build (no perflog), 2 runs per arm, 12 starts per run, route `nfs-mw-quickrace`. Predict:
   - countdown period (pace ms/60 pooled over the 12 starts): off 41-42 ms warm, on <= 38; cold start 1: off
     56-62, on <= 55;
   - the v2/v3/v4 histogram (v2 share up by >= 10 points warm);
   - `p_fence` at site #54 -> 0 on a frametrace confirmation run (one run, perflog, optional).
   A/B on the plain build, judged by period and histogram, not by a phase line (phase fields are per-flip EMAs;
   nfs30plan1010 NOTES 3). Readers: `docs/lanes/nfs30plan1010/phaseread.py` (pace), `ftwin.py` (frametrace).
   The route copy request.sh needs: `docs/lanes/nfs30plan1010/nfs-mw-quickrace.route` -> copy into
   `docs/testing/titles/routes/` of your worktree; do not commit that copy.
5. **If texscan1010 has landed or its switch is available on your base, run one pair with both switches on** vs
   both off: that pair is the plan's step 1+2 prediction (warm countdown <= 34 ms, post-GO <= 34 ms).
6. **PR.md:** `State: ready`; measured numbers and the prediction verdict; `Needs device: yes (Nova, used)`;
   `Release note (performance): <what a player notices>` or `none` if opt-in; whether this lane recommends
   default-on, with the step-1 instrument's table as the reason.

## Rules
- Territory: hw/xbox/nv2a/pgraph/vk/reports.c, hw/xbox/nv2a/pgraph/vk/render_thread.c, hw/xbox/nv2a/pgraph/vk/renderer.h,
  docs/lanes/reportasync1010/**, docs/testing/predictions/reportasync1010-*.json. The finish enqueue in draw.c and
  the report write in pgraph.c: ask for them by name on the board (drawrec1010 holds draw.c).
- Titles run on the Nova only. Use pad.sh for input (RT is the gas), never `adb shell input keyevent`.
- No clock or performance-mode arms. A faster clock is not a fix (briefs/_next-step-rule.md).
- Perf claims come from this lane's runs only; cite the run id for every figure.
- A measured scene needs a moving player: confirm it from the `s*-g11.png` frames, not the HUD clock.
- No `gh`. Never `pkill -f` or `pgrep -f`.
- This is a headless session, and it ends when the turn ends. Never end a turn "waiting for a background task". With
  runs pending, commit and push `docs/lanes/reportasync1010/WAITING`, one `run <request-id>` line each; lanewaker
  resumes you when they are DONE.
