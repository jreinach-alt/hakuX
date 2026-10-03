# lane.vcpuwait433: what puts Tron 2.0's vCPU to sleep for a quarter of every slow frame (#433)

Brief: lane.local 2026-10-02 18:03 PDT (owner-approved), from lane.near30's
lever 1 (`docs/lanes/near30/NOTES.md` on origin/lane/near30). Base master
9550493846. Nova, at most 3 runs, shared with uberdefault569 and memfast.

The premise, measured by near30 (Nova, device defaults): in Tron windows
below 28.5 fps (median F ~43 ms) the vCPU thread is asleep, neither running
nor runnable, ~10 ms per frame. That sleep tracks GPU ms per frame (r 0.64),
not the renderer's CPU draw work (0.08). BF2: 21 ms of a 64 ms frame.

## Attempt 4 (2026-10-03 06:47-07:10 PDT): the fix is on the branch; arms registered

### Why attempt 3 did not finish

It finished in the waiting state. The fix needed `hw/xbox/nv2a/user.c` and
`pfifo.c`, which were outside this lane's territory. Attempt 3 asked
lane.local for the grant (OUTBOX 21:10 PDT), ran the offline per-tid pass
while it waited (21:25), and parked. Addendum 4 (06:47) granted both files.

### What attempt 4 did

| step | what | result |
|---|---|---|
| merge | origin/master 5661db4f2b (uberdefault569: the ubershader is on by default; buildstamp) into the branch: ef511dbd19 | clean |
| fix | `userread-lockless.diff` applied unchanged: 012fa08a94 (user.c 25+/14-, pfifo.c 1 line) | `git apply --check` clean |
| selftest | `selftest_userread.sh`: compiles the real `user.c` with `-Wall -Werror` against a stub `nv2a_int.h`, using the real `qemu/atomic.h` and `nv2a_regs.h` | **PASS**. With the fix, reads of DMA_GET, DMA_PUT and REF return in 0 ms while another thread holds pfifo.lock for 400 ms. `user_write` still waits (402 ms). The PUT store is visible to the next read. pfifo.c's GET store is a release store. **Falsifier:** the pre-fix `user.c` (5661db4f2b) blocks 400-405 ms on all three reads, so the harness sees the lock |
| pixel prediction | `predictions/vcpuwait433-pixels.json` (sha256 51885311...): A ef511dbd19, B 012fa08a94; must not move: DMA_corruption_around_surfaces (3 goldens), Texture_render_target (41), Texture_render_update_in_place (1) | registered and pushed before any run |
| Tron prediction | `predictions/vcpuwait433-tron.json` (sha256 020b10df...): legs V, M, O1, O2, below | registered and pushed before any run |
| pixel arms | Thor, pinned, release tier: B `1-1791035760-vcpuwait433-4105238` (apk b43d7cbb8930), A `1-1791035764-vcpuwait433-4105418` (apk ac5b7cf64c9d) | **PASS** (ab_compare, PRE-REGISTERED, done 07:02 PDT): 45 of 45 captures byte-identical; better 0, worse 0, exact 5 -> 5. B's run is also the first NDK build of the fix |
| Tron arm | Nova, one run | **not queued: waits for savestate433 to fold** (below) |
| compile | the pixel arm B built 012fa08a94 with the NDK | built and ran |

Suite choice: these three are where the guest or the GPU consumes
GPU-written memory right after the pushbuffer drains. One behaviour is new:
a guest that sees GET == PUT can now run while the PFIFO thread is still in
the STALLED finish, which copies staged downloads into guest RAM. If any
golden depended on that hold, it would show in these suites.
`Surface_as_vertex_array` was the first pick, but it has no goldens, and
request.sh refuses a key that matches none.

### The Tron A/B: a like-for-like A was already on disk

uberdefault569's Tron B rerun, **`1-1790994313-uberdefault569-990012`**, is
master's emulator code with the ubershader on (ref d4a02e2060). It used
`PERF_REGIMEN=default HAKUX_PREBUILD=0 HAKUX_PLC_WIPE=1`, 720 s, and
uberdefault569's `tron-newgame` route, the one with the DOWN. Tron's disk
held the golden 5489ae7f9b58: hdd.after harvested it, and the Single Player
frame (200443-menu-down) shows Auto Load enabled with New Game highlighted.
So with the golden profile, **the DOWN lands on New Game and the run plays
the in-engine intro**: tron2's window, and the brief's.

decompose.py on 990012:

| rows | n | fps | F ms | v_run | v_blk ms/frame |
|---|---|---|---|---|---|
| all | 254 | 35.58 | 28.10 | 22.38 | 5.59 |
| below 28.5 | 45 | 23.70 | 42.19 | 31.30 | **9.80** |

