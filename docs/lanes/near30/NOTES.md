# lane.near30 -- why near-30 titles do not hold 28.5 fps (#433)

Brief: owner 2026-10-02 ~16:25 PDT, "We're close but not quite there yet."
Bar: >= 28.5 fps for >= 90% of the scored window (title_verdict.py, targets.toml).

## Attempt 4 (resumed 2026-10-03 09:31 PDT): why attempt 3 did not finish

Attempt 3 did its work: the Blinx 2 session, the ocean decomposition, the levers, PR.md at
`State: ready`, pushed at 262eac35ad. What it missed was written after its session had started:
the 10-03 rule that every finding outliving the session goes to OUTBOX.md as a `NEW ISSUE:` line,
and the rule that a missed bar is not retested. Its OUTBOX had no NEW ISSUE lines. It also left one
question from Addendum 1 open: whether the first-appearance dips are texture uploads, compiles or
readbacks ("not measured here"). That question could be answered from the raw logcat it had
already captured. This attempt adds no device runs. It merges master (memfast phase 1, 6c828f9860),
answers the hitch question offline (step 2d), notes that lane.vcpuwait433 has taken Tron's lever 1,
and writes the NEW ISSUE lines. Blinx 2 is not retested: its cost is named (2c, 2d), and the fix is
the successor lane's.

## Attempt 3 (resumed 2026-10-03 08:14 PDT): why attempts 1-2 did not finish

Attempt 1 (10-02, to 16:50 PDT) finished the offline Tron/ToeJam decomposition and one Tron
perflog run, then stopped at Step 2b: "WAITING" for lane.local's addendum that the owner's save
existed. Attempt 2 (resumed after that wait) found no addendum on the session it had, so it
wrote OUTBOX and stopped again. The addenda came later: "save exists" at 10-02 17:57 PDT and
"GO" with the golden (savestate433, Blinx 2 golden = save 377a8488c7c5) at 10-03 08:20 PDT. Both
arrived after the sessions had ended, so **no Blinx 2 run was ever made, and the Blinx 2 row,
the ocean repro and the scored window were never written.** This attempt does those.

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

## Step 2c: Blinx 2 on the Nova, the owner's save "Jaguars" (attempt 3, 10-03 08:14-09:20 PDT)

