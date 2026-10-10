# lane.pmucounters (#433): hardware counters on the vCPU thread

Brief: `briefs/pmucounters.md` (owner, 2026-10-05). Make the table that says
why the JIT's code is slow (front-end, back-end/memory, bad speculation, or
just instruction count) from the CPU's own counters, not from sampled time
share. No emulator behaviour changes.

## 0. What was already known (read, not redone)

- Every profile in the tree used the software `cpu-clock` event. No hardware
  PMU event has been tried on either handheld (search of docs/, 10-05).
- The vCPU is not pinned (`XEMU_OPT_THREAD_AFFINITY` defaults to 0, no build
  sets it). It sat on cpu7 (the X3) 92-99% of a GTA capture on the Thor
  (gta482), 79% in vcpuprime428, 72% on Galleon, 15% on one Crimson capture
  (perfarch). So the core type must be read per slice, not assumed.
- Access: `security.perf_harden` resets to 1 at every reboot, which sets
  `perf_event_paranoid` to 3 and refuses every unprivileged
  `perf_event_open`. `setprop security.perf_harden 0` (shell may set it) gives
  paranoid 1. Hostops has set it for held sessions with leave (gta482). The
  Nova has read paranoid 1; the Thor reboots more often.
- A user build refuses `perf_event_open` on a bare pid from shell;
  `simpleperf --app` works because run-as enters the debuggable app's context
  (profile_guest.sh).
- The JIT arithmetic (vcpu60): the whole JIT list priced with memfast's
  discount is 4-10% of v_run; 60 fps on Simpsons needs v_run -58%. memfast:
  21% fewer host instructions per TB bought 4.3-6.2% of vCPU time (about 1/4);
  fastmem's ~9% sampled bought 0.6-1.5% (1/6 to 1/15).
- vcpu60's expert review: "IPC around 1 with back-end/memory stalls caps any
  rewrite low; front-end or mispredict stalls widen the gap toward 2x." That
  is the question this lane's table answers.
- On-CPU is not busy: Simpsons' vCPU is on-CPU 61.5% on master, and with the
  posted store it spun 14.9 ms/frame of guest idle at 96% on-CPU (vcpusleep).
  So the counters will mix real guest work with guest polling. The slice line
  carries `tclk` and the frame count so a reader can tell them apart; R1 must
  not read an idle-spin loop's IPC as the JIT's.

## 1. Instrument

`hakux-pmu.c.inc` (this directory until the grant; then
`accel/tcg/hakux-pmu.c.inc`, included and called from `cpu-exec.c` at the
existing [tlb68]/[jc425] gate). Off unless `HAKUX_PMU=1`; when off it costs a
load and a branch per 1024 loop returns and opens nothing.

- One set of event groups **per core-type PMU** (every
  `/sys/bus/event_source/devices/*` with a `cpus` file), by that PMU's own
  `type` and raw PMUv3 event numbers. A generic hardware event goes to one
  PMU only, and a per-thread event counts only while the thread is on that
  PMU's cores, so a single generic event would read zero on the X3. Per-PMU
  running time is the migration record.
- Three groups of cycles + 6 (the PMUv3 minimum of programmable counters),
  multiplexed. Every group carries cycles and instructions, so a ratio is
  always taken inside one group. User mode only.
- One line per ~1 s slice at the vCPU loop's gate: frames flipped in the
  slice and the longest of them (`g_nv2a_stats`), task-clock, context
  switches, migrations, CPUs seen, then each PMU's groups (running ms and raw
  deltas).
- `HAKUX_PMU_CTL=1` runs eight control kernels on the vCPU thread first,
  through the same file descriptors.
- `HAKUX_PMU=2` is R2's mode, in the same file so that one grant and one
  build serve both. Per PMU, the leader samples one raw event
  (`HAKUX_PMU_EV`, hex; `HAKUX_PMU_PERIOD`), with cycles and instructions
  as followers so the event's rate comes from the same run. The vCPU thread
  drains the ring at each slice and attributes every sample while the TB
  still exists: `jit` = in a TB (`tcg_tb_lookup`: guest pc, guest physical
  address, icount, host bytes, tier); `stub` = in the code buffer but in no
  TB (prologue/epilogue, the goto_ptr return: the dispatch stub); `host` =
  anywhere else, in 64-byte buckets keyed by library and offset. Every 10
  slices: totals, then the top 20 TBs and the top 20 host buckets. ARM
  overflow interrupts skid, so a sample is near its instruction, not on it.
  At TB granularity that blurs a block's last instructions into its
  successor.
- `elfsyms.py` names a host offset from the APK's own `libxemu.so`. Its
  `.symtab` is kept (`jniLibs.keepDebugSymbols`): 23,577 functions in
  521ea8a93e.apk, statics included (`cpu_exec_loop`, `do_ld4_mmu`).
  dladdr's hint names exported symbols only. `pmuread.py --samples LOG
  --apk APK` sums the windows and sorts host functions into dispatch /
  softmmu / translation / helper / other. The code-buffer stub and TB code
  get their own rows.
- A refused follower event (a core that lacks, say, 0x7a) no longer loses its
  group: the slot counts instructions instead, prints as `x`, and the reader
  treats it as missing. The open line names the refused event and errno.
- Host test of the plumbing (x86, `-DPMU433_TEST_SW` forces software
  task-clock events; no ARM counter is involved). Groups open and read; the
  controls and slices print. In sampling mode, 80,669 samples over 10 s,
  0 lost, all attributed `host`; `elfsyms.py` puts the top bucket at
  `main+0x110`, the probe's busy loop. The same run showed the per-gate
  `getcpu` syscall at 35% of a tight loop's samples, so it now runs on 1 gate
  call in 16. The emulator's gate is 1 in 1024 TB returns, and jc425 already
  reads the clock there.
- `pmuprobe.c` builds the same file standalone (NDK, `-Wall -Wextra
  -Werror`, `build_probe.sh`), so R0 can run on a device with no emulator
  build (`r0_probe.sh`, host-run, ~90 s, no title).
- `pmuread.py` reads both: `--controls` judges the kernels against the
  expectations below; the default mode prints the slice table, good vs slow.
  `--selftest` feeds it synthetic lines, one control built to FAIL
  (ind8 at 0.40 mispredicts/branch) and a good/slow slice pair with
  hand-computed ratios. PASS on 2026-10-05.

`syntax_check.py` compiles a copy of `accel/tcg/cpu-exec.c` with the
granted patch applied (`apply_hook()`: the include block after the [jc425]
`#endif`, and `PMU433_TICK()` after `rr425_tick(cpu)` at the gate), using the
Android build's own compile command from its `compile_commands.json`. The
new code produces no diagnostic (PASS, 10-05). `--falsify` plants an
undeclared name in the hook and FAILS, so the include is really compiled
(XBOX and `__linux__` are set in that build). The first run caught a real
defect: `sched_getcpu()` is undeclared there, since `<sched.h>` was included
before `_GNU_SOURCE`. The hook now uses the `getcpu` syscall.
`syntax_check.py --write` applies the same patch to the tree once granted.

The disassembly of the standalone build was checked: `alu1` is 64 dependent
`add x8, x8, #1` per iteration, `mul1` 64 dependent `mul`, `ind*` one `br`
through an 8-entry table per iteration plus one `b` and one `b.ne`.

## 2. Pre-registration (written before any device run)

### Controls: a counter that misses its row is not an instrument

| kernel | what it does | metric | expected (X3/A715) | why |
|---|---|---|---|---|
| alu1 | 64 dependent adds per iteration | IPC | 0.95-1.12 | add latency 1: 66 instr in ~64 cycles |
| mul1 | 64 dependent multiplies | IPC | 0.45-0.58 | mul latency 2 on X3/A715 |
| ind1 | indirect `br`, one target | mispredicts per branch | < 0.01 | predicted |
| ind8 | indirect `br`, 8 random targets | mispredicts per branch | 0.75-0.95 | 7/8 unpredictable |
| chase16k | random pointer chase in 16 KB | L1D refills per load | < 0.02 | fits L1D |
| chase64m | random pointer chase in 64 MB, 64 B lines | L1D refills per load | 0.9-1.1 | every load misses |
| chase64m | " | L2D refills per load | 0.85-1.1 | 64 MB >> L2 and L3 |
| chase64m | " | STALL_BACKEND / cycles | 0.8-1.0 | waits on memory |
| code16k | 256 64-B code blocks in random order | L1I refills per block | < 0.05 | fits L1I |
| code512k | 8192 blocks (512 KB) | L1I refills per block | 0.8-1.2 | one new line per block |
| code512k | " | STALL_FRONTEND / cycles | 0.4-1.0 | fetch waits on L2 |

