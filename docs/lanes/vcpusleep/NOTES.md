# lane.vcpusleep (#507): what the vCPU sleeps on in Simpsons Hit & Run

Brief: `briefs/vcpusleep.md` (lane.local, 2026-10-04), from lane.vcpu60's
rank 1 (`docs/lanes/vcpu60/NOTES.md` section 5). Base: origin/master
425ffe1ad1, merged (no change). Nova only. Budget: one capture run, at most
two arm runs.

The premise, measured by vcpu60 on the 10-04 pathfind hold: in free roam the
Simpsons vCPU thread is on-CPU 17.2 ms and **asleep 9.4 ms** of a 26.7 ms
frame (v_blk, r 0.96 with frame time). The guest itself never idles (gidle
0.65 ms).

## Session 3 (2026-10-04, attempt 3): simp2 read. The sleep is gone and the frames did not come back

**Why attempt 2 did not finish.** It ended on purpose, waiting on things
outside the session: the host capture simp2 (lane.local runs device captures)
and the two pixel arms. Both arrived (addendum 14:28 PDT). WAITING is removed.

**Result: M and S pass, O1 and O2 fail. The posted store removes the vCPU's
sleep, and the frame is then paced by the GPU side. The code is reverted on
the branch (f6ac723228). c2dfca18a1 stays in history for re-arming.**
`selftest_postput.sh` went with the revert, because it compiles the
reverted block. It is at c2dfca18a1 with the code it tests.

### Validity of simp2 (B, c2dfca18a1), checked first

| check | result |
|---|---|
| cap log | `--trace-offcpu` attempt 1 recorded 59.98 s, 1,071,700 samples, 0 lost; `profile=1 void=no`; battery 80 |
| record window | 14:24:05-14:25:05 PDT, mark gameplay 14:21:52.404, so mark+133..193 s (simp1: mark+148..208) |
| frames in the window | `142421-hold.png`, `142455-hold.png`: Homer on foot in Evergreen Terrace, Marge portrait top left, minimap bottom right, no dialog box. **Free roam** |
| build proof | every `fifoskew` line carries `posted=` (1,433-2,901 a window); only c2dfca18a1 prints it |
| rows | decompose.py: 124 over the hold (>= 60), 30 in the window (>= 20). No BugCheck; pathfind held play |

Leg V passes.

### A against B

decompose.py, whole hold (`all` row), with the same stub `ROUTE` line from
logcat's mark gameplay:

| | A simp1 (master) | B simp2 (posted store) |
|---|---|---|
| fps (decompose `all`; mean of rows) | 40.05; 40.03 | **36.22; 37.88** |
| frame F ms | 24.97 | 27.61 |
| guest busy ms/frame | 24.45 | 12.62 |
| guest idle ms/frame (timer-woken) | 0.62 (0.35) | **14.93 (12.41)** |
| Ri, PFIFO parked ms/frame | 9.50 | **0.20** |
| v_run ms/frame | 16.13 | **26.67** |
| v_blk ms/frame | 8.85 | **0.80** |
| record window: fps / v_blk (row means, 30 rows each) | 39.81 / 8.84 | 37.40 / 1.14 |

waitsite.py on simp2: vCPU off-CPU **2,543 ms of 60,017 (4.2%)**, against
19,987 (33.3%) in simp1. `pfifo.lock in USER MMIO` is 75 ms, **3.3%** of
attributed. Top site: `BQL <- cpu_exec_loop` 1,198 ms (53%), about 0.5 ms a
frame.

| leg | bar | B | verdict |
|---|---|---|---|
| M | USER MMIO <= 10% of attributed, posted > 0 | 3.3%, posted 1,433+ a window | **PASS** |
| S | whole-hold and window v_blk <= 6.0 ms/frame | 0.80 / 1.14 | **PASS** |
| O1 | whole-hold fps >= 44.0 | 36.22 (37.88 row mean) | **FAIL** |
| O2 | whole-hold fps >= 48.0 | same | **FAIL** |

Pixel arms (`ab_compare.py` against `vcpusleep-pixels.json`): **PASS**, 45 of
45 captures byte-identical, 5 exact in each arm.

### Where the sleep went

The prediction's row "M and S pass, O1 fails" says the freed time went to
guest spin or the renderer became the limit. **Both happened:**

1. **Guest spin.** v_run rose 10.5 ms/frame as v_blk fell 8.05. The guest
   now finishes its frame's work in 12.6 ms. It then idles 14.9 ms, woken
   by the timer, and the vCPU spins through that idle on the CPU: it was
   on-CPU 57.5 s of 60. It also took the X3 (cpu7) for 53.7 s, against
   18.3 s in A (`cpu_switches.py`, from `simpleperf dump`'s per-record
   CPU).
