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

**CORRECTED in session 3 (section 6):** the next sentence is wrong. `[rr425w]`
reads `idle_us > 0` in 134 of Nightfire's 168 gameplay windows (up to
0.8 s of each 2 s); only Tron's idle is negligible (1 ms/frame). As
first written: ~~The guest's kernel idle loop never ran in Nightfire's
gameplay: `[rr425w]` reads `idle_us=0` in every window, so G1's absence
costs nothing there and the vCPU's on-CPU time is the guest's own code.~~
Nightfire's 99.8% `run` is therefore an upper bound. On late frames the PFIFO
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

### The duty run's verdict (session 3): PASS, the instrument does not move the pace by 3%

`overhead.py --duty <result> -v` (ref 65bd51712b, Nova, Nightfire, 29
switches, 23 phases scored, 10 on/off pairs). Windows that hold a route
frame or a `--frames-every` screencap (file mtime, +-1 s) are dropped; the
rule as written dropped only the route frames, so both are shown.

| leg | on - off, % of off (95% interval) | screencaps dropped | as written |
|---|---|---|---|
| O2 fps (pace counter) | +8.2% (-0.6 .. +17.0) | +8.2% (-1.1 .. +17.4) | pass: cost bound under 3% |
| O2 gfps | +6.5% (-1.1 .. +14.1) | +5.6% (-2.3 .. +13.5) | pass |
| O3 vCPU run share | +0.07% (-0.35 .. +0.49) | -0.10% (-0.38 .. +0.18) | pass: inside +-3% |
| O1 builder + writer, us/frame | 27.1 + 62.2 = **89** (insmax 115) | | pass (<= 200) |

The positive point estimate is content, not the instrument: the per-phase
series (`-v`) shows two scene changes on phase boundaries (k=8 -> 11 falls
from 40 to 24 fps, k=16 climbs back) that make the +50% and +22% pairs. In
the steady stretch (k=18-26, every phase 38-40 fps) the five pairs are
-2.8 .. +2.0%, mean +0.2%. Forza's capture (same ref, instrument on
throughout) costs 19.4 + 56.5 = **76 us/frame**.

**Milestone (a): the instrument costs 71-89 us/frame in-process on the
Nova, and moves neither the pace nor the vCPU's run share by 3%, the
resolution one 6-minute run gives.**

## 6. Forza, and the guest idle the in-row record books as `run` (session 3)

### Forza Motorsport, Nova, ref 65bd51712b (`1-1791225335-lane.frametrace-2925645`)

Route: lane.gpuclock's blind Nova route (`forza-nova-frametrace.route`).
The route frames inside the window show the race (race clock 1:26 at
17:00:31, 3:51 at 17:03:11, lap 1/2); the blind pattern keeps the car
against a wall at 0 MPH much of the time, so the window is the race scene
with eight cars, not a lap driven well. `ftread.py captures/<id>`
reproduces every number here.

| | Forza |
|---|---|
| window | 6980 frames, 260 s |
| guest interval (deadline) | 2 VBLANKs (33.4 ms) |
| fps; period p50/p95/p99/max ms | 26.9; 34.4/47.8/51.6/140.8 |
| late frames | 46.1% |

| class (as the in-row record reads it) | all | late |
|---|---|---|
| vsync | 53.9% | - |
| run | 44.2% | 95.8% |
| block | 0.2% | 0.3% |
| unattr | 1.8% | 3.9% |

**That `run` is wrong for Forza; the next table is the correction.** The
in-row build has no guest-idle hook (G1), and Forza idles by spinning in the
kernel idle loop (`sti; nop; nop; cli` at 0x8001b02e), which the record
books as vCPU on-CPU. The selftest pins exactly this
(`rule.gidle_unmeasured_reads_run`). The always-on `[rr425w]` line has the
idle loop's wall time per 2-s window and the interrupt that ended each idle
stretch; `idlejoin.py` spreads each window's idle over its frames:

| per frame, ms (mean; p10-p90 of windows) | Forza | Nightfire | Tron |
|---|---|---|---|
| vCPU on-CPU | 36.0 (31.2-44.9) | 25.7 (20.7-33.0) | 24.2 (16.1-29.7) |
| guest idle loop | **12.5** (6.8-19.6) | **8.2** (0-15.1) | 1.0 (0-2.8) |
| idle ended by the timer (vec 0x30) | 10.9 | 6.0 | 0.7 |
| idle ended by the NV2A (vec 0x33) | 0.8 | 0.9 | 0.1 |
| guest work = on-CPU - idle | 23.5 (20.3-26.9) | 17.5 (9.6-33.0) | 23.2 (14.1-29.1) |
| late frames whose guest work alone exceeds the deadline (window-mean idle / all idle in the late frames) | 44% / 41% | 40% / 34% | 89% / 88% |
| corr over windows: late share vs guest work; vs idle | 0.09; 0.34 | 0.77; -0.39 | 0.58; 0.10 |

Windows binned by their late share (guest work ms/frame, idle ms/frame):

| late share | Forza | Nightfire | Tron |
|---|---|---|---|
| 0-0.2 | 22.3, 10.3 (43 windows) | 15.1, 3.6 (3) | 15.4, 1.1 (60) |
| 0.2-0.5 | 25.3, 10.3 (17) | 12.3, 9.7 (87) | 20.7, 0.2 (25) |
| 0.5-0.8 | 25.2, 16.3 (36) | 14.8, 12.1 (37) | 27.8, 0.4 (34) |
| 0.8-1.0 | 22.2, 12.5 (33) | **31.4, 1.8** (40) | **60.5, 4.7** (10) |

Read per title:

- **Tron: the vCPU is the pacemaker.** Its guest barely idles; 88-89% of
  its late frames exceed the deadline on guest work alone, and its worst
  windows run 60 ms of guest work a frame. Section 4's verdict stands.
- **Nightfire: two regimes.** In 40 of 167 windows nearly every frame is
  late and the guest works 31 ms a frame with almost no idle: vCPU-bound.
  In the other 124 the guest works 12-15 ms a frame, *under* the 16.7 ms
  deadline, idles 10-12 ms a frame, and still misses a third to two thirds
  of its VBLANKs. Those late frames are not the vCPU's work: the guest
  waited, while the PFIFO thread also waited for work (9.1 ms per late
  frame, section 4) and the GPU was a third busy. Section 4's "99.8% run" is
  an upper bound; the window split puts the vCPU-bound share of late frames
  between 34% and 99.8%, most likely near the 40-window regime's share.
- **Forza: not vCPU-bound.** Guest work is 22-25 ms a frame against a
  33.4 ms deadline in every bin, and the late share tracks the idle, not
  the work. Every party is partly idle or blocked in a late frame:

| ms/frame, Forza (on time / late) | on time | late |
|---|---|---|
| period | 35.4 | 39.3 |
| vCPU on-CPU (of which ~12.5 is the idle loop) | 33.8 | 37.1 |
| PFIFO on-CPU | 15.9 | 16.6 |
| PFIFO blocked, in no hooked wait (blocked - its idle) | 13.8 | **15.9** |
| PFIFO idle (waiting for work) | 5.7 | 6.7 |
| GPU execution (timestamp queries) | 16.9 | 18.3 |

  The PFIFO thread is blocked ~15 ms a frame on something the in-row build
  cannot name, while the GPU is busy under half of the frame (p50 48%, no
  frame >= 90%). The shape is a serial chain: the PFIFO thread translates
  (16 ms), then waits on the GPU side (15 ms), and the guest, idle 12.5 ms
  a frame and woken mostly by the timer tick, waits on the PFIFO's
  progress. That is a hypothesis with a direct test: G3 names the PFIFO's
  blocked time (fence, submit, render thread) and G1 makes the guest's idle
  a span the holder split can intersect with it. Not measured until then.

Q2, GPU ms against MHz: 615 MHz on every Forza frame (p50 16.0, p95 28.4
ms). As with Nightfire and Tron, one clock: the clock-or-work question
cannot be answered from these runs, and the owner's rule (10-05 17:05) is
that a clock is not a remedy anyway.

Q3, vCPU blocked by reason (ms/frame, late in brackets): BQL 1.75 (2.95),
held by the main loop while it ran (1.62); halt 0.08; DMA_PUT pfifo.lock
0.03; 81 waits a frame.

Q4, hitches (5 in the window):