A510 rows: only the core-independent ones (alu1, ind*, chase16k/64m L1D,
code16k). If a row fails, that counter is not used in R1 for that core type,
and the failure is reported as the result for that counter.

### R1: what each reading means (the classes in the brief)

Thread-level counts mix JIT code with the C it calls (helpers, softmmu slow
path, the exec loop, translation). R1 says so; R2 splits it.

| class | hit looks like | miss looks like |
|---|---|---|
| front-end bound (code size/layout) | STALL_FRONTEND >= 25% of cycles AND L1I refill >= 10 /kins or iTLB refill >= 1 /kins | STALL_FRONTEND < 15% or L1I refill < 3 /kins |
| back-end bound on memory | STALL_BACKEND >= 40% AND (L1D refill >= 20 /kins or L1D TLB refill >= 2 /kins) | STALL_BACKEND < 25% |
| bad speculation (dispatch, IBC) | branch mispredicts >= 5 /kins (at ~15 cycles each that is >= 7% of cycles at IPC 1) | < 2 /kins |
| instruction count | IPC >= 2 with all three above in their miss column | IPC < 1.5 |

The good-vs-slow split: a counter is a lead for the slow frames only if it
moves between good and slow slices by more than its own slice-to-slice
spread in the good slices. A counter equal in both is not the cause. Cycles
per frame up with IPC flat means more work per frame (instruction count or
guest polling), not a JIT stall.

## 3. State (2026-10-05)

- R0 has two routes, both waiting on something outside this session:
  - the in-process hook needs a grant for `accel/tcg/hakux-pmu.c.inc` (new)
    and `accel/tcg/cpu-exec.c` (an include and one call at the gate), then a
    queued Thor soak with `HAKUX_PMU=1 HAKUX_PMU_CTL=1`. This is the route
    that reaches R1: it needs no hold, only `perf_harden 0` on the device;
  - `r0_probe.sh` is host-run (~90 s, no title), any idle handheld under a
    hold. It answers simpleperf's path (a, c), lists the events and runs the
    controls on each core type, without a build.
- Asked in OUTBOX.md: the grant, `security.perf_harden 0` on both handhelds
  (until reboot; hostops's leave), and one r0_probe.sh run.

## 3a. Attempt 2 (2026-10-05 night, resume)

Why attempt 1 did not finish: it built the instrument and stopped at the
asks in OUTBOX.md (the grant, `perf_harden 0`, one R0 probe). The owner's
R0 order (09:04 PDT) went to lane.local and was never run, so no device
read exists yet. Nothing in the tree was wrong; the lane was waiting on
actions outside its session.

Attempt 2: merged `origin/master` (45 commits behind; merge clean). hostops
has set `security.perf_harden` to 0 on the Thor (read back 0 at 04:50Z) and
the addendum makes R0 the standalone probe, no `HARDEN0`. The probe does not
need the hook in the build, so R0 can run now. R1/R2 stay blocked until the
grant is on origin/board and the hook is in a build.

## 3b. Attempt 3 (2026-10-05 22:2x PDT, resume on Sonnet)

Why attempt 2 did not finish: its R0 run was refused by the tool permission
layer, so no device read was made from the session. Hostops then ran the
probe under lanelocal-fanwait (log `logs/hostops/r0-thor-20261005-2206.log`,
result dir `perf/2026-10-05-pmucounters/r0-thor/`). That run answered less than
it looked like:

- **Pinning to the X3 failed.** `taskset 80` (cpu7) returned `Invalid argument`
  from shell, from `run-as`, and from `simpleperf` under taskset. `taskset 08`
  (cpu3) and `taskset 01` (cpu0) succeed, and the slice lines read `cpus=8` and
  `cpus=1`, so the pin took. cpu7 is online (`/sys/.../cpu7` reads 0-7).
  EINVAL from `sched_setaffinity` means the mask has no CPU in the caller's
  cpuset. Hypothesis (not yet read from the device): the shell's cpuset
  excludes cpu7 (the prime core) and the app's top-app set includes it. The
  emulator's vCPU sat on cpu7 for 92-99% of a GTA capture, so the app can reach
  it. The probe was also missing the cpuset read, so this run could not show it.
- **The hardware counters read zero.** Every probe run opened its groups
  (`g0=ok g1=ok g2=ok`), but no slice line carries a `p=` field, and the
  control kernels printed no `ctl=` line. `pmu433_fmt` and the control
  printer skip a group whose `time_running` delta is zero, so the run was silent
  about it. Either the read failed or the events never ran; the probe did not
  say which. Its selftest did not catch this, because the selftest feeds
  synthetic lines and never exercises a real zero read.
- **There is one PMU, not one per core type.** `/sys/bus/event_source/devices/`
  holds `armv8_pmuv3` (type 8, `cpus=0-7`), not `armv9_cortex_x3` /
  `armv8_cortex_a510` as the hook's comment and the control expectations assume.
  The per-PMU migration record in the slice line therefore does not exist on this
  kernel; the core is read from `getcpu` (`cpus=`) alone. Consequence: a
  control's `p=` name is no longer a core name on this device.
- The CPU parts (`/proc/cpuinfo` MIDR): cpu0-2 0xd46 (A510), cpu3-4 0xd4d
  (A715), cpu5-6 0xd47 (A710), cpu7 0xd4e (X3). The probe's cpu3 step is the
  A715, not an X3.
- `simpleperf stat` and `record` did not run on cpu7 for the same EINVAL.
  `security.perf_harden` is 0 and `perf_event_paranoid` is 1, as hostops said.
  `getenforce` is denied from shell (not a blocker for perf).

Attempt 3 changes: the hook logs the first bad group reads (short read,
wrong `nr`, or enabled but never running: `[pmu433] read ...`, at most 12
lines, with errno and the raw `nr/en/run`), so the next run names which of the
two it is. The probe's pinned steps use cpu3 and cpu0 (what the shell cpuset
allows), keep one cpu7 attempt as the recorded EINVAL, and the probe reads the
shell's cpuset first. The X3 reading needs the app's own process (the in-process
hook), not a shell pin, if the cpuset hypothesis holds.

## 4. Plan once granted (the resume starts here)

1. `syntax_check.py --write` (applies the two hunks and copies the .inc to
   `accel/tcg/`), re-run `syntax_check.py`, commit, push.
2. **R0 in-process + controls, one Thor run** (<= 480 s, cold slot): GTA SA
   (`54540082-Grand_Theft_Auto_San_Andreas.xiso.iso`, Thor, `gta-sa.route`),
   `--env HAKUX_PMU=1 --env HAKUX_PMU_CTL=1 --device thor`, `--no-expect`
   (a measurement, no arm). Read `[pmu433] open` (paranoid, errno, PMUs),
   then `pmuread.py --controls` on its logcat, then the slices after the
   gameplay mark. A control that misses its row removes that counter for
   that core type (section 2).
3. **Overhead pair**: the same title, the same ref, no env. Counting must not
   move gfps by more than the run-to-run spread; if it does, say so and
   price it into R1.
4. **R1**: 60 s or more of confirmed play per title, `HAKUX_PMU=1`:
   Forza (race), Tron 2.0 (`vcpuwait433/tron-newgame*.route`, Nova),
   Nightfire (`nightfire.route`, Nova), GTA (from 2). Simpsons needs a
   pathfind hold, so it goes to the owner as an `owner` line with
   `HAKUX_PMU=1` in the hold's env. Check where each title lives first (one
   copy per title).
5. **R2**: `HAKUX_PMU=2 HAKUX_PMU_EV=<R1's dominant event>` on the two titles
   where that counter is largest; period set for ~5k samples/s on the X3.
   Read with `pmuread.py --samples LOG --apk dispatch/builds/<ref>.apk`.
6. **R3**: price the top candidate per `briefs/_next-step-rule.md` with the
   discount (section 0). Recommend it; do not build it.

## 3c. Attempt 4 (2026-10-05 late, resume on Sonnet)

