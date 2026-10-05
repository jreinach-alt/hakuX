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

## 3. The Thor pilot (2026-10-05 09:06-09:09 PDT): the instrument works; the Thor run did not reach the race

| arm | id | ran | how it ended |
|---|---|---|---|
| B, HAKUX_FRAMETRACE=1 | `1-1791216352-lane.frametrace-2340761` | 42 s, boot + intro videos | `guest exited after 42s`; route `result=terminated` in intro_video; no F/libc line |
| A, unset | `1-1791216356-lane.frametrace-2340965` | 25 s | `ROUTE STOPPED: ...:xemu is gone ... (not-foreground: com.magneticchen.daijishou ...)` |

The arm WITHOUT the instrument died first, with a launcher in front: the
same Thor foreground fault lane.gpuclock's Forza pair hit at 08:51 (Lime3DS
in front, both aborted at 10 s). Not the instrument, and not re-queued on
the Thor (reported in OUTBOX).

What B's record shows (761 frames, `ftread.py --all`; boot and the 30 Hz
intro, not gameplay, so no gameplay claim is made from it):

- **The record is sane end to end.** Every frame has the vCPU, PFIFO and
  main rows; the guest's interval was inferred as 2 VBLANKs (98.2% of flips
  on 2) and 703 of 760 frames read vsync; the 57 late ones are the boot's
  multi-second frames, all **run** (the vCPU on-CPU for most of each).
- **The app can read the GPU clock**: kgsl `gpuclk` read 615 MHz on every
  frame (the max regimen's floor). lane.gpuclock had this as an open
  question.
- **Builder cost: `ins` 17-19 us/frame** in steady state (mean 19.7 over
  the run, boot included). O1's budget is 200.
- In the intro the vCPU is on-CPU about 30 of each 33 ms frame while the
  guest is vsync-paced and **[rr425w] reads idle_us=0**: Forza's intro waits
  for the VBLANK by polling outside the kernel idle loop. G1 (the idle-loop
  hook) cannot see such a wait either; on a late frame it would read
  **run**. A limit to state for any title that busy-waits in its own code.
- **No [hakuX-ft*] line arrived**: the dispatcher's logcat keeps only the
  tags in LOGCAT_SPEC. Fixed at 0bb89cd1f5 (lines go out on `hakuX-lane`).
  pathfind's own logcat spec does not carry `hakuX-lane` either, so the
  Simpsons capture script runs a second logcat.

Slack, as measured: p50 32.6 ms on a 33.4 ms deadline. The flip time is
when the PFIFO thread reaches FLIP_STALL; it stalls there until the guest's
present, so frame N's flip comes about one processing time (1-2 ms) after
frame N-1's release whenever the guest has already submitted frame N. Slack
is therefore "deadline minus when frame N was submitted AND translated",
and it shrinks only when the guest or the PFIFO thread is late; it does not
include the GPU's execution of frame N (asynchronous).

## 4. First reads: Nightfire and Tron on the Nova (ref 0bb89cd1f5)

Read with `ftread.py` (window: `mark gameplay` + 20 s to the end). Raw
frames and the [hakuX-ft*] lines: `captures/<result id>/` (`archive.py`;
`ftread.py captures/<id>` reproduces the tables). Neither run has frames
inside the window (no `--frames-every`): gameplay rests on the route's mark
and its frame, which showed gameplay for both. The duty and Forza runs
queued now carry `--frames-every`.

| | Nightfire (`1-1791216614-...2373212`) | Tron 2.0 (`1-1791216620-...2374008`) |
|---|---|---|
| window | 13017 frames, 335 s | 11642 frames, 260 s |
| guest interval (deadline) | 1 VBLANK (16.7 ms) | 1 VBLANK (16.7 ms) |
| fps; period p50/p95/p99/max ms | 38.8; 24.1/36.7/45.2/246 | 44.8; 17.3/38.3/57.7/1079 |
| late frames | 50.4% | 23.6% |

**Q1. Pacemaker.** Late = more VBLANKs than the guest asked for.

| class | Nightfire all | Nightfire late | Tron all | Tron late |
|---|---|---|---|---|
| vsync | 49.6% | - | 76.4% | - |
| run (guest vCPU on-CPU > deadline) | 50.3% | **99.8%** | 21.0% | **88.9%** |
| unattr | 0.1% | 0.2% | 2.6% | 11.1% |
| bgpu, block, rsub, pgraph, gpu | 0 | 0 | 0 | 0 |

Tron's unattr frames are the DMA_PUT pfifo.lock wait (`lockw`, 5.1 ms per
late frame), which this build sees only as a total with no holder (G4).

