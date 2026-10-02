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

## Step 2: captures

(in progress -- see below)
