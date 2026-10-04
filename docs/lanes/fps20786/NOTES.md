# lane.fps20786: why a class of titles runs at ~20 fps on the Nova (#786, #747)

Brief (2026-10-03): name the bound once for NBA Live 2004/05/06/07, Top Spin,
Counter-Strike and Midnight Club 3. Telemetry, not retests: one `--perflog` soak
per title, decomposed with the near30 method. No fix in this lane.

## Method

`decompose.py` here is docs/lanes/near30/decompose.py plus two things: `--mark
HH:MM:SS` for a held run (pathfind) whose run.log has no ROUTE mark, and two
columns for the render (PFIFO) thread:

| column | source | meaning, per guest frame of F ms |
|---|---|---|
| Ri | hakuX-perf `Ri:` | render thread parked waiting for a kick. This includes the flip stall waiting for VBLANK: the pusher exits on `waiting_for_flip` and the thread parks (pfifo.c 2186-2236) |
| rcpu | `[rdc] tcpu/dt` x F | render thread on-CPU (CLOCK_THREAD_CPUTIME_ID of the thread that prints [rdc], tid checked) |
| rblk | F - Ri - rcpu | render thread neither parked nor on-CPU: blocked. The GPU fence wait at each flip lands here: `pgraph_vk_flip_stall` calls `pgraph_vk_finish(VK_FINISH_REASON_FLIP_STALL)` (vk/renderer.c 2557) before the next frame's methods are read |

The other columns (gbusy/gidle, wake classes, v_run/v_blk, lockw, ph_*) are
near30's; see docs/lanes/near30/NOTES.md "Method".

## Registered before any run (2026-10-03, this commit): what each bound looks like

Read on the slow windows (2-s rows below 28.5 fps) of each title.

| bound | signature | owner |
|---|---|---|
| vCPU (guest code) | gbusy >= 0.85 F, or for a title that never reaches its idle loop v_run >= 0.85 F with v_blk small; Ri >= 0.3 F (renderer waiting for the guest) | lane.memfast #507 (fastmem); TLB / re-translation if `[tlb68]`/`[jc425]` flush counts lead (lane.flushstall787 #787) |
| GPU | ph_GPU >= 33 ms per flip; Ri < 0.2 F; rblk large and ph_Fin (finish wait) carrying it | #474 |
| render thread CPU | rcpu >= ~30 ms per frame with ph_GPU < 33; Ri < 0.2 F | new (renderer CPU) |
| serial renderer (CPU then GPU, at the flip) | neither rcpu nor ph_GPU alone reaches 33, but rcpu + rblk (= F - Ri) > 33.3; Ri < 0.2 F; guest idle large | new: the flip-stall finish serialises the frame |
| lock / sync | lockw >= 5 ms per frame, or Ri >= 0.3 F AND gidle >= 0.3 F together (both sides waiting on each other) | #474 lock work |

The 20-fps number itself: when frames take exactly 3 VBLANKs (hakuX-pace `v3`
dominant), a frame cost anywhere in (33.3, 50] ms reads as 20.0 fps. So the
cost that matters is F - Ri, not F, and a fix pays nothing until it lands
under 33.3 ms.

Predictions per title, before its run:

| title | evidence before the run | predicted bound | P |
|---|---|---|---|
| NBA Live 2005 | always-on lines of pathfind's 609-s hold (below) | serial renderer; GPU alone < 33 | 0.6 (GPU-bound 0.25, render CPU 0.15) |
| NBA Live 2004/06/07 | same engine (EA, same publisher family) | as NBA 2005 | 0.5, untested |
| Top Spin | one 20-fps frame (pathfind 10-02) | serial renderer or GPU | 0.5 |
| Counter-Strike | one 13-fps frame | vCPU | 0.4 (GPU 0.3) |
| Midnight Club 3 | 09-30 soak below: near 30, slow rows guest-busy | vCPU in its slow windows; not a 20-fps title | 0.6 |

## Step 1: what the existing logs already say (offline, no device)

### NBA Live 2005: pathfind's held run, 2026-10-03 16:37-16:47 PDT (Nova)

`docs/lanes/pathfind/runs/nba-live-2005-hold` (lane/pathfind; logcat copied to
scratch here, not committed). Debug app, device defaults (HAKUX_GPL default 3),
12-minute quarters, 609 s of play, verdict 19.97 fps window median, 0.0% at 30.
Decomposed with `--mark 16:37:00` (the logcat starts at the hold):

| rows | fps | F | gbusy | gidle (timer-woken) | Ri | rcpu | rblk | v_run | v_blk | lockw |
|---|---|---|---|---|---|---|---|---|---|---|
| 304 (all below 28.5) | 19.96 | 50.1 | 22.0 | 28.3 (24.3) | 8.2 | 26.4 | 15.5 | 48.5 | 1.6 | 0.9 |
| slowest quarter (77) | 19.18 | 52.1 | 22.8 | 29.2 (25.3) | 8.1 | 26.7 | 17.3 | 49.7 | 2.0 | 1.1 |

hakuX-pace: 48 of 56 frames per line take exactly 3 VBLANKs (v3). Read:

- **Not vCPU.** The guest runs code 22 ms of a 50-ms frame and sits in its
  idle loop for the other 28 (v_run is 48.5 only because the idle loop is
  spun, `[idlehalt] on=0`). A guest that needs 22 ms could make 30 fps.
- **Not lock.** vCPU waits on pgraph.lock 0.9 ms per frame.
- **Renderer.** The render thread is parked only 8.2 ms of 50 (and that
  includes the wait for the third VBLANK), so its own cost is ~42 ms per frame:
  26.4 ms on-CPU plus 15.5 ms blocked. 42 is in (33.3, 50], hence 3 VBLANKs,
  hence 20.0 fps on every row.
- Open: whether the 15.5 ms blocked is the GPU (the flip's finish wait) or
  something else. That is what the perflog run's ph_GPU / ph_Fin answer.

### Midnight Club 3: 1-1790734333-titleroutes-3037624 (2026-09-30, Nova, Arcade street)

| rows | share >= 28.5 | fps | F | gbusy | Ri | rcpu | rblk | v_blk |
|---|---|---|---|---|---|---|---|---|
| all 145 | 0.86 | 29.7 | 33.7 | 28.3 | 12.6 | 14.5 | 6.9 | 7.2 |
| below 28.5 (20) | -- | 22.9 | 43.6 | 34.9 | 12.2 | 20.1 | 11.4 | 9.2 |

MC3 in Arcade mode is a near-30 title, not a 20-fps one: 86% of its 2-s rows
are at or above 28.5. Its slow rows are guest-busy (gbusy 35 of 44 ms).
Pathfind's "22 fps" (10-02) was one overlay reading on a different route.

## Step 2: runs (lane.fps20786, Nova, --perflog, HAKUX_GPL=3)

Routes: `routes/fps786-*.route`, generated by `make-routes.sh` /
`steps2route.py` from pathfind's recorded runs (each step's input at the
step's own time + 4 s, then a 600-s genre loop). Pending.
