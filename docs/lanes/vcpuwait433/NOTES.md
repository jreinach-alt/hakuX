# lane.vcpuwait433: what puts Tron 2.0's vCPU to sleep for a quarter of every slow frame (#433)

Brief: lane.local 2026-10-02 18:03 PDT (owner-approved), from lane.near30's
lever 1 (`docs/lanes/near30/NOTES.md` on origin/lane/near30). Base master
9550493846. Nova, at most 3 runs, shared with uberdefault569 and memfast.

The premise, measured by near30 (Nova, device defaults): in Tron windows
below 28.5 fps (median F ~43 ms) the vCPU thread is asleep, neither running
nor runnable, ~10 ms per frame. That sleep tracks GPU ms per frame (r 0.64),
not the renderer's CPU draw work (0.08). BF2: 21 ms of a 64 ms frame.

## 0. Attempt 2 (2026-10-02 18:54 PDT): why attempt 1 stopped, what tron1 showed

Attempt 1 did not fail. It finished in the waiting state the protocol asks
for: the capture is host-operated, the request went to lane.local through
OUTBOX.md, and the session parked on it. lane.local ran it 18:46-18:54 PDT
(addendum 1) and resumed the lane. The output landed in
`~/hakux-work/perf/2026-10-02-vcpuwait433/tron1/`, the path the script
writes to. The addendum said it was in the worktree, but that path is only
in the script.

**tron1 is void for the brief's question: it recorded a menu, not the level.**

- Frames: the "gameplay" frames from mark through prof end (185202 to 185346)
  all show Options > Display at 59 fps.
- Cause: the Nova's `hdd.img` no longer holds a Tron save. On Single Player
  (185013) Auto Load and Load Game are greyed and the cursor starts on New
  Game. The route's one DOWN was written while a save existed (tronhang672 v4).
  Here it skipped the greyed Load Game and landed on Light Cycles (185021).
  A then opened Circuit Play (185027), and the 8 START/A pairs walked out to
  Options > Display.
- decompose.py on the run's own logcat: 56 rows, all at or above the bar,
  59.9 fps. v_run 16.1, v_rq 0.04, **v_blk 0.52 ms/frame**. Near30's slow
  window had 10.

waitsite.py on tron1.data (vCPU tid 737, 60.0 s span) is still a usable
**control**: what the vCPU's off-CPU time looks like when nothing is slow.

