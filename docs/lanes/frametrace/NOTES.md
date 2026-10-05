# lane.frametrace (#433): per-frame critical-path telemetry

Brief: `briefs/frametrace.md` (owner intent 2026-10-05 08:3x PDT: "A blind
search for inefficient code is not the right approach. It must be
targeted."). The lane builds the instrument that says, for every guest
frame, who set the pace. It makes no performance change.

Base: master @ d32c35d3ce (merged at start; already current).

## 1. The instrument (`HAKUX_FRAMETRACE=1`; off by default)

Code: `hw/xbox/nv2a/pgraph/profile.h` (the core, as a single header so the
selftest compiles it without QEMU), `profile.c` (its one implementation;
the flip and present hooks), `system/cpus.c` (BQL, halt, thread
registration).

### What a frame record holds

One `HakuxFtFrame` per guest flip (FLIP_STALL reaching the PFIFO thread).
Durations in us over the flip-to-flip period P, on one clock (cntvct on
arm64, as `nv2a_clock_ns`):

| field | source | always on in master? |
|---|---|---|
| P, vb (VBLANKs since the last flip), np (presents) | flip time; `pacing.vblank_fired`; `nv2a_profile_increment` (the guest's INCREMENT write from its VBLANK ISR) | yes (counters) |
| ireq, the guest's interval | smallest VBLANK count used by >= 5% of the last 256 flips (or `HAKUX_FRAMETRACE_VB`) | new |
| vCPU / PFIFO / main rows: run, rq, blk | each thread's `/proc/self/task/<tid>/schedstat` at the flip (on-CPU, run-queue wait; blocked = P - both) | new |
| waits by reason, per row | `hakux_ft_wait_begin/end` around a wait; a wait in progress at the flip is split there | new |
| vh: the vCPU's lock waits by what the holder did | see below | new |
| gidle (guest idle loop) | **needs grant G1** (`accel/tcg/cpu-exec.c`); NA until then | - |
| pidle (PFIFO waiting for a kick) | `renderer_idle_acc_ns` (pfifo.c) | yes |
| lockw (the DMA_PUT pfifo.lock wait) | `cpu_working.lock_wait_ns` (user.c) | yes |
| gpu, rp | `phase_working.gpu_total_ns` from `gpu_ts_readback`: GPU time of the command buffers whose fences were waited this frame, so about one frame late | yes |
| mhz | `pread` of kgsl `gpuclk` (or devfreq `cur_freq`) per frame, if the app may read it; 0 otherwise | new |
| ins | this builder's own time | new |

In-row hooks today: the vCPU's contended BQL acquires (with the holder's
role), the vCPU's halt (idle halt or hlt), the flip, the present, thread
registration for the vCPU (`cpu_thread_signal_created`), the main loop
(`qemu_init_cpu_loop`) and the PFIFO thread (its first flip). The hooks
outside the row are requested in OUTBOX (G1-G7).

### The holder split ("A waits on B")

A vCPU lock wait names its holder role (pfifo.lock and pgraph.lock: the
PFIFO thread; the BQL: whichever role took it last). At the wait's end, its
span is intersected with the holder's own recorded waits (its span ring,
spans >= 200 us, plus its wait in progress); each overlap is booked to that
wait's class (GPU: fence or download; RENDER: submit or render-thread;
IDLE; WAIT: another lock or halt) and the rest to RUN (the holder on its own
work). So a wait during which the holder sat in a GPU fence is booked GPU;
during which it ran, RUN; half and half, half each.

The first version booked a wait to a class only if the holder's state word
was the same at both ends (the brief's "B was running the whole span"
taken literally). **The live selftest refuted it**: a holder always leaves
its fence wait before it can release the lock, so its state changes inside
every real GPU-held wait and every one read MIXED. The overlap split reduces
to the literal rule when the holder was in one state throughout.

### The attribution rule

`hakux_ft_attribute()` in profile.h, run on the device (the 1 Hz histogram,
the CSV's `cls`) and in the selftest. D = ireq x the VBLANK period.

1. On time (vb <= ireq): **vsync**. The guest asked for this pace.
2. Late, and guest work + run-queue wait > D: **run** (guest-vCPU-run). With
   every wait removed the frame would still miss.
3. Late otherwise: the waits made it late. Each wait is charged to a class
   and the largest charge is the pacemaker:
   - lock wait, holder running or in another lock: **block**
   - lock wait, holder in a GPU wait; the vCPU's own fence/download wait: **bgpu**
   - lock wait, holder in a render/submit wait; the vCPU's own: **rsub**
   - lock wait, holder unknown or idle; the DMA_PUT wait seen only by
     `lock_wait_ns`; blocked in no named wait: **unattr**
   - guest idle (the guest waited): GPU busy >= 90% of P: **gpu**; else the
     PFIFO thread's largest non-idle share if it is at least its idle (fence:
     **gpu**, render: **rsub**, on-CPU work: **pgraph**, blocked unnamed:
     **unattr**); else **unattr** (both sides idle: the guest waited on time).

`crit` is the charged length: work for run, work + the pacemaker's charge
otherwise. A high unattr share is a finding: it says which hook is missing.

