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

## Why attempt 1 did not finish

Attempt 1 ended with the perflog soak `1790450181-doa413-1721403` still queued, about 12
requests deep. That was a wait on a device request, not on its own task. Attempt 2 reads that
soak (section 3) and closes the PR.

## 2. Next measurement (as queued in attempt 1; read in section 3)

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

## 3. The perflog soak (`1790450181-doa413-1721403`, Nova ee317437, ref dc38b745b8, apk 853368f2e827)

420 s of the same route, PDT 12:51-12:58. `status` is fine: 7673 logcat lines, 165 `hakuX-phase`
lines, 546 `hakuX-stall`, no crash, adb_failures=0. The tables below come from
`tools/phase_table.py` and `tools/work_table.py` run over its `logcat.txt`. Every phase figure is
ms per guest frame, smoothed over the 60-flip window.

### (a) The fight: the renderer thread spends most of its time in `surface_update`

| window (PDT) | gfps | Tot | **Surf** | Draw (Pipe) | Fin (Sub / Fen) | Idle | GPU | draws/frame (BE) | Finish sd / 60 fl |
|---|---|---|---|---|---|---|---|---|---|
| menus 12:51:36-12:52:21 | 59 | 16.2 | 0.1 | 0.1 | 0.2 | 15.8 | 0.2 | 3 | 0 |
| light play 12:57:13-12:57:24 | 59 | 15.5 | **0.3-0.6** | 1.6 | 0.2 | 13 | 1.1 | 244 | 0 |
| fight 1, 12:53:25-12:53:33 | 41-50 | 14-22 | 3-8 | 3-7 | 1.6-5.4 | 1-7 | 4-11 | 240-390 | 0 |
| **fight 2, 12:54:01-12:56:04** | **14-15** | 55-67 | **33-52** | 8-10 (3) | 2-19 (0.4-15 / 1-11) | 0.1-1.3 | 31-44 | 564-766 | **0** |
| fight 3, 12:58:00-12:58:30 | 15-16 | 55-59 | 36-46 | 8-14 (3-9) | 4-10 (3-4 / 1-7) | 0.0-1.1 | 27-32 | 630-700 | **52-58** |

The 15 fps fight repeats the original run's number (16 fps). The phase line splits it:

- **The renderer is never idle** (Idle 0.0-1.3 ms). This matches the original run's `Ri`.
- **`Surf` is 60-80% of the frame**: 33-52 ms of 55-67. `Surf` is the exclusive timer around
  `pgraph_vk_surface_update` (vk/surface.c:4043-4143), which the pusher calls once per draw.
  Per call that is about 64 µs in fight 2 (45 ms / ~700 draws), against about 2.5 µs in light
  play (0.6 ms / 244). **The per-call cost rose 25-fold.** The draw count only tripled.
- **Not blinx372c's eviction.** Fight 2 has **zero** `Finish sd` and zero eviction downloads
  (`sd[ev0 dl0]`, `evict[dl:0]`). Fight 3 has about one `sd` finish and two eviction downloads
  per frame, and its `Surf` is the same. So the eviction adds nothing measurable to `Surf`.
- **Not a Finish wait.** `Sub` is 0.4-15 ms and `Fen` 1-11 ms, and together they are under
  a fifth of `Surf`.
- **Not a pipeline or shader storm.** `Pipe` is about 3 ms, and `Shd` is 0 outside two
  one-off compiles (below).
- **The GPU is not the bound, but it is loaded.** GPU is 31-44 ms per frame against 55-67 of
  Tot. With `Surf` at zero the frame would be about 20 ms of CPU, so the GPU's 33 ms would
  bound it at about 30 fps. **Removing `Surf` is worth 15 to about 30 fps, not to 60.**
- The pusher's method time (`hakuX-cpu` `Mth`) tracks Tot (57-65 ms). The pusher is the
  renderer thread, so this is the same time seen from its side. The vCPU's 21-33% in section 1
  is the guest waiting on it.

**Which part of `surface_update` it is, the soak cannot say.** The sub-split (populate, dirty,
enrp, lookup hit/evict/nosurf, create, put, bind, upload, download, expire) is accumulated in
`g_nv2a_stats.surf` and logged once per 60 frames under tag **`xemu-surf`**
(profile.c:645). The dispatcher's `LOGCAT_SPEC` (docs/testing/dispatcher.sh:1379) does not
carry that tag, so the soak dropped it. The columns that did reach the log correlate with
`Surf` but do not separate it:

