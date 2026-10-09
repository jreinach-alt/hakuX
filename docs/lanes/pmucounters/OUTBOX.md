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