Setup. `titlestate.py prepare --device nova --title-id 4D530065 --state returning` under a held
session (`hold.sh wait`, then `wait-idle` after pathfind's Black Stone hold). It loaded golden
377a8488c7c5 (plan `keep`). The Nova's installed build at 08:15 was vcpuwait433's arm (012fa08a94,
which changes the vCPU sleep this lane measures), so it was NOT used. I built the perflog APK of this
branch (= master 9d1155f919 emulator code + docs) in the worktree with `build-perflog.sh`, installed it
under the hold (`adb install -r`, stamp `0.4.1-1003-9169b18587-perflog`), and ran the session with
`b2.py` (pad, shot, mark) and `scored433.py`. Logcat ran to a file. Nothing was reset or deleted:
Load Game -> slot 1 "Jaguars" -> 1P -> cutscene -> Story mission cards. The save is untouched; the
release wrote the run's writes to `latest` only. `hddPath` was restored.

Build notes for the next lane (cost me two failed builds): `build-perflog.sh` must put
`~/.local/bin` (meson) AND `~/Android/Sdk/cmake/3.30.3/bin` (ninja) on PATH, or CMake fails with
"meson not found" and then "Could not detect Ninja". The build takes about 6 min warm.

Device runs: 1 held session (this is the owner's 2 remaining runs, used as: the ocean repro, then
the scored window). The scored window needed a retry (see below).

### What happened in the session (device clock; marks in `blinx2-perflog-extract.tsv`)

- Post-tutorial zone is the "Arch" timed challenge, not the tutorial's open area. The save loads
  into a cutscene, a mission card, then free roam with a challenge timer.
- **Yaw.** RX +22000 yaws; RX -22000 also yaws in the other direction; RX 11000 does not (as the
  blinx2input notes say). Ocean-in frames: `p6` and `oin1-4`. Ocean-out: cliff faces `p1-p5`, `oout1-3`.
- **Checkpoint retry.** At ~08:52:47 a "RETRY CHECKPOINT? Yes / No" prompt sat on screen for the
  rest of batches 2 and 3 (08:55-09:00). Those batches are NOT gameplay: the 29.97 fps and GPU 0.1 ms
  rows in them are the prompt, so they are excluded from every number below. Choosing Yes at 09:04
  (a button press, not a new run) restored the challenge.
- **Operator dialogue.** Batch 4 ends in a scripted "This is the Operator." dialogue at ~09:08 (the
  last frame). The valid span ends at 09:07:50.

### Ocean in vs out (the owner's dip), perflog, 2-s rows (`ocean433.py`)

| window | s | fps | renderer Tot ms | Draw | Fin (fence) | GPU ms | draws/frame (BE) | guest busy | vCPU on-CPU |
|---|---|---|---|---|---|---|---|---|---|
| ocean OUT (oout 1-3) | 18 | **25.0** | 33.2 | 10.4 | 20.0 | 35.3 | **26** | 0.50 | 0.88 |
| ocean IN (oin 1-4) | 24 | **19.0** | 44.4 | 14.0 | 27.5 | 49.6 | **44** | 0.43 | 0.88 |
| sweep, cliff/sea mixed (s1-s8) | 28 | 21.1 | 39.2 | 12.4 | 23.6 | 42.4 | 31 | 0.45 | 0.88 |

draws/frame = BE per 2-s row / (fps x 2). GPU ms per draw: out 1.36, in 1.13. So the ocean does not
make each draw dearer; it adds draws (+70%), and GPU time follows the count (+40%). TexU is 0 in every
window: no texture uploads in steady-state ocean frames. The "first-appearance" texture dips the owner
saw are NOT measured here (no first-appearance event in these windows).

Owner's read: CPU or GPU? The vCPU is on-CPU 0.88 in both windows (no change). The guest is idle
about half the time (guest busy 0.43-0.56), so the guest is not the long pole. The renderer waits on
the GPU (Fin) and the GPU's time grows with draw count. **Ocean dip: GPU-side, draw-count-driven**
(water/reflection draws, per the owner's candidates). Not CPU-side.

### Scored window (the Playable input), valid spans only

| span | s | rows | share >= 28.5 | median fps | Tot ms | GPU ms | Fin ms | guest busy | vCPU on-CPU |
|---|---|---|---|---|---|---|---|---|---|
| A: batch 1, first pass | 98 | 39 | **0.44** | 28.0 | 33.7 | 34.4 | 19.1 | 0.56 | 0.85 |
| B: retry to Operator | 216 | 74 | **0.03** | 21.2 | 40.8 | 44.2 | 24.4 | 0.45 | 0.89 |
| all valid | 314 | 182 | **0.115** | 22.2 | | | | | |

The 600-s bar is NOT met: 314 s of valid play (about 5 minutes) out of about 20 minutes of scored
batches, with the retry prompt and the dialogue in the rest. The batch-4 frames' FPS overlay reads
17-28 on free roam; the
earlier OCR'd Test 1 median (27) is a different area. The post-tutorial Arch area is far below 30.

Caveats, stated: (1) a screenshot every 6 cycles; a screencap may stall the emulator, so some
low rows may be the shot. Not measured. (2) pace rows arrive ~every 2-3 s, so windows of 18-24 s
hold 7-8 pace rows. (3) GPU ms is the phase line's `GPU:`; GPU >= Tot in B, so it is not a
disjoint slice of the frame; read it as relative cost, not as ms that add up. (4) no simpleperf on
this session.

### Blinx 2 frame-time budget (per frame; out vs in, and the valid-A/B spans)

| ms per frame | ocean OUT (median ~ 40 ms frame) | ocean IN (~ 53 ms) | valid span B (~ 49 ms) | gap to 33.3 |
|---|---|---|---|---|
| vCPU on-CPU | 0.88 x F | 0.88 x F | 0.89 x F | not the gap: the guest idles 45-55% |
| guest idle | ~50% of F | ~57% of F | ~55% of F | guest is not the long pole |
| renderer GPU (Fin + Draw) | 30 | 42 | 37 | the gap lives here |
| draws / frame | 26 | 44 | ~37 | the count, not per-draw cost |

Honest about the table: the per-frame values are from the 2-s rows and are relative, so the gap
column is a ratio read, not an exact ms sum. The ocean-in frame is ~1.3x the ocean-out frame.

### Levers, ranked by P x win (the rule: effort is a tiebreaker)

| # | lever | P | evidence for P | win if it works | cost |
|---|---|---|---|---|---|
| 1 | **Cut the water/ocean draw count on the GPU path** (batch or instance the water and reflection draws; push constants per the bf2push656 pattern to cut binds) | 0.35 | draws +70% with GPU ms +40% and per-draw cost down: the count is the cost. bf2push656 halved binds on BF2 but BF2's GPU time did NOT move (judged), so the bind count alone is not the lever; the draws themselves are | ocean dip 19 -> ~24 fps if the ocean half of the draws goes; sweeps ~21 -> ~25 | 1 measurement (frame dump at in vs out to name the draws) + a renderer change |
| 2 | **Memfast / fastmem for the vCPU** | 0.15 here | the vCPU is busy 0.88 but the guest is idle half the time, so faster JIT buys little on this title. P is low for Blinx 2, high for Tron (near30 NOTES step 3) | ~1-2 fps on Blinx 2; the broad win is on CPU-bound titles | board grants (stranded) |
| 3 | Ubershader / shader-compile stalls | 0.05 | TexU 0 and no compile events in the steady windows; the ubershader is already the default (folded 10-02) | first-appearance hitches only | none |
| 4 | Texture upload / readback (first-appearance dips) | 0.2 | the owner's dips at first appearance; NOT measured here (no event in these windows) | hitches; steady fps not affected | 1 run with a first-appearance trigger |
| 5 | GPU clock regimen | 0.2 | GPU-side verdict, but GPU MHz not read in this session | up to ~20% of the GPU ms if it is clock-limited | the regimen, not code |

Ranking note: #1 is first on P x win: it explains the ocean dip with a measured count (+70%), and it
has a cheap decider. It is not the cheap option: naming the draws is one frame dump at in and out, and
the fix is a renderer change. #2 is the approach that fits this hardware, but on Blinx 2 the guest
is not the long pole, so its P is low here.

### Successor brief (lever 1)

    Lane: oceandraw433   Issue: #433   Device: Nova, 1 held session (frame dump, no scored window)
    # Name the draws the ocean adds to Blinx 2's frame, and decide: batch them, or make each one cheaper

    lane.near30 (docs/lanes/near30/NOTES.md, step 2c): Blinx 2 (golden "Jaguars", post-tutorial Arch area)
    drops from 25 fps to 19 when the sea is in view. Draw calls per frame rise 26 -> 44; GPU ms per draw
    fall 1.36 -> 1.13; the vCPU is on-CPU 0.88 in both; TexU is 0.

    1. ONE held session, perflog build of master, the same Load Game path (`b2.py`, `oin`/`oout` marks,
       `ocean433.py`). Take the per-draw frame dump (`frame_dump.on`) at ocean-in and ocean-out.
    2. Classify the extra ~18 draws per frame in the in-frame by shader, texture and render target, and by
       coverage (screen area). Expected if the count is the cost: many small draws with the same state
       (batch them). If a few large draws dominate: fragment cost (the water shader or a render-to-texture
       pass), then lever 1 is the wrong fix.
    3. Decide by the split: small same-state draws -> lever 1 (batch/instance, P 0.5); a few large -> fragment
       (a different lever, the reflection pass). Write the prediction before any arm.
    4. Do not touch the JIT (memfast owns it) or the ubershader path (folded).

## Step 2d: Blinx 2's first-appearance hitches, from attempt 3's logcat (attempt 4, offline, no run)

`dips433.py <logcat>` builds one row per `hakuX-pace` second from lines that every build prints:
fps, worst frame (`max`), draws per frame (BE), GPU ms, texture uploads (`txu[` n/KB, `new`, `rb`),
surface downloads (`sd[... dl`), pipeline and shader cache misses and draw-path pipeline create
ms (`[shd413]` dpm, dsm, dpc_ms). Input: attempt 3's raw logcat (`b2run/r1/logcat.txt`, untracked),
which runs the ubershader default (`[gpl569] mode=3`, `[uber569] uncovered=0`). Gameplay rows run
from 08:44:05 to 09:07:50 with >= 5 draws per frame (n = 258).

| second | worst frame ms | GPU ms/frame | new textures (KB) | pipeline misses | draw-path create ms | GPL lib compile ms in the row |
|---|---|---|---|---|---|---|
| 08:44:08 (first gameplay load) | **3685** | 28 | 7 (37) | 55 | **2960** | 161 |
| 08:44:14 | 203 | 87 | 13 (94) | 13 | 0.3 | 0 |
| 08:44:18 | 107 | 47 | 5 (98) | 2 | 0.1 | 0 |
| 08:44:21 | 102 | 38 | 0 | 5 | 0.2 | 0 |
| 08:44:23 | 116 | 35 | 3 (14) | 0 | 0 | 0 |
| 08:46:04 | 184 | 29 | 17 (106) | 2 | 0.1 | 0 |
| 08:46:56 | 131 | 27 | 1 (64) | 5 | 0.2 | 0 |
| 08:52:19 (challenge reset) | 379 | 63 | 0 | 29 | 78 | 77 |
| 09:06:12 | 161 | 34 | 0 | 1 | 16 | 16 |

Over all 258 gameplay rows, surface downloads appear in 1 row and texture readbacks in none.
Pipeline misses appear in 8 of the 9 hitch rows and in 3 of the 249 other rows.

Read:
- **Not texture upload or convert.** A hitch second carries at most 17 new textures and 106 KB.
  The steady 1-s rows upload 30 MB/s of dirty-texture refresh (`cvt30720K`) at 60 fps in menus
  without a hitch.
- **Not surface readback.** There are 0 readbacks in hitch rows.
- **It is a new pipeline: 8 of 9 hitches, against 3 of 249 other rows. But the CPU-side compile we
  measure is not the time.** In 5 of the 8, the draw-path create time is at most 0.3 ms and the GPL
  library compile is 0, because the ubershader covers the miss. In 2 more (08:52:19 and 09:06:12),
  the compile is 78 and 16 ms, against worst frames of 379 and 161 ms. The one exception is the cold first
  load at 08:44:08, which is a loading screen: 55 misses and 2.96 s of draw-path create. In that row
  the ubershader cannot cover the miss yet.
- So the 100-380 ms frames at a new pipeline are spent somewhere these counters do not see. Two
  candidates, neither measured: Turnip's first use of a fast-linked GPL pipeline (lazy driver
  work at bind or first submit), and the GPU frame itself (GPU ms rises to 35-87 in those rows).
  Per-frame (not per-second) timing at a hitch would separate them. The `[uber569]` swap from the
  uber pipeline to the specialised one is a third candidate.

What a hit would look like for each: (a) driver first use: the render thread's Draw or Pipe phase
rises in the hitch frame while GPU ms does not; (b) GPU frame: GPU ms for that frame rises; (c) the
swap: the hitch lines up with an `[uber569] next=` increment.

## Lever table, re-scored at attempt 4 (all three titles)

| # | lever | title | P | evidence for P | win | cost | owner |
|---|---|---|---|---|---|---|---|
| 1 | **Blinx 2: the sea's extra draws** (name them with a per-draw dump, then batch them or cut fragment cost) | Blinx 2 | 0.35 | draws 26 -> 44 per frame, GPU 35 -> 50 ms, fps 25 -> 19; per-draw cost falls, so the count is the cost | sea-in 19 -> ~24 fps; Blinx 2 is the title furthest below the bar (0.115) | 1 held session + a renderer change | unowned: successor `oceandraw433` (step 2c) |
| 2 | Tron: the vCPU's GPU-side sleep | Tron, BF2 | 0.3 (unchanged) | vcpuwait433 removed the intro's pfifo.lock wait (pixels PASS 45/45). In-level v_blk did not drop (6.93 against 5.70 ms), and the in-level site is unmeasured | ~3 ms/frame on Tron, ~6 on BF2 | its lane's in-level off-CPU capture | lane.vcpuwait433 |
| 3 | vCPU JIT (memfast phase 2, fastmem) | Tron, every CPU-bound title | 0.5 on Tron, 0.15 on Blinx 2 | phase 1 folded at 6c828f9860 (pixels PASS, J not shown at the 30 fps cap) | ~3.5 ms/frame on Tron | board grants | lane.memfast |
| 4 | Blinx 2 new-pipeline hitches (step 2d) | Blinx 2 | 0.25 that per-frame timing names one of (a)-(c) and that it has a fix | 8 of 9 hitches sit on a new pipeline. In 5 of those 8, the measured compile is at most 0.3 ms | 100-380 ms hitches. Not the scored share: they are 9 of 258 seconds | 1 perflog session with per-frame logging at hitches | unowned |
| 5 | GPU clock regimen | Blinx 2 | 0.2 | GPU-side verdict, but no GPU MHz in the held session | up to ~20% of GPU ms | regimen | -- |

Lever 4 ranks below lever 1 because the hitches are about 3% of gameplay seconds, while the sea
costs about 6 fps on every view of the sea. Lever 1 is still the top lever for Blinx 2.

## Files

`dips433.py` (attempt 4: the per-second hitch classifier, step 2d).

`decompose.py` (the reader), `decompose.out` / `windows.tsv` (the 8 plain
runs), `tron-perflog.out` / `tron-perflog.tsv` (run 1), `tron-newgame.route`
(copied from origin/lane/tronhang672), `peek_runs.py`, `peek_rdc.py` (scratch
readers).

Attempt 3 (Blinx 2): `ocean433.py` (decomposer, marks on the device clock), `blinx2-perflog-extract.tsv`
(the perflog lines it reads, 1 MB, from the held run's logcat), `b2.py` (the held-session hands),
`scored433.py` (the walk-and-look batches), `build-perflog.sh` (the perflog APK with meson/ninja on
PATH). The frames (92 MB, `b2run/`) and the raw logcat (12 MB) stay untracked on the worktree.