2. **The PFIFO thread is paced by the GPU.** It is never parked (Ri 0.2)
   and never preempted (6 ms of 47.6 s off-CPU), yet it is off-CPU 79% of
   the time. Paired exactly (`exact_offcpu.py`, below), it takes **one
   long sleep per frame: n = 2,058, median 21.3 ms, 43.4 s in total. In A
   the same sleep is n = 2,054 with median 8.0 ms.** The render thread
   does not run during it (1 of 2,058). Each sleep comes right after a
   short wake out of `wait_frame_submitted`, with no on-CPU sample between
   (`lastrun.py`). In that code path (`pgraph_vk_finish`'s frame rotation)
   the only call that blocks without the render thread is
   `vkWaitForFences` on the frame slot (draw.c:4351). So **the sleep is the
   GPU fence of an earlier frame**. This is inference: none of these
   switch-outs carries a sample. `wait_timestamp_safe`, the other GPU
   wait, is sampled at 1.8 s.
3. **Same work per frame.** `[shd413]`: 316 against 311 pipeline binds a
   frame, and 100 against 99 shader binds. The PFIFO thread's CPU per frame
   fell, from 6.56 to 5.46 ms. Also, the guest's 1,700 kicks a second
   became about 80 posted batches (`fifoskew` kicks 144-179 a window, drain
   mean 13 ms against 1.5).

So B's frame is 27 ms of GPU-side time for the same draws as A. A's
frame-slot fence wait was already 8 ms a frame, so the GPU side was near the
limit in A as well. The lock was making the vCPU wait out the GPU. Removing
the lock moves that wait into guest idle; it does not shorten the GPU's
frame.

**Why B's GPU frame is longer than A's is not measured.** One run each, and
Simpsons free roam varies with the route: vcpu60's hold read 37, simp1 40,
simp2 37.9. The candidate mechanisms:

- power: the vCPU now spins at 96% of the X3 against 67%;
- placement: the PFIFO thread lost the X3, 4,584 ms on cpu7 down to 251;
- submission shape: 80 large batches a second instead of 1,700 small ones.

Separating them needs the GPU clock and per-frame GPU time on both builds.
That is the telemetry for the next lane (below), not a rerun.

### waitsite.py's pairing hands a bounce's sample to the long sleep after it

waitsite.py (vcpuwait433) charges each off-CPU interval to a sched_switch
sample within +-200 us of its switch-out. A thread that wakes, runs under
50 us and sleeps again unsampled gets its long sleep charged to the short
one's sample. `exact_offcpu.py` pairs a switch-out only with a sample taken
after the thread's previous switch event.

| reading | +-200 us (waitsite) | exact |
|---|---|---|
| simp1 vCPU, `user_write` | 11,225 ms | **11,224 ms**: R1 stands |
| simp1 PFIFO, `wait_frame_submitted` | 12,656 ms | **561 ms**, all under 5 ms; the long sleeps are unsampled |
| simp2 PFIFO, `wait_frame_submitted` | 12,732 ms (8.8 s in waits >= 20 ms) | **170 ms** |

So session 2's holder line ("PFIFO asleep in `wait_frame_submitted`,
3,366 ms") is wrong about the site. During the vCPU's waits the PFIFO
thread was asleep in the frame-slot fence wait that follows it. The holder
was asleep on the GPU, not on the render thread. The go decision does not
change, because the store needs nothing from either. The recommendation
does: see the ranking.

### Next, ranked by P x win

| # | what | P | win | evidence |
|---|---|---|---|---|
| 1 | **Name the GPU-side frame time on Simpsons.** Per-frame GPU time from `gpu_ts_readback` plus the GPU clock (perfarch's `HAKUX_TOPO` sampler), on master and on c2dfca18a1, in free roam (`capture_simpsons_offcpu.sh` drives it). Then cut what the GPU spends 25-27 ms on. This is GPU-side work (async794's or a Simpsons GPU lane), not this row | 0.7 that it names the GPU's frame; 0.35 that the cut is reachable | it gates every Simpsons gain. The vCPU's own work is 12.6 ms a frame (CPU-side ceiling about 79 fps) and the PFIFO thread's is 5.5 ms | A's fence wait is already 8 ms a frame and B's is 21; same draws |
| 2 | **Re-arm the posted store on top of #1's cut** (`git revert f6ac723228`) | 0.5 | once the GPU stops pacing the frame, the 8.85 ms/frame lock wait returns as the vCPU's limit. The posted store then turns it into frames: vcpu60's 45-58 band | M and S pass, and pixels are byte-identical, so it is ready |
| 3 | Guest idle without the spin on Simpsons (idlehalt): the vCPU spins through 12.4 ms a frame | 0.2 that it recovers B's 2-4 fps, if power is the cause | small in fps; real on battery | B's vCPU is on-CPU 96%, on the X3 |

Do not rerun simp2 hoping for 44: the outcome leg is decided by the GPU
side, not by noise.

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
| P-A | pixel arm A, 3 suites, Nova pinned, 3ff55c9ac2 | `1-1791146994-vcpusleep-base-1384096` | 45 captures, 5 exact |
| P-B | pixel arm B, 3 suites, Nova pinned, c2dfca18a1 | `1-1791146995-vcpusleep-fix-1400786` | 45 of 45 byte-identical to A: PASS |
| B | host capture `simp2` on c2dfca18a1 (lane.local) | `perf/2026-10-04-vcpusleep/simp2/` (14:24 PDT) | valid. M, S pass; O1, O2 fail (36.2-37.9 fps against 40.0) |

Budget: one capture (simp1) plus the arm (simp2) plus two short pixel arms.
Nothing else was queued.

## Do not repeat

- Do not read a lock or wait site's holder from waitsite.py's +-200 us
  pairing when the holder wakes and re-sleeps. Use `exact_offcpu.py` (run
  from the repo root; it imports waitsite.py's parser). Preemption and CPU
  placement need `cpu_switches.py`; report-sample has no CPU field.
- Do not take "the vCPU sleeps on a lock" as "the vCPU's sleep is the
  frame's limit". Here the lock carried a GPU wait, and removing it gave
  the same frames with the vCPU spinning instead. Read the holder's own
  long sleeps before pricing the win.
- The simp1/simp2 report-sample dumps are 3 GB each. Make them with
  `simpleperf report-sample --show-callchain` called from python3. The Bash
  tool refuses the NDK path outside the worktree.

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