**Q2. GPU ms against MHz.** The kgsl clock read 615 MHz on every Nightfire
frame and on 99.1% of Tron's (107 frames at 680). One clock: the
clock-or-work question cannot be answered from these runs (the 107-frame
"elasticity" is a different scene, not a clock effect). It does not decide
anything here: GPU execution p50/p95 is 7.5/14.4 ms (Nightfire) and
4.4/8.5 ms (Tron), the GPU is busy 34% / 22% of the median frame, and **no
frame in either window had the GPU busy >= 90% of its period.**

**Q3. vCPU time per frame, ms (mean; late frames in brackets).**

| | Nightfire | Tron |
|---|---|---|
| on-CPU | 24.85 (27.39) | 19.46 (29.62) |
| run queue | 0.04 (0.04) | 0.03 (0.08) |
| blocked | 0.92 (0.95) | 2.88 (5.97) |
| BQL wait (holder running) | 0.78 (1.07), holder ran 0.75 | 0.41 (0.72), holder ran 0.39 |
| halt | 0.04 (0.08) | 0 |
| DMA_PUT pfifo.lock (`lockw`, no holder) | 0.28 (0.25) | 2.32 (5.06) |
| PFIFO on-CPU / idle (waiting for work) | 13.7 / 5.3 (12.6 / 9.1) | 7.0 / 13.0 (11.2 / 18.8) |
| GPU execution | 7.43 (7.31) | 4.77 (6.85) |

The guest's kernel idle loop never ran in Nightfire's gameplay: `[rr425w]`
reads `idle_us=0` in every window, so G1's absence costs nothing there and
the vCPU's on-CPU time is the guest's own code. On late frames the PFIFO
thread waits for work 9.1 ms (Nightfire) and 18.8 ms (Tron) of the frame:
the GPU side is waiting for the vCPU, not the other way round. The JIT
compiles almost nothing in gameplay (`[tlb68] jcus` 0-1 ms per 2 s); the
on-CPU time is spent running translated code (`[rr425] tbus` 1.2-1.3 s per
2 s, which includes helpers and MMIO: nothing in-row can split those).

