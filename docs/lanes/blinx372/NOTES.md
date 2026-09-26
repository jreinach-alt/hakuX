# lane.blinx372 -- #372 Blinx attract-demo frame split

Master 6550967a5e, Thor (bdc158a5). Runs (raw logs copied to
/home/justin/hakux-work/perf/2026-09-26/blinx372/):

| id | build | held | slow window |
|---|---|---|---|
| 0-0-y-1790405024-titlebench-2 (the issue's) | 290cba668b65 | 240 s | 120-265 s |
| 1790408373-blinx372-4030372 (run 1) | b5f276b45557 | exited 125 s | ~10 s of demo |
| 1790408374-blinx372-4032207 (run 2) | b5f276b45557 | exited 200 s | 130-231 s |
| 1790408376-blinx372-4033793 (perflog) | 900f249658d1 | exited 50 s | none |
| 1790409163-blinx372-166381 (run 3) | queued | | |
| 1790409543-blinx372-195142 (perflog retry) | queued | | |

## Instruments, and what the brief named that a lane cannot run

`profile_guest.sh` and `loadsample.sh` both call `adb` directly (default serial
ee317437, the Nova) and are not dispatcher modes, so a lane cannot run them.
The split is read from lines every dispatched soak already carries:

- `hakuX-perf` `Ri` = renderer (pfifo puller) thread idle ms per guest frame,
  pfifo.c:1853. Renderer busy share = 1 - Ri/G.
- `hakuX-perf` `Tq` = texture dirty-bitmap test-and-clear calls per guest
  frame, vk/texture.c:536 (one per bound texture per draw, via
  pgraph_vk_poll_bound_textures).
- `[tlb68] cpu=` = vCPU thread CPU time per 2 s window (CLOCK_THREAD_CPUTIME_ID,
  cputlb.c:224); `rd/rdus`, `rdo/rdous`, `jc/jcus` = TLB dirty-reset and
  jump-cache flush counts and their time.
- `fifoskew` = pushbuffer backlog (bytes the guest wrote that the puller has
  not consumed) and drain latency.
- `[surf92] updates=` heartbeat every 2048 update_surface_part calls = draw rate.
- Time-weighted fps = 60 frames per consecutive gfps-line interval
  (profile.c:614 prints every 60th frame). `soakread.py` does all of this.

**hakuX-pace is missing from every dispatched soak**: dispatcher.sh:1356's
LOGCAT_SPEC is an allow-list ending in `*:S` and does not name `hakuX-pace`
(PR #310 added the line, not the tag). The brief's "record the hakuX-pace
line" cannot be met through the dispatcher until that one token is added.
`hakuX-cpu`, `xemu-gpu`, `xemu-surf` (perflog lines) are also filtered.

**Early exits**: 3 of 3 Thor soaks on master today lost the guest (125, 200,
50 s) with no crash line, no libc/DEBUG fatal; the logcat simply stops.
Same pattern on the Nova today (Galleon, DOA, GoldenEye, Crimson Skies across
three apks). Not Blinx-specific and not investigated here.

## Measurements

| field | menus (0-90 s) | demo, original | demo, run 2 | demo, run 1 (10 s) |
|---|---|---|---|---|
| time-weighted fps | 57-60 | 14.9 | 13.8 | 14.3 |
| G (guest frame, ms, median) | 16-17 | 62.1 | 59.8 | -- |
| Ri (renderer idle, ms/frame) | 13-15 | 2.2 | 2.3 | 1.7-20 |
| renderer busy | ~15% | 96% | 96% | 95% |
| Tq (tex dirty queries/frame) | 8-12 | 2314 | 2190 | 2069 |
| surface updates/s ([surf92]) | low | ~70k | ~51k | ~51k |
| fifoskew backlog mean (bytes) | ~4.5k | | 70-103k | |
| fifoskew drain mean (ms) | 8-10 | | 70-95 | |
| vCPU thread CPU (ms per 2 s) | 1937-1940 | | 1842-1902 | |
| TLB reset-dirty time (vCPU, ms per 2 s) | 18 | | 17-61 | |

Reading: the vCPU thread is ~95% busy in the 60 fps menus as well as in the
demo, so its busy share does not discriminate (the guest spins; the brief's
60% threshold is never crossed either way). What does discriminate is the
other side: the renderer thread goes from 85% idle to 4% idle, and the
guest's pushbuffer backlog grows ~20x with ~1.5 guest frames of drain
latency. The guest is AHEAD of the renderer. The wall is the renderer
(pfifo/pgraph) thread, at ~2000+ draws per guest frame.
