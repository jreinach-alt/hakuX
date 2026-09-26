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
  That is the single-instruction retranslation QEMU does after a store into the page of the
  running TB.
- Audio continues through the stall with no starvation, so the APU is not what stops.

## 2. Next measurement (queued)

A perflog Nova soak of the same route on master dc38b745b8, to get (a)'s per-frame phase split
(`Sub`, `Fen`, GPU, `Finish sd`/stall sites) and a second occurrence of (b).

## Do not repeat

- Do not read (b) as a renderer problem from the pictures. The renderer is idle through it.