**Known gap before G1:** without the guest-idle hook the vCPU's on-CPU time
cannot be split into guest work and the idle loop's spin. A title that idles
by spinning (Forza: 20 ms a frame, vcpu60 1.2) then reads **run** where it is
GPU-paced. The selftest pins this (`rule.gidle_unmeasured_reads_run`). Read
in-row captures of such titles with that in mind.

### Output

- `hakuX-ft1`, once a second of frames: frames, wall clock (`rt_ms`, to
  merge thermal.jsonl) and trace clock (`t_ms`), ireq, the pacemaker
  histogram (`pm=`) and the same for late frames only (`pml=`), period
  p50/p95/p99/max, GPU ms p50/p95, mean MHz, per-frame means of vCPU run /
  guest work / guest idle / run queue / blocked, vCPU waits by reason
  (`vw=`, order `bql,pfl,pgl,halt,idle,fence,submit,rthr,dl,oth`), vCPU lock
  waits by holder class (`vh=`, `unk,run,gpu,rnd,idle,wait`), the PFIFO
  row, slack p50 and p5, VBLANKs-per-flip counts, the builder's cost
  (`ins`, `insmax`, us/frame) and the writer thread's CPU (`wcpu_us`).
- `hakuX-ft`, a hitch block: any period over max(2 x the last second's
  median, 50 ms) dumps the 60 frames before and 10 after (`F` lines) and
  every span >= 0.5 ms in that stretch (`S` lines: row, reason, start,
  length, holder, the share booked to the holder's GPU and run).
- `frametrace_<date>.csv` in the app's external files dir: every frame.
  `--pull 'frametrace_*'` collects it.
- Slack (CSV `slack`, summary `sl50`/`sl05`): the guest's deadline for frame
  N is the present that released frame N-1 plus ireq VBLANKs; slack = that
  deadline - flip N. Negative = late. The present stands in for the VBLANK
  until G6 (it includes the guest ISR's latency).

### Selftest (`selftest.py`, host, ~7 s)

32 checks: the rule on synthetic frames (the brief's pair: a 9 ms
fence-held lock wait reads **bgpu**, the same wait with the holder running
reads **block**), the holder split on live threads (fence holder, running
holder, a holder that runs 4 ms then waits 5 ms), a 30 ms wait split across
two flips, the hitch trigger (one 330 ms frame at 30 fps dumps frames 90-160;
90 ms at 20 fps and 45 ms at 60 fps do not trigger; 110 and 55 do), the
summary histogram adding up, and the off path recording nothing.

Then nine mutants of the header, each removing one mechanism, must each FAIL
the check named for it (holder spans not read, holder wait in progress not
read, holder remainder not booked RUN, step 2 removed, guest idle not taken
out, in-progress split removed, hitch floor removed, holder class taken from
the wait instead of the holder, off path recording). All nine are caught.
Six repeat runs: all pass.

Proposed harness fragment: `selftest-fragment.sh` (to become
`docs/testing/jobs/selftest.d/90-frametrace.sh`; outside the row, named in
OUTBOX).

Checks on the real build: NDK clang type-check of profile.c and cpus.c with
the shared tree's Release compile line re-pointed at this worktree
(`docs/lanes/shaderprebuild569/typecheck.py`): clean (three pre-existing
warnings). `check_android_guards.py`: ok. Desktop build: not run (this
host cannot build desktop; AGENTS.md, the libcurl gap).

## 2. Overhead A/B, written before the run

Same ref (this branch's head), Forza Motorsport on the Thor (the Thor's
copy), `drive forza 400 mark` (lane.gpuclock's Forza route), 400 s. Arm B
`HAKUX_FRAMETRACE=1`, arm A unset, queued B first so the device is left in
the shipped state. Thor runs get cold slots (hakux-thor-coldconfirm).

| leg | measure | pass |
|---|---|---|
| O1 direct cost | B: mean `ins` (builder us/frame) + `wcpu_us` / frames (writer) over the scored window | <= 200 us/frame (target), report the number |
| O2 the pace | median 2-s gfps of the scored window, B vs A | \|B - A\| <= 3% of A, or inside the per-window IQR of A |
| O3 vCPU thread time | `[idlehalt]` run_us per frame (always on, both arms) | B within 3% of A |

One pair cannot separate a 1% effect from run-to-run variance; O1 is the
number the budget is judged on, O2/O3 say whether the instrument moved the
pace by more than the noise. If O2 fails, a second pair is queued (B and A
order swapped) before any conclusion.

## Log

- 10-05 session 1: read profile.c, cpus.c, the vcpu60 / vcpusleep NOTES,
  near30's decompose.py; designed the record; grant request G1-G7 in
  OUTBOX; instrument and selftest written; holder test redesigned after the
  live selftest refuted the whole-span version (section 1).

## Do not repeat

- A whole-span holder test ("same state at both ends") books every real
  GPU-held lock wait as MIXED: the holder leaves the fence before it can
  unlock. Use the overlap split.
- QEMU threads are not named on Android (`debug-threads` is off), so
  `/proc/self/task/*/comm` cannot find the render thread; and
  `pthread_setname_np` refuses names over 15 characters
  (`pgraph.vk.render` is 16). A thread is found only by registering itself.
