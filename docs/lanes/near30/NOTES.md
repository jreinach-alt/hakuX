# lane.near30 -- why near-30 titles do not hold 28.5 fps (#433)

Brief: owner 2026-10-02 ~16:25 PDT, "We're close but not quite there yet."
Bar: >= 28.5 fps for >= 90% of the scored window (title_verdict.py, targets.toml).

## Method

`decompose.py <result dir>...` reads only lines every build prints (plus the
perflog lines when the build has them) after `mark gameplay`. One row per 2 s
vCPU telemetry window ([rr425w], [idlehalt], [tlb68]); its frame rate is the
hakuX-pace frame counter over the same 2 s (interpolated between lines, no
rate across a >10 s gap). For a frame of F = 1000/fps ms:

| column | source | meaning |
|---|---|---|
| gbusy / gidle | [rr425w] busy_us, idle_us | guest running code vs in the kernel idle loop (0x8001b02e) |
| vblank/pgraph/timer/disc_ms | [rr425w] per-wake idle | which interrupt ended each idle stretch |
| v_run / v_rq / v_blk | [idlehalt] run_us, rq_us, rest of span | vCPU THREAD on-CPU / runnable but waiting for a core / sleeping (lock or cond wait) |
| Ri | hakuX-perf `Ri:` | PFIFO (render) thread idle per guest frame, waiting for the guest's next kick |
| rthr, rwait | [rwait526] | render thread CPU %, its deferred-wait % |
| lockw | [lock474] rd+wr wait (perflog only) | vCPU waiting on pgraph.lock in PGRAPH MMIO, ms per frame |
| ph_GPU, ph_Draw, ph_Fin, ph_Idle, BE | hakuX-phase, xemu-work (perflog only) | GPU ms/frame, renderer phases, draws per frame |

Read with care: gbusy = F whenever the guest never reaches the idle loop
(Tron), so for such a title the guest split says nothing and the thread split
(v_run / v_blk) and Ri carry the answer.

## Step 1: offline, existing soaks (all Nova, device defaults, no thermal pause)

Runs: Tron 2.0 `0-*-tronhang672-*` (6) and `1790981973-lanelocal-3657361`;
ToeJam & Earl III `1790970734-lanelocal-1022425`. Output: `decompose.out`,
per-window rows `windows.tsv`. 2276276 and 2397053 never left the Xbox Live
sign-in loop (60 fps menus) and are excluded below.

### Per run (2 s rows after the mark)

| run | path | share >= 28.5 (rows) | slow-row median fps | F | v_run | v_blk | Ri |
|---|---|---|---|---|---|---|---|
| tron 2186958 | Auto Load | 0.90 | 27.7 | 36.1 | 28.8 | 7.0 | 15.8 |
| tron 2513164 | New Game | 0.98 | 27.9 | 35.9 | 28.3 | 7.8 | 15.6 |
| tron 2727294 | New Game | 0.67 | 24.0 | 41.7 | 32.0 | 9.0 | 17.5 |
| tron 3184149 | New Game, cold, hung | 0.50 | 22.0 | 45.5 | 33.8 | 10.1 | 19.1 |
| tron 3657361 | New Game, cold, GPL=3 | 0.73 | 23.6 | 42.4 | 31.6 | 10.2 | 16.1 |
| toejam 1022425 | level 1 | 0.99 | (2 rows) | -- | -- | -- | -- |

### Pooled Tron in-level rows (fps < 50; n = 984), medians by frame time

| F band (ms) | n | v_run (vCPU on-CPU) | v_blk (vCPU asleep) | renderer busy (F - Ri) | Ri (renderer idle) | render thread CPU % |
|---|---|---|---|---|---|---|
| < 30 | 508 | 21.2 | 4.7 | 13.0 | 13.1 | 29.6 |
| 30 - 33.3 | 174 | 25.4 | 6.1 | 17.1 | 14.6 | 31.9 |
| 33.3 - 40 | 158 | 28.0 | 7.4 | 19.8 | 15.8 | 31.0 |
| 40 - 50 | 93 | 32.7 | 10.3 | 26.3 | 17.6 | 29.8 |
| >= 50 | 51 | 45.4 | 12.3 | 30.2 | 24.1 | 27.2 |

