# lane.vcpusleep (#507): what the vCPU sleeps on in Simpsons Hit & Run

Brief: `briefs/vcpusleep.md` (lane.local, 2026-10-04), from lane.vcpu60's
rank 1 (`docs/lanes/vcpu60/NOTES.md` section 5). Base: origin/master
425ffe1ad1, merged (no change). Nova only. Budget: one capture run, at most
two arm runs.

The premise, measured by vcpu60 on the 10-04 pathfind hold: in free roam the
Simpsons vCPU thread is on-CPU 17.2 ms and **asleep 9.4 ms** of a 26.7 ms
frame (v_blk, r 0.96 with frame time). The guest itself never idles (gidle
0.65 ms).

## Session 2 (2026-10-04, attempt 2): R1 read. `user_write` owns the sleep: go

**Why attempt 1 did not finish.** It ended on purpose, waiting on the host
capture R1 (lane.local runs device captures; a lane does not). The WAITING
file named `perf/2026-10-04-vcpusleep/simp1/simp1.data`; lane.local captured
it at 13:28 PDT and resumed this lane with an addendum. WAITING is removed.

### Validity (fail closed), checked before any verdict

| check | result |
|---|---|
| frames in the record window (13:28:46-13:29:46 PDT) | `route-frames/132842-hold.png` (4 s before) and `132919-hold.png` (in window): Homer on foot in Evergreen Terrace, Marge portrait top left, minimap bottom right, no dialog box. **Free roam** |
| cap log | attempt 2 recorded 59.96 s, 1,083,515 samples, 0 lost; `void=no` (pathfind state play throughout) |
| decompose.py over the window (29 rows, mark+148..207 s) | fps 39.6, F 25.7 ms, v_run 16.7, **v_blk 8.88 ms/frame** (premise 9.4 +- 3: in), gidle 0.98, Ri 9.4. Whole hold (123 rows): fps 40.0, v_blk 8.79 |
| simpleperf's own view of the vCPU | off-CPU 19,987 ms of 60,019 (33.3%) = 8.4 ms per 39.6-fps frame, agreeing with v_blk |

