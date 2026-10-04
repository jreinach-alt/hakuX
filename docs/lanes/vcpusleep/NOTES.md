# lane.vcpusleep (#507): what the vCPU sleeps on in Simpsons Hit & Run

Brief: `briefs/vcpusleep.md` (lane.local, 2026-10-04), from lane.vcpu60's
rank 1 (`docs/lanes/vcpu60/NOTES.md` section 5). Base: origin/master
425ffe1ad1, merged (no change). Nova only. Budget: one capture run, at most
two arm runs.

The premise, measured by vcpu60 on the 10-04 pathfind hold: in free roam the
Simpsons vCPU thread is on-CPU 17.2 ms and **asleep 9.4 ms** of a 26.7 ms
frame (v_blk, r 0.96 with frame time). The guest itself never idles (gidle
0.65 ms).

## Session 1 (2026-10-04 12:00-12:40 PDT): R1 set up, waiting on the host

### Why R1 is a host run

- Simpsons has no route file. The only driver that reaches free roam is
  pathfind's model-read hold (`pathfind.py --hold-s`, recorded path
  `pathknow/paths/56550015.json`, on `origin/lane/pathfind` only). It drives
  the device over adb from the host.
- `request.sh` has no simpleperf mode. `--route` reads `titles/routes/`
  only.
- So the capture is lane.local's to run, as vcpuwait433's three captures
  were. A lane never touches a device.

### What the capture does (`capture_simpsons_offcpu.sh`)

It is a copy of vcpuwait433's `capture_offcpu.sh` with the soak and route
replaced by a pathfind hold:

| step | what |
|---|---|
| hold | `hold.sh wait nova lane.vcpusleep`, then `wait-idle` |
| build | `dispatch/builds/3ff55c9ac2.apk`, plain. It is master's code: `git diff 3ff55c9ac2 425ffe1ad1 -- . ':!docs'` is empty |
| driver | `pathfind.py 56550015 --hold-s 240 --no-record` from a lane/pathfind checkout (`PATHFIND_TREE`) |
| anchor | the hold's own `hakuX-route: mark gameplay` (pathfind writes it at the claim), then 60 s |
| gate (fails closed) | records only while pathfind's newest `state=` line is `play` or `still`, waiting up to 90 s; otherwise ABORT with no record |
| record | `simpleperf record --app ... -e cpu-clock --trace-offcpu --call-graph dwarf,8192 --duration 60 -f 1000`, 3 off-CPU attempts 15 s apart (as vcpuwait433) |
| void check | any `state=` line other than play/still between `prof start` and `prof end` writes `VOID` |
| out | `perf/2026-10-04-vcpusleep/<short>/`: `<short>.data`, `pf/logcat.txt` (decompose.py reads it), `pf/route-frames/`, `pf/hold.jsonl`, `pathfind.log` |

The parsers for both gates were tested on a constructed logcat
(`state=play`, `prof start`, `state=still`, `state=cutscene`, `prof end`).
The window check printed the cutscene line only, and the newest-state read
gave `menu` at the end.