Correlations over those rows: F with v_run **0.95**; F with v_blk 0.70;
v_blk with renderer busy **0.70**; v_run with renderer busy 0.37. Runqueue
wait (v_rq) is under 0.1 ms per frame everywhere: the vCPU is never waiting
for a core.

### ToeJam & Earl III (the control, 60 fps, share 0.99)

Per 16.7 ms frame: guest busy 11.0, guest idle 9.3 (7.5 of it ended by the
PIT timer, 0.2 by vblank, 0.4 by PGRAPH), vCPU thread on-CPU 16.4 (it spins
in the idle loop, idle-halt is off), asleep 0.35; renderer idle 2.5. Its
headroom to 33.3 ms is 3x. Its two slow rows are a load (disc wakes).

### Thermal and clocks

No run paused. Hottest zone 84-96 C. CPU clocks reached max on every run
(cpu3 to 2803, cpu7 to 3187 MHz). **GPU 401-401 of 680 MHz on every Tron and
ToeJam run**, while the same Nova under the same default regimen goes to 680
for BF2 (`1790983118-lane.bf2push656-*`): the GPU governor saw too little load
to raise the clock. Neither title is GPU-bound.

### Verdict per title, for the frames below the bar

- **Tron 2.0: CPU-bound on the vCPU thread.** The guest never idles; the
  renderer is idle 16-24 ms of every slow frame; the GPU sits at its floor
  clock. About three quarters of a slow frame is the vCPU executing guest code
  (v_run, which tracks F at r = 0.95) and about a quarter is the vCPU thread
  ASLEEP (v_blk), not runnable and not queued -- a lock or condition wait --
  and that sleep tracks the renderer's busy time (r = 0.70). So the vCPU
  partly waits on the render thread. Not pacing: no idle, no vblank waits.
- **ToeJam & Earl III: holds.** 11 ms of guest work in a 16.7 ms frame.

## Step 2a: one Tron perflog capture (run 1 of 3)

