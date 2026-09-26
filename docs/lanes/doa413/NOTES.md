# lane.doa413 -- #413: DOA2 Ultimate, 16 fps fights and a 0-2 fps span after a ring-out (Nova)

Base master dc38b745b8. Title `54430006-Dead_or_Alive_1_Ultimate.xiso.iso` (boots DOA2 Ultimate).
Source run: `0-0-y-1790433159-titleplay-p1-doa1u` (ref a5b5b628f2, apk 25abcaccbf45, Nova ee317437,
no perflog). Its route is saved here as `survey.route` (verbatim from its request.json).

## 1. The two symptoms, split on counters from the run on disk

The run has no `hakuX-phase`/`hakuX-stall` lines (no perflog). It does have, per 2 s: `[tlb68]`
(vCPU thread CPU ms `cpu=`, TLB/code-arming counters), `vbl`/`vblphase` (the emulated VBLANK
rate and how late each timer assertion landed), `fifoskew` (pusher kicks), and per 60 flips
`gfps` (with `Ri`, renderer idle ms per frame) and `hakuX-pace`.

| window (PDT) | vCPU `cpu` ms / 2000 | VBLANK rate | vblphase late mean | FIFO kicks / 2 s | `Ri` / `G` (ms) | `rdo` (other-thread dirty resets) / 2 s |
|---|---|---|---|---|---|---|
| fight 08:09:20-08:09:58 | **410-670 (21-33%)** | 17.7-30.5 Hz | 24-30 ms | 1120-1470 | **0.2-3.2 / 56-76** | 2800-3600 |
| stall 08:10:13-08:11:24 (excluding the short bursts) | **1780-1810 (90%)** | **59.94 Hz** | 0.1-0.2 ms | **0-40** | 0.0 / 1863 | 0-60 |

**(a) The fight is renderer-bound.** The renderer is idle for 0.2-3 ms of a 56-76 ms guest frame,
so it is busy 95-100% of the time. The guest CPU runs for only a quarter of the wall clock, so it
waits on the GPU side. This is the opposite of fps382's shape, where the renderer was 95% idle and
the vCPU was 97% busy. Guest slow stores are 15-16k per 60 flips (about 4k/s), 600 times fewer
than fps382's 2.5M/s. So this is not the watched-surface store trap.
The VBLANK timer (main loop, BQL) lands 24-30 ms late on average while the renderer is busy, and
0.1 ms late in the stall where it is idle. So a thread holding BQL or a lock the timer needs is
busy exactly when the renderer is. That is a second clue, not yet a site.
The run cannot say *what* the renderer spends its time on (GPU, recording, `Sub` waits, surface
downloads). That needs the perflog soak in section 2.

**(b) The stall is guest-side: the guest runs flat out and hands the GPU nothing.** Across the
76 s gap the vCPU thread burns 90% of the wall clock, the VBLANK arrives on time at 59.94 Hz, the
pusher sees 0-40 kicks per 2 s (against about 1200 in the fight), other-thread dirty resets drop
to 0, and `Ri`/`vblphase` show an idle renderer. So:

- It is **not a pipeline or shader-compile storm, and not a synchronous download loop**. Both
  of those run on the renderer thread and need pushbuffer work to trigger them. There is none:
  kicks are ~0 and the renderer is idle.
- It is **not an emulator lock or wait holding the guest**. The guest's own CPU time is at its
  maximum, and the main-loop timer is on time.
- What the guest does with its 90% is not resolved by these counters. The two readings are
  (i) a guest busy-wait on something the emulator delivers slowly (disc, timer, an APU or
  PCI status), or (ii) guest work made slow by TCG. The code-side counters are *not* elevated
  per CPU-second: code re-arms (`rd`=`rdc`=`jci`) run at 490 per CPU-second in the stall
  against 720 in the fight. But the pages line over the second gap (08:11:25-08:12:09) has
  45,093 blocks discarded by the store invalidator, against about 1,700 per 60 flips in the
  fight. tier1 also promotes TBs whose cflags carry an instruction count of 1 (`0xff031001`).
  From the code these are **`cpu_io_recompile` TBs**
  (`CF_MEMI_ONLY|CF_NOIRQ|1`, translate-all.c:1109), not self-modifying-code ones
  (`CF_NOIRQ|1`, tb-maint.c:1616). In this QEMU any MMIO access that is not the last instruction
  of its TB (`can_do_io` false, cputlb.c:1625) exits the loop and re-runs that one instruction.
  So the guest is touching device registers from its hot code during the stall. That fits
  reading (i), a device poll. It does not prove it: the promote lines are sampled, one per
  10,000.