decompose.py needs `ROUTE <time> mark gameplay` in `run.log`; pathfind's
run.log has none, so the stub line was added from logcat's `hakuX-route: mark
gameplay` at 13:26:19.466.

### R1: what the vCPU sleeps on

`waitsite.py` (vcpuwait433's, unchanged) on `report-sample` text of simp1.data:

| site | ms | % of off-CPU | % of attributed | n |
|---|---|---|---|---|
| **pfifo.lock in USER MMIO** | **11,225** | 56.2 | **79.3** | 5,852 |
| (unsampled switch-out) | 5,823 | 29.1 | - | 7,228 |
| BQL <- cpu_exec_loop | 1,556 | 7.8 | 11.0 | 22,043 |
| pgraph.lock in PGRAPH MMIO | 566 | 2.8 | 4.0 | 3,198 |
| BQL <- mttcg_cpu_thread_fn | 496 | 2.5 | 3.5 | 5,778 |
| BQL <- MMIO (ld, st, stb) | 205 | 1.0 | 1.4 | 6,841 |

`--detail`: **100.0% of the site is `user_write <- memory_region_dispatch_write
<- do_st_mmio_leN`**, the guest's DMA_PUT store (the read has been lock-free
since bc2bced563). 11,224 ms of 11,225. By length: 946 waits of 5-10 ms carry
6.8 s and 192 waits over 10 ms another 2.3 s; the short waits are noise.

Holder pass: the PFIFO thread (tid 26130) was **off-CPU for 10.9 s of the
11.2 s** of these waits (97%). So it holds pfifo.lock asleep. Its sampled
switch-out chains during the waits: `wait_frame_submitted <- pgraph_vk_finish
<- pgraph_vk_process_pending_reports <- pfifo_thread` 3,366 ms,
`wait_timestamp_safe` 351 ms, the rest unsampled (7,126 ms). The render thread
(`render_thread_func`) was idle for 99.3% of them, waiting for work.

As a share of the 9.4 ms: 79.3% of the attributed sleep, about **6.7 ms per
frame** if the unsampled switch-outs split like the sampled ones (4.7 ms per
frame counting the attributed waits alone).

So this is vcpuwait433's predicted "second layer" (its NOTES, 10:25 resume):
after its lock-free read, the guest's next pfifo.lock acquire, the DMA_PUT
store, waits out the same STALLED finish.

### Go/no-go: go

The table written before the run says `user_write >= 50%, holder the PFIFO
thread -> go`. The row "pfifo.lock >= 50% but holder in pgraph_vk_finish ->
stop" was for a wait the vCPU cannot leave without the lock (a read or a
PFIFO MMIO access). The DMA_PUT store is not that: on the hardware it is a
posted write, the vCPU needs nothing back from the pusher, and DMA_PUT has one
writer (the guest). Removing the vCPU's acquire removes the wait whatever the
holder is doing; the finish stays on the PFIFO thread.

What can still make it inert (assume it, as the brief says): the guest's next
step after the kick may need the finish's result (a report, a semaphore, ring
space). If so the sleep turns into guest spin (v_run up, v_blk down, fps flat)
or into a third site. The renderer is idle 9.4 ms a frame (Ri), so the GPU
side has room for the vCPU to run ahead.

### The fix (c2dfca18a1): post the DMA_PUT store when pfifo.lock is busy

| file | change |
|---|---|
| `user.c` | `user_write` of DMA_PUT, when `pfifo_dma_put_may_post()` (skew bound off, channel in DMA mode and current): `qemu_mutex_trylock`. Free: the locked store, unchanged. Busy: `pfifo_post_dma_put()` and return. Every other store and the bound-on case take the lock as before |
| `pfifo.c` | the `posted-put` block: release store of DMA_PUT, kick set atomically, lock taken only to wake a PFIFO thread that is `parked` (Dekker pair: kick then parked on the poster, parked then kick on the PFIFO thread, `smp_mb` between). `pfifo_park()` replaces the three `fifo_cond` waits. The loop clears the kick with `qatomic_xchg`; the pusher loads DMA_PUT with acquire. `pfifo_take_posted()` records a posted store for `fifoskew` (one submission at the oldest post's time) at the loop top and at catch-up; the line gains `posted=`. `XEMU_OPT_POSTED_DMA_PUT 0` restores the locked store |
| `nv2a_int.h` | `parked`, `posted_ts`; the two prototypes; `skew_last_put`'s comment (it is now also written by the PFIFO thread, still under the lock) |

Checked before any device time:

| check | result |
|---|---|
| NDK clang type-check of user.c, pfifo.c, nv2a.c (the Release compile line from compile_commands.json, re-pointed at this worktree), plain, `-DNV2A_PERF_LOG=1` (the cbl path), and `-U__ANDROID__` (the desktop path) | clean (one pre-existing unused `t0` warning in the bound's scan, desktop only) |
| `selftest_postput.sh` (compiles user.c and pfifo.c's posted-put block verbatim, -Wall -Werror) | **PASS**: posted in 0 ms under a 400 ms hold; locked path when the lock is free; locked under the bound (399 ms); 100,000 stores (69,706 posted, 30,294 locked) all consumed, no lost wakeup, with a 20 us window widened between the PFIFO stand-in's kick check and its sleep |
| falsifier F1: the block with the parked wakeup removed | loses a wakeup on the 2nd store: check 4 sees the race |
| falsifier F2: user.c at 425ffe1ad1 | blocks 399 ms under the hold: check 1 sees the lock |
| `check_android_guards.py`, `preflight.sh` | ok, passed |
| desktop build | not run: this host cannot build desktop (AGENTS.md, the libcurl gap) |

What the selftest does not show: that the `smp_mb` pair is needed. Removing
one barrier would be caught only by a store-load reorder, which an x86 host
rarely produces; the argument for it is the Dekker pattern, not a run. One
narrow cost is left: a poster that reads `parked` true in the nanoseconds
before the PFIFO thread reads the kick (and so does not wait) blocks on the
lock for that thread's next critical section. That window is one barrier
wide per park.

### Predictions, registered and pushed before any device run (f5bdecacea)

| file | sha256 | what |
|---|---|---|
| `predictions/vcpusleep-pixels.json` | a4174c60... | A 3ff55c9ac2, B c2dfca18a1; must not move: DMA corruption around surfaces, Texture render target, Texture render update in place (vcpuwait433's three suites: where the guest or GPU reads GPU-written memory right after a submission drains) |
| `predictions/vcpusleep-simpsons.json` | 92394bb4... | A simp1 (on disk), B a host capture `simp2` on c2dfca18a1. Legs V (free roam, `posted=` present, rows), **M** (USER MMIO <= 10% of attributed, posted > 0; P 0.85; separates inert from refuted), S (v_blk <= 6.0; P 0.5), O1 (fps >= 44; P 0.4), O2 (fps >= 48; P 0.2) |

Tron cross-check and GTA: not armed. The budget is at most two arm runs; the
pixel A/B are short suite runs on the Nova and Simpsons B is the decider.

### Next, by P x win, after the arm

| B shows | then |
|---|---|
| M pass, S pass, O1 pass | fold (pixel arms PASS required). Simpsons +10% or more; GTA's sub-30 windows are the next title to read |
| M pass, S fail | inert: B's capture names the next site (waitsite top site, --detail, holders). Rank that site against the render-side options in vcpu60's plan; do not rerun |
| M pass, S pass, O1 fail | the freed time went to guest spin (v_run) or the renderer is now the limit (Ri ~0): the next lever is GPU side (async794's row), not the vCPU |
| M fail | refuted: the posted path did not act. Read --detail for which store still waits |

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
| R1 | host capture `simp1` (lane.local) | `perf/2026-10-04-vcpusleep/simp1/` (13:28 PDT) | valid (free roam, v_blk 8.88). `user_write` (DMA_PUT) 79.3% of attributed off-CPU |
| P-A | pixel arm A, 3 suites, Nova pinned, 3ff55c9ac2 | `1-1791146994-vcpusleep-base-1384096` | queued 13:50 PDT behind pathfind's hold |
| P-B | pixel arm B, 3 suites, Nova pinned, c2dfca18a1 | `1-1791146995-vcpusleep-fix-1400786` | queued 13:50 PDT; its build makes `dispatch/builds/c2dfca18a1.apk` for simp2 |
| B | host capture `simp2` on c2dfca18a1 (lane.local) | requested in OUTBOX 13:55 PDT | waiting |

## Do not repeat

- Do not re-run `simpleperf report-sample` to re-read simp1: the 3 GB text
  dump takes a minute to make and waitsite reads it with `--from-text` in
  75 s. pathfind's `run.log` has no `ROUTE ... mark gameplay` line, so
  decompose.py needs one appended from logcat's `hakuX-route: mark gameplay`.
- Do not take a pfifo.lock wait in `user_write` as a reason to move the
  STALLED finish out from under the lock (vk/reports.c, accuracy804's row).
  The store needs nothing from the holder; posting it removes the wait
  without touching the finish.

- Do not look for `Lw:` (`lock_wait_ns`) in a plain build's logcat. It is
  printed only on `hakuX-cpu`, which only perflog builds emit.
- Do not look for a Simpsons route on master. The recorded path is
  `pathknow/paths/56550015.json` on `origin/lane/pathfind`.