`1790983969-lane.near30-3991603`, Nova, ref 59a4b423c0 (master 7e1b471ef1 +
docs), `-Pperflog=true`, PERF_REGIMEN=default, prebuild and pipeline cache as
shipped, the same New Game route as the 0-*-tronhang672 runs
(`tron-newgame.route`, byte-identical to 3657361's). Docked: battery +0.31 W
discharging with USB in 6.31 W (the dispatcher's charging state; I cannot
unplug). Hottest zone 95.1 C, no pause. GPU 401-615 MHz (the first Tron run
to leave 401). Output `tron-perflog.out`, rows `tron-perflog.tsv`.

Written before it ran (in the request's purpose): EXPECT `[lock474]` vCPU wait
on pgraph.lock >= 60% of the vCPU's sleep in below-bar windows, and GPU ms per
frame < 20 there. **Result: the lock half MISSED, the GPU half missed
narrowly.**

| rows | n | fps | F | v_run | v_blk | lockw | GPU | renderer Tot | of it Fin (fence waits) | Draw | renderer idle | draws (BE) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| >= bar | 197 | 38.2 | 26.2 | 20.0 | 5.5 | 0.12 | 14.6 | 18.4 | 4.8 | 5.4 | 7.7 | 667 |
| < bar | 49 | 26.7 | 37.4 | 26.4 | 10.5 | 0.37 | 22.4 | 29.9 | 11.1 | 8.2 | 8.1 | 854 |

Share at the bar 0.80 on this run (perflog adds a clock read per method, so
its fps is not comparable with the plain runs' 0.67-0.73).

Correlations over in-level rows (n = 187): **v_blk with GPU ms 0.64**, with
the renderer's fence waits (Fin) 0.50, with draws 0.38, with the renderer's
CPU-side draw work 0.08, with the pgraph.lock wait 0.13. F with the
renderer's total 0.72; v_run with the renderer's total 0.78.

What the vCPU's sleep is NOT, measured:
- pgraph.lock in PGRAPH MMIO (#474's lock): 0.37 ms of 10.5 ms per slow frame.
- the guest<->PGRAPH skew bound: `fifoskew bound=0 held(n=0)`, it is off.
- read-downloads of GPU-written pages: `[tlb68] rdus` + `rdous` ~9 ms per
  2 s (`[rdc] rdous` ~1.3 ms of it), under 0.2 ms per frame.

What it tracks: GPU time per frame. So the vCPU waits, somewhere, for GPU
work to complete, while the GPU waits for the vCPU the rest of the frame --
CPU and GPU are serialized for about a quarter of every slow frame. That is
also why the Nova's GPU governor keeps the clock at 401 MHz on Tron: the GPU
is idle whenever the vCPU runs, so its average load stays low. Candidate
waits still standing (read from the code, not measured): the BQL (the PFIFO
thread takes it to raise PGRAPH interrupts; every non-RAM MMIO from the vCPU
needs it); pfifo.lock in user_read/user_write (DMA_GET/PUT polls);
`pgraph_vk_process_pending`'s render-thread round trip; the APU's d->lock.

BF2, context only (`1790983118-lane.bf2push656-3848741`, perflog): vCPU
asleep 21 ms of a 64 ms frame with 0.7 ms of pgraph.lock wait. The same
unattributed sleep, twice the size.

## Step 2b: Blinx 2 capture -- WAITING

No lane.local addendum about the owner's save past Test 1 had arrived by
16:50 PDT. Per the brief, not queued. When it arrives: one perflog run,
Nova, device defaults, Continue/Load from the title menu (never reset or
delete the save), walk back and forth >= 600 s, then
`decompose.py <dir>`. Budget left: 2 Nova runs (this lane used 1 of 3).
Expected result to write on it: Blinx 1 history and the OCR'd overlay
(median 27, min 22) make the same split as Tron likely -- v_run the larger
share, some v_blk -- but nothing measured says so yet.

## Step 3: the frame-time budget and the levers

### Tron 2.0, Nova, device defaults (plain builds; 33.3 ms is 30 fps, 35.1 ms is the 28.5 bar)

| ms per frame | at the bar (F < 33.3, median ~27) | slow (F 40-50, median ~43) | slowest 5% (F >= 50) |
|---|---|---|---|
| vCPU running guest code (v_run) | 21-25 | 32.7 | 45.4 |
| vCPU asleep, unattributed, tracks GPU ms (v_blk) | 5-6 | 10.3 | 12.3 |
| vCPU waiting for a core (v_rq) | < 0.1 | < 0.1 | < 0.1 |
| guest idle | 0 | 0 | 0 |
| renderer idle (overlapping) | 13-15 | 17.6 | 24.1 |
| GPU (perflog run, at 401-615 MHz) | ~15 | ~22 | -- |
| **gap to 35.1 / to 33.3** | none | **8 / 10** | 15+ / 17+ |

The guest never reaches the kernel idle loop, so all of a Tron frame is the
vCPU's: either running JIT code or asleep waiting on the GPU side. The
renderer always has idle time; the GPU is not saturated (its clock rarely
leaves the floor). CPU-bound on the vCPU thread, with a CPU/GPU
serialization worth a quarter of the slow frame.

### ToeJam & Earl III (control): median 11.0 ms of guest work in a 16.7 ms frame, the guest reaches the idle loop every frame, vCPU asleep 0.35 ms. Holds at 60.

### Levers, ranked by probability x size (Tron's slow windows; breadth noted)

| # | lever | size if it works | P | evidence for P | expected |
|---|---|---|---|---|---|
| 1 | **Name and remove the vCPU's GPU-side wait** (v_blk) | 10 ms of 43: the median slow window reaches 33 ms alone; BF2 carries 21 ms of the same | 0.3 (0.5 an off-CPU trace names a removable wait x 0.6 it can go without an accuracy cost) | three named causes measured out above; #474 removed a wait of this shape on DOA (`flip474`) | ~3 ms/frame on Tron, ~6 on BF2 |
| 2 | **vCPU JIT throughput: memfast phase 2 (fastmem)**, then the rest of the FEX/Box64-class plan | 20-25% of v_run = 6.5-8 ms of 43 on Tron, on every CPU-bound title | 0.5 | memfast's own profile (GTA, Thor): inline TLB compare 17.4% + softmmu helpers 7.9% of vCPU samples; phase 1 alone measured -4.3/-6.2% work per frame | ~3.5 ms/frame, broadest |
| 3 | GPU clock: let the serialized GPU run faster (regimen, or fixing #1 so devfreq sees real load) | shortens v_blk by the GPU's share; GPU 22 ms at 615 vs ~34 at 401 | 0.3 | v_blk-GPU r = 0.64; GPU 401-401 MHz on all 7 plain Tron runs and ToeJam | ~1-2 ms; mostly subsumed by #1 |
| 4 | vCPU on the prime core (cpu7, 3187 vs 2803 MHz) on the NOVA | up to 12% of v_run, ~4 ms | 0.2 | refuted on the Thor (vcpuprime428: -21.5%, thermal ejection); the Nova never pauses, so untested there | ~0.8 ms |
| 5 | ibcache (merged, off) | TB lookups are a share of v_run | 0.15 | GTA neutral (x1.021), Forza FAIL (x1.10) | small |
| 6 | push constants (bf2push656), the ubershader | renderer CPU work and compile stalls | 0.05 for this bar | Tron's renderer has 8-24 ms idle per frame; v_blk does not track renderer CPU work (r = 0.08); compile stalls are hitches, not the steady share | ~0 |

Ranking note. #1 and #2 tie on expected ms for Tron. #1 is first because
its first step is one measurement that decides it, and the same sleep is
twice as large on BF2; #2 is the approach that fits the hardware and should
start no later -- it is stranded on board grants (`hw/xbox/xbox.c`,
`target/i386/.../excp_helper.c`) and an unfinished F0a microbenchmark, not
on evidence (origin/lane/memfast NOTES). Neither alone clears Tron's slowest
5% (17+ ms to find); together they reach ~10-11 ms on the median slow window.

## Successor brief (lever 1)

    Lane: vcpuwait433   Issue: #433   Device: Nova, 3 runs   Territory: docs/lanes/vcpuwait433/** (+ a grant if a fix lands)

    # Name the wait that puts Tron 2.0's vCPU to sleep for a quarter of every slow frame

    lane.near30 (docs/lanes/near30/NOTES.md) measured Tron 2.0 on the Nova:
    in windows below 28.5 fps the vCPU thread is asleep (not runnable, not
    queued) 10 ms of a 43 ms frame, and the sleep tracks GPU ms per frame
    (r = 0.64), not the renderer's CPU work (0.08). Measured out: pgraph.lock
    (#474, [lock474] 0.37 ms), the fifo skew bound (off), read-downloads
    (~0.15 ms). BF2 shows 21 ms of the same in a 64 ms frame.

    1. ONE capture that names the wait: an off-CPU callchain profile of the
       vCPU thread (lane.slowdown462's method, docs/lanes/slowdown462/
       capture_profile.sh: the trace that found DOA's pgraph_read lock), Tron
       New Game route (docs/lanes/near30/tron-newgame.route), 60 s inside the
       in-level window. Host-operated: ask lane.local/the host to run it
       under hold.sh. Expected: >= 70% of off-CPU stacks under one of
       bql_lock (which caller), user_read/user_write's pfifo.lock,
       pgraph_vk_process_pending's qemu_event_wait, or the APU's d->lock.
       If no single site holds >= 50%, stop and report the split.
    2. If one site owns it: say why the vCPU waits there (what the guest
       touched), whether the wait is required for correctness (a golden or
       title that needs it), and the smallest change that drops it, as the
       #474 fix did for DOA (release the lock across the fence wait).
       Register a Tron + BF2 prediction (share at the bar, v_blk per frame
       from docs/lanes/near30/decompose.py) before any arm.
    3. Do not touch the JIT (memfast owns that), the renderer's draw path
       (bf2push656) or the shader path (ubershader lane).

## For the next lane: do not repeat

- Reading guest busy/idle ([rr425w]) on a title whose guest never idles: it
  is F by construction. Use the vCPU thread split ([idlehalt] run_us/rq_us)
  and the renderer's idle (Ri) instead.
- Suspecting pgraph.lock, the fifo skew bound or read-downloads for Tron's
  vCPU sleep: all three are measured out above.
- Expecting simpleperf from a dispatched soak: `profile_guest.sh` drives the
  device directly; a lane cannot run it. Ask the host.
- Older Blinx 2 Nova runs (idlehaltdefault, retreason425, slowdown462) have
  no `mark gameplay`; they cannot be decomposed.

## Files

`decompose.py` (the reader), `decompose.out` / `windows.tsv` (the 8 plain
runs), `tron-perflog.out` / `tron-perflog.tsv` (run 1), `tron-newgame.route`
(copied from origin/lane/tronhang672), `peek_runs.py`, `peek_rdc.py` (scratch
readers).
