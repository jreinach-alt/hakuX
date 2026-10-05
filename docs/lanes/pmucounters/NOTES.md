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
