# lane.slowdown462 -- per-title frame-time attribution (#462)

Five slow titles, one protocol, one device (Nova ee317437, MAX). Measure and
attribute only; fixes go to the per-title lanes.

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
| GPU (Rnd 19.4, Xfr 19.3; 9 render passes) | 38.3 | 51%, overlapped |
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
| GPU | 29.0 ms (Rnd 14.4, Xfr 14.6) |
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
| GPU (GR 20.0) | 23.3 ms |
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
| GPU (GR 16.7) | 17.0 ms |
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
| GPU (GR 18.0, GX 2.4) | 20.2 ms | 19.2 |
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

## Summary (Nova, MAX, e5db66fa37 soaks / a593d8eb85 profiles)

| title | fps (soak window) | sets the frame | top cost (ms/frame, share) | owner | bound if it goes |
|---|---|---|---|---|---|
| DOA1U | 13.2 | the flip's GPU wait under `pg->lock`; guest blocks in `pgraph_read` | 34 (49%) | #474 | <= 26 fps |
| AUF | 15.1 | vCPU (94% on-CPU) | exec-loop returns 42 (63%) | #425 / #412 | <= 34 fps (<= 30 at its pacing), if the returns are overhead |
| Blinx | 17.2 | vCPU (73% on-CPU, 27% blocked) | exec-loop returns 21.7 (36%) | #425 | <= 26 fps (<= 30 with the blocked time too) |
| Blinx 2 | 28.9 | at its 2-VBLANK cap | exec-loop returns 13.5 (40%) | #425 | none above the 30 cap |
| Forza | 23.0 | PFIFO (waits on deferred downloads) | deferred download finishes 18.1 (51%) | #414 | <= 30 fps (pacing) |

Two mechanisms cover four titles: the exec loop between TBs on the vCPU (AUF,
Blinx, Blinx 2; Forza's variant is the indirect-jump lookup), and PFIFO waits
for the GPU inside `pg->lock`, which the guest's `pgraph_read` then waits
behind (DOA at the flip, Forza and Blinx 2 at surface downloads).

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
- Do not end a session waiting on a background task: attempt 1 did, and
  nothing resumed it for the ~25 min after the Nova came back.
  `systemd-run` and `setsid` are refused by this lane's permissions; a held
  session fits in one foreground call if the hold is taken during the
  running request and handed to the script (`.cap/prof.sh` pattern:
  release and re-take in the same call).
