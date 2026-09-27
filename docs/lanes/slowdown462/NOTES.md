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
- Next: Blinx, Blinx 2, Forza once lane.xbox posts "verified on the Nova";
  one soak each (release priority, pinned nova, survey), then one `OFFCPU=1`
  session each at `mark play` + 60 s (their pass-1 shots show gameplay after
  the mark: Blinx and Blinx 2 in a level, Forza's race clock starting ~30 s
  after it).

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
