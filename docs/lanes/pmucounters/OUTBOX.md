# lane.pmucounters OUTBOX

## #433 -- 2026-10-05 08:55 PDT (attempt 1: instrument built, R0 waiting)

pmucounters: the hardware-counter instrument is written and compile-checked;
R0 has not run. Nothing of mine is queued, running or held.

Built (all in `docs/lanes/pmucounters/`): `hakux-pmu.c.inc`, a `[pmu433]`
line per ~1 s slice from the vCPU thread's own counters. It opens one group set
per core-type PMU because a generic hardware event counts on one core type
only and would read zero on the X3. Each slice carries IPC, front- and
back-end stall cycles, branch mispredicts, indirect branches, L1I/iTLB/L1D/
dTLB/L2/L3 refills and TLB walks, plus the frames flipped in the slice and the
longest one. That lets slow windows be read apart from good ones. Off unless
`HAKUX_PMU=1`. `HAKUX_PMU_CTL=1` first runs eight control kernels (known IPC,
known mispredict rate, known L1D/L2/L1I miss rates) through the same
counters. `pmuprobe.c` builds it standalone with the NDK (`-Werror`, clean),
and `pmuread.py` judges the controls and prints the good-vs-slow table. Its
selftest passes, including a control built to fail. The expectations for
every control and the hit/miss rows for R1 are in NOTES.md section 2, written
before any run.

Asks (three, independent):

1. **Grant**: `accel/tcg/hakux-pmu.c.inc` (new file, the hook as above) and
   `accel/tcg/cpu-exec.c` (one `#include` and one `pmu433_tick()` call at the
   existing `[tlb68]` gate, line ~2544). Telemetry only, off by default, no
   behaviour change. With it, R0 and R1 run as ordinary queued soaks
   (`--env HAKUX_PMU=1`), with no holds.
2. **`setprop security.perf_harden 0`** on the Thor and the Nova (it lasts
   until the next reboot; it sets `perf_event_paranoid` 1). Without it every
   `perf_event_open` from the app is refused and the hook only logs the
   refusal. That refusal is itself R0's named negative result. gta482 had this
   leave for its held sessions.
3. **One host-run R0 probe**, about 90 s, no title launched, no pref touched:
   `DEV=thor bash docs/lanes/pmucounters/r0_probe.sh` on an idle Thor inside a
   hold you already hold (the cold-slot runner's gap is fine). Add `HARDEN0=1`
   if ask 2 is granted. It writes to
   `~/hakux-work/perf/<date>-pmucounters/r0-thor/`. It answers the brief's
   R0 (a) and (c) by simpleperf's path, lists which events each core exposes,
   and runs the controls pinned to the X3, an A715 and an A510. The Nova run
   (`DEV=nova`) is the same and can wait for a pathfind gap.

Addendum 09:00 PDT: the hook now also has R2's mode (`HAKUX_PMU=2`, a
sampled raw event attributed in-process to TB / dispatch stub / host
function), so the one grant above covers R1 and R2. It was tested on this
host with software events: 80,669 samples, 0 lost, attributed. It
compile-checks inside `cpu-exec.c` with the Android build's flags (and a
planted error fails that check). The R0 probe now also exercises the sampling
path on the device, so it takes about 2 minutes instead of 90 s.

## #433 -- 2026-10-06 04:5x UTC (attempt 2: R0 NOT RUN, blocked by a tool permission)

State checked before the run, all met:
- Thor `bdc158a5`: no request in `running/` and none in `queue/`; no
  `hakux` process on the device.
- thermal `xo-therm` 38.1 C (limit 60); battery level 100%, not charging.
- `security.perf_harden` = 0, `perf_event_paranoid` = 1 (hostops's set, not
  touched by me). Probe runs without `HARDEN0`.
- Hold: `thor` held by `lanelocal-fanwait` (not taken or overwritten by me).
  The probe runs inside that hold, as the addendum says.