| f | P ms | vb | in-row class | vCPU run / blocked | of the blocked, in a hooked wait | PFIFO run / blocked | GPU |
|---|---|---|---|---|---|---|---|
| 6055 | 140.8 | 5 | run | 54.4 / 86.2 | 2.1 (BQL) | 113.1 / 25.7 | 12.6 |
| 7678 | 140.1 | 4 | run | 41.9 / 98.1 | | 116.7 / 23.3 | 16.5 |
| 7800 | 75.7 | 3 | run | 57.1 / 18.6 | | 15.7 / 60.0 | 16.8 |
| 8131 | 138.7 | 4 | run | 27.1 / 111.1 | | 107.5 / 30.7 | 13.0 |
| 8134 | 73.3 | 4 | run | 38.7 / 34.6 | | 12.6 / 60.5 | 8.9 |

Four of the five hitches have more than 20 ms of vCPU blocked time in no
hooked wait (60% of all hitch time). Frame 6055's block shows the
mechanism: the vCPU is off-CPU 86 ms, 2 ms of it in a named BQL wait; the
main loop waits 20 + 51 + 11 ms on the BQL **held by the vCPU**; the PFIFO
thread is on-CPU 113 ms. So the vCPU blocked while holding the BQL, in a
wait the in-row build does not hook, while the PFIFO thread worked. The
sites that fit (a wait taken under the BQL on the vCPU thread) are
`pgraph_mmio_lock`'s settle wait (G5) and the surface-download wait on a
guest access (G8, `surface.c` 2560); the reset paths in `nv2a.c` drop the
BQL and do not fit. The in-row class reads `run` because step 2 sees 54 ms
of on-CPU time; the frame's real pacemaker is the vCPU blocked on the
PFIFO thread. The hitch frames carry the attribution's flaw in the
other direction too: such a frame should read `block`/`pgraph`, not `run`,
once the wait is hooked.

Q5, deadline against delivery: VBLANKs per flip 1/2/3/4: 3.5/71.5/24.7/0.3%
(the guest asks for 2); slack p50 11.9 ms, p5 -6.8, min -108.7.

### What the session-3 reads change

1. The in-row `run` class is trustworthy only where the guest does not
   idle (Tron). For Forza it is wrong and for most of Nightfire's windows
   it is unproven. **G1 is not optional**; section 7 moves it to the top.
2. The "GPU side waits on the vCPU" conclusion of section 4 holds for Tron
   and for Nightfire's vCPU-bound regime only. In Forza and in Nightfire's
   other regime, both sides wait, and the PFIFO thread's unnamed blocked
   time (Forza 15 ms/frame, Nightfire 6.6 ms/frame) is the largest
   unexplained span on the GPU side.

## 7. Next steps, ranked by P x win (three titles read; Simpsons queued)

Win: the late frames (or hitches) the step reaches. P: the probability it
decides or removes what it targets, with the evidence. Per the owner's
10-05 17:05 rule every remedy below is a wait in our code; no clock or mode.

| # | step | win at full scale | P, and why | kind |
|---|---|---|---|---|
| 1 | **G1 + G3 together**: the guest-idle span (`cpu-exec.c` 1255/1276) and the PFIFO thread's fence / submit / render-thread spans (`draw.c`, hooks.diff). Patch written and type-checked. | Forza: all of its late frames (46%, 26.9 -> 30 fps needs ~4 ms a frame). Nightfire: the 124-window regime, roughly half of its late frames. | 0.8 that it names both ends of the wait: the PFIFO spans feed the holder split already (selftest), and the guest idle is already measured per window ([rr425w]); what is unknown is only which PFIFO wait coincides with the guest's idle. The remaining 0.2: the guest's timer-woken wait may be on a condition the host never blocks on (a guest-side poll), which G1 would show as idle with every host thread busy. | instrument (grant) |
| 2 | **If step 1 shows the PFIFO blocked in fence waits while the guest idles: remove the synchronous wait in the translation path** (pipeline the finish so the PFIFO thread keeps translating while the GPU executes). | Same frames as step 1. Forza's serial chain is 16 (translate) + 15 (blocked) + 6 (idle) ms; overlapping the 15 would put the frame under 33.4 ms with GPU execution (17-18 ms) still under half the period. | 0.5 now (conditional on step 1); the shape fits, the site is unnamed. The work that fits the hardware: the GPU is idle half the frame, so the CPU side waiting for it is the waste. | code (the hard work) |
| 3 | **G9** (MMIO split, `system/memory.c`) and the vCPU JIT direction it aims (owner 09-28). | Tron (89% of late frames are guest work; 60 ms a frame in its worst windows) and Nightfire's 40 vCPU-bound windows (31 ms a frame against 16.7). | 0.8 that G9 separates guest code from MMIO; ~0.9 that a faster vCPU moves these frames (measured: the guest works past the deadline with nothing else busy); the size per JIT change is unknown (memfast: 21% of host instructions for 4-6%). | instrument, then the hard work |
| 4 | **G5 + G8**: the vCPU's waits under the BQL (`pgraph_mmio_lock`, surface download on guest access). | Forza's hitches: 4 of 5, 60% of hitch time (82 ms of vCPU blocked in no hooked wait in f6055, with the main loop stalled behind it). Hitches only; the average does not move. | 0.7 that one of the two is the site (they are the waits on the vCPU thread that keep the BQL). | instrument (grant) |
| 5 | **G4** (DMA_PUT pfifo.lock holder). | Tron: 5.1 ms of each late frame, its 11% unattributed. | 0.5 | instrument (grant) |
| 6 | Load-shaped hitches (Tron 0.6-0.7 s, runs of 100+ ms frames): join with `[ide425]` and frames. | Hitches only. | Medium; hitchcause found MTV's 330 ms hitches are guest-side waits, not the IDE read. | read, no device |

