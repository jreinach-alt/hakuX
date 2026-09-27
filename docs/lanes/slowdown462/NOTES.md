# lane.slowdown462 -- per-title frame-time attribution (#462)

Five slow titles, one protocol, one device (Nova ee317437, MAX). Measure and
attribute only; fixes go to the per-title lanes.

> **Correction, 2026-09-27 13:18 PDT (lane.flip474, #474 section 3):** every
> GPU, `Rnd`/`R` and `Xfr`/`X` figure read on the Nova from `xemu-gpu` or
> `hakuX-phase` is 0.636 of the true value. The Nova's GPU timestamps tick at
> 19.2 MHz, while `limits.timestampPeriod` reports 30.2 MHz, and hakuX uses that
> as `gpu_ts_period_ns`. This file's Nova GPU rows and the bounds read from them
> are restated below at x1.573, each beside the old value. GTA's rows are the
> Thor's, which has not been checked, and are left as read.

## The build and the instruments (same for every title)

- **Soaks:** ref `e5db66fa37` (master when this lane started), `--perflog`,
  survey route, 420 s, Nova, release priority (`HAKUX_RELEASE_PRIO=1`), MAX
  regimen (soak_title.sh's default; `perf_regimen.json` in each result).
- **Profiles:** `capture_profile.sh` (this dir), a held Nova session per title,
  APK `builds/a593d8eb85.apk` (not perflog). a593d8eb85 and e5db66fa37 build
  the same emulator: `git diff --stat a593d8eb85 e5db66fa37 -- ':!docs'` is
  empty. Asked of the host in `dispatch/board-requests/slowdown462.md`.
- **Window:** from the route's `mark play` + 30 s to 10 s before `soak end`.
  The survey route writes `mark play`, not `mark gameplay`; that the window is
  gameplay is checked from the route's `play` shots.
- **Readers:** `titleread.py <result-id>` runs, over that one window, the
  readers earlier lanes validated: aufire412's `splitread.py` (phase, cpu,
  work, stall medians), aufire412b's `pace.py` and `vbl.py` (VBLANKs per flip,
  VBLANK rate, clamps), tbchurn424's `churn.py` (#424 churn). Checked on
  `1790470425-aufire412b-4161655` (AUF, 53a9b91df3 perflog, MAX): it
  reproduces aufire412b's mission numbers (15.0 fps, Vpf 3.82, vCPU 86%).
- `waitres.py`: bounded wait on result ids, printing queue position and holds.

## What is already known, and what it does not answer

| title | prior evidence | open |
|---|---|---|
| DOA1U | doa413 (dc38b745b8, default regimen): fight 14-15 fps, `Surf` 33-52 of 55-67 ms, GPU 31-44 ms. doa413b's lazy-surface cut refuted (14.9 off vs 13.6 on) and ships default-off (PR #440, must-not-move PASS). | which part of `surface_update`: `xemu-surf` is not in the dispatcher's LOGCAT_SPEC |
| AUF | aufire412b: vCPU 54% in `cpu_exec_loop` (37% at one barrier), 26% guest JIT; renderer `Surf` 26.5, Draw 16.7, GPU 29.3 ms (1790470425, MAX) | the return causes (retreason425 in queue) |
| Blinx | blinx372d/c: attract demo, Sub 25-35 ms of 57-71 (synchronous zeta downloads); gameplay not read | gameplay split |
| Blinx 2 | nothing | everything |
| Forza | forza414 (Thor): race `Sub` 26-37 of 43-63 ms, ~5.5 uncoalesced `sd_complete_def` finishes/frame | Nova numbers; which caller |

## Windows: pick them from the frames, not from `mark play`

The pilot (DOA1U) showed that the survey route's `mark play` can fall AFTER the
gameplay: DOA fights during the 14 menu rounds (from about the 8th `press
START`, ~87-91 s after `mark booted`, in all three DOA runs) and by `mark play`
is on the replay, CONTINUE and title screens. `timeline.py <result-id>` prints
every 60-frame phase line with the route events; each title's window is picked
from it and checked against the route's shots. AUF's mission does start after
`mark play` (aufire412b's reading holds).

## DOA1U (54430006, #413)

**Soak** `1-1790481863-slowdown462-3154279` (e5db66fa37 perflog, apk
c4b30cf46bd6, Nova, MAX restored), fight window 151-288 s after logcat line 1
(PDT 21:20:31-21:22:47; shots 212038-212205 show stage 1 with the route's
START toggling the pause menu over it; the fight costs the same paused or not).

| | ms/frame | share of 75.8 ms |
|---|---|---|
| fps (gfps cadence) | 13.19 | |
| PFIFO Tot (renderer, never idle: Idle 0.1) | 70.8 | 93% |
| `Surf` (`pgraph_vk_surface_update`, exclusive timer) | 59.8 | 79% |
| Draw (Pipe 3.1, Sh 2.1, Syn 2.0) | 9.0 | 12% |
| Fin (Sub 0.1 / Fen 1.5) | 1.6 | 2% |
| GPU (Rnd 19.4, Xfr 19.3; 9 render passes); **x1.573: 60.2 (30.5, 30.4)** | 38.3 -> **60.2** | 51% -> **79%**, overlapped |
| vCPU busy (`[tlb68]`) | 25% | not the bound |

Render-pass breaks 541/60 flips, 420 of them for a surface reason (7 per
frame); draws 729/frame. VBLANK 17.1 Hz with 1786 clamps: the timer is
starved while the PFIFO is busy (doa413 saw 21-25 Hz). #424 churn 1.8%.

**Profile** `perf/2026-09-26-slowdown462/doa2/doa2.data` (apk a593d8eb85, not
perflog, fight 21:57:58-21:58:29 PDT, 11-19 fps, shot 215809 = fight under the
pause menu). Session #1 (`doa/`) missed the fight and is not used.

- **The fight is not CPU-bound on any thread.** 30 s of cpu-clock: vCPU (tid
  12202) 8,048 ms on-CPU (27%), PFIFO (tid 12213) 6,875 ms (23%). The perflog
  line says the PFIFO thread is never idle and 60 ms of its 71 are in
  `surface_update`. So most of `Surf` is **blocked time** inside
  `surface_update`, not work. What it blocks on needs an off-CPU capture
  (board request Ask 2; `OFFCPU=1`).
- PFIFO on-CPU, top self: `memcpy_opt` 25.5% (36% of it from
  `pgraph_vk_finish` at FLIP_STALL, 20% `pgraph_vk_snapshot_state` per draw
  pass, 12% `complete_staged_downloads` under `surface_update`, 10%
  `apply_uniform_updates`), `tlb_reset_dirty` 8.3% (95% from
  `sync_vertex_ram_buffer` -> `tlb_reset_dirty_range_all`),
  `rewrite_indices` 4.9%. Under `pgraph_vk_surface_update` inclusive: 4.7% of
  on-CPU (~0.3 ms of CPU per 1000/15 ms frame against 60 ms of `Surf` wall).
- vCPU on-CPU: 40% guest JIT, `cpu_exec_loop` 12%, TB lookup (`tb_lookup`,
  `helper_lookup_tb_ptr`, qht) ~22%.
- doa413b's lazy-surface cut (PR #440) was refuted on this fight (14.9 fps
  off vs 13.6 on) and ships default-off. That fits: it cut CPU work inside
  `surface_update`, and the frame is not CPU work (below).

**Off-CPU profile** `perf/2026-09-26-slowdown462/doa3/doa3.data` (a593d8eb85,
`--trace-offcpu`, fight 22:36:13-22:36:48 PDT, 13-14 fps with two ~25 fps
windows, 30 s). On/off time from the context-switch records (exact);
attribution from the switch-out samples (`offcpu.py`):

| thread | on-CPU | off-CPU | where the off-CPU time goes |
|---|---|---|---|
| vCPU (tid 18019) | 7,753 ms (26%) | 22,204 ms | **14,556 ms `qemu_mutex_lock` in `pgraph_read`** (`pg->lock`, pgraph.c:898); `user_read` 650, BQL in `cpu_exec_loop` 486; 27% unsampled |
| PFIFO (tid 18033) | 6,315 ms (21%) | 23,653 ms | sampled 33%: **`wait_timestamp_safe` 5,593 ms** (Turnip/KGSL GPU-timestamp wait), `pfifo_thread` mutex 722, idle cond-wait 575 |

The GPU waits' emulator caller (the unwinder stops in the vendor driver, so
each wait is matched to the thread's last on-CPU sample before it, median 0.9
ms earlier): **79% `pgraph_vk_finish` <- `pgraph_vk_flip_stall` <-
FLIP_STALL**, 2.7% uniform updates, 0.9% `WaitForFences` in
`download_surface_complete_deferred`. 272 sampled waits, median 12.3 ms, p90
53 ms.

The mechanism, from the code: FLIP_STALL runs inside the pusher's batch hold
of `pgraph.lock` (pfifo.c:1427, `XEMU_OPT_PFIFO_LOCK_BATCH`); its handler calls
`pgraph_vk_flip_stall` -> `pgraph_vk_finish(FLIP_STALL)` (renderer.c:2311),
and nothing in `vk/` drops `pgraph.lock` around the wait. `pgraph_read` takes
the same lock. So at every flip the PFIFO waits for the GPU with the lock held,
and the guest's PGRAPH register reads wait behind it, holding the BQL (the
perflog soak's VBLANK 17 Hz with 1,786 clamps is that BQL hold). CPU record,
GPU execution and the guest are serialised.

The perflog `Surf` 60 ms does not show up as work in the shipping build
(`surface_update` inclusive is 4.7% of the PFIFO's on-CPU time: 263 ms in
30 s, ~0.6 ms per frame); the perflog build's timers put the waits there, not in `Fin`. Price
DOA from the profiles, not from `Surf`.

**DOA1U answer** (frame ~71 ms at ~14 fps, shipping build, fight):

