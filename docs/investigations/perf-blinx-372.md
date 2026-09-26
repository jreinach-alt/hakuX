# Blinx: The Time Sweeper attract demo, ~14 fps on the Thor (#372)

2026-09-26, lane.blinx372. Title 4D530013, Ayn Thor (bdc158a5), master
6550967a5e, hands-off 240 s soaks through the dispatcher. Raw logs are in
`/home/justin/hakux-work/perf/2026-09-26/blinx372/<run id>/`.

## Answer

**The slow window is not bound by the guest CPU. It is bound by the renderer
(pfifo/pgraph) thread, and more than half of that thread's frame is a
synchronous wait for the GPU.** Per guest frame in the demo (perflog run,
medians over the slow window):

| renderer thread, ms per guest frame | demo | menus |
|---|---|---|
| guest frame G (flip to flip) | 68.1 | 17.3 |
| renderer total | 60.9 | 19.4 |
| **Fin:Sub, GPU-completion waits inside pgraph_vk_finish** | **32.1** | 0.2 |
| Draw (recording ~2,050-3,090 draws) | 23.0 | 3.1 |
|   of which Pipe (Sh 8.1, Lu 1.3, Tx 0.5) | 11.0 | 2.9 |
| Surf | 1.8 | 0.0 |
| Idle (renderer waiting for guest commands) | 2.5 | 13.2 |
| Flip wait | 0.0 | 0.0 |
| GPU time (timestamps; R 28.7, X 7.8) | 37.1 | 0.2 |
| render passes per frame | 31 | 5 |

The guest is ahead of the renderer, not behind it: the pushbuffer backlog the
puller has not consumed goes from ~4.6 KB (menus) to ~94 KB mean (demo), and
command drain latency goes from ~14 ms to 70-95 ms, about one guest frame.