| window | Surf | draws/frame | surface render-pass breaks / 60 fl (`rpbrk srf`) | `xemu-sfp` noRp / shC |
|---|---|---|---|---|
| light play 12:57:21 | 0.5 | 251 | 40 | 41 / 4879 |
| fight 1 12:53:29 | 6.8 | 387 | 113 | 114 / 5281 |
| fight 2 12:55:06 | 44.0 | 737 | 413 | 472 / 6199 |

Fight 2 breaks the render pass for a surface reason about 7 times per frame, which fits the
original run's 6 shape changes per frame (color 0x02CB0000 and 0x02E18000 alternating with
zeta 0x02F80000 in `[surf92]`). The candidate is the `upload && framebuffer_dirty` branch
(`unbind_surface` on both, then `update_surface_part`), plus `expire_old_surfaces` and
`prune_invalid_surfaces`, which run on *every* call (surface.c:4133-4139). That is a
candidate, not a site: the unsplit timer cannot price it.

### (b) The stall: second occurrence, the same shape, shorter

The 76 s span did not recur at that length. Two shorter spans of the same shape did, and a
third gap has a different cause:

| gap (PDT) | length | vCPU `cpu` ms / 2000 | VBLANK | FIFO kicks | renderer |
|---|---|---|---|---|---|
| 12:52:43-12:52:57 (menu -> first fight) | 14 s (Gmax 12.4 s) | **1833-1974 (92-99%)** | **59.94 Hz** | no `fifoskew` line from 12:52:43.5 to 12:52:56.4 | Idle |
| 12:57:32-12:57:45 (fight -> next stage) | 13 s (Gmax 10.5 s) | **1667-1808 (83-90%)** | **59.94 Hz** | none until 12:57:41 | Idle |
| 12:53:16-12:53:24 | 7 s (Gmax 7.2 s) | 1780 | 59.94 Hz | 57 | **`Shd` 747 ms, `Pipe` 753 ms in one window: a one-off shader compile** |

The two long ones match the original run's 76 s gap on every counter: the guest runs flat
out, the timer is on time, and the pusher gets nothing. Both fall on scene changes (menu to
fight, fight to the next stage). The original's gap also followed a ring-out, which is a
scene change. So **(b) is a guest-side CPU-bound span at scene loads, repeated with the same
counters.** It is 13-14 s here and was 76 s in the original. Whether that difference comes
from what gets loaded (the ring-out stage) or from the disc path is not something these
counters can say. The only renderer-side event in any gap is the single 747 ms compile, and a
compile cannot hold the renderer idle.

The desktop xemu check is still not done, for section 2's reason (the disc is not on the host).

### What would unblock a priced hunk

- **(a)** The same soak with `xemu-surf:I` in the logcat spec. That is a one-token edit to
  `docs/testing/dispatcher.sh:1379`, a harness file outside this lane's grant. It must also
  reach the running dispatcher (the dispatcher tree lags master). With the sub-split, the
  hunk sits in `vk/surface.c`, which PR #396 (lane.blinx372d) holds. So there is **no priced
  hunk and no arm now**. The code site to grant once #396 folds is
  `hw/xbox/nv2a/pgraph/vk/surface.c:pgraph_vk_surface_update` (4040-4144).
- **(b)** An IDE/ATAPI command and completion counter (hw/ide/core.c, needs a grant), plus the
  guest PC sampled during the span. Those separate a guest waiting on the disc from TCG-slow
  decompression.

## Do not repeat

- Do not chase blinx372c's `update_surface_part` eviction for DOA's 15 fps. Fight 2 has zero
  `sd` finishes and still spends 45 ms in `Surf`.
- Do not expect 60 fps from a `Surf` fix alone: the GPU's 31-44 ms per frame bounds it near 30.
- Do not queue another soak for (a) before `xemu-surf` is in the dispatcher's spec. It will
  measure the same unsplit timer.

- Do not read (b) as a renderer problem from the pictures. The renderer is idle through it.
- Do not read the fight's 21-25 Hz VBLANK as a pacing-mode bug. The timer lands 24-30 ms late
  whenever the renderer is busy, and on time when it is idle. It is a symptom of the same
  contention, and the deferral cap is period/2, so deferral alone cannot produce it.
- Do not price the fight from `[tlb68]`/pages. Slow stores are about 4k/s, and other-thread
  dirty resets cost about 60 ms per 2 s (3%).