- The store invalidator does not separate the two windows either. Per CPU-second it is about
  1,400 in the fight and about 1,100 in the second gap.
- Disc reads are inline (`XEMU_ANDROID_INLINE_AIO=1`, block/file-posix.c:2536). That makes each
  read synchronous in the thread that issues it, which for IDE is the main loop with BQL held.
  A long read would therefore make the VBLANK timer late. The stall's VBLANK is on time
  (0.1 ms mean lateness), so **the main loop is not blocked on the disc during the stall**. A
  guest waiting on *completions that come slowly but without blocking*, or on its own schedule,
  is not excluded. No counter in the tree reports IDE/ATAPI commands. `grep android_log_print`
  over hw/ide, hw/block and block finds none.
- Audio continues through the stall with no starvation, so the APU is not what stops.

### Surface traffic (`[surf92]`, same run)

| window | surface_update/s | shape-dirty/s | flips/s | shape-dirty per flip |
|---|---|---|---|---|
| menus 08:07:00-08:08:00 | 20,243 | 91.9 | 22.3 | 4.1 |
| fight 08:09:00-08:09:58 | 20,746 | 95.8 | 16.0 | **6.0** |
| stall 08:10:13-08:11:24 | 1,925 | 3.8 | ~0 | -- |
| after 08:12:10-08:12:40 | 16,619 | 70.6 | 11.8 | 6.0 |

The fight re-shapes a surface binding about 6 times per frame (color 0x02CB0000 and zeta
0x02F80000 alternate on every line). That is the shape in which blinx372c found the
incompatible-binding eviction (`update_surface_part`, two synchronous finishes per frame). It is
only a candidate here. Whether each shape change costs a `Finish sd` is what the perflog soak's
`hakuX-stall` line says.

## 2. Next measurement (queued, not yet run)

`1790450181-doa413-1721403`: a perflog Nova soak of the same route (`survey.route`, 420 s) on
master dc38b745b8. For (a) it gives the per-frame phase split: `Sub` against `Fen` (the
pfifo-thread finish wait is in `Sub`, see blinx372c), GPU, and the `Finish sd`/`evict` stall
sites. For (b) it gives a second occurrence, if the ring-out repeats. When it queued, it had
about 12 requests ahead of it on two devices.

What each reading would mean:

- (a) `Sub` near `Tot - GPU` with `Finish sd` about 2 per shape change: blinx372c's eviction,
  with the hunk in `vk/surface.c:update_surface_part`. That file is held by PR #396, so it is
  not requestable now.
- (a) GPU near `Tot`: the Adreno is the bound, and the next step is per-pass GPU time, not a
  sync site.
- (a) `Idle` large with `Ri` small is impossible. It would indict the instrument.
- (b) recurs with kicks ~0 and the vCPU at 90% again: guest-side, confirmed on a second
  occurrence. The next instrument is an IDE/ATAPI command and completion-latency counter
  (hw/ide/core.c or atapi.c; the file needs a grant) plus the MMIO address the guest polls.
- (b) does not recur on the same route: it depends on where the ring-out lands, which is
  itself a finding for the route, not for the emulator.

**Desktop xemu check (brief step 3): not done.** The disc is not on the host. The title
pipeline deletes the local XISO once the handheld copy is verified, and `titles/` holds only
the inventory JSON. `request.sh --device desktop` would need the ISO staged on the host first.

## Do not repeat

- Do not read (b) as a renderer problem from the pictures. The renderer is idle through it.
- Do not read the fight's 21-25 Hz VBLANK as a pacing-mode bug. The timer lands 24-30 ms late
  whenever the renderer is busy, and on time when it is idle. It is a symptom of the same
  contention, and the deferral cap is period/2, so deferral alone cannot produce it.
- Do not price the fight from `[tlb68]`/pages. Slow stores are about 4k/s, and other-thread
  dirty resets cost about 60 ms per 2 s (3%).