**Validity, decided before any verdict:** the record window's kept frames
(`pf/route-frames/`, one every 30 s) must show Simpsons in free roam: HUD
portrait bottom left, minimap bottom right, no dialog box (the 10-04 claim
frame's description). decompose.py on `pf/logcat.txt` over the record window
must show v_blk within 9.4 +- 3 ms/frame. Otherwise the window is not the
brief's, and the capture is void for the question whatever waitsite says
(vcpuwait433's tron1: a menu read "BQL owns the wait").

### What the code says before the run

The pusher holds `pfifo.lock` for most of the time it runs:

- `pfifo_thread` holds it across `pgraph_process_pending`, the pusher loop,
  and `pgraph_process_pending_reports` (whose STALLED finish waits for the
  render thread to submit: vcpuwait433's holder on Tron) (pfifo.c:2119-2163).
- Inside the pusher, `XEMU_OPT_LOCKLESS_FAST_DISPATCH` (=1) runs
  `pgraph_method_try_fast` **with pfifo.lock held and no other lock**
  (pfifo.c:1765-1780). Only a slow method drops pfifo.lock, and it takes
  pgraph.lock first while still holding pfifo.lock (pfifo.c:1782-1790). So
  a run of fast methods, or a wait for pgraph.lock, holds pfifo.lock
  throughout.
- The guest's DMA_PUT store (`user_write`, user.c:92-95) takes pfifo.lock,
  and the wait is counted in `lock_wait_ns`. That counter prints only as
  `Lw:` on the `hakuX-cpu` line, which only perflog builds emit
  (profile.c:723-729). The 10-04 hold was not a perflog run, so no line has
  it.

**What the 10-04 hold's own `fifoskew` line adds** (`briefs/vcpu60-data/logcat.txt`, per 2 s window):

| field | value | reading |
|---|---|---|
| kicks | 3,071-3,789 | about 1,700 DMA_PUT stores a second, about 45 a frame |
| behind | = kicks | **every** store arrives while the pusher is behind |
| backlog mean / max | 47-67 KB / 249-277 KB | the pusher is never caught up for long |
| drain mean / p99 | 1.4-1.8 ms / 5-8 ms | a published segment waits about 1.5 ms to be consumed |
| bound | 0 | the skew bound is off (default, `XEMU_OPT_FIFO_SKEW_BOUND 0`), so `pfifo_bound_skew` is not a sleep site |

So whenever the guest kicks, the pusher is running and most likely holds
pfifo.lock. That is the mechanism by which `user_write` could own the sleep.
It is not a measurement of the wait.

### Priors: which site holds >= 50% of the free-roam sleep

| site | what a hit looks like in waitsite.py | prior | evidence |
|---|---|---|---|
| pfifo.lock in `user_write` (DMA_PUT) | `pfifo.lock in USER MMIO`, `--detail` split mostly `user_write <- do_st_mmio` | 0.35 | above: every kick finds the pusher busy, and the pusher holds the lock across fast methods and the stalled finish. Against: on Tron's intro the write was 4.5% of that site, and the read-lock fix moved Tron's in-level sleep by nothing visible |
| BQL (interrupt entry, MMIO) | `BQL <- cpu_exec_loop` or `<- do_ld/st_mmio` at several ms/frame (tron1's menu baseline: 0.26) | 0.15 | the PFIFO thread takes the BQL per PGRAPH IRQ. No path that holds it across GPU-paced work has been read |
| GPU surface download on guest access | `GPU surface download on guest access` | 0.15 | `[rdc]` and `hakuX-pages` show texture and code-page write traffic. vcpuwait433 notes this wait has never been measured on any title |
| pgraph.lock in PGRAPH MMIO | `pgraph.lock in PGRAPH MMIO (#474)` | 0.05 | #474 cut it; tron2 had it at 10% |
| render-thread round trip / other | its bucket | 0.05 | |
| no site >= 50% | the verdict line reports a split | 0.25 | Tron's sleep was layered |

### Go/no-go, written before the run

| R1 says | then |
|---|---|
| `user_write` >= 50%, holder the PFIFO thread | **go**. Lock-free DMA_PUT: a release store of PUT, an atomic kick, and the pusher's lock and cond taken only if it is parked (a parked flag with a full barrier on both sides, so no wakeup is lost); `run_pusher` loads PUT with acquire. Only while the skew bound is off: the bound needs the lock. Files: user.c, pfifo.c, nv2a_int.h (granted rows) |
| BQL >= 50% | name the holder (per-tid pass); stop with a ranked recommendation. The BQL is outside this lane's row |
| surface download >= 50% | name the surface and access; stop and rank. surface.c is outside the row |
| pfifo.lock >= 50% but holder in `pgraph_vk_finish` (vk/reports.c path) | stop: the fix is in vk/reports.c (accuracy804's row) or the finish path (async794's); name it in OUTBOX |
| split | rank the parts by P x win and stop with a recommendation |

## Device use

| # | what | id | result |
|---|---|---|---|
| R1 | host capture `simp1` (lane.local) | requested 2026-10-04 12:40 PDT | waiting |

## Do not repeat

- Do not look for `Lw:` (`lock_wait_ns`) in a plain build's logcat. It is
  printed only on `hakuX-cpu`, which only perflog builds emit.
- Do not look for a Simpsons route on master. The recorded path is
  `pathknow/paths/56550015.json` on `origin/lane/pathfind`.