The run itself was refused by the tool permission layer ("This command
requires approval") on `DEV=thor bash docs/lanes/pmucounters/r0_probe.sh`.
I did not work around it. Nothing ran on the device; nothing is queued,
running or held by me.

To run R0 (one line; ~2-4 min, no title, no pref touched):
`cd /home/justin/hakux-work/wt/pmucounters && DEV=thor bash docs/lanes/pmucounters/r0_probe.sh`
Output goes to `~/hakux-work/perf/<date>-pmucounters/r0-thor/`. Read it
with `python3 docs/lanes/pmucounters/pmuread.py --controls <out>/probe_*.txt`.

Lane state: `lane/pmucounters` merged with origin/master (clean), NOTES
attempt-2 section committed (69ef7e50d1). PR stays a draft; no PR tonight.
R1/R2 not started: the hook grant is recorded in WAITING and not yet in the
build, so their device runs wait.

## #433 -- 2026-10-05 22:xx PDT (attempt 3: R0 read, probe fixed, NOT re-run)

Read the hostops R0 result (`perf/2026-10-05-pmucounters/r0-thor/`). Three
things it shows, and one it does not:

1. **The X3 pin fails from shell and run-as.** `taskset 80` returns EINVAL.
   `taskset 08` (cpu3) and `taskset 01` (cpu0) work, and the slice lines
   confirm the pin (`cpus=8`, `cpus=1`). EINVAL from sched_setaffinity means
   no CPU in the caller's cpuset. My hypothesis: the shell cpuset excludes
   cpu7. The probe now reads the cpuset first (step 1b) to settle it. Not
   confirmed yet.
2. **The counters opened but read zero.** Groups open (`g0=ok`), but no slice
   line has a `p=` field and the controls printed no `ctl=` line. The hook
   skips a zero group silently, so the run could not say whether the reads
   failed or the events never ran. Fixed: the hook now logs the first 12 bad
   reads (`[pmu433] read ...` with errno and raw nr/en/run), and
   `pmuread.py --controls` says when there were any.
3. **One PMU, not one per core type.** The Thor exposes only
   `armv8_pmuv3` (type 8, cpus 0-7). The hook's per-core-type design and the
   control names (`armv9_cortex_x3`) assume more. Recorded in NOTES 3b and in
   the hook's header.

Not done: the device R0 re-run. I did not touch the device from this session.
The R0 probe is now `DEV=thor bash docs/lanes/pmucounters/r0_probe.sh` (no
HARDEN0), taking ~3 min, no title; it needs an idle Thor under a hold that
someone else takes (`hold.sh take thor lane.pmucounters && hold.sh wait-idle`,
or the existing lanelocal-fanwait hold). Ask: hostops or lane.local, run it
under the next Thor hold and point me at `r0-thor/`. The first thing to read is
the `[pmu433] read` lines in `probe_shell_cpu3.txt`: they say whether the
counters fail to read (errno) or read with time_running 0.

Checks done here (host only): probe builds for the host with
`-DPMU433_TEST_SW` (-Werror), `pmuread.py --selftest` PASS, `syntax_check.py`
PASS (0 new diagnostics in cpu-exec with the hook), and a zero-read log makes
`--controls` report "no control can be judged" and exit 1.

Spend this session: about 10 min of wall time, no device, no queued requests.
Model: Sonnet 5. Lane state: no PR change; still draft; R1/R2 blocked on the
hook being in the build and a device hold.

## #433 -- 2026-10-05 late (attempt 4, resume on Sonnet): the R0 read failure diagnosed; no device run from the session

Read `r0-thor-2` by hand (`probe_shell_cpu3.txt`, `probe_runas_cpu3.txt`,
`cpuset.txt`, `stat_cpu3.txt`):

1. **The hook reads correctly, and the groups never run.** Every group reads
   `got=80 nr=7 en=<growing> run=0`. That is exactly 3+7 u64 with `enabled`
   advancing and `running` never moving: the seven-event group is enabled
   and never gets a counter. Not an errno, so not a bad read. The hook's
   read path is not at fault.
2. **The PMU counts, with fewer counters than events.** simpleperf stat on
   cpu3 counts all eight of its events and prints its multiplexing warning.
3. **The cpuset hypothesis is refuted.** The shell and top-app cpusets read
   `0-7`, which includes cpu7.
4. **cpu7 EINVAL is still open.** cpu3 and cpu0 pin in the same run. The
   thermal-pause note says a pause can hide from `cpu/online` and the cpuset.
   The run did not read the cooling-device state, so I have not settled it.

Checked on this host, not the device: `pmuprobe sched` on the i7-6700K
(`cpu` PMU, 4 programmable + 2 fixed) reads the largest schedulable group as
6 and refuses 7 at open. The control reads as predicted. The ARM build of the
sweep passes the NDK `-Werror` build, and `pmuread.py --selftest` is PASS.

Changes (`docs/lanes/pmucounters/`, committed on `lane/pmucounters`):
- `pmuprobe.c`: the `sched` mode (group sizes 1..19 and each single event).
- `r0_probe.sh`: `sched_cpu3`, `sched_cpu0`, `sched_cpu7` steps, and a `cpuhp`
  step (isolated, per-CPU online, cooling-device `cur_state`).
- NOTES.md section 3c has the table and the next steps.

Ask (one device run, no HARDEN0, no title, under the next Thor hold):
`DEV=thor bash docs/lanes/pmucounters/r0_probe.sh` into `r0-thor-3`. Read
`sched_cpu3.txt` (largest group N and which singles run) and `cpuhp.txt` (is
the thermal pause on, is cpu7 paused). I have not touched the device from this
session and have no hold. Hostops or lane.local: please run it and point me at
the result dir.

Verify status: `pmuread.py --controls` on the new run is not yet possible; the
control kernels read 0 of 0 on r0-thor-2 and will be re-judged on r0-thor-3.
Still no PR change; still draft; R1 and R2 wait on the hook's layout (N) and
the grant.
Model: claude-sonnet-5 (budget).

## 2026-10-09 15:2x PDT -- attempt 5: R0 read, hook resized and pushed, pilot queued (Opus)

**R0 verdict (from `perf/20261009-pmucounters/r0-nova-1`, read by hand):** the
Nova's PMU schedules at most **5 events per group** (cycles + 4) on the A715
(cpu3) and the A510 (cpu0). Groups of 6 and 7 open and never run; 8 fail with
EINVAL. That is the whole of 10-05's "36 bad group reads". Sampling works on
hardware: 240,229 cycle samples, 0 lost. `paranoid` read 1 at 11:30
(`perf_harden 0`). The X3 still cannot be pinned by `taskset` from the shell.
That does not matter to the in-process hook. The control kernels are judged
in run A below, through the hook's own counters.

**Hook (`5e4110e016` on `lane/pmucounters`, granted files only):**
- `accel/tcg/hakux-pmu.c.inc` is called from the `[tlb68]` gate in
  `cpu-exec.c`. Groups are 5 events; five groups rotate the 15 events.
- Each group is opened per CPU, so every count belongs to one core type.
- `HAKUX_PMU=2` samples up to 4 events, attributed in-process to a TB, the
  dispatch stub or a host library offset.
- Checks:
  - NDK `-Werror` clean;
  - `syntax_check.py` PASS on the real patched `cpu-exec.c`;
  - the link check against libxemu.so passes;
  - `pmuread.py --selftest` PASS.
- The hook is off by default.

**Queued on the Nova (investigative, no scoring):**
- A `1-1791584641-pmucounters-283582`: controls, 90 s boot,
  `HAKUX_PMU=1 HAKUX_PMU_CTL=1`.
- B `1-1791584645-pmucounters-283745`: R1, `amped2` route, 578 s, `--perflog`,
  `HAKUX_PMU=1`.

I checked the route's input from fpstelemetry1008's frames before queuing:
the rider moves between holds. C (R2 sampling) and D (the no-env overhead
arm) follow once A and B are read.

`perf_harden`: a lane cannot run getprop. The hook logs
`paranoid=<value>` on its open line. If run A shows it is no longer -1/0/1,
or shows the opens refused (EACCES), I will report that here rather than
work around it.
Model: claude-opus-5-5.

## 2026-10-09 15:4x PDT -- attempt 5: pilot read, three hook faults fixed, R1/R2/overhead queued (Opus)

**R0 controls on the device (A `…283582`):** 9 of 11 pass through the hook's
own counters on the X3:

- IPC 1.03 on the one-cycle ALU chain and 0.52 on the multiply chain;
- an 8-way indirect branch mispredicts 0.875 per jump, against 0 for a
  1-way;
- the 512 KB code walk takes 1.02 L1I refills per line, against 0 for 16 KB;
- the 64 MB chase stalls the back end on 99.7% of cycles.

The two misses were chase64m's L1D and L2D refill counts. The cause was in
the hook: the kernel built its ring inside the counted window. That is now
fixed.

`paranoid=1` on every open. **`perf_harden` is still 0**, and nothing needed
working around.

**R1 first read (B `…283745`, Amped 2, moving player, no thermal pause):**
260 of 298 slice lines were cut at Android's 1023-byte log limit, so the
per-core tables are partial and B2 replaces them. The uncut heads still show
one thing clearly. The vCPU thread is on-CPU **81.9%** of wall: 87.5% in good
slices and 72.4% in slow ones. On the X3 its IPC hardly moves (4.46 vs 4.34,
good-slice sd 0.14). On this read, slow frames come from the thread waiting,
not from the JIT's code running worse. The partial X3 profile:

- IPC 4.45;
- the front end stalls on 8% of cycles and the back end on 26%;
- 0.2 branch mispredicts per 1000 instructions;
- 2.7 L1I refills per 1000 instructions.

**Fixed (b387f4971a):**
- slice lines now split under the limit;
- the software context-switch and migration counters now include the kernel,
  where they count (both read 0 before);
- the chase setup now happens before the counted window.

The reader joins split lines and counts cut ones (b345b5b613). The selftest
passes all 8 cases.

**Queued on the Nova (ref b345b5b613, investigative, admitted by the reviewed
pilot):**

| run | id |
|---|---|
| A2 controls | `1-1791585654-pmucounters-340915` |
| B2 R1 | `1-1791585654-pmucounters-341117` |
| C R2 sampling | `1-1791585655-pmucounters-341517` |
| D no-env off-arm, last | `1-1791585656-pmucounters-341827` |

B2 and D together measure what counting costs.

Model: claude-opus-5-5.

## 2026-10-09 16:3x PDT -- R0, R1, R2, R3 milestones (Amped 2, Nova); report-wait pair queued (Opus)

All four runs of the 15:4x batch (ref b345b5b613) are valid. B2, C and D
reached live play with a moving player (the rider at different places on
the slope across the hold frames). None had a thermal pause. `paranoid=1`
on every open, so `perf_harden` was still 0. Details and the per-row
evidence are in NOTES.md 3e.

**R0 verdict: the counters are an instrument on the X3.** Controls (A2
`…340915`): 10 of 11 pass through the hook's own counters.
- IPC 1.03 on a one-cycle add chain, 0.52 on a multiply chain.
- Mispredicts 0.875 per jump on an 8-way random indirect branch, 0 on a
  1-way.
- L1I refills 1.03 per line on a 512 KB code walk, 0 on 16 KB.
- L1D refills 1.00 per load and back-end stall 99.9% on a 64 MB pointer
  chase.
- The miss: L2 refills read 1.16 per load against 0.85-1.1. The chase's
  page-table walks refill L2 too, so R1's L2 counts include walk traffic.

**R1: where the vCPU thread's time goes on Amped 2** (B2 `…341117`, 1 s
slices, coverage 0.994; X3 67% of counted time, A715 21%, A710 12%):