share at the bar 0.82. The slow-row sleep matches tron2 (9.93, GPL 0) and
near30 (~10).

B is the same request at 012fa08a94, on `tron-newgame-returning.route`. That
route is A's route text byte for byte (apart from the trailing newline), plus a
`# state: returning` header. Registered legs:

- **V**: route-frame menu-down shows New Game, `mark gameplay` is logged, the hdd plan prepared 5489ae7f9b58, `[gpl569] mode=3`, shader cache cleared, no BugCheck, >= 200 rows. Otherwise VOID.
- **M** (mechanism; separates inert from refuted): slow-row v_blk <= 7.0 (A 9.80), or all-row v_blk <= 4.6 (A 5.59) if B has fewer than 10 slow rows. P 0.85.
- **O1**: share >= 0.87 (A 0.82) and mean fps >= 37.4 (+5%). P 0.45.
- **O2**: share >= 0.90 (the PM's bar). P 0.3.
- noise: one run per arm, and near30's New Game shares spread from 0.50 to 0.73. O alone is weak evidence; M is the low-noise leg.

**Why the Tron run is not queued yet.** `titlestate.py show --device nova`
(06:52 PDT) puts Tron's titles-disk profile at **d2aff0a53543**, the
first-run leftover (title data only). In that state Auto Load is greyed, and
A's DOWN goes to Light Cycles: tron1's void. On master the dispatcher keeps
whatever the disk holds, and the `# state:` line is enforced only by
savestate433 (State: ready, not folded at 06:55). Queuing now would void for
a known cause, which the owner's 10-02 order forbids. The v5 route (no DOWN)
does not help: it reaches the intro only from first-run state, and from the
golden it reaches Auto Load and the level, a different window from A.

### Next (P x win, attempt 4)

| candidate | P | evidence for P | win if it works | cost |
|---|---|---|---|---|
| **A. Tron arm on the Nova, after savestate433 folds** | M 0.85, O1 0.45, O2 0.3 | M: the read now returns while the lock is held (selftest), and tron2 put 65% of this window's sleep there. O: the PFIFO thread is asleep for >= 86% of the waits, so the guest gains whatever it would have done in that time, unless it then waits on GPU output in RAM | up to ~4 ms of A's 42 ms slow frame; share 0.82 to 0.87-0.90 | 1 Nova run (~14 min); the lane's 3rd |
| B. Release pfifo.lock across the STALLED finish | 0.3 | covers the DMA_PUT store (4.5%) and the pusher-side waiters too, but exposes renderer state to the display thread | <= A + 4.5% of the site | grant (vk/reports.c), build, goldens, arm |
| C. If M passes and O1 fails: off-CPU + on-CPU capture of B | 0.8 that it names where the freed time goes (spin on a RAM report vs another sleep) | tron2's method worked | knowledge; picks between B and a report-path fix | 1 run, needs a 4th from lane.local |

The pixel arms passed (45/45 byte-identical), so they no longer gate the
fold. What remains is A's outcome, plus the fold's run at the final head.

## Result (attempt 3, 2026-10-02 21:05 PDT): pfifo.lock in `user_read` owns the wait

**The site:** in Tron's slow window the vCPU sleeps on **`pfifo.lock` in
`user_read`**, a guest load of DMA_GET, DMA_PUT or REF. That is 65.2% of the
attributed off-CPU time (95.5% of it reads, 4.5% the DMA_PUT store), about
4.0 ms of a 36-45 ms frame. The largest named holder is the PFIFO thread
asleep in `wait_frame_submitted <- pgraph_vk_finish <-
pgraph_vk_process_pending_reports <- pfifo_thread`, with pfifo.lock held. That
finish runs only when DMA_GET == DMA_PUT, so the guest waits out a GPU batch to
read a value that is already final. The per-tid pass puts the PFIFO thread
asleep for at least 86% of those waits. The fix is a lock-free `user_read`
(`userread-lockless.diff`, section 4). It needs a grant for
`hw/xbox/nv2a/user.c` and `pfifo.c`, and a build. Tables are in section 4.

### Why attempt 2 did not finish

Attempt 2 ended where the protocol says it should: in the waiting state, on
host run 2 (tron2). The host ran it (19:54-20:01 PDT), and addendum 2 called it
void because the record covered the opening-credits cinematic, not the level.
Run 3 was parked behind lane.savestate433. Attempt 3 found that tron2 is **not
void for the brief's question**, for two reasons:

1. **The old gate's "60 fps" was a parse bug, not a fast window.** A
   `hakuX-pace` line is written every 60 guest frames, not every second, and
   the gate read the f difference between two lines as fps. That is 60 on
   every line, so the gate could never open. decompose.py on tron2's record
   window: median 27 fps, 22 of 36 rows below 28.5, v_blk 7.8 ms/frame (9.2 in
   the slow rows).
2. **The brief's premise was measured in this same window.** Near30's slow
   rows (F 43, v_blk 10) come from its New Game soaks, minutes 0-2 after
   `mark gameplay`. tronhang672 identified that span as the ~4.5 min in-engine
   intro after New Game. tron2's whole run reads share 0.51, slow-row F 45.2,
   v_blk 9.93: near30's numbers. The one Auto Load run (2186958, in-level) had
   share 0.90 and v_blk 6-7 at 28-34 fps.

So tron2 measured the brief's 10-of-43 ms window, but not gameplay. The
in-level sleep is smaller (about 6.5 ms of 33).

### What changed in the capture for run 3 (owner orders 19:57 and 20:05)

- `titlestate.py prepare --title-id 42560001 --state returning` before the
  soak, and `release` on every exit. The script refuses unless prepare reports
  `loaded golden`. `TITLESTATE=` points at a savestate433 checkout until that
  lane folds.
- **The gate fails closed.** It records only when `levelcheck.py` sees Tron's
  HUD (health and energy bars) in at least 4 of the route's last 6 loop frames
  with a moving view, AND 5 pace lines in a row are in [18, 40) fps. Otherwise
  it logs `ABORT: <reason>`, takes one screencap and exits 7 without
  recording. The fps is (f - previous f) * 1000 / ms.
- `levelcheck.py`, validated on frames before any capture used it:

| frames | loop frames | with HUD | gate replay (`.scratch/replay_gate.py`, the script's logic on the run's logcat + frames) |
|---|---|---|---|
| 2186958 (Auto Load, in-level, 28-34 fps) | 89 | 87 (the 2 misses are the Save Game screen) | OPEN at mark+28 s: 5 slow lines, 31 fps, hud 5/6, moves 4/4 |
| tron1 (Options menu, 59 fps) | 24 | 0 | ABORT at mark+130 s: 59 fps, no HUD |
| tron2 (credits cinematic, 31 fps) | 42 | 0 | ABORT at mark+130 s: 11 slow lines, but no HUD |

  HUD-pair view difference in-level: median 59 grey levels (p10 9). The bar
  is 12, so one moving pair out of five is enough.

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

## 4. tron2: the site, why the vCPU waits there, the fix

`waitsite.py tron2.data --detail "pfifo.lock in USER"` (vCPU tid 29645, 60.0 s;
the record window is 27.9 fps mean, so about 1,674 frames):

| site | ms | % attributed | waits | ms/frame |
|---|---|---|---|---|
| **pfifo.lock in USER MMIO** | **5,257** | **65.2** | 7,415 | 3.1 (4.2 with its share of the unsampled) |
| (unsampled switch-out) | 2,787 | (25.7% of off-CPU) | 8,063 | |
| BQL <- cpu_exec_loop | 1,233 | 15.3 | 40,468 | 0.7 |
| pgraph.lock in PGRAPH MMIO (#474) | 833 | 10.3 | 701 | 0.5 |
| BQL <- mttcg_cpu_thread_fn | 442 | 5.5 | 10,259 | 0.3 |
| **total off-CPU** | **10,848 (18.1%)** | | | **6.5** (decompose v_blk 7.1) |

Against the tron1 control (60-fps menu), pfifo.lock goes from under 3% to
65%. BQL <- cpu_exec_loop goes from 0.26 to 0.7 ms/frame.

Inside the site:

| split | ms | share |
|---|---|---|
| `user_read <- memory_region_dispatch_read <- do_ld_mmio_beN <- do_ld4_mmu` (a guest 32-bit load) | 5,019 | 95.5% (6,424 waits) |
| `user_write <- ... do_st_mmio_leN` (the DMA_PUT store) | 236 | 4.5% |
| waits of 2-10 ms | 3,089 | 59% (777 waits) |
| waits under 0.5 ms | 944 | 18% (5,417 waits) |

**Holder** (other threads' switch-out chains, overlapping the vCPU's waits):
the PFIFO thread is asleep in **`wait_frame_submitted <- pgraph_vk_finish <-
pgraph_vk_process_pending_reports <- pfifo_thread`** for 2,100 ms of the
5,257 (40%). On-CPU samples inside the waits add `memcpy_opt`/`swizzle_box`
under `pgraph_vk_complete_staged_downloads <- pgraph_vk_finish <-
process_pending_reports` (94 samples). Every emulator thread is named
`qemu_main`, so the first pass mixed threads. **Per-tid pass (D, done
21:20 PDT):** the PFIFO thread (tid 29653) covers 92% of the vCPU's pfifo
waits:

| PFIFO thread during the vCPU's waits | ms | share of 5,257 |
|---|---|---|
| asleep in `wait_frame_submitted <- pgraph_vk_finish <- process_pending_reports` | 2,100 | 40% |
| asleep, switch-out unsampled | 2,448 | 47% |
| on-CPU (cpu-clock samples at 1 kHz: staged-download memcpy/swizzle in the same finish, lock hand-off) | ~312 | 6% |
| display thread (SDLThread) inside `pgraph_vk_get_framebuffer_surface` | 584 | 11% (overlaps the above) |

For at least 86% of the wait time the pusher is asleep, not advancing
DMA_GET. Its sleeps that release the lock (the idle `cond_wait`, the
process_pending event) cannot block the vCPU, so the unsampled 47% is most
likely the same finish. Either way, **the value the guest is waiting to read
does not change while it waits.**

**Why the vCPU waits there.** `pfifo_thread` calls
`pgraph_process_pending_reports(d)` with pfifo.lock held (pfifo.c:2162).
`pgraph_vk_process_pending_reports` (vk/reports.c:176) calls
`pgraph_vk_finish(STALLED)` when `DMA_GET == DMA_PUT` and a command buffer is
open. The finish waits for the render thread to submit the frame
(`wait_frame_submitted`, draw.c:3972), and that wait is paced by the render
thread's Vulkan work. Meanwhile the guest loads a USER register, DMA_GET (ring
space or progress) or REF, and `user_read` (user.c:32) takes pfifo.lock for a
single word. **The value it is waiting to read is already final:** the finish
runs only once the pusher has caught up, so GET == PUT, and REF is written by
the guest alone (user.c:104; no method writes CACHE1_REF). The guest's read
waits out the GPU-side batch and gets no new information for it. That is
near30's "sleep tracks GPU ms" (r 0.64).

**Is the wait required for correctness?** No golden or title can need it.
The lock gives a read of one word exactly one property: ordering with the
pusher's earlier work. An acquire load against a release store of DMA_GET gives
the same. DMA_PUT and REF have only the guest as writer. `pfifo_bound_skew`
already reads DMA_GET without the lock (pfifo.c:1471, "a benign race: the
pusher is its only writer"). No golden exercises a guest reading USER while
the PFIFO thread is in a stalled finish: the nxdk tests draw and flip. The
change cannot alter pixels, because it only changes when a value is returned,
not which value.

**The smallest change** (`userread-lockless.diff`, applies to master
9550493846, 25+/14-; it was **not compiled** here, because there is no build
tree):
- `user_read`: no pfifo.lock. Acquire loads of DMA_PUT, DMA_GET and REF;
  relaxed loads of MODE and PUSH1.
- `user_write`: unchanged locking. The three stores become release stores.
- `pfifo_run_pusher`: `*dma_get = dma_get_v` becomes
  `qatomic_store_release(dma_get, dma_get_v)` (pfifo.c:2071).

This follows the #474 pattern: #474 stopped holding pgraph.lock across a
fence wait that MMIO needed, and this stops the read needing the lock at all.
The alternative, releasing pfifo.lock across the stalled finish (B below),
also frees the DMA_PUT store and the pusher-side users. But it opens the
renderer state that pfifo.lock currently shields: the display thread's
`pgraph_vk_get_framebuffer_surface` surface lookup, and vk/surface.c's
pfifo-locked sections.

**Prediction to register before the arm** (draft; it needs concrete refs on
this branch, so it waits for the grant). Tron, New Game route, 2 min from
`mark gameplay` (the window of near30 and tron2), decompose.py:
- **Mechanism** (the falsifier that separates inert from refuted): pfifo.lock
  in USER falls from 3.1 ms/frame to < 0.3. Measured with the per-thread wait
  from `[rr425w]`/`v_blk`, without a profiler: v_blk in rows below 28.5 drops
  from 9.9 to <= 7.0 ms/frame.
- **Outcome**: share at the bar rises from 0.51 (tron2) / 0.50-0.73 (near30
  New Game) to >= 0.65, or the slow-row median fps rises >= 5%.
- If v_blk drops but fps does not move, the freed time became guest spin on
  GET/REF ([rr425pc]: the guest was waiting on the GPU anyway). That refutes
  the win and names the next wait.
- BF2: its 21 ms/frame sleep has no measured site. The prediction is v_blk
  down >= 2 ms/frame at P 0.35, as a second title, not a gate.

### Next (P x win, after tron2)

| candidate | P | evidence for P | win if it works | cost |
|---|---|---|---|---|
| **A. Lock-free `user_read` arm** (patch ready) | 0.45 that Tron's slow-window fps rises >= 5% (0.9 that the site's sleep goes) | for: 95.5% of the site is reads; the PFIFO thread is asleep for >= 86% of the waits (D), in a finish that runs only at GET == PUT, so the value read is final and nothing it polls can change; in slow rows the renderer is idle 18 ms of 45 (Ri), so the pipeline waits on the guest. Against: after the read the guest may wait on GPU results in RAM (e.g. a report the finish writes), so the freed sleep can turn into spin ([rr425pc]) | up to 4.0 ms of the window's 36 ms mean frame (27.9 -> at most 31.4 fps, +12%; the bound, if all of it is on the critical path); in-level up to about the same share of 6.5 ms; BF2 unknown (21 ms sleep, site unmeasured) | grant (user.c, pfifo.c), 1 NDK build, Tron arm + BF2 arm (2 Nova runs) |
| B. Release pfifo.lock across the STALLED finish in `pgraph_vk_process_pending_reports` | 0.3 | covers the named 40% holder for every pfifo.lock user (reads, the DMA_PUT store, the pusher); against: the lock shields the renderer state from the display thread and vk/surface.c during the finish, so a correctness audit and a golden run are needed | <= A's on reads, plus the 4.5% DMA_PUT share | grant (pfifo.c, vk/reports.c), build, goldens, arm |
| C. In-level capture (run 3: script ready, gate fixed, golden profile) | 0.85 that it names the in-level owner | the gate replay opens on 2186958 at mark+28 s | knowledge only: whether the same site owns gameplay's 6.5 ms. A's arm on an in-level route answers that and the win together | 1 Nova run |
| D. Per-tid holder pass on tron2.data (offline) | done | PFIFO thread asleep for >= 86% of the waits | raised A from 0.4 to 0.45 | done |

A first: it is the change that moves frames, and the arm measures the win and
the in-level case together. C is not worth a run unless A's arm is blocked.

## Device use

| # | what | id | result |
|---|---|---|---|
| 1 | off-CPU capture tron1 (host-run, d8d36c9161) | 18:46-18:54 PDT | void: the route ended in Options > Display (no save, so the DOWN went to Light Cycles). Usable as a fast-window control: off-CPU 0.53 ms/frame, 69% BQL <- cpu_exec_loop |
| 2 | off-CPU capture tron2 (v5 route + slow gate) | 19:54-20:01 PDT | recorded the New Game intro cinematic (not the level) at 27 fps: **the brief's slow window** (section 4). pfifo.lock in `user_read` 65.2%, which OWNS the wait |
| 3 | Tron arm B (012fa08a94, returning golden, A = 990012) | not queued yet | waits for savestate433 to fold (attempt 4) |
| Thor | pixel arms B / A (3 suites) | 1-1791035760-vcpuwait433-4105238 / 1-1791035764-vcpuwait433-4105418 | PASS: 45/45 byte-identical |

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
- Do not read fps from the f difference of two `hakuX-pace` lines. A line is
  written every 60 frames, so the difference is always 60. fps =
  f-difference * 1000 / ms (the line's own `ms=`). Runs 1-2's gate read 60
  that way while tron2 ran at 27.
- Do not trust the FPS overlay on a route frame as guest fps. tron2's credits
  frames say "FPS: 59" while pace says 27-31.
- Do not call near30's Tron slow window "in-level". On the New Game route it is
  the in-engine intro (minutes 0-2 after `mark gameplay`). In-level (Auto
  Load) runs at 28-34 fps with v_blk about 6.5.
- Do not take the display thread's `vkWaitForFences` under pfifo.lock
  (vk/renderer.c:2803-2826) as THE holder. In tron2, SDLThread is inside
  `pgraph_vk_get_framebuffer_surface` for 584 ms (11%) of the vCPU's waits
  and in `clock_nanosleep` for 76%. The PFIFO thread is the main holder.

## Files

`userread-lockless.diff` (the fix, applied in 012fa08a94),
`selftest_userread.sh` (the fix's host selftest, with its falsifier),
`tron-newgame-returning.route` (A's route + `# state: returning`, for the Tron arm),
`levelcheck.py` (the capture gate's in-level check),
`capture_offcpu.sh` (the host's capture), `waitsite.py` (the reader; `--detail`
splits a site and names holders),
`tron-newgame.route` (near30's, v5 since run 2) and `decompose.py` (near30's, byte-identical), for the
capture and the prediction.
