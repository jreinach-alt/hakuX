# lane.aufire412b -- #412 Agent Under Fire: what paces the frame (vCPU side)

Base: master @ 747b27ddc5 (the #416 UBO-ring hunk, 1b557ff6a4, is an ancestor).
Title 4541000D, Nova ee317437. PR #444 (MAX perf regimen) is **not** folded, so
every capture here ran at the default regimen.

## 0. What the brief asked for, and what could not run as written

The brief's first counter is a vCPU-thread simpleperf profile queued through
`request.sh`. **The dispatch path has no simpleperf hook.** `request.sh` has
no such option and `dispatcher.sh` never mentions simpleperf; ghoul311's NOTES
say the same. The profiles that exist (perfbase, buildflags427) were taken by
the host with `docs/testing/perf/profile_guest.sh` through
`host-tools/profile_ab.sh`. That script drives **Crimson Skies with a pad mash**.
AUF needs the survey route (14 START/A rounds) to reach its scene. So the
profile is a board request to the host (section 4), not something a lane can
queue.

Everything below was read offline from AUF logcats already on disk, using
always-on lines that the brief did not name: `[tlb68]` (vCPU CPU time and
churn), `hakuX-pace` (VBLANKs per flip), and `vbl`/`vblphase` (the guest-visible
VBLANK). Those lines carry most of the answer.

Captures (all Nova, survey route):

| id | ref | what |
|---|---|---|
| `0-0-y-1790433159-titleplay-p1-aufire` | a5b5b628f2 | pass 1, not perflog, 420 s |
| `1790450038-aufire412-1573805` | dc38b745b8 | master perflog soak (aufire412 section 4) |
| `0-0-x-1790453714-aufire412-rerunA` | be41e81662 | A (pre-hunk), perflog, the judged A |
| `1790453714-aufire412-3780657` | be41e81662 | A first run (adb faults), replicate |
| `1790453716-aufire412-3780798` | 1b557ff6a4 | B (UBO ring grows, no finish), perflog |

Windows are seconds since the logcat's first line, the same as aufire412's
`splitread.py` windows: mission play 299-483 (pass 1: 345-423), pause menu
over the scene 220-285.

## 1. The vCPU levers #424 and #425 (jump-cache part) are ~0 here

`churn.py` from lane/tbchurn424 (the build's own `[tlb68]` timers, not sampled),
mission play:

| run | vCPU CPU / wall | jc% | rd% | **churn%** | discards/s | slow stores/s |
|---|---|---|---|---|---|---|
| pass 1 | 96.6% | 0.1 | 0.5 | **0.5** | 365 | 365 |
| master soak | 95.1% | 0.1 | 0.5 | **0.5** | 342 | 342 |
| A rerun | 96.0% | 0.1 | 0.4 | **0.5** | 346 | 346 |
| A first | 96.0% | 0.1 | 0.4 | **0.5** | 359 | 359 |
| B | **84.1%** | 0.1 | 0.5 | **0.6** | 324 | 324 |

- **#424** (code-write invalidation and dirty re-arm, PR #434): 0.5% of vCPU
  CPU. That is at most 0.3 ms of a 64 ms frame (a bound: `jcus+rdus` over `cpu=`).
  Crimson on its route reads 23.9%. **AUF is not a case for #424.**
- **#425, the jump-cache wipe part** (PR #443): `jc%` is 0.1%, at most 0.06
  ms per frame. #425's larger part is the TB lookup path (`helper_lookup_tb_ptr`
  and the qht, ~11% on Crimson). `[tlb68]` cannot see that part, and only the
  profile in section 4 can price it for AUF.

## 2. After #416, neither thread is saturated, and fps is still flat

aufire412 section 6 said "the vCPU is saturated in both arms". **It is not.**
It was saturated in A and **is not in B**:

| mission play | fps | ms/flip | vCPU busy | vCPU busy per frame | renderer idle (post-flip `Fr`) | renderer CPU (Tot-Idle-Fin) | GPU |
|---|---|---|---|---|---|---|---|
| A rerun | 15.08 | 66.3 | 96.0% | 63.7 ms | 8.9 | 30.6 | 40.0 |
| A first | 15.14 | 66.0 | 96.0% | 63.4 ms | 8.8 | 30.8 | 37.5 |
| B | 15.48 | 64.6 | **84.1%** | **54.3 ms** | 11.7 | 41.8 | 28.3 |

(vCPU busy per frame = `[tlb68]` `cpu=`/`dt=` x ms/flip. It is thread CPU time,
so it **bounds** the guest's work from above: a guest spin-wait is CPU time
too. Renderer and GPU columns are the `hakuX-phase` medians from aufire412
section 6. `St`, the starve idle, is 0 in all three runs, so all renderer idle
is post-flip.)

In B the vCPU does ~9 ms less CPU per frame, the renderer idles ~3 ms more,
the GPU does 12 ms less, and the frame is 1.7 ms shorter. Every side of the
pipeline gained slack, and none of it became frame rate. So the frame is not
throughput-bound on any one thread. It is paced by a wait that every side
reaches.

## 3. The frame is counted in VBLANKs, and #416 made the VBLANK late

`pace.py` (hakuX-pace, per 60 flips) and `vbl.py` (`vbl`/`vblphase`, per ~2 s),
mission play 299-483:

| run | fps | VBLANK/flip | flips at 2 / 3 / 4+ VBLANKs | guest VBLANK rate | clamps | late, undeferred (mean) | deferred |
|---|---|---|---|---|---|---|---|
| A rerun | 15.08 | 3.95 | 3 / 6 / 91% | 59.57 Hz | 59 | 0.34 ms | 19.3% |
| A first | 15.14 | 3.93 | 3 / 6 / 90% | 59.46 Hz | 73 | 0.33 ms | 19.1% |
| master soak | 15.19 | 3.91 | 3 / 9 / 88% | 59.35 Hz | 90 | 0.43 ms | 18.9% |
| **B** | 15.48 | **3.69** | **11 / 24 / 65%** | **57.16 Hz** | **414** | **1.52 ms** | 19.2% |

Pause menu over the scene, 220-285: A rerun 59.65 Hz with 16 clamps. **B:
54.49 Hz, 232 clamps, undeferred lateness 3.07 ms, worst interval 71.7 ms.**
Front end at 60 fps (pass 1, 121-209): 59.94 Hz, 0 clamps.

- fps = VBLANK rate / VBLANKs per flip, to the digit: 59.57/3.95 = 15.08 and
  57.16/3.69 = 15.49. **The guest got 7% faster in VBLANK units in B, 35% of
  flips now take 3 VBLANKs or fewer, and 4% of that went back because the
  VBLANKs came late.** The menu window loses 9% of its VBLANKs.
- A clamp is the timer callback running more than a whole period late
  (nv2a.c `nv2a_vblank_timer_cb`, grid re-base). The guest loses that VBLANK
  outright. The callback runs on the main loop under the BQL
  (nv2a.c:314-316). B has 5-7x the clamps and 4.5x the undeferred lateness of
  every A run. **Something holds the main loop or the BQL longer in B.** The
  deferral share is equal in both (19%), so the policy did not change and the
  timer's delivery did.
- The vCPU idle that appeared in B (~10 ms per frame) and the renderer's
  post-flip idle (~11.7 ms) are the same size. That is the shape of both
  sides waiting for the same event after the flip. If the title flips on
  VBLANK, that event is the late VBLANK.

What this does **not** establish, and what would:

- **Whether the title waits for VBLANK, or whether the VBLANK count only
  measures frame length.** The pace line cannot tell the two apart, because
  vb/flip = frame x rate holds either way. Per-frame flip intervals would
  settle it: they cluster at multiples of 16.7 ms only if the title waits. The
  front end's exact 1.00 VBLANK per flip at 59.9 fps says the title presents
  on VBLANK there.
- **Who delays the main loop in B.** Three candidates were read in the code;
  none is measured:
  1. The guest's MMIO. `user_write` (user.c:82-85) takes `pfifo.lock` with the
     BQL held, and already times the wait into `cpu_working.lock_wait_ns`.
     **That counter is smoothed into `lock_wait_ms` (profile.c:121) and never
     printed.** The `hakuX-cpu` format (profile.c:810) omits it.
  2. PGRAPH register reads from the guest, blocked on `pgraph.lock`. The puller
     holds that lock across whole method batches (`XEMU_OPT_PFIFO_LOCK_BATCH`,
     pfifo.c:1407-1451), and B's Surf/Tx grew by 10 ms inside those batches.
  3. ~~The display path.~~ Read and excluded as a BQL holder. The Android
     display loop calls `nv2a_get_framebuffer_surface` (ui/xemu.c:2045)
     without the BQL, and under `XEMU_OPT_REDUCE_BQL` it takes no BQL around
     the blit either (xemu.c:2162-2189). It does take `pfifo.lock`
     (vk/renderer.c:2557), so it can contend with the guest's `user_write`,
     and it would show in candidate 1's counter.
  The FIFO skew bound is not a candidate: `fifoskew bound=0` and `held(n=0)`
  in every run.

## 4. Requests (the lane cannot run these)

1. **Host, a routed simpleperf of AUF** (board request
   `dispatch/board-requests/aufire412b.md`): the B APK (1b557ff6a4, the
   folded hunk), survey route, 30 s of vCPU-thread samples in the pause-menu
   window, and a second 30 s in mission play. `profile_guest.sh`'s pad mash does
   not reach AUF's scene, so the route has to drive it. The profile prices the
   #425 lookup path, #427's runtime helpers, and guest-code self time, and it
   shows guest spin loops, which appear as one hot JIT block.
2. **A file grant for `hw/xbox/nv2a/pgraph/profile.c`**: print `lock_wait_ms`
   on the `hakuX-cpu` line. The counter already exists, so this adds no timer.
   Candidate 1 above is then read off any perflog soak.

## 5. Per-lever pricing for AUF (bounded, from which capture)

| lever (owner) | AUF share | bound on ms per frame | from | can it move AUF? |
|---|---|---|---|---|
| #424 invalidation/re-arm (PR #434) | 0.5% of vCPU CPU | <= 0.3 | `[tlb68]` all five captures | no |
| #425 jump-cache wipes (PR #443) | 0.1% | <= 0.06 | `[tlb68]` | no |
| #425 TB lookup / qht | unmeasured | -- | needs profile (4.1) | open |
| #427 build flags (PR #435) | unmeasured on AUF; 3.4% of vCPU on Crimson/Nova | ~1.8 if AUF matches Crimson | buildflags427 a.data | below any change fps has shown |
| #428 vCPU on prime (PR #437, refuted) | B's vCPU is 84% busy, not saturated | -- | `[tlb68]` B | no |
| VBLANK delivery (no lever lane) | B lost 4% of VBLANKs (9% in menu) | 2.7 ms per frame at 3.69 VBLANK/flip | `vbl` A vs B | +4-9% fps if restored |

"2.7 ms per frame": B's frame at 59.57 Hz instead of 57.16 Hz is 3.69 x
(16.79 - 17.49) ms. It bounds what on-time VBLANKs could give back **if** the
title's frame is counted in VBLANKs. If it is not, the late VBLANK is a
symptom and gives nothing.

## Status (2026-09-26, session 1)

Filed: `dispatch/board-requests/aufire412b.md` (asks 4.1 and 4.2). Posted on
#412 (issuecomment-5851252069). Delivered to lane.tbchurn424 on #424 and to
lane.jcache425 on #425. #427's lane is finished (PR #435 is ready), and its
bound (~3% of vCPU on Crimson) is quoted in section 5 rather than sent.

Not done, with the reason:

- **The simpleperf profile.** The dispatcher cannot take it, and it is filed
  with the host (4.1).
- **The wait-excluded timer on Surf/Tx.** It needs vk/surface.c and
  vk/texture.c, which are not this lane's. The `lock_wait_ms` print (4.2) is
  cheaper and tests the contention reading first. If the guest's `pfifo.lock`
  wait is ~0 in B, the Surf/Tx timer is the next ask.
- **No prediction.** No code changed. The first arm this lane would register is
  the `lock_wait_ms` print (instrument only, no pixel leg), after the grant.

Waiting on: the host's `[host]` comment on PR #451 with p1/p2.data, and the
board's answer to the profile.c grant.

## Session 2 (2026-09-26 PDT, attempt 2)

**Why attempt 1 did not finish.** It ended waiting on the host's answer to
the two board asks (section 4). Both were outside the lane, so the wait was
real, but the session named no resolvable signal the handback could see, and
the lane sat idle until the host resumed it. Both asks came back granted at
17:49 PDT: profile.c lent for the one field, and the profile as a held Nova
session this lane runs itself (<= 15 min, APK 1b557ff6a4).

Done in this session:

- `hakuX-cpu` now ends with `Lw:%.1f`, the guest's `pfifo.lock` wait in
  `user_write`, ms per guest frame (EMA, alpha 0.2), commit 9aff9caf99.
  Perflog-gated like the rest of the line. aufire412's `splitread.py`
  (not this lane's file, left unedited) reads `hakuX-cpu` by key: its
  `--selftest` passes, and its `cpu()` returns `cpu_Lw` for a line built from
  the new format string (checked by hand). No pixel leg is possible, so no
  golden prediction. Read by request `1790470425-aufire412b-4161655`
  (perflog soak of 53a9b91df3, survey route), queued 2026-09-26 17:53 PDT.
- `capture_p1p2.sh` (this dir): the held session. The survey route verbatim,
  run through `soak_title.sh` with a private lease path, p1 5 s after the 11th
  menu `press START`, p2 40 s after `mark play`, both 30 s of
  `simpleperf record --app ... -e cpu-clock --call-graph dwarf,8192 -f 1000`.
  The `p1 start`/`p2 start` marks go to logcat (`hakuX-route`) so the windows
  can be cut from the session logcat. Output:
  `~/hakux-work/perf/2026-09-26-aufire412b/`.

## 6. The profile: the vCPU spends half its time returning to the exec loop

Held Nova session 2026-09-26 18:31-18:37 PDT (01:31-01:37Z), APK
1b557ff6a4 (the folded #416 hunk, not perflog), survey route verbatim, run by
`capture_p1p2.sh`. **Default regimen**: #444 (MAX perf) folded after this
branch's merge, and the session ran `soak_title.sh` from this tree. The hold
stood 01:17:53-01:36:56Z; the first 14 min of it waited on a jcache425
request, and the device was used 01:31:40-01:36:56 (5 min 16 s).

Files: `~/hakux-work/perf/2026-09-26-aufire412b/{p1,p2}.data`, `logcat.txt`,
`soak.log`, `prefs.xml`, `apk/libxemu.so` (the APK's own copy, with debug
info). vCPU tid 9188 (its chains end in `__start_thread`, and it alone carries
`cpu_exec_loop`, `helper_lookup_tb_ptr` and the JIT).

**The windows match the soaks** (`pace.py`/`vbl.py`, seconds since the logcat's
first line):

| window | fps | VBLANK/flip | v2/v3/v4+ % | vCPU busy | VBLANK Hz | clamps |
|---|---|---|---|---|---|---|
| p2, mission, 272-303 | 16.12 | 3.55 | 9/29/61 | 87.0% | 57.22 | 67 |
| B soak mission 299-483 | 15.48 | 3.69 | 11/24/65 | 84.1% | 57.16 | 414 |
| p1, menus over the scene, 189-220 | 20.55 | 2.72 | 33/31/21 | 83.2% | 56.02 | 73 |
| B soak pause 220-285 | 15.71 | 3.46 | 16/28/51 | 72.8% | 54.49 | 232 |

p2 is the soak's mission play. p1 sits on rounds 11-13 of the menus, a
lighter screen than the soak's pause window (20.6 fps against 15.7), with the
same VBLANK loss. p1 is a near match, not the same screen. The late VBLANK
reproduces without perflog: 57.2 Hz here, 59.6 Hz in pass 1 (pre-hunk, not
perflog).

**Sample counts, vCPU thread** (`vcpucount.py`, plain `report-sample`
records, cpu-clock at 1 kHz):

| | p1 | p2 |
|---|---|---|
| vCPU samples | 24,698 | 26,139 |
| `cpu_exec_loop` self | 12,642 (51.2%) | 14,152 (54.1%) |
| of which the `stlrh; dmb ish; ldar` at 0x5b1a84-0x5b1a90 | 8,735 (35.4%) | 9,781 (37.4%) |
| `cpu_tb_exec` self | 1,737 (7.0%) | 1,945 (7.4%) |
| guest JIT code (file `unknown`) | 7,090 (28.7%) | 6,843 (26.2%) |
| TB lookup (`x86_get_tb_cpu_state`, `curr_cflags`, `helper_lookup_tb_ptr`, qht) | 7.8% | 7.1% |
| #424's code-write invalidation + re-arm | 0.74% | 0.59% |
| host runtime (emutls, PLT, outline atomics) | 1.08% | 1.08% |
| `tb_add_jump`, `helper_pause`, `helper_hlt`, `cpu_handle_exception`, `io_readx/writex`, `bql_lock` self | 0 / ~0 | 0 / ~0 |

Crimson on the Nova (buildflags427 `a.data`, same method): `cpu_exec_loop`
self 11.7%. **AUF's 51-54% is its own.**

What the pile is. `cpu_exec_loop` -> `cpu_handle_interrupt` (cpu-exec.c:1575)
clears `icount_decr.u16.high` with `qatomic_set_mb` and then tests
`interrupt_request` with a load-acquire. On arm64 that is `stlrh; dmb ish;
ldar`. The samples land on the `ldar` and the `cbnz` after it, which is
where a `dmb ish` stall gets billed. The loop runs this once per TB that
returns to it. So in AUF the guest's TBs return to the loop instead of running
chained, and every return pays a full barrier. The barrier also drains the
store buffer, so part of that 37% is the cost of the guest's own stores,
surfacing at the barrier rather than being spread over the JIT code. That is
a bound, not a value: it is the most removing the barrier could give.

Why the TBs return. `tb_add_jump` has zero samples in 14,152 loop samples,
so the loop is not patching jumps. Every return therefore arrives with
`last_tb == NULL`. In this code that happens three ways:

1. an indirect jump whose `helper_lookup_tb_ptr` probe misses and exits the
   TB with 0;
2. `TB_EXIT_REQUESTED`: something set `icount_decr.u16.high` (a kick or
   `cpu_exit`);
3. the target TB spans two guest pages (`tb_page_addr1(tb) != -1` clears
   `last_tb`, cpu-exec.c:1770-1772), so nothing ever chains into it. A title's
   hot loop straddling a 4 KB page would return on every iteration. That
   would be specific to one title, which fits Crimson reading 11.7%.

The profile rules out PAUSE spins, HLT, exceptions, MMIO exits and the BQL.
It cannot tell 1-3 apart. **The instrument that can** is one counter per
return reason in `cpu_exec_loop` (tb_exit value, `last_tb` NULL by cause,
page-spanning target, `interrupt_request` non-zero), plus the loop's iteration
count and the guest PCs of the top returning TBs, printed on `[tlb68]`'s
2-second cadence. `[tlb68]` has no tick count, and `[tier1] threshold=`
(printed every 5,000,000 loop iterations) goes to stdout, not logcat, so no
existing line gives the iteration rate.

**Priced against the frame** (p2; frame 62.0 ms = 1000/16.12, vCPU CPU per
frame 54.0 ms = 87.0% of that, from `[tlb68]` in the same window; each figure
is the category's share of vCPU samples times 54.0 ms, so it bounds that
category's vCPU CPU per frame from above):

| consumer | share of vCPU | ms per frame (bound) | lever (owner) |
|---|---|---|---|
| exec-loop returns: loop self + `cpu_tb_exec` + lookup | 68.6% | 37.0 | #425 block chaining / jump cache (lane.jcache425, PR #443) |
| of which the per-return barrier | 37.4% | 20.2 | #425, same site (cpu-exec.c) |
| guest JIT code | 26.2% | 14.1 | none: this is the guest's own work |
| #424 invalidation + re-arm | 0.6% | 0.3 | #424 (PR #434, merged): not a case |
| host runtime helpers | 1.1% | 0.6 | #427 (PR #435): below any fps effect |
| vCPU placement/priority | vCPU 87% busy, not saturated | -- | #428 (PR #437, refuted): not a case |

What this means for fps, stated as a condition. If the loop time is overhead
on real guest work, cutting it takes the guest's per-frame vCPU time from
~54 ms toward ~17-25 ms (JIT plus what dispatch must still cost). That is
under 3 VBLANKs, and could be under 2 (30 fps) if the GPU's 28 ms and the
renderer allow. If the returning TBs are the guest polling (a wait written as
a loop that does not chain), the same cut only makes the wait cheaper, and fps
does not move. The per-reason counter separates those cases: a poll returns
from a handful of guest PCs, while real work returns from many.

Handed to lane.jcache425 on #425 (deliver.sh), and posted on #412.

## Do not repeat

- The brief's premise that "the vCPU is saturated in both arms" came from the
  pre-hunk runs. Read `[tlb68]` `cpu=/dt=` per arm: B is 84%.
- Do not read fps from `Vpf` alone. fps = VBLANK rate / Vpf, and the rate is
  not a constant: B's is 4-9% low.
- The dispatcher cannot take a simpleperf profile. Ask the host.
- Do not take `report-sample --show-callchain` counts as the denominator. It
  drops the samples whose unwind fails, mostly JIT: 3,511 of 26,139 on p2,
  which reads the exec loop as 62.5% instead of 54.1%.
- A held session has to take the hold while a request runs: the dispatcher
  claims the next request within seconds of a finish, and a 60 s poll never
  sees the Nova idle. The running request's `.owner` stays up through
  host-side scoring after the device is free.
