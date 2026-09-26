# lane.blinx372 -- #372 Blinx attract-demo frame split

Status: 2026-09-26, reproductions queued on the Thor at master 6550967a5e:
- 1790408373-blinx372-4030372  plain soak, 240 s, frames every 10 s (run 1)
- 1790408374-blinx372-4032207  plain soak, 240 s, frames every 10 s (run 2)
- 1790408376-blinx372-4033793  -Pperflog=true soak, 240 s (renderer phase split)

## Instruments, and what the brief named that a lane cannot run

`profile_guest.sh` and `loadsample.sh` both call `adb` directly (default serial
ee317437, the Nova) and are not dispatcher modes, so a lane cannot run them
(lane contract: never touch a device directly). The thread split is read
instead from two always-on fields of the `hakuX-perf` line and from the
perflog build's `hakuX-phase` line:

- `Ri` = renderer (pfifo puller) thread idle time per guest frame, ms,
  pfifo.c:1853. Busy share = 1 - Ri/G.
- `Tq` = texture dirty-bitmap test-and-clear calls per guest frame,
  vk/texture.c:536 (one per bound texture per draw).
- `hakuX-pages inval ... generated X of Y calls` = TB codegen per 2 s window
  (guest-CPU translation churn).

`soakread.py` here buckets those per 30 s and summarises a window.

## Original run (0-0-y-1790405024-titlebench-2, apk 290cba668b65), window 120-265 s

| field | menus (0-90 s) | demo (120-265 s) |
|---|---|---|
| G (guest frame, ms) | 16.2-17.1 | 42-84, median 62.1 |
| Ri (renderer idle, ms/frame) | 13.7-14.5 | 1.4-2.0, median 2.2 |
| renderer busy | ~15% | ~96% |
| Tq (tex dirty queries/frame) | 8-12 | 1533-3012, median 2314 |
| TB codegen per 2 s | -- | 28-2212 generated (mostly <100) |

This apk predates PR #310, so it has no `hakuX-pace` line.