Why attempt 3 did not finish: it made the hook log bad group reads and moved
the probe's pins, but the device run that answered them (hostops, `r0-thor-2`)
was read only for the controls. The read failure was never diagnosed, and the
cpuset hypothesis from 3b was never checked against the probe's own output.

### What `r0-thor-2` shows (read by hand, not from pmuread)

- Every group, on cpu3 (shell and run-as) and cpu0: `got=80 nr=7 en=... run=0`.
  80 bytes is exactly 3 + 7 u64, so the read is intact. `en` grows and `run`
  stays 0: the group is enabled and never gets a counter. It is not an errno.
  The hook's read path is not the fault.
- simpleperf stat on cpu3 counts all eight of its events, with its warning
  "the number of hardware events are more than the number of available CPU PMU
  hardware counters" (multiplexing). So the PMU does count, and it has fewer
  counters than eight.
- The cpuset is `0-7` for the shell, for top-app and for foreground
  (`cpuset.txt`). The cpuset hypothesis from 3b is refuted.
- cpu7 still returns EINVAL, while cpu3 and cpu0 pin in the same run. The
  thermal-pause note (`thor-thermal-pause`) says a pause can hide from
  `cpu/online` and the cpuset, so that is the live hypothesis. The run did not
  read the cooling-device state, so it stays open.

### Diagnosis

Each hook group is seven events: cycles plus six programmable ones. The probe
never asks the PMU how many events one group can hold, so I checked the
mechanism on a known PMU first:

| check | what it reads | expectation | result |
|---|---|---|---|
| host sweep (i7-6700K, `cpu` PMU, `-DPMU433_TEST_HW`) | group sizes 1-7, 4 programmable + 2 fixed | largest scheduled group 6 | largest group 6; n=7 refused at open (EINVAL) |
| host singles | each generic event alone | all count | all count |
| ARM sweep build (NDK, `-Werror`) | | builds | PASS |

The host refuses an oversize group at open. The ARM kernel does not: the
hook's 7-event groups opened, and then never got a counter. So the open-time
check cannot be the test on the Thor; the run-time read is (`run == 0` with
`enabled` growing). The hypothesis is that this PMU has fewer than six
programmable counters beside the cycle counter, so no seven-event group can
run. Not yet read from the device.

### Changes this attempt

- `pmuprobe.c`: `pmuprobe sched`. Groups of 1..19 events (cycles leader first)
  and each event alone, 50 ms of work on the thread each, printing
  `[pmu433] sched ... run=` and `largest scheduled group=N`.
- `r0_probe.sh`: `sched_cpu3`, `sched_cpu0`, `sched_cpu7` steps (the X3 step
  records whether the X3 pins at all and whether it schedules), and a `cpuhp`
  step (isolated, possible/present, per-CPU online, and every cooling device's
  `cur_state`, which shows `thermal-pause` if it is active).
- The hook (`hakux-pmu.c.inc`) is unchanged. Its group layout waits on N: the
  groups must hold at most N events each, and the 7-event groups split if N < 7.
  Splitting changes which events share a window, so R1's ratios are taken only
  inside one group, as now.

### Next

1. One device run of R0 (`DEV=thor bash docs/lanes/pmucounters/r0_probe.sh`,
   no `HARDEN0`, under the next Thor hold). Read first: `sched_cpu3.txt`
   (largest group N, and which singles read run=0), then `cpuhp.txt` (is the
   thermal pause on, and is cpu7 offline or paused).
2. If N is at most 5, the hook's layout changes before R1. If N is 6, the
   seven-event group loses one event. Either way the change is in the hook,
   not the probe.
3. R1 and R2 stay behind the grant and the build.

## 3d. Attempt 5 (2026-10-09, resume on Opus): grant in, hook resized, R1/R2 queued

Why attempt 4 did not finish: it ended correctly, waiting. Its diagnosis (a
7-event group never gets a counter) needed one device run to read the
largest group the PMU schedules, and a lane session cannot run the host-side
probe. That run happened on 10-09 11:29 PDT on the Nova (lane.local,
`perf/20261009-pmucounters/r0-nova-1`), and the grant for
`accel/tcg/hakux-pmu.c.inc` and `accel/tcg/cpu-exec.c` landed on board
82379753c2 the same day. Nothing in attempt 4 was wrong; it had nothing left
it could do.

### What `r0-nova-1` shows (read by hand)

| step | reading |
|---|---|
| `sched_cpu3` (A715) | n=1..5 run (n=5: `en=run=50.0 ms`); n=6 and n=7 open and read `run=0`; n=8 refused at open (errno 22). Largest scheduled group **5** |
| `sched_cpu0` (A510) | the same: largest **5** |
| `sched_cpu7` | `taskset` EINVAL again: the X3 cannot be pinned from shell (still unexplained; irrelevant to the in-process hook, which reads whichever CPU the vCPU is on) |
| `cpuhp` | every CPU online, no isolated CPU, every `thermal-pause-*` and `pause-cpu*` cooling device at `cur_state 0` |
| sampling (`sample_cyc_cpu3`) | 240,229 cycle samples, 0 lost: the overflow ring works on hardware |
| paranoid | 1 at 11:30 PDT (`perf_harden 0`, set by lane.local at 10:55) |
| singles on a spin loop | A715: 0x7a (BR_INDIRECT_SPEC), 0x34 (DTLB_WALK), 0x2a (L3D_CACHE_REFILL) read 0; A510: 0x35, 0x2a read 0. A zero on a loop with no indirect branch or data miss does not show the event unsupported; the ind8 / chase64m controls decide it |

So attempt 4's hypothesis holds: 4 programmable counters beside the cycle
counter. Every 7-event group in the 10-05 hook could never run.

### Hook changes (the brief's "groups of <= 5, rotated")

- Groups are cycles + instructions + 3 events (5 in all, `HAKUX_PMU_GSZ`),
  five groups covering the same 15 events as before. The kernel rotates them;
  two 5-event groups cannot share the PMU, so per unit the groups' running
  times add up to the thread's time there (less rotation gaps). One
  `[pmu433] layout` line names the groups; the reader takes names from it.
- **One counter set per CPU.** One PMU covers four core types, so a
  per-thread event mixes them. Each group is now opened per CPU (pid = this
  thread, cpu = N): it counts only while the thread runs on CPU N, and units
  of different CPUs never compete. Units are named `c7-x3` etc. from
  /proc/cpuinfo's CPU part. Fallback to one any-CPU set (`HAKUX_PMU_PERCPU=0`,
  or if no per-CPU open succeeds).
- The bad-read diagnostic now fires only for a unit that ran >= 50 ms in the
  slice while one of its groups got `run=0`; a CPU the thread never visited
  is not an error.
- Sampling (`HAKUX_PMU=2`): up to four events, each its own group
  `[ev, cycles, instructions]` with its own ring, period and tables;
  `HAKUX_PMU_EV=11:1500000,24:1000000`. Samples carry their CPU
  (`PERF_SAMPLE_CPU`), reported per event as `cpu=7:N,...`.
- One copy: the hook lives at `accel/tcg/hakux-pmu.c.inc` only;
  `pmuprobe.c` and `syntax_check.py` read it there.

### Checks (host)

| check | result |
|---|---|
| `build_probe.sh` (NDK 29, `-Werror`) | clean |
| host build `-DPMU433_TEST_SW` (gcc `-Werror`), mode 1, per-CPU units | 8 units x 5 groups open; slice s=1: c2 350.7 ms + c3 684.0 ms = 1034.7 = task-clock |
| host mode 2, `11,24` | 97,233 / 97,617 samples, 0 lost, per-CPU counts, `dladdr` offsets |
| host mode 2 at 50k samples/s | `lost=237526` reported (a 512 KB ring drained once a second holds ~21.8k samples); device periods are set for <= 5k/s per event |
| `pmuread.py --selftest` | 7 cases PASS (the 10-05 formats unchanged, plus layout, per-CPU, merged ctl lines, the good-slice spread flag, two-event sampling); the ind8 control built to fail FAILs |
| `syntax_check.py` (Android flags, the real patched cpu-exec.c) | PASS, 0 diagnostics in the new code; `--falsify` FAILs |
| link check (`objcheck433.py`: cpu-exec.o built with the Android flags vs `libxemu.so` of 34a0b032b9) | every new undefined symbol is defined in libxemu.so or imported from libc, except `__clear_cache`, a compiler-rt builtin that the NDK links statically (defined `T` in `libclang_rt.builtins-aarch64-android.a`; present in pmuprobe) |