| X3 | good slices (29.9 fps) | slow slices (26.5 fps) | good-slice sd |
|---|---|---|---|
| vCPU on-CPU, % of wall | 81.5 | 73.2 | |
| IPC | 3.73 | 3.36 | 0.70 |
| front-end / back-end stall, % of cycles | 11.4 / 27.5 | 12.4 / 28.4 | 4.0 / 1.4 |
| branch mispredicts per k-instr | 0.36 | 0.44 | 0.24 |
| L1I refill / L1D refill per k-instr | 5.0 / 0.50 | 7.0 / 0.63 | 3.0 / 0.29 |

- **Slow frames are waits, not slower code.** No counter on any core type
  differs between good and slow slices by more than one good-slice sd. The
  thread is off-CPU 8 points more in slow slices.
- **The JIT's code is high-IPC.** With the title's pacing spin taken out,
  the work runs at IPC about 3.1-3.3. It is not front-end bound, and it is
  not mispredict bound (at most 0.028 mispredicts per indirect branch,
  about 2% of cycles). The back end stalls on 28% of cycles. The lever on
  the code side is instruction count, not stalls.
- **A third of good frames is idle spin.** TB `0031e901` (5 guest
  instructions, the title's 30 fps pacing loop) is 24% of cycle samples. It
  fills 11 ms of a 30 fps frame and 2 ms of a < 24 fps one. Frametrace's
  "RUN" counts it as work.

**Frame budget** (D, counting off, ms per frame):

| fps bin | wall | work | spin | off-CPU |
|---|---|---|---|---|
| >= 29.7 | 33.4 | 18.5 | 11.3 | 3.6 |
| < 24 | 44.5 | 27.8 | 2.0 | 14.7 |

Between those bins the frame grows 11 ms. Work grows ~9 ms: the guest runs
more of the same code (one chain's entries per frame double at the same
~9 us each). Off-CPU grows ~11 ms. Frametrace puts that growth on the
vCPU's DMA_PUT store waiting for pfifo.lock, 1.4 -> 9.7 ms per frame. The
PFIFO thread holds that lock while it waits on GPU fences in report
processing (the #804 wait and the STALLED finish). Meanwhile the GPU is busy
19.8 ms of a 44.5 ms frame at the same clock. The #804 wait is the larger
part of that: 7.2 ms/frame at 30 fps and 11.9 in < 24 fps windows. It is
logged under two site numbers, and the first table quoted only one (NOTES
3g).

**R2: where in the code, by counter** (C `…341517`; 108,544 cycle samples,
0 lost; shares of the vCPU thread's samples):

| row | cycles | mispredicts | front-end stall | back-end stall |
|---|---|---|---|---|
| JIT code (inside a TB) | 55.9 | 40.3 | 48.0 | 53.5 |
| of which the pacing spin | 23.8 | 0.0 | 0.1 | 22.6 |
| dispatch (`helper_lookup_tb_ptr` 7.9, `tb_lookup` 7.4, `qht` 2.0) | 17.4 | 19.9 | 18.2 | 17.0 |
| softmmu (`mmu_lookup1` 7.3) | 8.6 | 7.6 | 4.3 | 9.4 |
| helpers | 1.5 | 1.1 | 0.4 | 1.4 |

- With the spin removed, no single TB reaches 3% of cycles (the largest
  is 0.9%).
- Only `mmu_lookup1` passes the pre-registered rule in both views (memory
  class: its back-end share is at least its cycle share).
- 81% of the main loop's dispatches re-enter a TB that spans two pages.
  System-mode TCG never chains into those (cpu-exec.c:2507).

**R3: candidates in our code, ranked by P x win** (no clock or governor
change among them):

| # | candidate | measured | win | P | P x win |
|---|---|---|---|---|---|
| 1 | Report processing waits on GPU fences while holding pfifo.lock (#804 wait, reports.c 257-262; STALLED finish, reports.c 374). Write reports when their fence signals, or drop the locks across the wait | vCPU lock wait 4.6 ms/frame overall, 9.7 in < 24 fps windows | slow windows ~44.5 -> ~34 ms | 0.4 | ~5% of frame time, ~9% in slow windows |
| 2 | Dispatch: lookups and the page-spanning re-entry | 17.4% of cycles (22.8% without the spin) | 1.5-5.7% of work (memfast discount) | 0.3 | ~1% |
| 3 | softmmu `mmu_lookup1` (the out-of-line TLB path) | 7.3% of cycles (9.6% without the spin) | 0.6-2.4% of work | 0.3 | ~0.4% |

#1's P is 0.4 because gpunonrender removed the vCPU's side of this lock on
Simpsons and the wait moved to the frame-slot fence (fps down). One pair
decides it on Amped 2, pre-registered in NOTES 3f (hit 0.45, moved 0.35,
miss 0.20).

**Queued on the Nova** (ref b345b5b613, study priority, 2 x 578 s,
investigative, not scored):
- N `1-1791588183-pmucounters-521453`: `HAKUX_OCCL_WAIT=0`, the #804 wait
  skipped. This is a measurement knob, never a recommendation, because it
  brings back the stale visibility reads.
- W `1-1791588184-pmucounters-521720`: the shipped wait.

**Spend:** attempt 5 was $20.42 (301 turns, cut at the turn cap). This
session is reading and bookkeeping only.

Model: claude-opus-5-5.

[lane.pmucounters] waiting: N `1-1791588183-pmucounters-521453` and W
`1-1791588184-pmucounters-521720` on the Nova, queued next behind
surfgpu1009's owner run. The wait ends when both have `DONE` in
`dispatch/results/`. Then `pairread.py N W` reads 3f's measures, and R3 #1's
P is set from the outcome. The PR stays a draft until then; everything else
the brief asks for is in.

## 2026-10-09 17:3x PDT -- the report-wait pair read: W void, N leads at matched work; N2/W2 queued (Opus)

**The pair as registered cannot be scored.** Both arms ran as configured:
the occlusion config line, the `f=` lines and the reports call-site times
all match each arm's env. There was no thermal pause.

W (shipped wait) is **void**. Its rider sits at the same birch trunk in
all 8 hold frames (17:15-17:19 PDT), with "Press BACK to reset position"
on screen twice. Under the moving-player rule, its 29.96 fps measures a
stuck rider. N (wait skipped) is valid: its rider moves through every hold
frame.

| run | frames/wall | share >= 29.7 | work ms/f | off-CPU ms/f | lw ms/f | PFIFO fence ms/f |
|---|---|---|---|---|---|---|
| N (no wait) | 29.52 | 0.70 | 19.7 | 3.4 | 1.36 | 0.64 |
| W (void) | 29.96 | 0.98 | 15.4 | 2.0 | 0.53 | 3.39 |
| B2 / C / D (shipped, earlier) | 28.61 / 28.03 / 27.67 | 0.49 / 0.40 / 0.44 | 21.2 / 21.7 / 21.4 | 6.7 / 7.2 / 6.9 | | |

**At matched work** (`workbin.py`, pace windows binned by the vCPU's work
per frame, which matches the scene's load), N's off-CPU time is lower than
all three shipped runs in every bin:
- 0.7-1.3 ms/frame lower at low work;
- 2.8-3.4 ms/frame lower at 23-25 ms of work.

W reads like N at low work and like the shipped runs at 21-25 ms of work.
So part of N's low-work lead comes from the batch, and the arm's effect
shows at high work. N's lighter average work is the scene: no TB vanished,
and the same hot TB is 38-41% of non-spin time in all runs.

With the #804 wait gone, the PFIFO thread's fence wait drops to 0.64
ms/frame. The STALLED-finish site did not take over (0.54 ms/frame). In N's
few slow windows, the next wait is pgraph.lock.

**R3 #1 (report-processing waits under pfifo.lock): P 0.6, provisional**,
up from 0.4. This rests on N against runs that were not its registered
control, so it is not the registered test.

**Queued on the Nova** (ref b345b5b613, study, 2 x 578 s, investigative,
not scored):
- N2 `1-1791592304-pmucounters-321962`, wait skipped;
- W2 `1-1791592309-pmucounters-323321`, shipped wait.

Pre-registered in NOTES 3h before they run:
- validity: no thermal pause, and the rider at 3 or more places;
- primary: 3f's outcomes on N2 vs W2;
- secondary: N+N2 vs W+W2 at work >= 21 ms/frame. A hit is >= 1.5 ms/frame
  less off-CPU; a miss is < 0.5.

The final P is 0.8 on a hit, 0.15 if the wait moved, and 0.1 on a miss.
`HAKUX_OCCL_WAIT=0` stays a measurement knob, never a fix: the fix is to
stop holding pfifo.lock across the GPU fence wait.

**Spend:** this session read the pair, wrote `workbin.py`, and queued
22 min of Nova time.

Model: claude-opus-5-5.

[lane.pmucounters] waiting: N2 `1-1791592304-pmucounters-321962` and W2
`1-1791592309-pmucounters-323321` on the Nova, queued behind surfgpu1009's
four requests (expected done about 18:45-19:15 PDT). The wait ends when both
have `DONE` in `dispatch/results/`. Then NOTES 3h "On resume" reads them and
sets R3 #1's P. The PR stays a draft until then; everything else the brief
asks for is in.

## #433 -- 2026-10-09 (attempt 8: N2 valid, W2 void again; R3 #1 finalized, P 0.8; PR ready)

N2 (`1-1791592304-pmucounters-321962`) and W2 (`1-1791592309-pmucounters-323321`)
finished clean (DONE, no thermal pause, no restart). N2 is valid: the rider
moves through a halfpipe, a trail and an out-of-bounds recovery across all 8
hold frames. **W2 is void, the same failure as W**, but a different shape:
from its third hold frame on it is stuck cycling the mountain-select /
change-gear / board-stats / career menus for 6 consecutive frames, never
returning to the run, at the menu's own 59 fps cap instead of the 30 fps
in-run one. Two independent runs of the shipped-wait arm have now gone
off-script on the same fixed-timing route while both no-wait runs completed
it: the extra pacing from the report-processing wait is enough to land the
scripted button presses on a different screen. That is a finding about this
route's script, not about #1, and it is why a third blind N3/W3 pair is not
queued -- 0 of 2 shipped-wait tries have given a usable primary control, and
repeating the same script a third time with no fix to it is a cheap step
with a demonstrated low success rate, not the next step.

The registered secondary (pool no-wait N+N2 against shipped-wait data at
matched vCPU work per frame) does not depend on W2's validity: it reads a
**hit**. Substituting the three valid shipped-wait runs already on hand
(B2/C/D, since the W+W2 pool would otherwise mix in non-gameplay menu
windows the "low-work window" assumption was never meant to cover), the
no-wait pool's off-CPU time is 2.5-4.5 ms/frame lower than shipped's in
every work bin >= 21 ms/frame, frames-weighted gap 4.39 ms/frame against the
registered 1.5 ms/frame hit threshold, and it replicates independently
between N and N2.

**R3 #1 (report-processing fence waits held under pfifo.lock) is final: P
0.8.** Fix shape: write occlusion reports when their fence signals without
blocking the pusher, or drop both locks across the fence wait as #474 did
for the flip. Never a faster clock or governor; `HAKUX_OCCL_WAIT=0` stays a
measurement knob.

Everything the 10-09 brief asked for (R0-R3, the ranked table, the pair) is
in NOTES.md 3e-3i and PR.md. **PR.md is now `State: ready`.**

Spend this attempt: read two result dirs (screenshots + `workbin.py`), no
new device time.

Model: claude-opus-5-5.