`Fin:Sub` is not the cost of `vkQueueSubmit`. For a finish reason that is not
deferred, the timed span includes `vkWaitForFences` (render-thread context,
draw.c:3516) or `qemu_event_wait` on the render thread's completion
(draw.c:3592). The finish counters on the `xemu-work` line say which reason
fires: in the demo it is `Sd2 St1` on most sampled frames (two
SURFACE_DOWN/SURFACE_DOWN_FLUSH finishes plus the flip's STALLED). In the
menus it is `St1` alone. So twice a frame the puller stops recording, waits
for the GPU to drain everything submitted so far, and only then records the
next batch. CPU recording and GPU execution are serialized: 23 + 32 ≈ 55 of
the 61 ms.

## Reproduction (step 1)

| run | apk | held | time-weighted fps, demo window | G median | renderer busy | Tq/frame |
|---|---|---|---|---|---|---|
| 0-0-y-1790405024-titlebench-2 (issue) | 290cba668b65 | 240 s | 14.9 (120-265 s) | 62.1 | 96% | 2314 |
| 1790408373-blinx372-4030372 (run 1) | b5f276b45557 | exited 125 s | 14.3 (~10 s only) | -- | 95% | 2069 |
| 1790408374-blinx372-4032207 (run 2) | b5f276b45557 | exited 200 s | 13.8 (130-231 s) | 59.8 | 96% | 2190 |
| 1790409163-blinx372-166381 (run 3) | b5f276b45557 | 240 s | 13.8 (130-265 s) | 72.0 | 98% | 2378 |
| 1790409543-blinx372-195142 (perflog) | perflog build | 240 s | 13.3 (135-266 s) | 68.1 | 96% | 2068 |

Spread over the two full master windows is nil (13.8, 13.8), and the issue's
apk read 14.9. Time-weighted fps is 60 frames per interval between
consecutive `gfps=` lines (profile.c:614 prints every 60th guest frame), which
weights by wall time as the brief asks. Every run used the same prefs: the
dispatcher's defaults, no `--env`, shader cache cleared on apk change.

Two things the brief asked for could not be delivered through the dispatcher:

- **No `hakuX-pace` line in any dispatched soak.** dispatcher.sh:1356's
  LOGCAT_SPEC is an allow-list ending in `*:S`, and PR #310 added the line
  but did not add the tag to the list. The perflog lines `hakuX-stall`,
  `xemu-sfp`, `xemu-gpu` and `hakuX-cpu` are dropped the same way. Board
  request filed (below).
- **No simpleperf profile or loadsample thread split.** `profile_guest.sh` and
  `loadsample.sh` call `adb` directly (default serial ee317437, the Nova) and
  are not dispatcher modes, and a lane may not touch a device. The split above
  comes from always-on counters instead: `Ri` (renderer idle, pfifo.c:1853),
  `[tlb68] cpu=` (vCPU thread CPU time, cputlb.c:224), `fifoskew`, and the
  perflog `hakuX-phase` / `xemu-work` lines. The top-20 self-symbol table is
  therefore not in this report.

Unrelated to Blinx, but it cost two runs: 3 of 5 Thor soaks on master today
lost the guest early (125, 200, 50 s) with no crash, no `libc:F`, no
`DEBUG:F`. The logcat simply stops. The Nova shows the same thing today on
Galleon, DOA, GoldenEye and Crimson Skies across three apks.

## Falsifier: "the slow window is guest-CPU bound"

Broken, on every run, but not by the brief's 60% threshold:

- The vCPU thread is 92-95% busy in the demo (`[tlb68] cpu=` 1842-1902 ms per
  2 s window). It is also 78-97% busy in the 60 fps menus. The Xbox guest
  spins rather than halting, so this share does not tell the two cases
  apart, and it never falls under 60% in either.
- The renderer thread is idle only 1.7-2.5 ms of a 60-72 ms guest frame
  (96-98% busy) on all four demo windows, against 13-15 ms idle of 17 ms in
  the menus. If the guest CPU were the wall, the renderer would be the thread
  waiting, and `Ri` would be large.
- The pushbuffer backlog grows ~20x and drain latency ~6x. The guest produces
  commands faster than the renderer consumes them.
- Flip-wait share: `Flip` 0.0 ms. GPU-busy share: 37.1 of 68.1 ms = 55%, so
  the GPU is not saturated either. It sits idle while the puller records.

## CPU side (step 3), for completeness

TLB and translation costs are small in the demo window. On the vCPU thread,
`tlb_reset_dirty` took 17.8 ms and `tcg_flush_jmp_cache` 2.3 ms per 2 s (about
1%). On other threads `tlb_reset_dirty` took 15.9 ms per 2 s, against 4.6 in
the menus: these are the renderer's texture dirty-bitmap hits. TB codegen
generated 28-323 blocks per 2 s. Neither TLB flushes nor dirty-page
invalidation matter here (lane.perfarch #68 territory; not pursued).

## Where the draw time goes

`xemu-work` per sampled demo frame: BE/DA 2,053 median (p90 3,088), **SBnd
equal to BE: `pgraph_vk_bind_shaders` runs on every draw**, PBnd 128, SGen 0
(no shader compiles), S2T 7 surface-to-texture copies, RP 17-32. `Tq` (texture
dirty-bitmap queries) ≈ 2,000-2,400 per frame, one per bound texture per draw.
At 8.1 ms for ~2,500 binds, `Pipe:Sh` is ~3 µs per draw. It is real, but it is
the smaller half.

## Lever

**No small, local lever found yet. The bound is two synchronous GPU drains per
guest frame (Sd finishes) serialized behind ~23 ms of draw recording.**

What decides the lever is which of the seven SURFACE_DOWN sites fires twice a
frame: `surface.c:957` (complete_deferred with nothing to coalesce), `:1108`,
`:1511` (sd_dl_to_buf), `:1762` (sd_pending_dl), `:1846` (sd_dirty_dl),
`texture.c:858/1151`, or `renderer.c:1399/2352`. The perflog build already
counts each one (`sd[ev noCb dl cDef cDefC pDl dDl]` and `dlSrc[...]` on the
`hakuX-stall` line, draw.c:984). That line is dropped by the dispatcher's
allow-list. One perflog soak with `hakuX-stall` allowed names the site. No
source change is needed for that.

The two ceilings are these. Removing the waits entirely leaves the renderer at
max(recording ≈ 26 ms, GPU ≈ 37 ms), so about 27 fps. Beyond that the GPU's
37 ms (31 render passes on a tiler) becomes the wall. A prediction is not
registered because no hunk is named.