| # | cost | ms/frame | share | evidence | candidate fix | owner |
|---|---|---|---|---|---|---|
| 1 | the flip's GPU wait under `pgraph.lock`; the guest blocks on it in `pgraph_read` | 34 (vCPU blocked 14.6 of 30 s) | 49% | doa3 `offcpu.py` tid 18019/18033; renderer.c:2311, pfifo.c:1427, pgraph.c:898 | drop `pgraph.lock` across the flip-stall wait (or defer the flip's finish so the next frame records while the GPU runs) | new issue (board Ask 3) |
| 2 | GPU transfer work (`Xfr`) | 19.3 of GPU 38.6 | 27% | soak `xemu-gpu` Rnd 19.4 / Xfr 19.3; 7 surface-reason render-pass breaks/frame | stop re-uploading surfaces each switch | #413 (lane.doa413b's successor; needs `xemu-surf` in the spec) |
| 3 | PFIFO CPU | ~15 | 21% | doa2: memcpy 30% (36% of it the flip's display download, 20% state snapshot), `sync_vertex_ram_buffer` TLB reset 9%, index rewrite 7% | per item; none dominant | #413 |

Bounds, not values: with (1) gone and CPU and GPU overlapping, the frame is
at least the GPU's 38.6 ms: **<= 26 fps**. With (2) also gone, at least
max(GPU render 19.4, vCPU ~18, PFIFO ~15) ms: **<= ~51 fps**.

**Restated at x1.573 (13:18 correction):** the GPU is 60.7 ms (Rnd 30.5, Xfr
30.4), so with (1) gone the bound is **<= 16.5 fps**, not 26. lane.flip474's
fitted span, 63.7 ms, gives 15.6. With (2) also gone the bound is max(30.5,
~18, ~15) ms, **<= 33 fps**, not 51. DOA on the Nova is GPU-bound. Row 2's
`Xfr` is 30.4 ms/frame.

## AUF (4541000D, #412)

**Soak** `1-1790483186-slowdown462-3496610` (e5db66fa37 perflog, Nova, MAX),
mission play `mark play`+30 s to 10 s before the end (264-412 s; shots
213606-213910 are first-person mission play, 15 fps):

| | value |
|---|---|
| fps (gfps cadence) / ms per flip | 15.12 / 66.1 |
| VBLANKs per flip (v2/v3/v4+) / VBLANK rate | 3.76 (12/24/63%) / 56.95 Hz, 347 clamps |
| vCPU busy (`[tlb68]` cpu/dt) | 83.8% = 55.4 ms/frame |
| perflog renderer: Tot / Idle / Surf / Draw (Pipe, Tx) | 56.5 / 13.9 / 23.4 / 18.6 (9.9, 6.0) ms |
| GPU | 29.0 ms (Rnd 14.4, Xfr 14.6); **x1.573: 45.6 (22.7, 23.0)** |
| #424 churn | 0.6% of vCPU |

**Profile** `perf/2026-09-26-slowdown462/auf/auf.data` (a593d8eb85, not perflog,
`--trace-offcpu`, 22:20:57 PDT, 13.5 s recorded of the 30 asked; 15 fps, vCPU
`cpu=` 1,800-1,970 per 2,000 ms in the same seconds):

- From the context-switch records (exact, not sampled): **vCPU (tid 15470)
  on-CPU 12,406 of 13,214 ms (94%)**; **PFIFO (tid 15486) on-CPU 3,214 ms
  (24%)**, off 9,991 ms. The vCPU sets the frame.
- vCPU on-CPU, by sample share (the sampler dropped ~25% of the vCPU's
  cpu-clock samples under `--trace-offcpu`, so shares, not ms):
  `cpu_exec_loop` self 61.3%, guest JIT 20.4%, `cpu_tb_exec` 6.2%, TB lookup
  (`x86_get_tb_cpu_state`, `curr_cflags`, `tb_lookup`, `helper_lookup_tb_ptr`,
  qht) 6.5%. Off-CPU 808 ms, mostly `qemu_mutex_lock` from `cpu_exec_loop`
  (BQL, 232 ms sampled), `pgraph_write`/`pgraph_read` (110 ms).
- PFIFO off-CPU, every interval charged to its switch-out sample: 60%
  unsampled; of the rest, `qemu_cond_wait` in `pfifo_thread` (idle, waiting
  for the guest's pushes) 2,617 ms, `pgraph_vk_process_pending` event wait
  888 ms, GPU timestamp wait 290 ms.
- This reproduces aufire412b's profile (p2: exec loop 54%, JIT 26%) at MAX
  and on this build, with the off-CPU half added: the renderer is waiting on
  the guest, not the reverse.

**What the perflog renderer line means here.** The perflog soak says the
renderer is busy 42 ms of every 66 ms frame; the shipping build's PFIFO thread
is on-CPU ~16 ms of it (24%). The phase timers are wall time and include
time the thread is switched out inside a timed section; and the perflog build
reads a clock around every method. Read `Surf`/`Draw` as upper bounds on
cost, never as CPU.

**AUF answer** (frame 66.1 ms at 15.1 fps; vCPU-bound, 94% on-CPU; ms =
share of vCPU on-CPU samples x 62 ms of vCPU time per frame):

| # | cost | ms/frame | share | evidence | candidate fix | owner |
|---|---|---|---|---|---|---|
| 1 | exec-loop returns: `cpu_exec_loop` self + `cpu_tb_exec` | 42 | 63% | auf.data tid 15470: 61.3% + 6.2%; aufire412b p2 54% + 7% | chain the returning TBs (cause per retreason425's split counter; aufdispatch's three designs, PR #469) | #425 lane.retreason425; #412 |
| 2 | guest JIT code | 13 | 19% | 20.4% of vCPU samples | none: the guest's own work | -- |
| 3 | TB lookup + lock waits (BQL, `pgraph_read`/`write`) | 4 + 4 | 12% | lookup 6.5% of samples; off-CPU 808 of 13,214 ms | #425 lookup path; lock waits not a lever at 6% | #425 |

Bound, not a value, and conditional: if cost 1 went to zero and it is
overhead (not a guest poll), the vCPU needs ~20 ms per frame and the frame is
at least the GPU's 29 ms: **<= 34 fps**, and **<= 30 fps** at the title's
VBLANK pacing (2 VBLANKs = 33.4 ms). If the returns are a guest wait loop,
removing them makes the wait cheaper and fps does not move (aufire412b).

**Restated at x1.573 (13:18 correction):** the GPU is 45.6 ms, so the same
condition gives **<= 21.9 fps**, not 34. The 30 fps pacing bound no longer
binds.

## Blinx (4D530013, #372)

**Soak** `1-1790492277-slowdown462-690144` (e5db66fa37 perflog, apk
c4b30cf46bd6, Nova, MAX restored). The level starts ~136 s after line 1
(shot 000642 in the first level, timer 0'01"); the menu rounds' START pauses
it until `mark play` (242 s). Window `mark play`+10 s to 10 s before the end
(252-411 s; shots 000852-001100: level play, 13-30 fps on the overlay):

| | value |
|---|---|
| fps (gfps cadence) / ms per flip | 17.17 / 54.6 (pace.py: 16.93 / 59.1) |
| VBLANKs per flip (v2/v3/v4+) / VBLANK rate | 3.01 (42/32/26%) / 51.2 Hz, 619 clamps |
| vCPU busy (`[tlb68]`) | 78% |
| perflog renderer: Tot / Idle | 42.1 / 2.9 ms |
| Draw (Pipe 17.2: Tx 6.9, Sh 7.9, Lu 1.2) | 28.9 ms |
| Fin (Fen 8.6; 77.5 FLIP_STALL-deferred finishes per 60 flips) | 8.9 ms |
| Surf / Syn | 2.0 / 1.4 ms |
| GPU (GR 20.0) | 23.3 ms; **x1.573: 36.7 (GR 31.5)** |
| draws / render passes / RP breaks | 2,829 / 19 / 1,205 per 60 flips (20 per frame) |
| #424 churn | 0.9% of vCPU |

Not blinx372d's attract-demo shape: `Sub` is 0.1 and no staged downloads
(`sd_*` all 0) in level play. The perflog timers are wall time; the split
between the vCPU (78% busy) and the renderer's `Pipe` waits the profile.

**Profile** `perf/2026-09-26-slowdown462/blinx/blinx.data` (a593d8eb85, not
perflog, **on-CPU only**: the `--trace-offcpu` attempt failed at once with
"Event type 'cpu-clock' is not supported", and the script's fallback recorded
without it). 00:23:11-00:23:42 PDT, `mark play`+15 s, level play
(`profwin.py`: 540 flips in 32.3 s = 16.7 fps, 59.9 ms/flip; gfps 13-18,
then 23 and 29 in the last 5 s). Per-thread on-CPU from cpu-clock samples (1
sample = 1 ms; ~501 frames in the 30 s record):

| thread | on-CPU (of 30 s) | ms/frame | top self |
|---|---|---|---|
| vCPU (tid 17669) | 22,046 ms (73%) | 44.0 | `cpu_exec_loop` 44.6%, guest JIT 30.8%, `cpu_tb_exec` 4.8%, TB lookup (`tb_lookup`, `helper_lookup_tb_ptr`, `x86_get_tb_cpu_state`, `curr_cflags`, qht) 12.2% |
| PFIFO (tid 17677) | 13,080 ms (44%) | 26.1 | `memcpy_opt` 30.5% (47% of it `pgraph_vk_snapshot_state` per draw pass, 27% `apply_uniform_updates`, 11% `pgraph_vk_finish` <- process_pending_reports), `apply_uniform_updates` 8.5%, `fast_hash` 4.7% (95% the uniform hash) |
| DSP (tid 17675) | 3,028 ms | | kernel 60% |

The vCPU is off-CPU ~8.0 s of 30 (15.9 ms/frame). The soak's FLIP_STALL
deferred finishes (77.5 per 60 flips, `Fen` 8.6 ms) are DOA's mechanism
(#474), but without the switch records that is a candidate, not a finding.

**Blinx answer** (frame 59.9 ms at 16.7 fps, shipping build, level play):

| # | cost | ms/frame | share | evidence | candidate fix | owner |
|---|---|---|---|---|---|---|
| 1 | exec-loop returns (`cpu_exec_loop` self + `cpu_tb_exec`) | 21.7 | 36% | blinx.data tid 17669: 44.6% + 4.8% of 22,046 ms | chain the returning TBs (retreason425's split, aufdispatch's designs PR #469); same shape as AUF | #425 (retreason425) |
| 2 | vCPU blocked | 15.9 | 27% | 30 s - 22.0 s on-CPU; cause not captured (no switch records) | if it is `pgraph.lock` at the flip (DOA's `pgraph_read` wait; Blinx 2's vCPU blocks there too), #474's fix | #474 (flip474), to be confirmed |
| 3 | TB lookup | 5.4 | 9% | 12.2% of vCPU samples | #425 jump cache (default off) | #425 |

The guest's own JIT code is 13.6 ms/frame (23%) and not a lever. The PFIFO
(26.1 ms on-CPU) is not the bound; its per-draw snapshot and uniform upload
are ~12 ms of it.

Bounds, not values: with (1) gone and the blocked time unchanged, the vCPU
still needs 22.3 on + 15.9 blocked = 38.2 ms per frame: **<= 26 fps**. With
(1) and (2) both gone, the frame is at least max(vCPU 22.3, GPU 23.3, PFIFO
on-CPU 26.1) ms: **<= 38 fps**, and the title's 2-VBLANK pacing (33.4 ms) caps
it at **<= 30 fps**.

**Restated at x1.573 (13:18 correction):** the GPU is 36.7 ms. The first bound
(<= 26 fps, the vCPU's) stands. With (1) and (2) both gone, the bound is
max(22.3, 36.7, 26.1) ms: **<= 27 fps**, not 38. The GPU, not the pacing, is
then the limit.

## Blinx 2 (4D530065, no issue)

**Soak** `1-1790492277-slowdown462-690171` (e5db66fa37 perflog, apk
c4b30cf46bd6, Nova, MAX restored). Window `mark play`+10 s to 10 s before the
end (246-415 s); shots 001525-001824 are the first mission ("Locate the 3
balloons"), the route walking into a wall:

| | value |
|---|---|
| fps (gfps cadence) / ms per flip | 28.86 / 33.8 (pace.py 28.82 / 34.7) |
| VBLANKs per flip (v2/v3) / VBLANK rate | 2.07 (93/7%) / 59.6 Hz, 46 clamps |
| vCPU busy (`[tlb68]`) | 92% |
| perflog renderer: Tot / Idle | 29.5 / 2.8 ms |
| Fin (Sub 13.6, Fen 1.6); `sd_dl` 60 and `sd_cDef` 31 per 60 flips | 15.4 ms |
| Draw (Pipe 4.9, Sh 3.7) / Surf / Syn | 11.1 / 0.9 / 1.9 ms |
| GPU (GR 16.7) | 17.0 ms; **x1.573: 26.7 (GR 26.3)**, under the 33.4 ms cap |
| draws / RP breaks | 1,230 / 926 per 60 flips |
| #424 churn | 0.7% of vCPU |

**On this build and device Blinx 2 is at its 30 fps pacing cap** in the first
mission (93% of flips at 2 VBLANKs). #462's 21.7 fps is the Thor's, from
another run; fps is compared on one handheld, so this lane's figure is 28.8.
The vCPU is at 92%, so a heavier scene would drop below the cap. The one
synchronous download per frame (`sd_dl` 60/60, `Sub` 13.6 ms) is
blinx372d's zeta-download shape, the same as Blinx 1's attract demo.

**Profile** `perf/2026-09-26-slowdown462/blinx2/blinx2.data` (a593d8eb85,
`--trace-offcpu`, 00:35:31-00:36:06 PDT, `mark play`+20 s, the same mission;
`profwin.py`: 1,020 flips in 34.2 s = 29.85 fps, 33.5 ms/flip; ~896 frames
in the 30 s record). From the switch records (`offcpu.py`):

| thread | on-CPU | off-CPU | where the off-CPU time goes |
|---|---|---|---|
| vCPU (tid 22890) | 26,451 ms (88%) = 29.5 ms/frame | 3,562 ms | `pgraph_read` `pg->lock` 1,293; BQL in `cpu_exec_loop` 1,054; `pgraph_write` 143; unsampled 825 |
| PFIFO (tid 22900) | 13,553 ms (45%) = 15.1 ms/frame | 16,459 ms | **`pgraph_vk_finish` <- `download_surface` 7,559** and <- `download_surface_complete_deferred` 3,306 (together 12.1 ms/frame); idle cond-wait 4,819 |

vCPU on-CPU shares (samples): `cpu_exec_loop` 41.3%, guest JIT 36.5%,
`cpu_tb_exec` 4.6%, TB lookup 9.0%. PFIFO on-CPU: `memcpy_opt` 31.5%,
`tlb_reset_dirty` 8.2%, `apply_uniform_updates` 6.0%.

**Blinx 2 answer** (frame 33.5 ms at 29.85 fps: at the 2-VBLANK cap; the
costs below are the headroom a heavier scene would eat):

| # | cost | ms/frame | share | evidence | candidate fix | owner |
|---|---|---|---|---|---|---|
| 1 | exec-loop returns | 13.5 | 40% | blinx2.data tid 22890: 41.3% + 4.6% of 26,451 ms | as AUF and Blinx | #425 |
| 2 | PFIFO waits for synchronous surface downloads | 12.1 | 36% | tid 22900: `download_surface` + deferred completion, 10.9 s of 30; soak `sd_dl` 60/60 flips, `Sub` 13.6 | blinx372d's zeta download made asynchronous | #372 (the Blinx lane; same engine) |
| 3 | vCPU blocked on `pg->lock` + BQL | 2.6 | 8% | tid 22890 off-CPU 2,347 of 3,562 ms | #474 | #474 |

Bound, not a value: none above the cap. The frame is at the title's 2-VBLANK
pacing (33.4 ms); removing any of these leaves it at **<= 30 fps**. No new
issue is asked for Blinx 2: it is not slow on this build and device.

## Forza Motorsport (4D53006E, #414)

**Soak** `1-1790492278-slowdown462-690198` (e5db66fa37 perflog, apk
c4b30cf46bd6, Nova, MAX restored). The race starts ~160 s after line 1 (shot
002700: race clock 00:09, 8th of 8); the survey route barely drives (0-3 mph).
Window `mark play`+10 s to 10 s before the end (243-414 s):

| | whole window | before the USB dialog (243-333 s) |
|---|---|---|
| fps (gfps cadence) / ms per flip | 22.95 / 42.0 (pace.py 22.99 / 43.5) | 24.13 / 39.5 |
| VBLANKs per flip (v2/v3/v4+) | 2.59 (46/49/5%) | 2.46 |
| vCPU busy (`[tlb68]`) | 96% | 95% |
| perflog renderer: Tot / Idle | 35.8 / 0.0 ms | 33.8 / 0.0 |
| Fin (Sub 19.9); `sd_cDef` per 60 flips | 20.2 ms; 371 (6.2 per frame) | 19.6; 378 |
| Draw (Pipe 5.4) / Surf | 12.1 / 3.3 ms | 10.9 / 3.2 |
| GPU (GR 18.0, GX 2.4) | 20.2 ms; **x1.573: 31.8 (GR 28.3, GX 3.8)** | 19.2; **30.2** |
| draws / RP breaks | 1,026 / 1,408 per 60 flips | |
| #424 churn | 1.5% of vCPU | |

At 00:30:20 PDT (shot 003020) an **"Allow USB debugging?" dialog** for an
unknown RSA key (2C:58:B6:23:...:F8) covered the Nova's screen. The pre-dialog
window reads the same shape, so the numbers stand; the dialog is a host
matter (reported on #462).

**Profile** `perf/2026-09-26-slowdown462/forza/forza.data` (a593d8eb85,
`--trace-offcpu`, 00:48:51-00:49:26 PDT, `mark play`+60 s; race, car stopped
on the start straight; `profwin.py`: 960 flips in 34.3 s = 28.0 fps, 35.7
ms/flip, gfps 28-30 falling to 19-25 in the last 10 s; ~840 frames in the 30
s record). **Lighter than the soak's median (23 fps)**, so the ms below are
at 28 fps; the soak's heavier stretches have `Sub` 22-23 ms.

| thread | on-CPU | off-CPU | where the off-CPU time goes |
|---|---|---|---|
| vCPU (tid 26799) | 25,650 ms (85%) = 30.5 ms/frame | 4,368 ms | **`pgraph_read` `pg->lock` 2,768**; BQL 399; unsampled 916 |
| PFIFO (tid 26809) | 13,593 ms (45%) = 16.2 ms/frame | 16,418 ms | **`pgraph_vk_finish` <- `pgraph_vk_download_surface_complete_deferred` 15,230** (18.1 ms/frame); `process_pending` 163; idle 91 |

vCPU on-CPU (sample shares): guest JIT 41.6%; **TB lookup 25.8%**
(`tb_lookup` 10.0, `qht_lookup_custom` 7.1, `helper_lookup_tb_ptr` 6.4,
`tb_lookup_cmp` 2.3); `cpu_exec_loop` only 5.1%;
`mem_access_callback_address_matches` 3.4%; `helper_mulss` 2.1%. Forza's
vCPU is not AUF's and Blinx's exec-loop shape: it misses in the indirect-jump
lookup instead. PFIFO on-CPU: `memcpy_opt` 23.6%, `rewrite_indices` 9.5%,
`fast_hash` 4.7%, `apply_uniform_updates` 4.3%.

The PFIFO thread is on-CPU or waiting for a deferred download 34.3 of every
35.7 ms: it sets the frame. The vCPU's `pgraph_read` waits are the same lock
as DOA's (#474), here held across the download waits, not the flip.

**Forza answer** (frame 35.7 ms at 28.0 fps in the profile; 42.0 ms at 23.0
in the soak window):

| # | cost | ms/frame | share | evidence | candidate fix | owner |
|---|---|---|---|---|---|---|
| 1 | PFIFO waits for deferred surface-download completions | 18.1 | 51% | forza.data tid 26809; soak `sd_cDef` 371/60 flips, `Sub` 19.9 | complete the ~6 deferred downloads per frame with one finish (forza414's uncoalesced `sd_complete_def`), or complete them off the PFIFO thread | #414 |
| 2 | vCPU TB lookup (indirect jumps) | 7.9 | 22% | 25.8% of 25,650 ms vCPU on-CPU | #425 jump cache (Forza is its workload) | #425 |
| 3 | vCPU blocked on `pg->lock` in `pgraph_read` | 3.3 | 9% | tid 26799 off-CPU 2,768 ms | drop `pg->lock` across the wait (#474's fix, applied to the download path too) | #474 |

The guest's own JIT code is 12.7 ms/frame (36%).

Bounds, not values: with (1) gone the PFIFO needs ~16 ms and the frame is at
least the vCPU's 30.5 ms on-CPU: **<= 33 fps**, and at the title's 2-VBLANK
pacing **<= 30 fps**. With (2) also gone the vCPU needs ~22.6 ms: still
**<= 30 fps** at the pacing. The same bound holds from the soak's heavier
window only if its vCPU on-CPU is also under 33 ms, which a soak cannot
show.

**Restated at x1.573 (13:18 correction):** the soak's GPU is 31.8 ms (GR 28.3).
With (1) gone, the frame is at least max(vCPU 30.5, GPU 31.8) ms: **<= 31
fps**, still **<= 30** at the pacing. This fits lane.forza414's finding that
`Sub` tracks the GPU's render time: the download waits are the GPU's frame,
seen from the PFIFO thread.

## Log (PDT, 2026-09-26)

- 21:04 pilot queued (DOA1U); ran 21:12-21:25; reviewed and
  `pilots/slowdown462.ok` written 21:40.
- 21:10 hostops granted five held profile sessions (board request Ask 1).
- 21:32 AUF soak `1-1790483186-slowdown462-3496610`.
- 21:39 `doa` session: missed the fight (anchored on `mark play`); unused.
- 21:54 `doa2` (on-CPU, anchored on the 8th `press START`).
- 22:15 `auf` (off-CPU). 22:33 `doa3` (off-CPU; owner's 21:45 override to
  finish DOA; Ask 2). 22:37 "Nova free" posted on #462.
- 22:47 DOA and AUF answers posted on #462, #413, #412. Ask 3 (new issue for
  the flip's lock-held GPU wait) filed.
- 23:36 waiting: the owner's charger-swap hold on the Nova (hold/nova,
  "only the owner lifts it") and lane.xbox's "verified on the Nova" notes for
  Blinx, Blinx 2 and Forza on #462. Neither had happened by 23:36.
- Attempt 1 ended at 23:36 on that wait, trusting a background watcher to
  resume it. The watcher died with the session (a headless lane's background
  tasks end with its turn), so nothing resumed the lane when the hold lifted
  (23:50) and the three copies landed (23:52-23:57, on #462).
- 23:58 attempt 2: merged origin/master; queued, on the same ref e5db66fa37,
  shape and priority as DOA/AUF: Blinx `1-1790492277-slowdown462-690144`,
  Blinx 2 `1-1790492277-slowdown462-690171`, Forza
  `1-1790492278-slowdown462-690198`. Waits are polled in the foreground.
- 00:18 `blinx` session (hold taken during the Blinx 2 soak, handed to the
  script); `--trace-offcpu` failed, on-CPU fallback recorded 30 s.
- 00:31 `blinx2` session (off-CPU). 00:43 `forza` session (off-CPU,
  `SOAK_S=360`, `mark play`+60 s). Each released the hold; the dispatcher
  ran retreason425 between them.
- Blinx, Blinx 2 and Forza answers posted on #462, #372 and #414; the
  five-title summary on #462.

## Attempt 3 (2026-09-27): GTA: San Andreas, the sixth title

Why there is an attempt 3: attempt 2 did finish. The five answers and the
summary were posted, and PR #463 folded into master. The resume's "background
job died" note is about attempt 1 (above). Attempt 3 exists because of
lane.local's 06:26 PDT addendum, which added GTA: San Andreas (54540082)
after the fold.

State at 06:27 PDT: GTA is **not on the Nova** (`ls /storage/*/Games/XBox/`).
It is on lane.xbox's `titlepush/queue-investigation.txt` (reason #462), to be
copied the next time the Nova is free. The Nova was running a titleroutes
benchmark then. A soak queued before the copy lands ends as the
dispatcher's `TITLE NOT FOUND` (dispatcher.sh:756), so the soak waits for
lane.xbox's "verified on the Nova" note on #462.

### Pre-read of the Thor benchmark (not the protocol's measurement)

`0-0-x-1790493356-titleroutes-734802`: ca54a41dd1, apk 397ae7dca16a, Thor,
MAX, no perflog. It has hakuX-pace only, so the read below is pacing only.
There were 22 pace lines (60 flips each) after the route's `mark gameplay`:

| | value |
|---|---|
| ms/frame, median of the 22 windows | 216 (min 156, max 256) = 4.6 fps |
| VBLANKs per flip, median | 12.5; the VBLANK rate is 58.4 Hz, so the timer is not starved |
| flips at >= 4 VBLANKs | 1316 of 1320 |
| the slowest frame in each window | 250-470 ms in 15 of the 22; 711, 955, 1152, 1855 and 1919 ms in the rest |

**The verdict's ten 11-15 s "hangs" are not stalls.** The hang detector
reports a gap as "N s without 60 guest flips", and at 216 ms/frame 60 flips
take 13 s. Every gameplay window is such a "gap". The steady frame time is
the problem. The real spikes are the five frames of 0.7-1.9 s. Their
excess over the median frame totals about 6 s of the ~285 s window (~2%).
The steady 216 ms is the other ~98%. Whether each spike is streaming, a
shader compile or a lock is a question for the Nova soak's hakuX-stall and
hakuX-phase lines and the profile, not this run.

### Queued, 06:59 PDT

- **Soak** `1-1790517499-slowdown462-1484367`: e5db66fa37 (the five's
  ref), perflog, MAX, Nova, release priority, route `gta-sa`, **500 s**. The
  Thor run's `mark gameplay` came ~225 s after `soak start`, so 420 s would
  leave only ~190 s of gameplay. The window is `mark gameplay` + 30 s to 10 s
  before `soak end`.
- Queued before the copy landed, to hold its place in line. At 06:58 the
  Nova was in a host update window (`hold/nova`, bounded 30 min) with four
  priority requests ahead (the flip474 and retreason425 arms, lanelocal). If
  the soak is claimed before lane.xbox's copy lands, it ends as `TITLE NOT
  FOUND` and is re-queued unchanged.
- **Profile** after the soak: `ROUTE=gta-sa ANCHOR="mark gameplay"
  SOAK_S=360 .cap/prof.sh gta 54540082-Grand_Theft_Auto_San_Andreas.xiso.iso
  60`. `capture_profile.sh` now takes `ROUTE` (default survey, so the five
  are unchanged).
- To answer the extra question, split the frames into the steady ~216 ms and
  the >= 0.7 s spikes. For each spike, read the hakuX-stall, hakuX-phase and
  hakuX-cpu lines around it.

## Attempt 4 (2026-09-27, 07:42 PDT): GTA's soak read; the profile is blocked

Why attempt 3 did not finish: it ended on a wait, as it should have. The
GTA soak was queued and the copy to the Nova had not landed. Two things
changed after it ended:

- hostops withdrew the Nova copy (07:11 PDT, on #462): GTA stays on the
  Thor only, under the one-handheld-per-title rule. At 07:50 PDT the Nova
  has no `54540082` file.
- hostops re-pinned the queued soak to the Thor and promoted it. It ran
  there 07:28-07:37 PDT as `0-0-x-1790517499-slowdown462-1484367`.

**So GTA's numbers are the Thor's, not the Nova's.** They do not compare
with the five Nova rows fps for fps. The shape (which thread, which cost)
is what carries over.

**The simpleperf profile was not taken.** This lane's brief says Nova only
and that the Thor is not touched. The messages on #462 (07:11, 07:12 and
07:25 PDT) offer one held Thor session, and the 07:12 one says to take it
"once the grant appears in your board-request file or brief". At 07:45 PDT
it is in neither. Board request Ask 4 asks for it there.

### Soak `0-0-x-1790517499-slowdown462-1484367`

e5db66fa37 perflog, apk c4b30cf46bd6, **Thor** (bdc158a5), MAX restored,
route `gta-sa`, 500 s, shader cache cleared before the run (APK change).
`regimes.py <id> --from 230 --split 80` gives one row per 60-flip window.

**The route's `mark gameplay` fell inside the police-stop cutscene.** Shots
073152-cut3, 073206-moved and 073212-gameplay are all the letterboxed
cutscene at 5-6 fps: the A presses did not skip it in this run. The route
takes no shot after the mark, so no frame shows what was on screen in the
275 s that follow.

After the mark the run has two regimes:

| | slow | fast |
|---|---|---|
| when (s after line 1) | 230-291 and 470-505 | 292-468 |
| windows / flips / wall | 8 / 480 / 90.9 s (34%) | 77 / 4,620 / 177.1 s (66%) |
| ms per flip, median (fps) | 197.5 (5.1) | 35.7 (28.0) |
| VBLANKs per flip | 9.8 | 2.1 |
| vCPU on-CPU (`[tlb68]` cpu/dt) | 69.9% = 138 ms/frame | 94.5% = 33.7 ms/frame |
| vCPU off-CPU | 30.1% = 59 ms/frame | 5.5% = 2 ms/frame |
| renderer `Tot` / `Idle` (of it `St`, starved mid-frame) | 178.3 / 117.5 (100.1) | 29.2 / 12.8 (7.0) |
| renderer busy (`Tot` - `Idle`): Draw (Pipe) / Fin / Surf | 61: 28.9 (12.1) / 7.1 / 3.5 | 16: 11.5 (4.9) / 2.7 / 2.7 |
| GPU | 7.0 ms | 5.2 ms |
| draws per frame | 561 | 643 |
| finishes because the FIFO ran dry (`stl`), per frame | 8.2 | 0.9 |
| #424 churn, share of vCPU (`churn.py`) | 4.4-5.0% | 1.6% |
| invalidations per second (`churn.py` inv/s) | 373 and 169 | 423 |
| audio callbacks' zero-filled output | 18% | 1.4% |

The phase fields are a running average over about the last 5 frames
(`SMOOTH`, alpha 0.2, profile.c), read once per 60 flips. The figures above
are medians over the windows.

**The slow regime is the benchmark's gameplay.** The Thor benchmark
`0-0-x-1790493356-titleroutes-734802` (ca54a41dd1, not perflog) has frames
of CJ on foot in the alley with the HUD, at 7-8 fps on the overlay. Over its
230-505 s it reads 219.4 ms per flip, 12.1 VBLANKs per flip, vCPU 68.1%,
churn 4.9%, 340 invalidations a second, 27.8% zero-filled audio: the soak's
slow regime in every column both runs have. So the slow regime is seen in
the cutscene (the soak's frames) and in alley gameplay (the benchmark's).

**What the fast regime is, this soak cannot say.** It holds the title's
2-VBLANK pacing for 175 s with the same draw count. No frame covers it. The
builds differ too (the benchmark's ca54a41dd1 has #465's jump cache on by
default; e5db66fa37 does not), so "the same scene, faster on the older
build" is not excluded either. A soak with frames after the mark separates
these (Ask 4).

### Attribution of the slow regime, as far as a soak reaches

1. **Which thread sets the frame: the guest.** The renderer is starved for
   100 ms of each frame (`St`: idle with the frame not yet flipped, waiting
   for the guest's next push). The GPU works 7 ms (4%). The FIFO runs dry
   8 times a frame, so the guest delivers the frame's commands in bursts.
2. **Within the vCPU: not split.** The vCPU thread is on-CPU 138 ms of each
   197.5 ms frame and off-CPU 59 ms. #424's churn is 4.4-5.0% of the on-CPU
   time (6-7 ms/frame), timed by the build. The rest of the split (exec
   loop, TB lookup, softmmu, helpers, guest code) is what the profile is
   for. What the 59 ms blocks on (a lock, a disc read, a halt) needs the
   off-CPU record.
3. **Within PFIFO:** 61 ms busy per frame, overlapped with the guest and
   not the bound. Draw 28.9 (Pipe 12.1, of it Sh 8.4), Fin 7.1 (Sub 4.0,
   Fen 2.8), Surf 3.5. One deferred download completion per 2 flips.
4. **Pacing:** 9.8-12.1 VBLANKs per flip at a VBLANK rate of 55-58 Hz. The
   timer is not starved; the guest is late.

### The extra question: the 11-15 s stalls against the steady frame time

- **The verdict's ten 11-15 s "hangs" are the steady frame time.** At
  197-219 ms per flip, 60 flips take 11.8-13.2 s, and the hang detector
  reports "N s without 60 guest flips". Every slow window is one.
- **Steady:** the time above the regime's median frame is 4% of the
  benchmark's gameplay wall (9.6 s of 274.2) and 7% of the soak's slow wall
  (6.8 s of 90.9). The rest is the steady frame.
- **Spikes (one frame over 700 ms):**

| run | window | spike frames (ms) | time above the steady frame | share of the wall |
|---|---|---|---|---|
| benchmark, gameplay 230-505 s | 274.2 s | 1919, 1855, 1152, 955, 711 | 5.5 s | 2.0% |
| soak, slow regime | 90.9 s | 1974, 1837, 936 | 4.2 s | 4.6% |
| soak, fast regime | 177.1 s | 1872 | 1.8 s | 1.0% |

- **Cause, in the soak: each spike sits with a shader or pipeline
  compile.** The window of each has a non-zero `Shd` at its end (253, 37.9
  and 118 ms) or pipeline-cache growth in it or the next (+18, +14, +6
  entries; `hakuX-stall pipe[used N/2048]`). The soak ran on a cleared
  shader cache.
- **Not settled:** the benchmark kept its shader cache and still has five
  spikes. It has no perflog lines, so its spikes have no cause on record. A
  disc read or a lock under the same frame would not show in either run.
  That needs the off-CPU record.

### GTA answer, attempt 4 (superseded in attempt 5: the slow regime it prices is a cutscene on this build)

| # | cost | ms/frame | share | evidence | candidate fix | owner |
|---|---|---|---|---|---|---|
| 1 | vCPU on-CPU, not split | 138 | 70% | `[tlb68]` cpu/dt 69.9% (soak), 68.1% (benchmark); renderer starved 100 ms/frame | none until the profile splits it | new GTA issue (Ask 5) |
| 2 | vCPU off-CPU, cause not captured | 59 | 30% | the same lines; zero-filled audio 18-28% | none until the off-CPU record names it | new GTA issue |
| 3 | #424 code-write churn (inside 1) | 6-7 | 3% | `churn.py`: 4.4-5.0% of vCPU, 340-373 invalidations/s | #424's path is already in this build | #424 |

The spikes are priced above: 2.0-4.6% of the wall, and not part of the
steady frame.

Bound, not a value: the title's pacing is 2 VBLANKs per flip, so **<= 30
fps**. The soak's fast regime held 28.0 fps for 175 s on this device and
build, on a screen no frame identifies.

### State at the end of attempt 4 (08:00 PDT)

- **Blocked** on the device for GTA's profile: `[lane.slowdown462] blocked:`
  on PR #477. Board request Ask 4 (the Thor grant in the brief, or the Nova
  copy) and Ask 5 (an issue for GTA) are filed.
- Nothing of this lane's is queued or running on either device. No hold is
  taken. No background task is left.
- The next attempt, once the brief names the device: the profile session
  (Ask 4 has the command), then one soak with `--frames-every 10` to see
  what the fast regime is, then rows 1 and 2 of GTA's table.

## Attempt 5 (2026-09-27, 08:15 PDT): GTA's profile on the Thor

- **Why attempt 4 did not finish:** it ended blocked on the device for GTA's
  profile (Ask 4). PR #477 folded with that state at 08:0x PDT. Hostops
  answered Ask 4 at 08:20 (option 1: one held Thor session under 10 min, and
  one Thor perflog soak with `--frames-every 10`) and Ask 5 (#482 is GTA's
  issue). This attempt runs both on a new PR.
- `capture_profile.sh` now takes `DEV=nova|thor` (default nova), finds the
  ISO under the device's `DEVICE_ISO_ROOTS` from `devices.sh`, and refuses
  the Thor below 30% battery (the Nova below 20%, as before).

### GTA's held profile (Thor, a593d8eb85, 08:18-08:23 PDT)

`DEV=thor ROUTE=gta-sa ANCHOR="mark gameplay" SOAK_S=360 OFFCPU=1
capture_profile.sh gta ... 15`, output `perf/2026-09-26-slowdown462/gta/`.
Hold taken during the Thor's running request (titleroutes), used only after
`running/` emptied of the Thor; REST restored (`perf_regimen.json`
`perf_restored: true`), caches cleared, hold released; battery 38%.

- **`--trace-offcpu` cannot open on the Thor**: harden=1, paranoid=3 ("Event
  type 'cpu-clock' is not supported"). The record fell back to on-CPU only.
  The Nova had paranoid 1. The off-CPU half of GTA is not measurable on this
  device without root.
- **The window is gameplay, at 26.6 fps.** Frame `082206-gameplay`: CJ in
  the Jefferson alley, HUD, 24 fps on the overlay. `profwin.py`: 840 flips
  in 31.6 s = 26.62 fps, 37.6 ms/flip (gfps 19-31 after the first line).
- vCPU (tid 29568) 28,045 of 30,000 ms sampled = 93.5% on-CPU = 35.1 ms per
  frame. Self: guest JIT 49.8%, `tb_lookup` 10.4%, `helper_lookup_tb_ptr`
  6.8%, `qht_lookup_custom` 4.8%, `voice_lock` 2.0%, `tb_lookup_cmp` 1.9%,
  softmmu (`tlb_set_page_full`, `tlb_reset_dirty`, `probe_access_internal`)
  3.9%, SSE helpers 4.3%. Inclusive: **27.9% under `helper_lookup_tb_ptr`**
  (the indirect-jump lookup), 4.9% under `cpu_exec_loop`, 2.2% `tb_gen_code`.
  Unlike AUF and Blinx, `cpu_exec_loop` self is not in the top: GTA's
  dispatch cost is the indirect-jump lookup (Forza's variant).
- PFIFO (tid 29579) 14,848 ms = 49.5% on-CPU: `memcpy_opt` 25.9% (of it
  `pgraph_vk_snapshot_state` 36%, `pgraph_vk_finish` at FLIP_STALL 18%,
  `apply_uniform_updates` 18%), `rewrite_indices` 4.5%. Not the frame's
  setter at half a core.
- Audio: four `voice_worker_thread`s 3.1-4.0 s each (~48% of a core in
  total), the DSP thread 3.9 s, SDLThread 4.0 s of which 68% is
  `__kernel_clock_gettime` (a poll).

### The soak with frames: GTA's 5 fps is the open world, not the build

`0-0-x-1790522043-slowdown462-3573620`: e5db66fa37 perflog, **Thor**, MAX,
JC off, `gta-sa`, 500 s, `--frames-every 10` (frames cost frame rate: do not
compare its fps with a soak without them). `mark gameplay` at 221.9 s.
`regimes.py <id> --from 150 --split 80`:

| | fast | slow |
|---|---|---|
| when (s after soak start) | up to ~262 | 265-500 |
| screen | the Jefferson alley (f00020, 29 fps on the overlay) | open world: streets, houses, traffic, a pedestrian (f00032 4 fps, f00042 2 fps) |
| wall | 111.8 s (33%) | 222.8 s (67%) |
| ms per flip, median (fps) | 35.0 (28.6) | 229.6 (4.4) |
| VBLANKs per flip | 2.0 | 12.7 |
| vCPU on-CPU (`[tlb68]` cpu/dt) | 93.0% | 68.9% = 158 ms/frame; off-CPU 71 |
| renderer `Tot` / `Idle` / `St` | 27.8 / 12.9 / 5.8 | 219.4 / 150.7 / 130.6 |
| Draw (Pipe) / Fin / GPU | 11.1 (4.6) / 3.0 / 4.3 | 35.7 (15.4) / 17.3 / 8.6 |
| guest `pf` / `cr3s` per s (hakuX-cpu) | 1,600 / 96 | ~10 / 0 |
| audio zero-filled | 0% | 29.9% |
| spikes over 700 ms | 0 | 3 (2.1, 1.7, 7.7 s) |

**This withdraws the jump-cache hypothesis I posted at 08:25 PDT.** The
three runs in that table (benchmark 4 gfps with JC on; soak and profile 27
with JC off) were read in different places. The two fast readings came from
the alley and the benchmark's came from past it, so the build difference was
a coincidence of the windows. I posted the correction on #425
(`deliver.sh`), #482 and #462 at 08:55 PDT, and withdrew Ask 6. The lesson
is in "Do not repeat".

The attempt-4 soak fits this too: its slow 230-291 s was the cutscene,
its fast 292-468 s was the alley (no frames), and its slow 470-505 s was
most likely CJ past it.

**The held profile (08:22) is of the alley, the fast regime.** It prices
28 fps gameplay, not the 4.4 fps that matter. **Ask 7** (host) asks for one
more held Thor session anchored at `mark gameplay` + 90 s. The slow regime's
`pf` and `cr3s` falling to ~0 says the guest stops switching address spaces
and taking page faults there. A guest stuck in one thread, spinning or
waiting (31% off-CPU), fits that. So does one long streaming or decompress
loop. The profile would tell them apart. On the Thor it cannot show off-CPU
time.

### GTA answer, attempt 5 (Thor, e5db66fa37 perflog soak with frames, open world, 229.6 ms/frame = 4.4 fps)

The guest sets the frame. The renderer idles 151 ms of every 230 ms frame,
131 of them starved mid-frame, and the vCPU is on-CPU 69% of the wall.

| # | cost | ms/frame | share | evidence | candidate fix | owner |
|---|---|---|---|---|---|---|
| 1 | vCPU on-CPU in the open world, not split | 158 | 69% | soak `...3573620` slow windows; frames f00032, f00042 | none until the profile of Ask 7 splits it | #482 |
| 2 | vCPU off-CPU (blocked), cause not measurable on the Thor | 71 | 31% | the same lines; audio 30% zero-filled | none: `--trace-offcpu` fails at paranoid 3 | #482 |
| 3 | indirect-jump TB lookup (from the alley profile, if the open world has the same mix) | <= 44 | <= 19% | gta.data: 27.9% of vCPU samples under `helper_lookup_tb_ptr` at 26.6 fps | the jump cache (#425) | #425 |

Row 3 scales the alley profile's share onto the open world's on-CPU time.
That is a bound for a mix nobody has measured yet, not a value.

The alley (the first ~40 s of gameplay) runs at 26.6-28.6 fps. Its profile
(a593d8eb85): vCPU 93.5% on-CPU, guest JIT 49.8%, indirect-jump lookup
27.9%, softmmu 3.9%; PFIFO 49.5% on-CPU. With the lookup at zero, the alley
is at the 2-VBLANK cap: <= 30 fps.

Bound, not a value: the pacing caps GTA at **<= 30 fps**. In the open world,
removing both vCPU rows leaves the renderer's busy 69 ms (Tot - Idle): at
most **~14 fps** until the renderer's own Draw/Fin (53 ms) moves as well.

The 11-15 s stalls: attempt 4 priced them at 2.0-4.6% of the wall, with
shader or pipeline compiles. This soak has three spikes over 700 ms in the
open world (2.1, 1.7, 7.7 s), 10.8 s of its 222.8 s. They are not the
steady frame.

### State at the end of attempt 5 (09:00 PDT)

- Done under the 08:20 grant: the held Thor profile (alley, 08:18-08:23;
  hold released, REST restored) and the Thor soak with frames
  (`0-0-x-1790522043-slowdown462-3573620`). Both grants are used up.
- **Waiting** on Ask 7 (host): one more held Thor session, anchored in the
  open world. Nothing of this lane's is queued or running, it holds no
  hold, and it has no background task.
- Next attempt, once Ask 7 is granted: `DEV=thor ROUTE=gta-sa ANCHOR="mark
  gameplay" SOAK_S=420 capture_profile.sh gta-open <iso> 90`, check with
  `profwin.py` and the frames that the window is past the alley, then split
  rows 1 and 3 of the answer above with `profread.py`.

## Summary (Nova, MAX, e5db66fa37 soaks / a593d8eb85 profiles)

GPU column and bounds corrected at x1.573 (13:18 PDT, #474 section 3): the
Nova's GPU timestamps tick at 19.2 MHz, not 30.2. The pre-correction bound is
kept beside each one.

| title | fps (soak window) | GPU ms/frame, corrected (read) | sets the frame | top cost (ms/frame, share) | owner | bound if it goes (corrected; was) |
|---|---|---|---|---|---|---|
| DOA1U | 13.2 | 60.2 (38.3) | the GPU (60 of 76 ms); the flip waits for it under `pg->lock`, and the guest blocks in `pgraph_read` | 34 (49%) | #474 | **<= 16.5 fps** (lane.flip474's fitted span: 15.6); was <= 26 |
| AUF | 15.1 | 45.6 (29.0) | vCPU (94% on-CPU) | exec-loop returns 42 (63%) | #425 / #412 | **<= 21.9 fps**, if the returns are overhead; was <= 34 (30 at pacing) |
| Blinx | 17.2 | 36.7 (23.3) | vCPU (73% on-CPU, 27% blocked) | exec-loop returns 21.7 (36%) | #425 | **<= 26 fps** (unchanged, the vCPU's); with the blocked time too **<= 27** (the GPU's); was <= 30 |
| Blinx 2 | 28.9 | 26.7 (17.0) | at its 2-VBLANK cap | exec-loop returns 13.5 (40%) | #425 | none above the 30 cap (GPU 26.7 < 33.4) |
| Forza | 23.0 | 31.8 (20.2) | PFIFO (waits on deferred downloads, which track the GPU's render) | deferred download finishes 18.1 (51%) | #414 | **<= 30 fps** (pacing; the GPU alone allows 31) |
| GTA: San Andreas (**Thor**; soak with frames, open-world profile) | 4.4-4.8 in the open world; 28.6 in the alley | Thor: its clock is not checked; not the bound (4% busy) | the guest: vCPU 70% on-CPU, renderer starved | guest JIT code 77.6 (37%); blocked 61.9 (30%); TB dispatch 46.0 (22%) | #482 (#425 for dispatch) | <= 6.1 fps without dispatch; <= 7.2 without all TCG overhead |

Two mechanisms cover four titles: the exec loop between TBs on the vCPU (AUF,
Blinx, Blinx 2; Forza's variant is the indirect-jump lookup), and PFIFO waits
for the GPU inside `pg->lock`, which the guest's `pgraph_read` then waits
behind (DOA at the flip, Forza and Blinx 2 at surface downloads).

With the GPU corrected, the GPU's own work comes next in line on four of the
five. It sets DOA's frame outright (60 of 76 ms). It caps AUF at 22 fps and
Blinx at 27 once their vCPU costs go, and it sits at 31.8 of Forza's 42 ms. So
the uncorrected ceilings were too high: by 10-12 fps for DOA's first bound,
AUF and Blinx, by 18 for DOA's second, and by 2 for Forza. On the
Nova a GPU-work lever (DOA's `Xfr`, now 30.4 ms/frame; render passes broken
for surfaces) matters as much as the TCG levers.

## Do not repeat

- Do not take a window from the survey route's `mark play` without the
  shots: DOA fights before it.
- Do not price a wait from the perflog phase timers. DOA's `Surf` (60 ms) and
  AUF's renderer "busy 79%" are wall time; the shipping build's PFIFO thread
  is on-CPU 21-24% in both.
- Do not read `simpleperf report`'s weighting under `--trace-offcpu` as
  blocked time: it charges each switch-out the time to the thread's next
  sample. Use `offcpu.py` (switch records). Under `--trace-offcpu` the
  cpu-clock sampler also drops samples (AUF vCPU: 9.3 s sampled of 12.4 s
  on-CPU), so read on-CPU ms from the switch records and only shares from
  samples. The `record` can end early (AUF: 13.5 s of 30).
- The vendor driver has no unwind info: a GPU wait's chain ends at
  `wait_timestamp_safe`. Match it to the thread's last on-CPU sample (median
  0.9 ms before) to find the emulator caller.
- A poll for an empty `running/` never sees the gap between Nova runs; take
  the hold during a run and touch nothing until `running/` empties.
- `--trace-offcpu` can fail at once ("Event type 'cpu-clock' is not
  supported", Blinx 00:23) and work 8 min later on the same boot (harden 0,
  paranoid 1). The script falls back to on-CPU; if the off-CPU half matters,
  rerun the session.
- `capture_profile.sh`'s soak is `SOAK_S` (330 s) from launch: `mark play`
  lands at ~235-245 s on these titles, so a delay over ~40 s needs
  `SOAK_S=360` or the record is cut by the soak's end.
- Do not take `mark gameplay` as gameplay either: GTA's fell inside a
  cutscene the A presses had skipped in the route's other runs. A route
  with no shot after its mark leaves the whole window unseen; ask for
  `--frames-every` on any soak whose window the frames must confirm.
- Do not compare per-window counts across regimes. A 60-flip window is 2 s
  at 30 fps and 12 s at 5, and hakuX-pages counts "since last": its raw
  counts read 5 times higher in GTA's slow regime while the per-second rate
  (`churn.py` inv/s) was the same.
- `titleread.py` passed `churn.py` offsets from logcat line 1. `churn.py`
  counts from `mark gameplay` when the route wrote one, so GTA's first
  churn read was of the wrong 53 s. Fixed in `titleread.py`; the five
  survey-route titles were not affected (their route writes `mark play`).
- The phase line is a running average of the last ~5 frames, not the
  window's mean. A `Shd` of 0.0 does not show that the window had no
  compile; pipeline-cache growth (`pipe[used N/2048]`) does.
- Do not end a session waiting on a background task: attempt 1 did, and
  nothing resumed it for the ~25 min after the Nova came back.
  `systemd-run` and `setsid` are refused by this lane's permissions; a held
  session fits in one foreground call if the hold is taken during the
  running request and handed to the script (`.cap/prof.sh` pattern:
  release and re-take in the same call).
- Do not compare runs of an open-world title across builds before the
  frames say where each window was. GTA's alley runs at 28 fps and the
  street past it at 4.4. Three runs lined up with the jump-cache switch by
  where their windows fell, and I posted a build hypothesis that the next
  soak refuted (08:25 -> 08:55 PDT, corrected on #425, #482 and #462).
- `--trace-offcpu` did not open on the Thor at 08:18 (paranoid 3). At 09:16
  it read paranoid 1 on the same boot, so read `perf:` in the session log
  before assuming either way.
- Do not delete a dispatcher marker in a held session's cleanup unless the
  session undid the thing the marker records. `.env_pref.<dev>` is how the
  next request's env gets cleared. Deleting it with the env still set ran
  titleroutes' Azurik benchmark under #424's range test (09:08).

### Attempt 6 (09:04 PDT): why attempt 5 did not finish

Attempt 5 did not fail. It ended waiting on Ask 7, a host grant outside the
session, with nothing of its own queued, held or running in the background.
Hostops granted Ask 7 at 09:03 PDT with a 25% battery floor, and this
attempt runs that one session. The request `0-0-x-1790517499-slowdown462-1484367`
named in the resume is the earlier GTA soak, which attempt 4 already read.

### GTA's open-world profile (Thor, a593d8eb85, Ask 7, 09:16-09:23 PDT)

`DEV=thor ROUTE=gta-sa ANCHOR="mark gameplay" SOAK_S=420 OFFCPU=0 MIN_BATT=25
capture_profile.sh gta-open ... 90`, output `perf/2026-09-26-slowdown462/gta-open/`.
The hold was taken during titleroutes' Azurik request (09:10) and used only
after `running/` emptied of the Thor (09:16:31). The battery was at 27%. REST
was restored (`perf_restored: true`), the caches were cleared and the hold
was released at 09:22:45.

- **The first try (09:08) refused, and its cleanup broke the next request.**
  tbflip424's request had left `HAKUX_TCG424_RANGE=1` in the Thor's
  `env_vars` pref. The script refused on it, which was correct. But its
  cleanup deleted `dispatch/.env_pref.thor`, and that marker is how the
  dispatcher knows to clear a previous env. So titleroutes' Azurik benchmark
  `1-1790519286-titleroutes-2112912`, claimed 10 s later, ran with the #424
  range test on. I restored the marker at 09:12, so the next Thor claim clears
  it. I fixed the script: it clears a leftover env itself, reads the clear
  back, and drops the marker only after that. I reported it in
  host-tools/hostops-inbox.md (09:15).
- **The window is the slow regime.** `profwin.py`: 120 flips in 25.0 s =
  4.79 fps, 208.7 ms/flip (gfps 3 5 6). This profile has no frame. The regime
  is identified from the soak with frames, where the slow regime started
  ~43 s after `mark gameplay`; this window is at +90 s.
- **The Thor now reads harden=0, paranoid=1, on the same boot** (uptime
  16.4 h). At 08:18 it read harden=1, paranoid=3. So `--trace-offcpu` may open
  there now. Ask 7 asked for OFFCPU=0, so the vCPU's blocked third is still
  unpriced.
- vCPU (tid 20343): 21,096 of 30,000 ms on-CPU = 70.3%. The soak read 68.9%.
  That is 146.8 ms of each 208.7 ms frame, and 61.9 ms blocked. Self: guest
  JIT 52.9%, `tb_lookup` 5.6%, `helper_lookup_tb_ptr` 3.9%, `tlb_reset_dirty`
  3.7%, `qht_lookup_custom` 2.7%, `voice_lock` 2.1% (all from APU MMIO
  writes, `do_st_mmio_leN`), SSE helpers ~2%. Inclusive: 21.3% under
  `helper_lookup_tb_ptr`, 10.0% under `cpu_exec_loop` (of it `tb_gen_code`
  5.6%), 3.9% under `tlb_reset_dirty`, and none under `io_readx`/`io_writex`.
- **It is the alley's mix, about 4.2 times over per frame.** Per frame, alley
  -> open world: JIT 17.5 -> 77.6 ms (x4.4), lookup 9.8 -> 31.3 (x3.2), exec
  loop 1.7 -> 14.7 (x8.6), `tb_gen_code` 0.8 -> 8.2 (x10). The guest runs
  4.4 times the JIT time per displayed frame. Translation is the one cost
  that grows faster than the rest: new code keeps arriving.
- **Not a spin loop.** `jitspots.py` (new): the vCPU's 11,162 JIT samples
  fall in 6,548 host-code buckets of 256 B, half of them in 1,353, and the
  top bucket holds 0.7%. A guest spinning in one loop would sit in a
  handful. Taken with `pf`/`cr3s` falling to ~0 in the soak, the guest runs
  a broad workload in one thread that never yields for 200 ms at a time.
- PFIFO (tid 20350): 7,309 ms = 24% on-CPU (the alley: 49.5%). Of it
  `memcpy_opt` 24.4%. It is starved, as the soak said.
- Audio: four `voice_worker_thread`s at 4.4-5.9 s each (~69% of a core in
  total), the DSP thread 5.2 s. That is more than in the alley (48%).

### GTA answer, attempt 6 (Thor, open world, 208.7 ms/frame = 4.8 fps)

| # | cost | ms/frame | share | evidence | candidate fix | owner |
|---|---|---|---|---|---|---|
| 1 | guest code (JIT) on the vCPU | 77.6 | 37% | `gta-open.data` tid 20343: 52.9% self `[guest JIT]`; 6,548 buckets, not a loop | find what the guest runs (a guest-PC profile, `profile_guest.sh`), then why it is 4.4x the alley's per frame | #482 |
| 2 | vCPU blocked (off-CPU), cause not measured | 61.9 | 30% | 30,000 - 21,096 ms; the soak: 71 ms, audio 30% zero-filled | an off-CPU profile, now possible on the Thor (paranoid 1) | #482 |
| 3 | TB dispatch: indirect-jump lookup + exec loop (incl. translation 8.2) | 31.3 + 14.7 = 46.0 | 22% | 21.3% under `helper_lookup_tb_ptr`, 10.0% under `cpu_exec_loop` | the jump cache (#425); for translation, why new code keeps arriving | #425 / #482 |

Bounds, not values. With row 3 gone, the frame is 162.7 ms: **<= 6.1 fps**.
With every non-JIT on-CPU vCPU cost gone (69.2 ms), it is 139.5 ms: **<= 7.2
fps**. So the TCG overhead levers cannot bring GTA's open world near 30. The
frame is guest work (rows 1 and 2, 139.5 ms, 67%), and pricing it takes a
guest-side profile and an off-CPU profile, not an emulator-side one.

The 11-15 s stalls stay as attempt 4 priced them: 2.0-4.6% of the wall, with
shader or pipeline compiles, and separate from this steady frame.

### State at the end of attempt 6

Ask 7 is used up, and this lane holds no hold and has nothing queued. The
next GTA step belongs to #482: a guest-PC profile of the open world, plus
an off-CPU session on the Thor (paranoid 1 now). Each needs a device grant.
This lane's deliverables are complete.

## Attempt 7 (2026-09-27, 13:18 PDT addendum): the PFIFO thread's SET_BEGIN_END on AUF and Blinx

### Why this is a new attempt, not an unfinished one

Attempt 6 finished: PR #483 folded (a3952caec3) with this lane's GTA work,
and it held nothing and had nothing queued. The resume notice named PR #477
as a draft, but #477 had already folded (49ca6d319d), so that notice was
stale. The work below is lane.local's 13:18 addendum: profile the PFIFO
thread on AUF and Blinx over lane.flip474's `[cblat]` windows, break
SET_BEGIN_END down, and restate the Nova GPU figures at x1.573 (done in
place above: the banner at the top, each title's GPU row and bound, and
the summary table).

### The sessions (Nova, MAX, `76cba82fd2-perflog`, the APK of flip474's `[cblat]` runs)

`capture_profile.sh` now takes `APK_REF`. There was one held session per
title, run with `OFFCPU=1 SOAK_S=360`. Each hold was taken during
forza414's running request and used only after `running/` emptied. REST was
restored (`perf_restored: true`), the caches were cleared and the hold was
released on exit.

| | AUF `auf474/` | Blinx `blinx474/` |
|---|---|---|
| session (PDT) | 13:25:42-13:31:50 | 13:39:22-13:44:58 |
| window, `mark play` + | 70 s (~315 s from launch; `[cblat]` read 299-420 s) | 30 s (~278 s; `[cblat]` read 255-411 s) |
| battery | 62% | 57% |
| `profwin.py` | 420 flips in 28.3 s = 14.87 fps, **67.3 ms/flip**; gfps 14-15 | 600 flips in 30.4 s = 19.73 fps, **50.7 ms/flip**; gfps 10-27 |
| shots | 133104, 133130: first-person mission play (FPS 14) | 134358, 134425: level play (FPS 24) |
| samples lost | 0 of 527,411 | 0 of 544,232 |
| PFIFO tid | 29610 | 5221 |

The Blinx window is lighter than flip474's run (19.7 fps against 16), and its
first 10 s ran at 10-17 gfps. `[cblat]` read over these same seconds
(`cblatwin.py`) is the comparison, not flip474's numbers.

### Three instruments, one window

`cblatwin.py` sums `[cblat]`'s split over the profile window.
`phasewin.py` averages the `hakuX-phase` and `hakuX-cpu` lines. `drawcost.py`
reads the profile. All figures are ms per frame.

| | AUF | Blinx |
|---|---:|---:|
| **`[cblat]` mdraw: SET_BEGIN_END wall, with its lock wait** | **51.0** (flip474: 50.1) | **31.9** (flip474: 36.8) |
| of which the nested download (`dl`) | 22.3 | 0.4 |
| `[cblat]` pflip (parked in FLIP_STALL on the VBLANK) | 10.6 | 0.0 |
| phase `Surf` (draw_begin's `surface_update`; holds the download) | 24.9 | 3.1 |
| phase `Draw` | 21.8 | 27.3 |
| of `Draw`: `Pipe.Tx` (texture bind, exclusive) / `Pipe.Sh` / `Lu` | 8.7 / 3.4 / 0.6 | 9.7 / 6.9 / 1.1 |
| of `Draw`: Mfp / Setup / Syn / Desc / Cmd | 1.5 / 0.8 / 0.5 / 0.5 / 0.4 | 0.1 / 1.2 / 1.2 / 0.3 / 0.8 |
| `hakuX-cpu` `Mth` (wall in `pgraph_method`) / `Lk` (puller's `pgraph.lock` wait) | 50.3 / 0.4 | 33.4 / 0.6 |
| **PFIFO thread on-CPU, whole frame** (switch records) | **20.5** (9,157 ms of 30 s) | **28.9** (17,101 ms) |
| PFIFO thread off-CPU, whole frame | 46.7 | 21.8 |
| **SET_BEGIN_END on-CPU** (profile) | **10.5**, at most 14.9 | **11.8**, at most 16.5 |
| GPU, corrected x1.573 (read) | 46.6 (29.6) = 69% of the frame | 33.2 (21.1) = 65% |

`[cblat]`'s mdraw equals `Surf` + `Draw` (AUF 46.7 of 51.0, Blinx 30.4 of
31.9), so the phase timers break the wall down. **SET_BEGIN_END is wall time,
not CPU:** 10.5-14.9 of AUF's 51.0 and 11.8-16.5 of Blinx's 31.9 are the
thread on-CPU. The rest, at least 36 and 15 ms/frame, is the PFIFO thread
blocked inside the method.

How "on-CPU" is counted:
- The switch records give each thread's exact on-CPU time. The cpu-clock
  sampler dropped samples under `--trace-offcpu`: 6,311 of 9,157 ms (AUF),
  11,173 of 17,101 (Blinx). Sample shares are therefore scaled by 1.451 and
  1.531.
- A sample is in draw dispatch when its chain holds a function only the draw
  path calls. A plain entry list misses most of them:
  - `--call-graph dwarf,8192` copies 8 KB of stack, and `flush_draw_one_pass`
    alone has a ~35 KB frame (below), so the chains are cut before they reach
    the method handler.
  - SET_BEGIN_END(begin) tail-calls `pgraph_vk_surface_update`, so draw_begin
    leaves no frame.
- The "at most" figure adds every `surface_update` sample with no draw frame
  (AUF 3.6, Blinx 3.5: draw_begin's share, and the flip's and the surface
  methods') and every chain that reaches neither a draw frame nor
  `pfifo_thread` (0.8, 1.2).

### SET_BEGIN_END's CPU, by what it does (ms/frame, scaled)

| bucket (innermost frame wins) | AUF | Blinx | functions |
|---|---:|---:|---|
| uniforms: hash, compare, upload | 3.53 | 3.70 | `apply_uniform_updates` (`memcpy_opt`), `fast_hash`, `pgraph_glsl_set_*_uniform_values`, under `pgraph_vk_bind_shaders` / `update_shader_uniforms` |
| **debug snapshot** | **2.48** | **2.17** | `pgraph_vk_snapshot_state` -> `memcpy_opt` |
| state checks: `flush_draw_one_pass` self, `pgraph_vk_draw_end` | 1.31 | 1.22 | |
| pre-draw state (`begin_pre_draw_inner` self, fast-path checks) | 1.23 | 1.65 | |
| lock handoff on-CPU (`pthread_mutex_unlock`, `__aarch64_swp*`) | 0.91 | 1.24 | |
| vertex RAM sync / dirty pages | 0.38 | 0.58 | `sync_vertex_ram_buffer`, `vertex_range_gpu_stale`, `tlb_reset_dirty` |
| vertex attributes, remap, index rewrite | 0.19 | 0.37 | |
| shader/pipeline lookup | 0.12 | 0.49 | `pgraph_glsl_compare_shader_state`, `vsh_get_field` |
| textures | 0.12 | 0.14 | `pgraph_vk_bind_textures` |
| Vulkan driver (`tu_*`) / descriptors / render pass | 0.15 / 0.03 / 0.01 | 0.09 / 0.05 / 0.02 | |
| **total** | **10.5** | **11.8** | |

The shipping build agrees: the old `a593d8eb85` profiles, read the same way,
give AUF 11.2 and Blinx 15.5 ms/frame (uniforms 4.4 and 6.0, snapshot 3.1 and
3.4) in their windows.

**The debug snapshot does nothing in a release build and is a clean cut.**
`flush_draw_one_pass` (draw.c:7784) copies `pg->regs_` (32 KB),
`program_data` (2 KB) and the rest into a `RenderCommandSnapshot` on its
stack for every draw pass. The copy exists only to `assert` four fields at
the end, under `#ifndef NDEBUG`. The Android CMake passes `-UNDEBUG` to every
release config (CMakeLists.txt:971, kept so QEMU's asserts stay live), so the
copy runs in every shipped build: 2.2-3.4 ms/frame of the PFIFO thread. It
is also why the unwinder cannot get past that frame.

### Where SET_BEGIN_END blocks

| | AUF | Blinx | evidence |
|---|---:|---:|---|
| the flip's display download, waited in draw_begin's `surface_update` | 22.3 | 0.4 | `[cblat]` `dl`; phase `Surf` 24.9; flip474's O1 |
| **inside `pgraph_vk_bind_textures`** | **~8.6** | **~9.6** | `Pipe.Tx` wall 8.7 / 9.7 (exclusive of nested timers) against 0.12 / 0.14 on-CPU; no uploads or hashes in the window (`txu[n0]`, `txh` all 0); `[cblat]` `fin` 0.00 / 0.07, so not a `pgraph_vk_finish` |
| shader bind and uniforms, beyond their CPU | ~0 | ~2.7 | `Pipe.Sh` 3.4 / 6.9 wall against ~3.6 / ~4.2 CPU |
| the rest, not placed | 5-10 | 3-7 | mdraw less on-CPU (lower to upper bound), less the rows above |

What the texture bind waits on is not in this capture:
- There are 41 (AUF) and ~3,700 (Blinx) bind calls per frame, of which
  `txr[... s2td]` counts 0.5 and 2 surface-as-texture binds per frame.
  `bind_surface_as_texture` flushes the queued draws and ends the render pass
  (`pgraph_vk_begin_nondraw_commands` -> `pgraph_vk_ensure_command_buffer`).
- The driver's GPU waits (`wait_timestamp_safe`) are 5.1 (AUF) and 1.5
  (Blinx) ms/frame where sampled. Matched to the thread's last on-CPU sample
  (median 0.5-0.6 ms before), Blinx's start in the draw path (snapshot,
  uniform upload, pre-draw), and 79% of AUF's have no on-CPU sample within
  2 ms.
- 51% (AUF) and 59% (Blinx) of the off-CPU time has no switch-out sample. It
  is mostly intervals of 20 ms or more, and 88% of AUF's follow less than
  2 ms of running. That fits the flip park and the download waits, not
  preemption.

Next measurement: a wall probe on each step of `pgraph_vk_bind_textures` (the
command-buffer begin, the surface bind, the range download check), counted
per frame.

### The answer for #474 (ms/frame; bounds are bounds, not values)

| # | cost | AUF | Blinx | candidate fix | owner |
|---|---|---:|---:|---|---|
| 1 | the flip's display download, waited inside SET_BEGIN_END(begin) | 22.3 | 0.4 | O1: lazy completion of the flip's download | #474 (flip474) |
| 2 | a wait inside texture bind, cause not placed | ~8.6 | ~9.6 | per-step probe of `pgraph_vk_bind_textures` first | #474, with #461's texture counters |
| 3 | uniform upload (hash, compare, copy per draw) | 3.5 | 3.7 | skip unchanged uniform blocks per draw (dirty ranges, not a whole-block hash and copy) | #474 |
| 4 | the debug snapshot per draw pass | 2.5 | 2.2 | guard it with a hakuX debug switch, not `NDEBUG`, or snapshot only the four asserted fields | #474 (a few lines in draw.c) |

Bounds, **not values**. Each assumes the ms leaves the frame one for one, per
flip474's reading that the guest waits on callbacks the PFIFO thread
dispatches late. Each is also capped by the corrected GPU time of the same
window.

| gone | AUF (67.3 ms, 14.9 fps) | Blinx (50.7 ms, 19.7 fps) |
|---|---|---|
| 4 (snapshot) | <= 15.4 fps | <= 20.6 fps |
| 3 + 4 | <= 16.3 fps | <= 22.3 fps |
| all SET_BEGIN_END CPU (10.5 / 11.8) | <= 17.6 fps | <= 25.7 fps |
| that and 2 | <= 20.7 fps | <= 30 fps: the GPU's 33.2 ms and the 2-VBLANK pacing both bind |
| that and 1 | <= 21.5 fps: the GPU's 46.6 ms | (1 is 0.4) |

The PFIFO thread's CPU per draw is real but small. It is 10.5-15.5 ms/frame
across two builds and four windows, and no single piece of it is over 6. The
larger levers are the blocks: AUF's download (22.3) and a texture-bind wait
in both titles (~9). With the clock corrected, the GPU is busy 65-69% of both
frames, so AUF cannot pass ~21.5 fps on its GPU work as it stands.

### Do not repeat (added)

- Do not read `[cblat]`'s or the phase line's per-method time as CPU. On
  these two titles, SET_BEGIN_END's wall is 1.9-4.9 times its on-CPU time.
- Do not take draw-path shares from chains cut at 8 KB without checking the
  entry frames. `flush_draw_one_pass`'s 35 KB debug snapshot stops the
  unwinder, and draw_begin reaches `surface_update` by a tail call.
  `drawcost.py` lists the draw-only functions it keys on, and prints the
  unplaceable share beside the result.
- `puller_lock_ns` (`hakuX-cpu` `Lk`) is the puller's `pgraph.lock` wait.
  It is 0.4-0.6 ms/frame here, so the lock is not the unplaced time.

### State at the end of attempt 7

Both sessions are done, and this lane holds no hold and has nothing queued.
The answer is posted on #474 and #462, and the #462 summary is corrected in
place.

## Attempt 8 (2026-09-27, from 14:40 PDT): the bind_textures wall probe (#474)

Why attempt 7 did not carry this: attempt 7 finished its brief (the #474
breakdown, PR #509, ready). The texture.c grant (hostops, 14:11 PDT) arrived
after that session ended. The resume header naming PR #477 as a draft was
stale: #477 had already folded.

The probe is on its own branch and PR, as the grant asked:
`lane/slowdown462-bindtex`, PR #512, commit 26936d9639. It branches from
this lane's #509 head merged with master (0e0ba23fb9), so the NOTES here do
not conflict with #509's copy.

- `hw/xbox/nv2a/pgraph/vk/texture.c`, `NV2A_PERF_LOG` only (lent from
  lane.remote; its #461 counters are untouched). One `hakuX-stall` line per
  60 guest flips: `txw[f<flips> <s> bt res ct sdl scan faf bs flq nd cp up]`,
  each `ms/flip` and most with `/calls per flip`. Nesting: bt holds res and
  ct; ct holds sdl, scan, faf, bs, cp, up; bs holds flq (draw and reorder
  queue flush) and nd (`pgraph_vk_begin_nondraw_commands`).
- The prime suspect going in, from reading the code: `create_texture` calls
  `pgraph_vk_flush_all_frames` (render-thread idle wait plus every frame
  fence) before a surface-to-texture rebind whenever the node was used in
  the last `num_active_frames` submits. That is a full GPU drain, and it is
  not a `pgraph_vk_finish`, which fits `[cblat]` `fin` reading ~0. `faf`
  measures it. The two `pgraph_vk_upload_surface_data` calls at the top of
  `create_texture` are dead (the line before them clears their condition),
  so they are not probed.
- Pilot: a perflog soak, not a held session. The dispatcher builds
  `26936d9639-perflog` only from a queued request, so a held session would
  have needed the soak first anyway, and the soak's logcat carries `txw[]`
  directly. AUF first: `1-1790543757-slowdown462-3565156` (Nova, 420 s,
  survey route, window 299-420 s as before). Blinx (255-411 s) follows
  once the pilot's lines are read. Both together are under the 30 min
  pilot budget.
- Not compile-checked here: no NDK is reachable from the lane sandbox. The
  dispatcher's build is the compile; an `ERROR` there is the first thing to
  read.

State at the end of this session: waiting on
`1-1790543757-slowdown462-3565156` (eleven requests were ahead of it on
the Nova at 14:56 PDT). No hold held.

## Attempt 9 (2026-09-27, from 15:45 PDT): the AUF pilot read; Blinx queued

Why attempt 8 did not finish: it ended correctly, waiting on the pilot
`1-1790543757-slowdown462-3565156` behind eleven Nova requests. The pilot
finished at 15:39 PDT and this session is the resume. `origin/master` was
merged at the start of this session (#509 had folded, so the PR diff is now
texture.c and these NOTES only).

### AUF: `txw[]` over 299-420 s (Nova, MAX, `26936d9639-perflog`, apk 3883925fc5c0)

`txwwin.py <result> 299 420` (seconds from the first `hakuX-route` line;
34 lines, 2040 flips in 122.6 s = 16.6 fps, 60.1 ms/flip). The frames at
15:38:02 and 15:38:58 are first-person mission play at FPS 16-17: gameplay.
`phasesoak.py` over the same seconds gives phase `Tx` 5.8 ms, `Pipe` 9.8,
`Draw` 18.3, `Surf` 21.1, GPU 25.6 (x1.573 = 40.3).

| step | ms/flip | calls/flip | share of `bt` |
|---|---:|---:|---:|
| `bt` whole `pgraph_vk_bind_textures` | **4.57** | 78 | 100% |
| `res` resolve_possibly_dirty | 0.02 | | 0% |
| `ct` create_texture, all slots | 4.54 | 88 | 99% |
| **`faf` `pgraph_vk_flush_all_frames`** | **4.47** | **0.27** | **98%** |
| `bs` direct surface bind (flq 0.00 + nd 0.01) | 0.02 | 1.00 | 0% |
| `sdl` / `scan` downloads | 0.00 / 0.00 | 0 / 86 | 0% |
| `cp` surface copy / `up` upload | 0.00 / 0.00 | 0 / 0 | 0% |

- **The dominant step is `faf`: 16.6 ms per call (4.47 / 0.27), once every
  ~3.7 flips.** That is a full drain: the render thread's idle wait, then
  every in-flight frame fence. No finish is involved (`[cblat]` `fin` ~0
  agrees), no upload, no copy, no download.
- `up` and `cp` are 0 in the window, so every `faf` in it is the
  surface-to-texture one (texture.c `create_texture`, the
  `snode->submit_time + num_active_frames > submit_count` test before the
  s2t branch), not the upload one. And `bs` is 1.00/flip with `cp` 0:
  every s2t bind here is a **direct** bind of the surface's own image view.
- The direct bind writes nothing into the texture node's image. It ends the
  render pass and puts its own COLOR_ATTACHMENT_WRITE -> SHADER_READ barrier
  on the surface image (`bind_surface_as_texture`). So the drain before it
  protects nothing that path writes. It is needed only before
  `copy_surface_to_texture`, which does write the node's image.
- **Descriptor sets, checked (code reading, line numbers at lane head
  `3d3c22f8c0`).** The direct bind also changes what slot `i`'s
  descriptor points at (`tex_surface_direct_views`,
  `texture_bindings_changed`), so the image-write argument alone does not
  cover it. The descriptor side, from
  `shaders.c:596-750`:
  - A changed binding takes a fresh ring set (`descriptor_sets[index]`,
    written by `vkUpdateDescriptorSets`, then `index++`). The ring rewinds
    to 0 only when nothing submitted is pending and nothing is recording:
    `draw.c:3663` and `3730` after the frame's fence or finish event,
    `draw.c:3838` only with no frame in flight, `draw.c:3446`
    (`flush_all_frames`) only when `!in_command_buffer`, and the ring-full
    paths `shaders.c:604-608`, `713-717` only after `pgraph_vk_finish` +
    `flush_all_frames`. So a fresh set is never one an in-flight frame
    holds, drain or no drain.
  - A cache hit (`shaders.c:699-710`) calls no `vkUpdateDescriptorSets`; it
    binds `ce->descriptor_set` as it is.
  - The s2t drain (`texture.c:2300-2303`) runs inside a recording command
    buffer, so its `flush_all_frames` does not rewind the ring; it changes
    nothing the descriptor path reads.
  So the drain protects no descriptor write either. **One hazard exists on
  this path with or without the drain, and removing the drain does not
  touch it:** a cache hit stores the cached handle into the ring array
  (`descriptor_sets[index] = ce->descriptor_set`), aliasing that ring slot
  to a set another slot owns, and no rewind clears `tex_desc_cache` (only
  the `shaders.c:713-717` ring-full path does). After a rewind, a stale hit
  can bind set S early in the new command buffer and a later miss whose
  ring slot aliases S rewrites S while that command buffer still holds it.
  That is a use-while-recording write in the existing cache, not in the
  drain; it is noted for the fix lane, not measured.
- The whole-soak figure (0-298 s: bt 2.90, faf 2.82 at 0.44/flip) shows the
  same shape in the menus and the early mission.
- The addendum's "~9 ms/frame" was attempt 7's `Pipe.Tx` 8.7 on
  `76cba82fd2-perflog`. In this run the phase `Tx` reads 5.8 and the probe
  reads 4.57 inside it. The remaining ~1.2 ms is in the `Tx` timer but
  outside `pgraph_vk_bind_textures`.

**Candidate fix:** in `create_texture`, take the `flush_all_frames` only on
the copy path (`!can_direct_bind`), not before a direct bind. Owner: a #474
fix lane. texture.c belongs to lane.remote (#461), so the fix lane needs it
lent the way this probe's was. Asked for as Ask 8 in
`dispatch/board-requests/slowdown462.md`.

**Bound (a bound, not a value):** removing the 4.47 ms/flip of PFIFO wall
takes AUF from 60.1 to at most 55.6 ms/flip, i.e. **at most ~18.0 fps**
(from 16.6), if the PFIFO thread sets the frame and nothing refills the
time. The corrected GPU time is 40.3 of the 60.1 ms, so the GPU does not
cap it first. The drain also serializes the CPU and the GPU for ~16 ms
each time, and this probe cannot price the overlap that is lost.

### Blinx: queued

`1-1790549006-slowdown462-1787985`: Blinx, 420 s, survey route, perflog,
`26936d9639`, pinned to the Nova, release priority, no prediction
(attribution probe). The window is 255-411 s, as before. The AUF pilot plus
this soak total about 17 min of device time, which is inside the pilot budget.
When it queued, a forza414 arm was running on the Nova and three Nova
requests (forza414 fix arm, flip474, flip474 fix arm) were ahead of it.
Read it with `txwwin.py <result> 255 411` and `phasesoak.py` over the same
seconds.

State at the end of this session (15:58 PDT): the AUF split is posted on #474
and #462 and Ask 8 (the fix lane) is on the board. Waiting on
`1-1790549006-slowdown462-1787985` (Blinx). On resume: read it with
`txwwin.py`/`phasesoak.py` over 255-411 s, check the frames, post on #474
and #462, run preflight, and mark #512 ready. No hold held.

## Attempt 10 (2026-09-27, from 16:10 PDT): Blinx's `txw[]` read

Why attempt 9 did not finish: it ended correctly, waiting on the Blinx soak.
The soak finished at 15:56 PDT (promoted to
`0-0-x-1790549006-slowdown462-1787985`), and this session is the resume.

**The soak ran on the Thor, not the Nova.** Its `request.json` says
`"device": "thor"` (serial bdc158a5), although attempt 9's NOTES said "pinned
to the Nova". That was a mistake in the enqueue. Blinx has a copy on each
handheld (the Thor's original and the Nova's #462 investigation copy), so the
run is valid, but its ms figures are Thor figures. They are not comparable
one-to-one with AUF's Nova run, and the Thor may have hit a thermal pause
(fps swings 9 -> 25 -> 11 -> 24 inside the window; this soak has no cooling
read to say whether it did). The mechanism answers below do not depend on the
device. The ms figures do.

### Blinx: `txw[]` over 255-411 s (Thor, MAX, `26936d9639-perflog`, apk 3883925fc5c0)

`txwwin.py <result> 255 411`: 41 lines, 2460 flips in 155.9 s = 15.8 fps,
63.4 ms/flip. The frames at 15:54:43 (FPS 26, stage timer 0'40") and 15:56:06
(FPS 22, timer 1'16") are stage play: gameplay. `phasesoak.py`, same seconds:
`Pipe` 15.6, `Tx` 4.0, `Draw` 27.5, `Fin` 14.4 (`Fen` 14.0), GPU 21.5
(Thor timestamps; the x1.573 correction is the Nova's, not applied).

| step | ms/flip | calls/flip | share of `bt` |
|---|---:|---:|---:|
| `bt` whole `pgraph_vk_bind_textures` | **3.36** | | 100% |
| `res` resolve_possibly_dirty | 0.02 | | 1% |
| `ct` create_texture, all slots | 3.18 | 362 | 95% |
| **`faf` `pgraph_vk_flush_all_frames`** | **2.99** | **1.81** | **89%** |
| `bs` direct surface bind (flq 0.00 + nd 0.02) | 0.02 | 2.70 | 1% |
| `scan` / `sdl` downloads | 0.02 / 0.00 | 357 / 0 | 1% |
| `cp` surface copy / `up` upload | 0.00 / 0.00 | 0 / 0 | 0% |

(`bt`'s calls column reads 3112/flip in `txwwin.py`; that is its counter's
own unit, not bind calls, and is not used here.)

Split by the window's fps (`.cap/txwregime.py`, scratch, not committed):

| stretch | lines | fps | ms/flip | `faf` ms/flip | drains/flip | ms/drain | share of flip |
|---|---:|---:|---:|---:|---:|---:|---:|
| slow (<14 fps) | 14 | 11.0 | 90.6 | 1.78 | 1.52 | 1.17 | 2.0% |
| mid | 13 | 17.7 | 56.4 | 2.73 | 1.79 | 1.52 | 4.8% |
| fast (>=20 fps) | 14 | 23.5 | 42.6 | 4.46 | 2.12 | 2.10 | 10.5% |
| AUF (Nova), for scale | 34 | 16.6 | 60.1 | 4.47 | 0.27 | 16.5 | 7.4% |

- **Same dominant step as AUF: `faf`.** Blinx drains ~1.8 times per flip
  for ~1.7 ms each. AUF drains once per ~3.7 flips for ~16.5 ms each. A
  drain waits for the GPU work in flight. Blinx has little queued at each
  one, and the drain grows when the frame is fast, because more GPU work is
  still in flight.
- **Direct binds, not copies.** `cp` 0 and `up` 0 over the whole window,
  `bs` 2.0-3.0 per flip. So every `faf` in the window is the s2t drain before
  a **direct** bind of the surface's own image view, and that bind writes
  nothing into the texture node's image. The drain protects nothing on this
  path, as on AUF: neither an image write nor a descriptor write (see the
  AUF "Descriptor sets, checked" bullet for the ring and cache lines read,
  and the cache-aliasing hazard that exists with or without the drain).
- **flip474's drain-only-on-copy fix (addendum 8) reaches Blinx:** with no
  copies, it removes every drain in the window.

**Bound (a bound, not a value; Thor figures):** removing 2.99 ms/flip takes
the window from 63.4 to at most 60.4 ms/flip, i.e. **at most ~16.6 fps**
(from 15.8). In the fast stretch it is 42.6 -> 38.1 ms, at most ~26.2 fps
(from 23.5). Both assume the PFIFO thread sets the frame and nothing refills
the time. The fix also ends ~2 CPU/GPU serializations per flip, and this
probe cannot price that lost overlap.

What is not measured: the same probe on the Nova. It would give Nova ms
beside AUF's, not a different answer. It is not queued. If #474's fix lane
wants a Nova Blinx baseline, its fix arm's A leg is that baseline.

State at the end of this session: posted on #474 and #462; PR #512 ready.
No hold held, nothing of this lane's queued.
