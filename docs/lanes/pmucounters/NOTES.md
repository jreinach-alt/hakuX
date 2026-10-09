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
| link check (`scratch/objcheck433.py`: cpu-exec.o built with the Android flags vs `libxemu.so` of 34a0b032b9) | every new undefined symbol is defined in libxemu.so or imported from libc, except `__clear_cache`, a compiler-rt builtin that the NDK links statically (defined `T` in `libclang_rt.builtins-aarch64-android.a`; present in pmuprobe) |

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