| site | ms in 60 s | % attributed | switch-outs | per frame (60 fps) |
|---|---|---|---|---|
| BQL <- cpu_exec_loop | 952 | 69.2 | 63,260 | 0.26 ms |
| (unsampled switch-out) | 521 | (27.5% of off-CPU) | 3,030 | |
| pgraph.lock in PGRAPH MMIO (#474) | 196 | 14.3 | 508 | 0.05 ms |
| BQL <- mttcg_cpu_thread_fn | 147 | 10.7 | 7,799 | 0.04 ms |
| everything else | < 40 | < 3 | | |
| **total off-CPU** | **1,895 (3.2%)** | | | **0.53 ms** |

The trace's 0.53 ms/frame matches decompose's v_blk of 0.52, so the reader
and the scheduler accounting agree on this build. In a menu the BQL wait is
about 1,000 short waits a second (15 us each), interrupt entry contending
with the I/O and PFIFO threads. For the slow-window capture, a BQL row near
0.3 ms/frame is this baseline. A BQL row near 10 ms/frame would be a holder
paced by the GPU.

**Fixes, so run 2 records the level:**
- `tron-newgame.route` v5 drops the DOWN. A then picks the top enabled entry:
  New Game with no save (near30's path), Auto Load with one. Both end
  in-level. The `menu-cursor` frame shows which one ran.
- `capture_offcpu.sh` gets a slow-window gate. After mark + 10 s it waits for
  a hakuX-pace second below 40 fps (cap 90 s) before recording, and logs
  which way it started. SOAK_S goes from 420 to 510 to cover the cap. On
  tron1's logcat the gate reads 60 fps and would have held.

### Next (P x win, after tron1)

| candidate | P | evidence for P | win if it works | cost |
|---|---|---|---|---|
| **A. Re-run the capture: v5 route + gate (run 2 of 3)** | 0.6 that it yields a named site: 0.8 reaches the level x 0.8 lands in a slow window x 0.95 that a site clears 50% or the split is clean | route: the frames show the no-save state, and New Game is near30's path. Slow: 4 of near30's 5 New Game soaks were slow in the first 2 min. The gate catches the 5th | names the wait behind up to 10 ms of a 43 ms Tron frame. That opens step 2 (removing it: BF2 21 of 64) | 1 run (~11 min Nova), ~20 min session |
| B. BF2 capture instead | 0.4 | bigger sleep (21 ms/frame). But I have no route evidence for a slow BF2 in-level window under this script, and the brief names Tron | same mechanism, x2 the ms on BF2 | 1 run + route work |
| C. Stop and report tron1 | - | a menu cannot answer the question | 0 | 0 |

A goes first: it is the brief's measurement, with its one known failure
fixed. If A again fails to reach the level, B uses run 3.

## 1. The capture (step 1), set up and waiting on the host

The capture is host-operated: a lane does not touch a device. Status:
**requested from lane.local in OUTBOX.md, 2026-10-02 18:20 PDT, not yet run.**

`capture_offcpu.sh` is slowdown462's `capture_profile.sh` (the trace that
found DOA's `pgraph_read` wait, #474) with only these changes:

| what | slowdown462 | here | why |
|---|---|---|---|
| route | titles/routes/survey | `tron-newgame.route` (near30's, sha256 a527657b...; v5 from run 2, e07149a1..., no DOWN: section 0) | the route of the decomposed soaks |
| anchor, delay | `mark play` + 60 s | `mark gameplay` + 10 s | on 4 of near30's 5 New Game soaks the first 2 min after that mark are the run's slowest: 16-25 of 30 rows below the bar, v_blk 8.4-11.3 ms/frame (table below) |
| record | 30 s; off-CPU attempt then on-CPU fallback | 60 s; 3 off-CPU attempts 15 s apart, on-CPU only as attempt 4 | an on-CPU profile cannot name a wait; `--trace-offcpu` can fail once and open minutes later on one boot (slowdown462, Blinx) |
| APK | a593d8eb85 | 16f09aa346 (plain) | the ref of 5 of near30's 7 plain Tron runs |
| regimen | max (soak_title default) | `PERF_REGIMEN=default` | the decomposed soaks' regimen |
| soak length | 330 s | 420 s (510 s from run 2: the slow gate's 90 s cap) | `mark gameplay` lands ~228 s after the route's first line (run.log: 14:52:43 to 14:56:31, 16:00:03 to 16:03:52, 16:34:30 to 16:38:21), and the record ends ~80 s later |
| logcat spec | its own | the dispatcher's | so `decompose.py` reads the session's logcat for the same window |
| hold | `hold.sh wait` + poll of running/ | `hold.sh wait` + `wait-idle` | hold.sh's own recipe |

Minute-by-minute after `mark gameplay` (near30's rows; minute: mean fps /
rows below 28.5 of ~30 / v_blk ms per frame):

| run | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| 2727294 (New Game) | 26/25/9.7 | 28/21/8.4 | 39/10/4.1 | 53/1/2.2 | 26/25/7.6 |
| 3184149 (New Game, cold) | 24/25/11.3 | 28/19/8.7 | 29/20/6.5 | 54/1/1.8 | 46/0/3.0 |
| 3657361 (New Game, GPL=3) | 27/23/10.2 | 30/16/8.6 | 36/13/4.8 | 51/0/2.4 | 29/10/6.6 |
| 3991603 (perflog) | 31/16/9.3 | 46/0/3.4 | 33/11/4.9 | 56/1/1.0 | 47/1/3.1 |
| 2513164 (New Game) | 36/6/5.6 | 40/0/4.5 | 41/0/4.3 | 42/0/4.2 | 41/0/4.3 |

So a record from mark+10 s to mark+70 s sits in the window where the sleep
is largest on 4 of 5 runs.

### The reader, validated before the capture

`waitsite.py <data>` charges every off-CPU interval of the vCPU thread
(switch records, as `offcpu.py` does) to its switch-out call chain and
buckets it by the brief's candidate sites. It then prints a verdict line:
one site at 50% or more of the attributed off-CPU time OWNS the wait.
Otherwise it reports the split. On bionic a BQL wait unwinds as a bare
`NonPI::MutexLockWithTimeout` under its caller, because `bql_lock` is a macro.
The reader names it `BQL <- <caller>` when the caller takes no other lock
(`cpu_exec_loop`, the MMIO helpers; `mmap_lock` is a no-op in softmmu,
`include/exec/mmap-lock.h:28`).

Validation on slowdown462's `doa3.data` (DOA, the capture that found #474):

| site | ms | % attributed |
|---|---|---|
| pgraph.lock in PGRAPH MMIO | 14,557 | 89.7 |
| (unsampled switch-out) | 5,983 | (27% of off-CPU) |
| pfifo.lock in USER MMIO | 844 | 5.2 |
| BQL <- cpu_exec_loop | 487 | 3.0 |
| fdatasync <- bdrv_co_flush | 189 | 1.2 |

That matches slowdown462's table (14,556 ms `pgraph_read`, `user_read` 650,
BQL in `cpu_exec_loop` 486), so the reader's verdict on DOA is #474's.

## 2. Candidates, read from the code before the trace

What each one looks like in the trace, and my prior that it owns at least
50% of Tron's vCPU sleep. Each prior comes with its evidence.

| site | what a hit looks like | prior | evidence |
|---|---|---|---|
| BQL, some caller | `BQL <- cpu_exec_loop` (interrupt entry) or `<- do_ld/st_mmio` | 0.35 | every guest interrupt and non-RAM MMIO takes it; the PFIFO thread takes it per PGRAPH IRQ (pgraph.c:1336, 2546, 2630). For the sleep to track GPU ms, a holder must keep it across GPU-paced work, and no such path has been read yet. DOA: 3% |
| pfifo.lock in `user_write` (DMA_PUT) | `pfifo.lock in USER MMIO` | 0.20 | the guest writes DMA_PUT at every push; DOA had 844 ms here; the pusher holds pfifo.lock while it walks the pushbuffer |
| surface download on guest access | `GPU surface download on guest access` | 0.10 | `surface_access_callback` (surface.c:2335) makes the vCPU wait on `downloads_complete`, which runs after queued GPU work, so it fits "tracks GPU ms". Near30's "read-downloads 0.15 ms" did NOT measure it: `[tlb68] rdus` times `tlb_reset_dirty` (cputlb.c:1259), not this wait. Against it: in the perflog run's slow window `[watch311]` stays at inserts=19 with `[surfwatch382] rearms=0`, so few watches fire |
| pgraph.lock (#474) | `pgraph.lock in PGRAPH MMIO` | 0.05 | measured out: `[lock474]` 0.37 ms of 10.5 |
| APU d->lock | `APU d->lock / APU MMIO` | 0.05 | no GPU coupling in the mechanism |
| none >= 50% (split, or mostly unsampled) | verdict line "report the split" | 0.25 | DOA left 27% unsampled; Tron's sleep may have several sources |

Correction for the next lane: near30's NOTES list "read-downloads
(~0.15 ms)" among the waits measured out. The figure is TLB dirty-reset time
(`hakux_tlb68_rd_ns`), so the vCPU's wait for a GPU surface download is not
yet measured. This trace measures it.

## 3. What the trace decides (written before it runs)

| outcome | then | P it yields a fix | win if it works | cost |
|---|---|---|---|---|
| BQL >= 50% | name the holder: the PFIFO/main-loop thread's on-CPU samples while the vCPU waits (same capture); the fix is to shorten that hold (raise the IRQ without the BQL, or move the work out of the BQL) | 0.5 | up to v_blk: 10 ms of 43 (Tron slow), 21 of 64 (BF2) | 1 arm (Tron + BF2) |
| pfifo.lock in user_write >= 50% | make DMA_PUT lockless (atomic store + kick); the pusher reads PUT once per batch | 0.6 (the store is a single word; the lock guards the pusher's view) | same | 1 arm |
| surface download >= 50% | name the surface and the access (read or write); a write to a draw-dirty surface waits for a FULL download (surface.c:2373-2414). Candidate: a write that covers whole rows needs no download of those rows | 0.3 (correctness: the 40 bump-map tests and the download generation logic depend on it) | same | 1 arm + goldens |
| APU >= 50% | shorten the APU thread's critical section | 0.4 | same | 1 arm |
| no site >= 50% | stop; report the split (brief) | - | - | 0 |

Every arm registers a Tron + BF2 prediction first (share at the bar, v_blk
per frame from `decompose.py`), with concrete refs, before it is queued.

## Device use

| # | what | id | result |
|---|---|---|---|
| 1 | off-CPU capture tron1 (host-run, d8d36c9161) | 18:46-18:54 PDT | void: the route ended in Options > Display (no save, so the DOWN went to Light Cycles). Usable as a fast-window control: off-CPU 0.53 ms/frame, 69% BQL <- cpu_exec_loop |
| 2 | off-CPU capture tron2 (v5 route + slow gate) | requested 19:00 PDT | waiting |

## Do not repeat

- Do not read `[tlb68] rdus`/`rdous` as surface-download wait time. It is
  `tlb_reset_dirty` time.
- Do not run `capture_profile.sh`'s on-CPU fallback for a wait question. An
  on-CPU profile cannot name a sleep.
- Do not run near30's or tronhang672's Tron route (with the DOWN) on the Nova
  while its disk has no Tron save. It ends in Options > Display at 60 fps
  (tron1). Look at the Single Player frame first: a greyed Auto Load means no
  save.
- Do not read a capture's verdict before decompose.py shows its window is
  slow. tron1's reader verdict ("BQL OWNS the wait") is true of a menu.

## Files

`capture_offcpu.sh` (the host's capture), `waitsite.py` (the reader),
`tron-newgame.route` (near30's, v5 since run 2) and `decompose.py` (near30's, byte-identical), for the
capture and the prediction.