**Q4. Hitches** (period > max(2 x median of the previous 60 frames, 50 ms);
every row in `ftread.py`'s section 4; blocks in `captures/*/ft.log.gz`).

| | Nightfire | Tron |
|---|---|---|
| hitch frames in window | 40 | 88 |
| pacemaker | run 39, vsync 1 (a 56 ms frame on 1 VBLANK) | run 88 |
| largest | 246 ms: vCPU on-CPU 241, PFIFO on-CPU 172 | 745 and 585 ms (11:12:01-02): vCPU on-CPU 731 / 528, PFIFO idle 731 / 570, GPU < 1 ms |
| runs of slow frames | 10:45:31-10:46:30: ~30 frames of 64-81 ms, vb 4-6, GPU 0.5 ms, PFIFO idle 62 ms, vCPU on-CPU throughout | 11:11:55-58: 30 frames of 100-142 ms, the same shape |

Every hitch is the vCPU running with the GPU side idle. The long ones
(Tron's 0.6-0.7 s, the 100+ ms runs) have the shape of a load: GPU ~1 ms,
PFIFO waiting, the JIT not compiling (`jcus=0` in Tron's 11:12:00 window),
the vCPU busy in guest code. Without frames in the window I cannot say what
was on screen; the queued runs capture frames.

**Q5. Deadline against delivery.**

| VBLANKs per flip | Nightfire | Tron |
|---|---|---|
| 0 / 1 / 2 / 3 / 4 / 5+ | 0.1 / 49.5 / 47.8 / 2.0 / 0.3 / 0.4 % | 0.8 / 75.6 / 19.6 / 2.9 / 0.3 / 1.0 % |
| slack p50 / p5 / min, ms | 1.26 / -12.24 / -229.1 | 15.41 / 5.79 / -554.6 |

Both titles ask for 60 (one VBLANK). Nightfire meets it on half its flips
and takes two on the other half; Tron meets it on three in four.

### What this first read says, and what it cannot

On both 60 Hz titles the late frames are the vCPU's: its on-CPU time alone
exceeds the 16.7 ms deadline (27.4 and 29.6 ms on late frames) while the
PFIFO thread waits for work and the GPU is busy a third of the frame or
less. Locks cost 1 ms (Nightfire) to 3 ms (Tron) of vCPU time per frame.
That is the answer to "which chip waits on which" for these two: **the GPU
side waits on the vCPU.**

What would make it wrong: guest code that busy-polls for the GPU side reads
as `run` (the Forza intro's VBLANK poll, section 3). Against that here: the
PFIFO thread is idle (waiting for pushes) a third to a half of each late
frame, which a guest polling for PFIFO progress would not produce. Not
excluded: a poll on something other than PFIFO progress. The check is the
`[rr425pc]` hot-pc list joined to the late frames, and G9 (below).

## 5. The overhead pair (separate runs) is void; a one-run test replaces it

| leg | B on (`...2373212`) | A off (`...2374160`) | |
|---|---|---|---|
| O1 builder + writer, us/frame | 25.3 + 46.0 = **71.3** (insmax 119) | - | pass (<= 200) |
| O2 gfps median (IQR) | 41 (33-45) | 37 (33-39) | B **faster** by 10.8% |
| O2 fps from the pace counter | 38.83 | 36.35 | B faster by 6.8% |
| O3 vCPU run_us per frame | 24887 | 25210 | -1.3% |

The instrument cannot make the emulator faster; the pair measured two other
things. **Content:** A's route lost sync (its `mark gameplay` frame is the
letterboxed opening cutscene; B's is the sniper scope), so the windows hold
different scenes. **Temperature:** A started at xo 47 C (it ran right after
Tron), B at 31 C. The pair is void as an O2/O3 reading; O1 (in-process
cost, 71 us/frame on the Nova, 0.3% of a 25 ms frame) stands.

Replacement, built at 65bd51712b: `HAKUX_FRAMETRACE_DUTY=<s>` makes the
writer switch the instrument off and on every s seconds inside one run
(on first). Off is the shipped path (every hook a load and a branch); the
first flip after it is a baseline, not a frame, and the writer reads no
slack across the gap. Each switch is logged
(`[hakuX-ft1] duty=on|off k= rt_ms= t_ms=`). Both arms then share the
content and the temperature, alternating every 15 s. Selftest: three new
checks, three new mutants, all caught (36 checks, 12 mutants).

Judging the duty run (written before it runs): label each 2-s
`hakuX-perf gfps` and `[idlehalt]` window by the phase it lies wholly in
(drop windows that straddle a switch or hold a route frame capture), pair
each on phase with the mean of its two neighbouring off phases, and report
the mean paired difference with its 95% interval. Pass: the interval lies
inside +-3% of the off-phase mean, or its upper cost bound is under 3%.

Queued: `1-1791225231-lane.frametrace-2914369` (Nightfire, duty 15 s,
360 s, frames every 15 s: the captures alternate phases, so each phase
holds one).

## 6. Next steps, ranked by P x win (two titles read; Forza and Simpsons to come)

The win is stated as the late frames it could reach; P is the probability
the step finds or removes what it targets, with the evidence.

| # | step | win at full scale | P, and why | kind |
|---|---|---|---|---|
| 1 | **Split the vCPU's on-CPU time** into translated guest code, MMIO dispatch by device (nv2a, APU, IDE, other) and the rest, per frame: grant **G9** (`system/memory.c` 1485 and 1546, two clock reads around `memory_region_dispatch_read1` / the write op on the vCPU thread). | It aims the vCPU work at every late frame read so far (99.8% and 88.9% of them are `run`): Nightfire needs 27.4 -> 16.7 ms on its late half. | High (0.8) that it decides where the vCPU time goes: `tbus` already puts 60-65% of each 2 s in TBs including helpers and MMIO, and nothing in-row separates them. It is a measurement, so P is the chance it separates, not that it speeds anything. | instrument (grant) |
| 2 | The vCPU JIT direction (owner, 09-28), aimed by step 1's split. | Same late frames; Nightfire 38.8 -> 60 fps needs a 1.6x faster vCPU on its late frames. | The vCPU being the pacemaker is now measured (P ~0.9 that speeding the vCPU's guest code moves these frames); the size per change is not: memfast removed 21% of host instructions for 4-6%. | the hard work that fits |
| 3 | Name the DMA_PUT pfifo.lock wait's holder: grant **G4** (`hw/xbox/nv2a/user.c` 92-95). | Tron: 5.1 ms of each late frame, 11% of its late frames unattributed. | Medium (0.5): it names the holder; whether that holder's time is removable is the next question. | instrument (grant) |
| 4 | The load-shaped hitches (Tron 0.6-0.7 s, 30-frame runs of 100+ ms in both titles): join the hitch blocks with hitchcause's `[ide425]` and the route frames. | The long hitches; they do not move the average. | Medium: the shape (vCPU busy in guest code, GPU and PFIFO idle, no JIT compile) points at the guest's own work on a load; the frames will say whether it is a load screen. | read, no device |
| 5 | G1 (guest idle hook) and G3 (PFIFO fence/submit spans). | Titles that idle by spinning (Forza) and the PFIFO thread's 6.6 ms of unnamed blocked time per Nightfire late frame. | Low for Nightfire and Tron (idle_us=0, so G1 changes nothing there); higher for Forza, which idles 20 ms a frame (vcpu60). | instrument (grant) |

Not on the list: anything GPU-side for these two titles. No frame had the
GPU busy over 90% of its period and the clock never moved off 615 MHz, so a
GPU or clock change cannot reach their late frames.

## Why attempt 1 did not finish

It finished by the contract: it ended at 09:20 PDT on a `waiting:` for three
queued Nova runs (WAITING), with the G1-G8 grant and the Simpsons host
capture outstanding in OUTBOX. The runs completed 10:50-11:22; this session
is the resume. The grant and the host capture are still not answered.

## Log

- 10-05 session 1: read profile.c, cpus.c, the vcpu60 / vcpusleep NOTES,
  near30's decompose.py; designed the record; grant request G1-G8 in
  OUTBOX (`hooks.diff`, type-checked); instrument and selftest written;
  holder test redesigned after the live selftest refuted the whole-span
  version (section 1). Thor pilot read (section 3). Holder thread (`vho`)
  and per-frame wait counts (`nw`) added at 22a1ac3942 (after the queued
  Nova runs' ref 0bb89cd1f5, so those runs do not carry them).
- 10-05 ~09:20 PDT, **waiting** (WAITING file): the three Nova runs
  (Nightfire on, Tron on, Nightfire off), queued behind pathfind's hold and
  five other requests. Also outstanding, not in WAITING because nothing
  resolves them automatically: the G1-G8 grant and the Simpsons host
  capture (OUTBOX).

- 10-05 ~11:30 PDT, session 2 (resume): merged master (750d572f1c). The
  three Nova runs were DONE. Read Nightfire and Tron (section 4); the
  separate-run overhead pair is void (section 5); built the one-run duty
  test (65bd51712b). Archived both captures (`captures/`). Found the env
  outlived my 10:50 run into pathfind's NFL Blitz 2002 hold (its CSV was
  pulled into the Tron result; `archive.py` drops it by clock range).
  Queued: the duty run (Nightfire) and Forza on the Nova (the Thor's Forza
  runs die in their first 42 s, 6 of 6 today; gpuclock's blind Nova route,
  copied as `forza-nova-frametrace.route`).

- 10-05 ~12:20 PDT: G9's in-row half (MMIO time per frame and by region;
  38 checks, 15 mutants) and `hooks-g9.diff` (type-checked, applies clean)
  at 537607f767; not in the queued runs (their ref is 65bd51712b), and
  inert until the grant. Preflight: all gates pass but `coverage` (#829,
  board). **Waiting** (WAITING): the duty run and Forza, behind five
  gpuclock requests and pathfind's hold.

### Next session, in order

1. Duty run `1-1791225231-lane.frametrace-2914369`: judge O2/O3 by the
   rule in section 5 (write the phase-labelling reader into `overhead.py`
   first, then read). Its frames show what the 64-81 ms stretch is.
2. Forza `1-1791225335-lane.frametrace-2925645`: the five tables; check
   the window's frames show the race; G1's absence matters here (Forza
   idles by spinning), so read `run` against `[rr425w] idle_us`.
3. Simpsons: still needs the host capture (OUTBOX). If it does not come,
   say so in the final NOTES rather than substitute a title.
4. If granted: apply `hooks.diff` (+ G9) as one commit, selftest,
   type-check, re-capture.

## Do not repeat

- A whole-span holder test ("same state at both ends") books every real
  GPU-held lock wait as MIXED: the holder leaves the fence before it can
  unlock. Use the overlap split.
- An overhead A/B as two separate runs on a timed route: Nightfire's route
  desynced in one arm (cutscene vs gameplay at the mark) and the second arm
  started 16 C warmer. Use `HAKUX_FRAMETRACE_DUTY` (both arms in one run).
- Trusting every `frametrace_*.csv` in a result's `pulled/`: the env stays
  on the device until the next request, so a held session in between
  writes its own CSV and the next `--pull` collects it (pathfind's NFL
  Blitz 2002 hold, 10:50-11:05, in the Tron result). Select by clock range
  (`archive.py`) or by the run's `[hakuX-ft1] csv=` line.
- QEMU threads are not named on Android (`debug-threads` is off), so
  `/proc/self/task/*/comm` cannot find the render thread; and
  `pthread_setname_np` refuses names over 15 characters
  (`pgraph.vk.render` is 16). A thread is found only by registering itself.