Not on the list: anything GPU-execution-side. No frame in three titles had
the GPU busy over 90% of its period, and the clock sat at 615 MHz.

## Why attempt 1 did not finish

It finished by the contract: it ended at 09:20 PDT on a `waiting:` for three
queued Nova runs (WAITING), with the G1-G8 grant and the Simpsons host
capture outstanding in OUTBOX. The runs completed 10:50-11:22; session 2
was the resume.

## Why attempt 2 did not finish

Also by the contract: it ended at 12:25 PDT on a `waiting:` for the duty
overhead run and the Forza capture (WAITING), queued behind five
lane.gpuclock requests and pathfind's hold. They ran 16:27-17:05; this
session (attempt 3) is the resume. The grant (G1-G9) and the Simpsons host
capture were still unanswered, so this session wrote a blind Simpsons route
(`simpsons-frametrace.route`) and queued it through the dispatcher instead
of waiting on the host capture.

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

- 10-05 ~17:00 PDT, session 3 (attempt 3, resume): merged master
  (02b01b7b44). Both runs DONE. Duty run judged: PASS (section 5).
  Forza read; the in-row `run` is wrong for it, and NOTES section 4's
  "Nightfire never idles" was wrong (section 6, `idlejoin.py`). Archived
  both captures. Wrote `simpsons-frametrace.route` (blind, from pathfind's
  hold) and queued `1-1791245535-lane.frametrace-680559` (Simpsons, Nova,
  65bd51712b, 420 s, frames every 20 s) behind gpuclock's and
  gpunonrender's five.

### Next session, in order

1. Simpsons `1-1791245535-lane.frametrace-680559`: first check its frames
   show free roam from `mark gameplay` + 20 s (fail closed if not: say so,
   do not substitute a title); archive; `ftread.py`; `idlejoin.py`; the five
   tables into section 6's shape. vcpusleep's 9.4 ms/frame blocked is the
   number to meet or refute.
2. Milestone (c) in OUTBOX; PR.md ready.
3. If granted: apply `hooks.diff` (+ G9) as one commit, selftest,
   type-check, re-capture Forza and Nightfire first (section 7 step 1).

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
- Reading the in-row `run` class as "the vCPU's guest work" without
  `idlejoin.py`: Forza reads 95.8% `run` and is not vCPU-bound. Until G1
  lands, every `run` verdict needs the [rr425w] idle join beside it.
- Checking "the guest never idles" on a few `[rr425w]` lines: count the
  zero and non-zero windows inside the gameplay window (Nightfire: 34 zero,
  134 non-zero; session 2 concluded "zero in every window").
- Judging the duty run without the `--frames-every` screencaps: each one
  costs frame rate (request.sh says so) and their mtimes are the only time
  they carry; `overhead.py` now drops them.
- QEMU threads are not named on Android (`debug-threads` is off), so
  `/proc/self/task/*/comm` cannot find the render thread; and
  `pthread_setname_np` refuses names over 15 characters
  (`pgraph.vk.render` is 16). A thread is found only by registering itself.