### Pre-registration added before the device runs (10-09)

- **Coverage** (summed group running time / task-clock): 0.90-1.00 expected.
  Below 0.8 means counters were taken away (another perf user, or a vendor
  counter reservation that varies), and every per-frame count is short by
  that much; ratios inside a group stay exact.
- **Core split**: the vCPU on the X3 most of the time (section 0: 72-99% in
  earlier captures). Tables are per core type; a type under 5% of counted
  time is not tabled.
- **Overhead (on/off pair)**: the counting run and a run with no PMU env, same
  ref, route and device. Hit (overhead negligible): median fps and the
  perflog vCPU busy per frame differ by less than the run-to-run spread of
  the earlier Amped 2 runs (27.23 median in fpstelemetry1008). Miss: the PMU
  run slower by more than that. One pair bounds the cost, it does not measure
  it below the noise.
- **R2**: a TB, the dispatch stub or a host function is a fix candidate only
  if its cycle share is >= 3% of the vCPU's samples, AND the event that marks
  its class (sbe for memory, sfe for front-end, brm for speculation) has a
  share there at least as large as its cycle share. A sampled share is priced
  at 1/4 to 1/15 of itself as removable time (memfast discount).

### Device plan (Nova only, investigative, no scoring)

| run | what | env | seconds |
|---|---|---|---|
| A | controls + paranoid + layout, Amped 2 boot, no route | `HAKUX_PMU=1 HAKUX_PMU_CTL=1` | 90 |
| B | R1: Amped 2 route (fpstelemetry1008's `amped2`), counting | `HAKUX_PMU=1` + `--perflog` | 578 |
| C | R2: same route, sampling 4 events | `HAKUX_PMU=2 HAKUX_PMU_EV=11:1500000,24:1000000,23:1000000,22:20000` + `--perflog` | 578 |
| D | overhead off-arm: same route, no PMU env | `--perflog` | 578 |

A + B is the pilot (~13 min with setup). C and D go after A and B are read
and `pilots/pmucounters.ok` is written.

### Queued (10-09 15:2x PDT, ref 5e4110e016)

- Route input checked before queuing: fpstelemetry1008's run
  `1-1791538465-fpstelemetry1008-1131600` hold frames 03:22:33 and 03:27:20
  show the rider at clearly different places on the slope (open run with
  the lift, then a tree-lined trail). The route reaches live play and the
  player moves.
- A: `1-1791584641-pmucounters-283582`. B: `1-1791584645-pmucounters-283745`.
  Both pinned to the Nova, release tier (#433 carries 0.5).
- B leaves `HAKUX_PMU=1` in the Nova's `env_vars` pref until the next
  dispatched request starts; an owner or held session in between runs with
  counting on (one `[pmu433]` line a second and the counters' own cost). D,
  the no-env arm, goes last of C and D for that reason.

### Pilot read (A and B, ref 5e4110e016)

**A (controls), 9 of 11 PASS**, all on c7-x3 (the X3 at 2.92 GHz). All 8
per-CPU units opened 5/5 groups. `paranoid=1` on every open line, so
`perf_harden` was still 0.

| control | metric | read | expected | verdict |
|---|---|---|---|---|
| alu1 | IPC | 1.031 | 0.95-1.12 | PASS |
| mul1 | IPC | 0.516 | 0.45-0.58 | PASS |
| ind1 / ind8 | brm per unit | 0 / 0.875 | 0-0.01 / 0.75-0.95 | PASS |
| chase16k | l1d per unit | 0 | 0-0.02 | PASS |
| chase64m | l1d / l2d per unit | 1.737 / 0.733 | 0.9-1.1 / 0.85-1.1 | **FAIL** |
| chase64m | sbe/cyc | 0.997 | 0.8-1 | PASS |
| code16k / code512k | l1i per unit | 0 / 1.023 | 0-0.05 / 0.8-1.2 | PASS |
| code512k | sfe/cyc | 0.640 | 0.4-1 | PASS |

The chase64m failure was the hook's fault, not the PMU's. The kernel built
its 64 MB ring inside the counted window: mmap, page faults, shuffle and link.
That added refills that are not one per load. Coverage was 0.938.

**B (R1, Amped 2):** a valid run with damaged data.

- **Valid:** the route reached play with a moving player (score 0, then 510,
  then 1,625 across frames 153203, 153427 and 153654), and there was no
  thermal pause.
- **Damaged:** 260 of the 298 gameplay slice lines ran past Android's
  1023-byte log payload and were cut. The units printed last were dropped, and
  c7 was often among them, so coverage was 0.30 and the core split cannot be
  trusted. `cs` and `mig` read 0: software events count in kernel mode, and
  the hook set `exclude_kernel`.

What still holds in B comes from the head of each line (task-clock, wall,
frames), which is never cut:

| | all | good (<= 34.5 ms) | slow |
|---|---|---|---|
| slices | 298 | 187 | 111 |
| fps | 28.4 | 29.9 | 25.9 |
| vCPU thread on-CPU, % of wall | 81.9 | 87.5 | 72.4 |
| X3 IPC (partial) | 4.45 | 4.46 | 4.34 (good sd 0.144) |
| X3 stall_fe / stall_be % of cycles (partial) | 8.1 / 25.9 | 8.1 / 25.9 | 8.8 / 26.0 |

In slow slices the thread is off-CPU 15 points more. Its code runs at almost
the same IPC. **On the first read, slow frames are waits, not slower code.**
B2 has to confirm this with whole lines.

### Fixes from the pilot (b387f4971a; reader b345b5b613)

- A slice line closes at 1000 bytes and continues on a `s=N+` line. The reader
  joins the two. A line that still reaches 1023 bytes has its last unit
  dropped and counted as cut.
- Software `cs` and `mig` count with the kernel included. If that open fails,
  the hook retries without the kernel and the open line says `kern=0`.
- Each chase kernel's ring is built before the first read and freed after the
  second.
- Per-unit control metrics are scaled by instructions, because each group sees
  only part of the kernel.
- The reader reads the `layout` line even when it comes before the `--after`
  mark.
- `--selftest` passes all 8 cases, including a new split/cut case.

### Queued (10-09 15:4x PDT, ref b345b5b613), after `pilots/pmucounters.ok`

| run | id | env |
|---|---|---|
| A2 controls, 90 s | `1-1791585654-pmucounters-340915` | `HAKUX_PMU=1 HAKUX_PMU_CTL=1` |
| B2 R1, route, 578 s, perflog | `1-1791585654-pmucounters-341117` | `HAKUX_PMU=1` |
| C R2, route, 578 s, perflog | `1-1791585655-pmucounters-341517` | `HAKUX_PMU=2 HAKUX_PMU_EV=11:1500000,24:1000000,23:1000000,22:20000` |
| D off-arm, route, 578 s, perflog | `1-1791585656-pmucounters-341827` | none (shipped behaviour, last) |

The pilot gate admitted the 36 minutes because the reviewed pilot was in
place. B2 and D are the overhead pair: same ref, same route, same device.

## 3e. Results (10-09 16:2x PDT): R0 on device, R1, R2, overhead, and where the frame goes

All four runs of the 15:4x batch are valid.
- **A2** is a boot run with no route.
- **B2, C and D** each reached live play with a moving player: the rider was
  at clearly different places on the slope across the hold frames (D:
  160924, an open run with the lift at score 500; 161259, a tree-lined
  trail).
- None had a thermal pause (D's hottest zone was 94.3 C).
- `paranoid=1` on every open line, so `perf_harden` was 0.

### R0 on device: A2 controls, 10 of 11 PASS (`1-1791585654-pmucounters-340915`)

| control | metric | read | expected | verdict |
|---|---|---|---|---|
| alu1 / mul1 | IPC | 1.031 / 0.516 | 0.95-1.12 / 0.45-0.58 | PASS |
| ind1 / ind8 | brm per unit | 0.000 / 0.875 | 0-0.01 / 0.75-0.95 | PASS |
| chase16k | l1d per unit | 0.000 | 0-0.02 | PASS |
| chase64m | l1d per unit, sbe/cyc | 1.000, 0.999 | 0.9-1.1, 0.8-1 | PASS |
| chase64m | l2d per unit | **1.162** | 0.85-1.1 | **FAIL** |
| code16k / code512k | l1i per unit | 0.000 / 1.031 | 0-0.05 / 0.8-1.2 | PASS |
| code512k | sfe/cyc | 0.641 | 0.4-1 | PASS |

The setup fix took: chase64m's l1d now reads 1.000, where it read 1.737.
l2d still reads 16% over the range. Each load into a 64 MB ring also misses
the TLB, and the page-table walk's own fetches refill L2 too, so this is
expected. The range stays as written and the row stays a FAIL. L2 refill
counts in R1 carry the same walk traffic.

### R1: B2, counting per 1 s slice (`1-1791585654-pmucounters-341117`)

- coverage 0.994;
- 244 slices: 137 good (frame time <= 34.5 ms), 107 slow;
- the vCPU on-CPU 77.9% of wall;
- context switches 2072/s, migrations 186/s (168 in good slices, 207 in
  slow).

Core split of counted time: X3 67.2%, A715 20.8%, A710 11.8%, A510 0.1%.

| X3 (67% of counted time) | all | good | slow | slow - good | good sd |
|---|---|---|---|---|---|
| fps | 28.4 | 29.9 | 26.5 | -3.45 | |
| vCPU on-CPU, % of wall | 77.9 | 81.5 | 73.2 | -8.3 | |
| on the X3, % of on-CPU | 66.8 | 70.5 | 61.6 | -8.9 | |
| M instructions per frame | 188 | 206 | 164 | -42 | |
| IPC | 3.59 | 3.73 | 3.36 | -0.37 | 0.70 |
| stall_fe / stall_be, % of cycles | 11.8 / 27.9 | 11.4 / 27.5 | 12.4 / 28.4 | +1.0 / +0.9 | 4.0 / 1.4 |
| branch mispredicts per k-instr | 0.39 | 0.36 | 0.44 | +0.09 | 0.24 |
| indirect branches (spec) per k-instr | 14.0 | 12.6 | 16.5 | +3.9 | 8.1 |
| L1I refill / L1I TLB refill per k-instr | 5.74 / 0.53 | 5.03 / 0.46 | 7.00 / 0.65 | +2.0 / +0.19 | 3.0 / 0.28 |
| L1D refill / L1D TLB refill per k-instr | 0.54 / 1.49 | 0.50 / 1.35 | 0.63 / 1.75 | +0.13 / +0.41 | 0.29 / 0.81 |
| L2D / L3D refill per k-instr | 1.32 / 0.94 | 1.23 / 0.88 | 1.48 / 1.03 | +0.25 / +0.15 | 0.80 / 0.58 |
| ITLB / DTLB walks per k-instr | 0.019 / 0.069 | 0.017 / 0.064 | 0.021 / 0.076 | | 0.013 / 0.043 |

The A715 (IPC 2.35, stall_fe 20%) and the A710 (IPC 2.11, stall_fe 22%) do
not differ between good and slow slices on any row by more than a good-slice
sd.

What R1 says:
- **Slow slices are waits, not slower code.** On every core type, no
  counter differs between good and slow slices by more than one good-slice
  sd. The pilot B said the same with a third of the data.
- **On the X3 the code is mostly high-IPC with moderate back-end stall.**
  It is not front-end bound (stall_fe 12%). The classes of section 2 put
  the X3's JIT time in "high IPC, a lot of instructions", with the back-end
  share as a second term.
- **The X3 IPC includes the title's pacing spin** (below), which runs
  five instructions a loop at a very high IPC. That is why good slices show
  more instructions per frame (206 M) than slow ones (164 M): the spin
  shrinks when frames are late.
- **In slow slices the thread spends 9 points less of its on-CPU time on
  the X3.** Migrations rise 23%. That follows from the waits: each block is
  followed by a wakeup and a new placement. It is not a lever this lane
  ranks; the owner's rule excludes clock and governor fixes, and the waits
  come first.

### R2: C, sampled attribution (`1-1791585655-pmucounters-341517`)

Sample counts and placement:
- 108,544 cycle samples, 13,006 brm, 22,682 sfe and 42,557 sbe.
- 0 lost and 0 dropped for every event.
- Cycle samples by CPU: X3 71.6%, A715 17.9%, A710 10.5%.

Shares are % of that event's samples on the vCPU thread:

| row | cyc | brm | sfe | sbe |
|---|---|---|---|---|
| JIT code (inside a TB) | 55.87 | 40.26 | 48.01 | 53.45 |
| of which TB 0031e901 (the pacing spin) | 23.84 | 0.00 | 0.11 | 22.59 |
| of which the next-largest TB (0002d786) | 0.90 | 0.86 | 0.36 | 1.07 |
| dispatch (`helper_lookup_tb_ptr`, `tb_lookup`, `qht_lookup_custom`, loop) | 17.37 | 19.92 | 18.20 | 17.04 |
| softmmu (`mmu_lookup1`, `mmu_lookup`, `do_ld4_mmu`, ...) | 8.63 | 7.59 | 4.31 | 9.42 |
| other (vdso clock 2.19, TB tree compare, ...) | 3.09 | 8.83 | 7.67 | 4.51 |
| helpers (`helper_maskmov_xmm`, `mulps`, `fldz`, ...) | 1.52 | 1.06 | 0.37 | 1.42 |
| translation | 1.25 | 2.24 | 1.75 | 1.47 |
| the dispatch stub in the code buffer | 0.03 | 0.07 | 0.05 | 0.04 |

| host function | cyc | brm | sfe | sbe |
|---|---|---|---|---|
| `helper_lookup_tb_ptr` | 7.93 | 6.55 | 4.63 | 7.55 |
| `tb_lookup` | 7.38 | 8.14 | 6.93 | 7.03 |
| `mmu_lookup1` | 7.34 | 5.41 | 3.19 | 8.07 |
| `[vdso]+0x300` (clock_gettime) | 2.19 | 4.77 | 3.90 | 2.84 |
| `qht_lookup_custom` | 2.04 | 5.11 | 6.39 | 2.46 |

**The pre-registered R2 rule** asks for >= 3% of cycles, and for the class
event's share to be at least the cycle share.

| row | as written | spin excluded |
|---|---|---|
| `mmu_lookup1` | **passes** (memory: sbe 8.07 >= 7.34) | **passes** (sbe 10.42 >= 9.64) |
| `tb_lookup` | passes (speculation: brm 8.14 >= 7.38) | **fails** (brm 8.14 < 9.69) |
| `helper_lookup_tb_ptr` | fails: no class (high instruction count) | fails |
| any single TB other than the spin | under 3% | under 3% |
| TB 0031e901 | fails (sbe 22.59 < 23.84); slack, see below | excluded |

Spin excluded means the spin's samples are removed from every event's
total. The spin has almost no brm or sfe samples, so it deflates the cycle
share of every other row against brm and sfe. That makes the as-written test
easier to pass for those two classes; the spin-excluded column is the
unbiased one. JIT code with the spin excluded is 42.06% of cycles and 47.95%
of sfe: front-end class as a body, but spread over thousands of TBs (the
largest is 0.9%), so no single TB is a candidate.

### The 0031e901 loop is the title's 30 fps pacing slack, not work

- The loop is 5 guest instructions ending in a `jb` at 0031e909.
- [rr425pc] shows a kick out of it about 1,400 times a second.
- Its share of TB time ([tpc787]) tracks frame rate in three runs:

| fps bin | B2 | C | fpstelemetry1008 `1131600` | D |
|---|---|---|---|---|
| < 24 | 0.05 | 0.05 | 0.02 | 2.0 ms/frame |
| 30 (>= 29.7) | 0.22 | 0.32 | 0.43 | 11.3 ms/frame |

- When frames are late the loop runs almost not at all; at the cap it fills
  the rest of the 33.3 ms.
- Frametrace's "RUN" verdict counts it as vCPU work. A per-frame "vCPU
  busy" over this title overstates work by the spin's ms.

### Where the vCPU's frame goes (D, shipped behaviour, `spinfps.py`)

D is `1-1791585656-pmucounters-341827`. All values are ms per frame.
- on-CPU comes from [tlb68];
- spin = [tpc787] share x [rr425] TB fraction x on-CPU;
- off-CPU = wall - on-CPU.

| fps bin | windows | wall | on-CPU | spin | work (on-CPU less spin) | off-CPU | pgraph.lock wait [lock474] |
|---|---|---|---|---|---|---|---|
| < 24 | 18 | 44.5 | 29.7 | 2.0 | 27.8 | **14.7** | 5.64 |
| 24-27 | 24 | 39.2 | 28.6 | 2.4 | 26.1 | 10.6 | 4.09 |
| 27-29 | 15 | 35.4 | 28.8 | 6.9 | 21.8 | 6.7 | 3.10 |
| 29-29.7 | 21 | 34.0 | 28.5 | 9.3 | 19.2 | 5.4 | 2.90 |
| >= 29.7 | 61 | 33.4 | 29.8 | 11.3 | 18.5 | **3.6** | 1.84 |
| all | 139 | 36.1 | 29.3 | 7.8 | 21.5 | 6.9 | 3.02 |

B2 and C give the same shape: work 21.2/19.0 -> 28.2/28.5 ms and off-CPU
6.4/5.1 -> 13.6/13.5 ms from the 30 fps bin to the < 24 bin. From a 30 fps
window to a < 24 one the frame grows 11 ms. The two parts:
- **Work grows ~9 ms.** The scene is heavier: the guest enters the same
  code more often per frame. The chain entered at 00324ffd keeps ~9 us per
  entry in every bin, while its entries per frame double, 550 to 1100. That
  is more of the same work, not a longer wait in one place. The guest code
  is on the device's ISO, not on the host, so what that chain does is not
  read here.
- **Off-CPU grows ~11 ms.**

With the slack gone in those windows, both land on the frame.

**What the off-CPU growth is** (frametrace, `1131600`, the same route on
4ea49d12e7, `HAKUX_FRAMETRACE=1`), the vCPU side, ms/frame:

| fps bin | vrq | vblk | named waits (vw) | of which pgraph.lock | of which BQL | `lw` (DMA_PUT on pfifo.lock) |
|---|---|---|---|---|---|---|
| 30 | 0.1 | 3.2 | 2.4 | 1.70 | 0.67 | 1.4 |
| 24-27 | | | | | | 6.3 |
| < 24 | 0.6 | 14.2 | 5.4 | 4.50 | 0.88 | **9.7** |
| all | | | | | | 4.6 |

The PFIFO side, ms/frame. This table misses site #19, the same #804 wait
logged with ctx=none (3.9-5.1 ms/frame in every bin). The #804 wait in
full is 7.2 at 30 fps and 11.9 under 24 fps; see 3g.

| fps bin | PFIFO fence wait | site #25 (#804 wait, ctx=rep) | site #6 (STALLED finish, ctx=rep) | gpu50 | GPU MHz |
|---|---|---|---|---|---|
| 30 | 7.4 | 1.71 | 0.22 | 14.0 | 615 |
| < 24 | 16.3 | 7.68 | 4.73 | 19.8 | 615 |

Reading:
- `vblk - vw - lw` is -0.6 and -0.9: the vCPU's blocked time is fully named.
- Its growth is the DMA_PUT store waiting for pfifo.lock (`user_write`,
  user.c:92-95), plus pgraph.lock.
- The holder is the PFIFO thread. `pfifo_thread` keeps pfifo.lock across
  its loop (pfifo.c ~2119-2235), including
  `pgraph_process_pending_reports`. There it waits on GPU fences:
  - the #804 `vkWaitForFences` on every submitted frame (reports.c 257-262);
  - the STALLED finish (reports.c 374), whose frame-slot rotation waits
    for the slot two finishes back.
- The GPU is not the limit: 19.8 ms busy at median in a 44.5 ms frame, at
  the same clock.
- The vCPU waits behind a CPU-GPU serialisation in report processing, not
  behind GPU throughput.

### Overhead: counting does not slow the run (pre-registration: hit)

| run | PMU | frames/wall fps | window fps median / p10 / mean | share of windows >= 29.7 | vCPU on-CPU ms/frame | off-CPU ms/frame |
|---|---|---|---|---|---|---|
| B (5e4110e016) | counting | | 29.57 / 25.48 / 28.60 | | 29.15 | |
| B2 | counting | 28.61 | 29.61 / 26.19 / 28.72 | 0.49 | 28.50 | 6.7 |
| C | sampling 4 events | 28.03 | 29.13 / 24.90 / 28.22 | 0.40 | 28.54 | 7.2 |
| D | **off** | 27.67 | 29.45 / 23.25 / 27.95 | 0.44 | 29.41 | 6.9 |

- The off arm is not faster. It has the lowest frames/wall, the lowest p10
  and the highest vCPU ms per frame, all inside the three runs' spread
  (0.94 fps, 0.9 ms/frame).
- The counting cost is below the route's run-to-run noise. One pair bounds
  it there; it does not measure it.
- The pre-registration's reference was fpstelemetry1008's 27.23 median;
  the same-ref spread above is the tighter one.

### Dispatch, from the counters [rr425] already prints (D, per 2 s window)

- `hc` = 16 M, so `helper_lookup_tb_ptr` runs 8 M times a second. It misses
  about 27 times a second (`hm`).
- `it` = 450 k loop dispatches. Of those, `g` = 367 k returned through an
  unpatched goto_tb exit, and **`gs` = 365 k of those because the target
  TB spans two pages**. System-mode TCG never chains into a page-spanning TB
  (cpu-exec.c 2501-2513).
- So 81% of the main loop's dispatches are re-entries of page-spanning
  TBs. They show in [tpc787] as entry pcs ending in `ff9`-`fff`.
- The loop gap (`gapus`) is 3.7% of wall. The rest of the dispatch row's
  17% is `helper_lookup_tb_ptr` on indirect jumps, returns, and direct
  jumps that cross a page (`translator_use_goto_tb` refuses those).
- lane.ibcache's inline probe (opt-in `HAKUX_IBC=1`, off here: `[ibc507]
  on=0`) removes helper calls on jump-cache hits. It gave no fps on any
  title it ran, and J/frame x1.10 on Forza with the idle halt off.

### R3: fix candidates in our code, by expected impact

Prices use the measured share. A sampled host share is worth 1/4 to 1/15 of
itself as removable time (memfast). A measured wait is priced at its
measured ms, times the probability that the time is not taken by the next
wait in line.

| # | candidate (our code) | measured share | win at full scale | P | P x win | evidence for P |
|---|---|---|---|---|---|---|
| 1 | **Report processing holds pfifo.lock (and pgraph.lock) across GPU fence waits**: the #804 wait (reports.c 257-262) and the STALLED finish (reports.c 374) run inside `pfifo_thread`'s lock. Fix shapes: write occlusion reports when their fence signals, without blocking the pusher (the hardware is asynchronous here too); or drop both locks across the fence waits as #474 did for the flip | `lw` 4.6 ms/frame overall (13% of a 36 ms frame), **9.7 ms/frame in windows under 24 fps** (22%); pgraph.lock +2.8 ms in the same windows | slow windows' off-CPU 14.7 -> ~4 ms: 44.5 -> ~34 ms frames there, time-weighted fps ~27.7 -> ~29.5 (the cap is 30) | 0.4 | ~5% of frame time overall, ~9% in slow windows | For: the GPU has headroom (gpu50 19.8 of 44.5 ms), and the vCPU's blocked time is fully named. Against: gpunonrender (reports.c 329-335) took the vCPU off the lock alone on Simpsons and the wait moved to the frame-slot fence, fps down. Decided by the N/W pair below |
| 2 | **Dispatch**: `helper_lookup_tb_ptr` + `tb_lookup` + `qht`, and the main-loop re-entry of page-spanning TBs | 17.4% of cycles (22.8% with the spin excluded), 8 M lookups/s, 182 k page-spanning re-entries/s | 1/15 to 1/4 of 22.8% of work = 1.5-5.7%, 0.3-1.2 ms/frame of 21.5 | 0.3 | ~1% | ibcache's probe removed most helper calls and moved no title's fps. Only the brm test as written passes it, and that pass is the spin's artifact |
| 3 | **softmmu `mmu_lookup1`** (the out-of-line TLB path taken from the load/store helpers) | 7.34% of cycles (9.64% with the spin excluded); the only row that passes the R2 rule in both views (memory class) | 1/15 to 1/4 of 9.64% = 0.6-2.4% of work, 0.1-0.5 ms/frame | 0.3 | ~0.4% | why the inline fast path falls through this often is not measured here (page-crossing or flagged pages, or TLB misses); `tlb_reset_dirty` at 1.25% of brm hints at code-page writes |

Candidates 2 and 3 are work-side and act in every frame. Candidate 1 acts
where frames are late, which is where the frame rate is lost. A 30 fps
title at 29.7+ in 44% of windows gains nothing from faster code in those
windows, because the spin absorbs it. Never a faster clock or governor:
none of the three is one.

## 3f. Pre-registration: does the report-processing wait cost Amped 2 its slow frames? (written before the runs)

Pair, Nova only, investigative (not scored):
- ref b345b5b613 perflog (the apk B2/C/D ran; shader cache warm);
- Amped 2 route `amped2`, 578 s per arm.

| arm | env | order |
|---|---|---|
| N | `HAKUX_FRAMETRACE=1 HAKUX_OCCL_LOG=100 HAKUX_OCCL_WAIT=0` (the #804 wait skipped) | first |
| W | `HAKUX_FRAMETRACE=1 HAKUX_OCCL_LOG=100` (shipped wait) | last |

W leaves `HAKUX_FRAMETRACE=1 HAKUX_OCCL_LOG=100` in the Nova's `env_vars`
pref until the next dispatched request. Both are logging only; the
behaviour is the shipped one.

**Did the code run (each arm, else the arm is inert and reads nothing):**
1. `[occl804] config ... wait=0` in N and `wait=1` in W;
2. `[occl804] f=` lines with `q>0` in both (Amped 2 reads occlusion queries
   in play);
3. frametrace's `fw=` site `pgraph_vk_process_pending_reports_internal+0x37c`
   carries >= 1 ms/frame in W and < 0.3 ms/frame in N.

**Valid:** live play with a moving player in the hold frames, and no
thermal pause.

**Measures,** whole window from the mark, per frame:
- frames/wall fps;
- the share of pace windows >= 29.7 fps;
- `lw` (frametrace);
- `vblk`;
- off-CPU (wall - [tlb68] on-CPU);
- the PFIFO fence wait.

The three-run spread on this ref and route (B2, C, D) is 0.94 fps
frames/wall, 0.09 in the share, and 0.5 ms/frame off-CPU.

**Outcomes:**
- **Hit, the wait is the cost.** All four of these:
  - N's `lw` <= 0.5 x W's;
  - N's off-CPU at least 1.5 ms/frame under W's;
  - frames/wall fps N - W >= +1.0;
  - the share >= 29.7 N - W >= +0.15.

  Then candidate 1 stands at P ~0.8, and the fix shape is the asynchronous
  report write (it gives the guest what the hardware does, without the stale
  read #804 fixed).
- **Moved, the wait goes elsewhere.** N's `lw` <= 0.5 x W's, but fps and
  off-CPU within the spread. Then name the wait that rose: frametrace `vw`
  reasons, the `fw=` sites (site #6, the STALLED finish, is the first
  suspect), and the TB shares of a guest poll. Candidate 1's P drops to
  ~0.15, and the next lever is the frame-slot rotation or ring space.
- **Miss.** N's `lw` > 0.5 x W's: `lw`'s holder is not the #804 wait.
  Read the `fw=` sites by context.

Prediction: hit 0.45, moved 0.35, miss 0.20.

`HAKUX_OCCL_WAIT=0` restores the pre-#804 stale visibility reads. N's frames
may show occlusion-driven artefacts (flares, sun). This is a measurement
knob and never a recommendation.

## 3g. Attempt 6 (2026-10-09 16:2x PDT, resume on Opus)

Why attempt 5 did not finish: it hit the 300-turn cap at 16:23 PDT
(`logs/lane/index.tsv`: MAXTURNS, $20.42), about a minute after it queued
the N/W pair of 3f. Its results (3e) and the pair's pre-registration (3f)
were committed and pushed in f248dd0552. The queue ids were not recorded,
and OUTBOX, PR.md and WAITING still described the 15:4x batch. Nothing it
measured was wrong.

### Queued (ref b345b5b613, Nova, study priority, 23:23Z)

| arm | id | env |
|---|---|---|
| N | `1-1791588183-pmucounters-521453` | `HAKUX_FRAMETRACE=1 HAKUX_OCCL_LOG=100 HAKUX_OCCL_WAIT=0` |
| W | `1-1791588184-pmucounters-521720` | `HAKUX_FRAMETRACE=1 HAKUX_OCCL_LOG=100` |

Both are 578 s on the `amped2` route with `--perflog`. 2 x (578 + 90) s is
22 min, inside `pilots/pmucounters.ok` (10-09).

### Checked before relying on the pair (read from the source, not run)

- **The knob exists at the queued ref.** `reports.c` at b345b5b613 reads
  `HAKUX_OCCL_WAIT`. `0` skips only the #804 `vkWaitForFences` loop and
  prints `[occl804] config ... wait=0`, so mechanism check 1 can be read.
- **R3 #1's premise.** `pfifo_thread` takes pfifo.lock at pfifo.c:2119 and
  calls `pgraph_process_pending_reports` at 2163 without dropping it. A
  fence wait in report processing therefore holds the lock the vCPU's
  DMA_PUT store waits on.
- **R3 #2's premise.** cpu-exec.c:2507 sets `last_tb = NULL` for any TB with
  a second page (`tb_page_addr1(tb) != -1`), counted as `RR_GS`.
- **A parked switch exists for the other wait site.** `HAKUX_STALLFIN=reports`
  (gpunonrender (C')) drops STALLED submits when no report is queued. It was
  refuted on Simpsons: gfps 30.3 -> 25.8, and the vCPU's DMA_PUT wait grew
  4.3 ms. If N reads "moved" to site #6, that switch is not the next arm
  unless something shows Amped 2 differs from Simpsons there.

### Two R1 figures the table implies

- **Mispredicts per indirect branch on the X3 are at most 0.028**
  (0.39 brm / 14.0 `BR_INDIRECT_SPEC` per k-instr). brm counts every branch
  kind, so this is an upper bound. At ~15 cycles a mispredict, 0.39 /kins
  at IPC 3.59 is about 2% of X3 cycles. The brief's bad-speculation row
  (`exit_tb` dispatch, the IBC) is answered no.
- **The JIT work's own IPC on the X3 is about 3.1-3.3.** No sample carries
  an instruction count, so there is no per-TB IPC. The spin's share of
  on-CPU time differs between the two slice classes (D's bins: 38% at 30
  fps; 8-24% across 24-29 fps). Solving good = (1-s_g)w + s_g p and
  slow = (1-s_s)w + s_s p with IPC 3.73 and 3.36 gives the spin p = 4.5-4.7
  and the work w = 3.1-3.3, for s_s from 0.08 to 0.15. The assumption is
  that the spin's share of X3 cycles equals its share of on-CPU time. The
  class verdict ("high IPC, a lot of instructions") holds with the spin
  out: IPC >= 2, front-end and speculation in their miss columns, back-end
  28% between its columns.

### Correction to 3e's frametrace table (written before N and W ran)

`pairread.py` (this directory) reads every measure 3f pre-registered from
a result dir's logcat. Checked against the recorded figures before use:

- On B2, C and D it gives the 3f spread inputs exactly: frames/wall 28.61 /
  28.03 / 27.67, share >= 29.7 0.49 / 0.40 / 0.44, off-CPU 6.7 / 7.2 / 6.9.
- On `1131600` it gives `waits.py`'s vw (bql 0.73, pgraph.lock 3.11, 8332
  frames) and the same impossible line dropped, plus `lw` 4.57 overall
  (3e: 4.6).

Its bins come from each `[hakuX-ft1]` line's own rate, so they differ
slightly from 3e's pace-window bins.

What it adds: in `1131600` the #804 wait has **two** site numbers.

- Site #19 is `pgraph_vk_process_pending_reports_internal+0x37c` with
  ctx=none. Site #25 is the same pc with ctx=rep.
- 3e's table quoted #25 alone.

| fps bin (ft1 lines) | frames | PFIFO fence wait | #804 wait (#19 + #25) | #19 | #25 | #6 STALLED finish | `lw` |
|---|---|---|---|---|---|---|---|
| < 24 | 1557 | 16.61 | **11.93** | 3.91 | 8.02 | 4.69 | 9.84 |
| 24-27 | 1898 | 13.08 | 9.82 | 3.46 | 6.36 | 2.96 | 6.84 |
| 27-29 | 1467 | 9.10 | 8.22 | 4.91 | 3.30 | 0.83 | 2.86 |
| >= 29.7 | 3382 | 7.68 | **7.20** | 5.14 | 2.06 | 0.24 | 1.65 |

- The #804 wait is the larger part of the PFIFO thread's fence wait in
  every bin: 72% in slow windows and 94% at 30 fps. The STALLED finish
  (#6) is the second part, and it grows only in slow windows.
- At 30 fps the PFIFO thread waits 7.2 ms a frame on the #804 fence, yet
  the vCPU's `lw` is only 1.65 ms. The lock costs the vCPU only when it
  needs the lock during the wait, and that happens more often in slow
  windows.
- 3f's mechanism check 3 matches by symbol, so it already covers both
  sites. The outcomes and the probabilities stay as registered. The
  correction makes "miss" less likely to come from the knob missing its
  wait, but it says nothing about "moved": site #6 is still next in line.

### Waiting (2026-10-09 16:4x PDT)

The lane waits on the Nova for N `1-1791588183-pmucounters-521453` and W
`1-1791588184-pmucounters-521720` (WAITING). They are queued behind
surfgpu1009's run. Steps on resume:

1. Run `pairread.py dispatch/results/<N> dispatch/results/<W>`.
2. Check validity from the hold frames (a moving player) and from
   `thermal.jsonl` (no pause).
3. Apply 3f's outcomes as written.
4. Set R3 #1's P from the outcome, then write OUTBOX and set PR.md
   `State: ready`.

Every other deliverable of the 10-09 brief is in 3e-3g.

## 3h. Attempt 7 (2026-10-09 17:2x PDT, resume on Opus): the pair read, W void, N2/W2 queued

Why attempt 6 did not finish: it ended correctly, waiting on N and W. They
finished at 17:10 and 17:20 PDT. Nothing it did was wrong.

### The pair as registered (3f): the knob ran, the control is void

N's request started three times. The 16:32 and 16:59 starts were cut
(`Terminated` in run.log). Its logcat holds only the third start (17:00:17
on, mark 17:05:04), so N's hold frames are the 1705xx-1709xx ones.

| check | N `…521453` (wait skipped) | W `…521720` (shipped wait) |
|---|---|---|
| `[occl804] config` wait= | 0 | 1 |
| `[occl804] f=` lines, with q>0 | 1820, 1820 | 1961, 1961 |
| reports-site fence wait, ms/frame (3f check 3) | 0.00 | 3.33 |
| thermal pause (`thermal.jsonl`) | none | none |
| moving player (hold frames) | **yes**: half-pipe, open slope, rails, a banner, 9 frames | **no**: the same birch trunk in all 8 frames (17:15:24-17:19:49), "Press BACK to reset position" twice, score 0 then 10 |

W is a parked player, so 3f's outcome cannot be applied to N vs W. W's
29.96 fps and 0.98 share at the cap come from the stuck scene, not from the
wait. Its vCPU work is 15.4 ms/frame, against 19.7-21.7 in every run with a
moving rider.

| run | frames/wall fps | share >= 29.7 | work ms/f | off-CPU ms/f | lw | PFIFO fence ms/f |
|---|---|---|---|---|---|---|
| N | 29.52 | 0.70 | 19.7 | 3.4 | 1.36 | 0.64 |
| W (void) | 29.96 | 0.98 | 15.4 | 2.0 | 0.53 | 3.39 |
| B2 / C / D (shipped, no frametrace) | 28.61 / 28.03 / 27.67 | 0.49 / 0.40 / 0.44 | 21.2 / 21.7 / 21.4 | 6.7 / 7.2 / 6.9 | | |

Against B2/C/D, N would meet all four of 3f's hit thresholds:
- frames/wall +1.42 over their mean;
- share +0.26;
- off-CPU -3.5 ms/frame;
- `lw` 1.36 against `1131600`'s 4.57.

These are not the registered control. The envs differ: frametrace is on in N
and off in B2/C/D. N's scene was also lighter: it had no window above 27
ms/frame of work, while B2/C/D had 13-26 such windows each.

### At matched work (`workbin.py`, written after N and W ran)

A route plays the same input, but the rider goes somewhere different each
run. `workbin.py` bins pace windows by the vCPU's work per frame (on-CPU less
the spin), so the scene's load is matched inside a bin. Off-CPU in ms/frame,
with the number of windows in brackets:

| work ms/f | B2 | C | D | N (no wait) | W (wait, void scene) |
|---|---|---|---|---|---|
| < 17 | 2.4 (28) | 2.7 (28) | 2.1 (37) | 1.4 (31) | 1.2 (109) |
| 17-19 | 3.9 (21) | 5.4 (21) | 3.6 (12) | 2.9 (31) | 2.3 (24) |
| 19-21 | 7.8 (23) | 6.0 (20) | 4.1 (14) | 3.2 (32) | 3.5 (7) |
| 21-23 | 6.6 (12) | 7.8 (10) | 8.2 (14) | 3.6 (27) | 6.9 (7) |
| 23-25 | 9.4 (26) | 9.4 (20) | 8.8 (18) | 6.0 (19) | 8.4 (5) |
| 25-27 | 8.5 (19) | 9.2 (16) | 11.2 (25) | 6.7 (9) | |
| >= 27 | 10.4 (13) | 11.4 (26) | 12.2 (19) | | |

- **N is lower than all three shipped runs in every bin.** The gap grows
  with work: 0.7-1.3 ms/frame under 17 ms of work, 2.8-3.4 at 23-25 ms.
- **W, with N's env and the shipped wait, reads like N at low work** (1.2
  vs 1.4, 2.3 vs 2.9). It reads like the shipped runs at 21-25 ms (6.9 and
  8.4, against N's 3.6 and 6.0), but on 12 windows only.
- So part of N's lead at low work is the batch (frametrace on, a later
  hour), not the arm. The arm's effect shows where work is high. That is
  what 3g's reading predicts: the lock costs the vCPU only when the vCPU
  needs it during the wait.

### N's lighter work is the scene, not the arm

The [tpc787] TB shares after the mark show no guest poll loop that vanishes
in N:
- outside the spin, every entry pc's share is in proportion;
- the 00324ffd chain is 38-41% of non-spin TB time in all five runs;
- the one pc absent in N (00164ffd, 0.4-0.5% in B2/C/D) is absent in W
  too.

### Where the wait went in N

- **The PFIFO thread's fence wait** is 0.64 ms/frame. In `1131600` it was
  7.7-16.6.
- **The STALLED-finish site** (`pgraph_vk_finish+0x1330`, ctx rep and
  none) is 0.54 ms/frame. It did not take over.
- **pgraph.lock**: the slow windows N still has (504 of 8967 frames under
  27 fps) wait on it, at 5.9 ms/frame in 24-27 and 11.8 in < 24 (94
  frames). This is the next wait in line, but it acts in few frames.

### Pre-registration: N2 and W2 (written before they run)

Same ref (b345b5b613), Nova, `amped2` route, 578 s each, `--perflog`, and the
same envs as N and W. Order: N2 first, then W2, so the Nova keeps the shipped
wait afterwards.

**Valid:** no thermal pause, and the rider at 3 or more distinct places
across the hold frames. If the rider sits at one spot in 4 or more
consecutive hold frames, the run is void (W's failure).

**Primary:** 3f's outcomes as written (hit, moved, miss), on N2 vs W2.

**Secondary,** scene-matched and inside the frametrace batch:
- Pools: no-wait = N + N2; wait = W + W2.
- W's windows count here. Binning by work conditions on load, and a stuck
  rider gives low-work windows, not wrong ones.
- Bins: work >= 21 ms/frame, each with >= 5 windows in both pools.
- **Hit:** the no-wait pool's off-CPU is lower by >= 1.5 ms/frame,
  frames-weighted over those bins.
- **Miss:** lower by < 0.5 ms/frame.
- Also expected: under 19 ms/frame of work, the pools differ by < 0.5
  ms/frame (N vs W read 0.2 and 0.6 there).

If the two disagree, the secondary sets R3 #1's P, because it controls for
scene and the primary does not. The disagreement is reported.

Prediction:
- either arm void: 0.3;
- primary, if both are valid: hit 0.6, moved 0.3, miss 0.1;
- secondary: hit 0.65, between the thresholds 0.25, miss 0.10.

R3 #1's P after the runs:
- hit: 0.8;
- moved: 0.15;
- miss: 0.1.

Until then the P is **0.6 (provisional)**, up from 0.4. The evidence is N
against the shipped runs at matched work. The registered control was void,
so this is not that test.
