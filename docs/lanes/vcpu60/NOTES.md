# lane.vcpu60 (#507): what it takes to get Simpsons, GTA SA, Nightfire and Forza to 60 fps

Brief: `briefs/vcpu60.md` (owner, 2026-10-04 ~11:35 PDT: "figure what we
need to do to get these framerates up on all these"). Planning lane: no
device run, no code change, no board edit. Base: origin/master merged at
`40b62fd533`.

## Attempt 2: why attempt 1 did not finish

Attempt 1 was stopped at 11:43 PDT by the host. Its research step sent a
WebFetch to a GitHub-hosted page, and GitHub contact is not allowed while the
account is suspended. It left a draft `PR.md` and scratch readers, but no
NOTES. Attempt 2 made no GitHub contact. WebSearch was denied to this session,
and the one non-GitHub fetch tried (IGN) was refused. So the external
evidence below comes from what the tree already cites (`vcpuplan` section 2),
and each place where that limits a claim says so.

## The short version

- **No ranked combination of JIT items reaches 60 on any of the four
  titles.** The whole vcpuplan list sums to about 30-40% of vCPU samples.
  Priced with memfast's measured discount, that is 4-10% of the vCPU's
  on-CPU time. Simpsons would need its on-CPU time cut by 58% to reach 60
  with today's sleep left in place. That leaves the JIT list about 48-54
  points short.
- **The brief's premise holds for one title of four.**

  | title | measured verdict |
  |---|---|
  | Simpsons | Below its target. Only partly saturated: its vCPU thread is on-CPU 61.5% of wall time and **asleep 9.4 ms of each 26.7 ms frame**, waiting on the render side. That is the shape lane.near30 found on Tron |
  | GTA SA | At its own 30 fps target in 88% of windows (its frame limiter waits 2 vblanks; `targets.toml`). Its sub-30 windows are the same vCPU sleep |
  | Nightfire | Bound by the **render thread**, whose phases fill 30.5 of a 33.8 ms frame. Its vCPU is on-CPU 28.6 ms, but that time does not grow in slow windows, so it likely holds a wait |
  | Forza | Target 30 (IGN, `targets.toml`). In its slow half it is **GPU/render-bound**: the guest idles 20 ms per frame, the renderer is never idle, and the GPU sat at 401 of 680 MHz all run |
- **The lever with the largest expected win is not in the JIT.** It is the
  vCPU's sleep on GPU-side work (rank 1). On Simpsons, removing half of the
  sleep reaches about 45 fps, and removing all of it about 55-58. On GTA it
  turns the sub-30 windows back into 30. Dolphin's dual-core mode and PCSX2's
  MTGS make the same decoupling.
  - The first candidate is in the code: the guest's DMA_PUT write takes
    `pfifo.lock` (`hw/xbox/nv2a/user.c:93`), and the PFIFO thread holds that
    lock across a GPU finish.
  - P 0.4. One off-CPU capture names the site, but Tron's sleep turned out
    to be layered.
- **The JIT program (FEX/Box64 class) ranks second.** Its value rises once
  rank 1 lands, because v_run then becomes the frame. Its first step is
  already built and off by default: the inline indirect-branch probe. That
  probe has never been measured below a cap. A one-binary pair on Tron
  decides it.

## 1. The premise, checked per title

### 1.1 Targets (`docs/testing/titles/targets.toml`, read at `40b62fd533`)

| title | target_fps on file | source on file | what the guest's own flips say |
|---|---|---|---|
| The Simpsons: Hit & Run | **no row** (no title id on file; the 10-04 run was a pathfind hold, judged at the 30 bar) | none | 65.1% of flips come one vblank after the last, 33.8% two (`hakuX-pace`, 23,220 flips). The game presents on the next vblank when it is ready, and no 30 fps limiter shows. So it is a 60 Hz-paced title, **measured from behaviour, not from a source** |
| GTA San Andreas | **30** | high confidence, from the game's code: the limiter at `default.xbe 0x273678` waits 2 vblanks (#482) | 93.1% of flips are 2 vblanks; 1.6% are 1 |
| 007 Nightfire | **60** | medium: IGN and TeamXbox (Xbox, 2002), "driving stages drop" (#431) | 15.3% of flips are 1 vblank, 68.5% are 2 and 14.9% are 3. Not a hard 30 cap, so the 60 on file is consistent |
| Forza Motorsport | **30** | medium: IGN (Xbox, 2005), "locks at 30 fps" (#431) | (no `hakuX-pace` lines in the run read) |

The brief says the 60 is "NOT sourced in targets.toml for any of them". That
is wrong for three of the four: two are sourced at **30**, and one at 60.
Only Simpsons has no row. No source for Simpsons was reachable from this
session (WebSearch was denied, IGN refused the fetch), so its 60 rests on the
flip pattern above.

**What this changes for the ask.** "60 on all these" asks GTA and Forza for
twice their own design rate. GTA's 30 is enforced by guest code: reaching 60
there needs a game patch to the limiter, and then about 2x the vCPU work
rate (section 5). The honest bar for GTA and Forza is **30, held**. Their
gap to that bar is what the plan prices.

### 1.2 What bounds each title (Nova, 2-s rows after the gameplay mark)

Rows: `docs/lanes/fps20786/decompose.py` on each run, then
`docs/lanes/vcpu60/bands.py` gives the medians by frame-time band
(`decompose4.tsv`). The columns are near30's (ms per guest frame):

| column | meaning |
|---|---|
| `v_run` | vCPU thread on-CPU |
| `v_blk` | vCPU thread asleep: neither running nor runnable |
| `gidle` | guest in its kernel idle loop |
| `Ri` | render thread parked waiting for work (this includes vblank) |
| `rcpu` | render thread on-CPU |
| `rblk` | render thread blocked: GPU fence waits |

| title, run | band | n | fps | F | v_run | v_blk | gidle | Ri | rcpu | rblk | renderer phases |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **Simpsons**, pathfind hold 10-04 (606 s) | all | 302 | 37.4 | 26.7 | **17.2** | **9.4** | 0.65 | 9.5 | 6.3 | 10.6 | (not a perflog run) |
| | F < 22.2 | 23 | 46.8 | 21.4 | 14.5 | 6.7 | 1.2 | 7.8 | 6.3 | 8.1 | |
| | F 26-31 | 147 | 35.4 | 28.3 | 18.0 | 10.3 | 0.6 | 9.8 | 6.9 | 11.2 | |
| **GTA SA**, `1790875419-autoverdict-2123622` (635 s) | F 31-36 (at the cap) | 279 | 29.8 | 33.6 | 32.0 | 1.5 | 0.4 | 20.9 | 12.4 | 0.3 | - |
| | F >= 36 (below the cap) | 39 | 24.4 | 41.0 | 32.3 | **9.7** | 0.2 | 16.3 | 14.4 | 10.8 | - |
| **Nightfire**, `1-1790676918-lane.memfast-1478620` (perflog) | all | 136 | 29.6 | 33.8 | 28.6 | 6.2 | 2.2 | 3.5 | **24.8** | 4.1 | GPU 9.1, Draw 11.9, Fin 10.3, Idle 3.5, Tot 30.5; 366 draws |
| | F 22-26 | 6 | 40.9 | 24.5 | 19.5 | 5.2 | 0.2 | 0.4 | 18.0 | 5.7 | Tot 20.1 |
| | F >= 36 | 44 | 26.5 | 37.7 | 29.5 | 7.8 | 2.7 | 3.7 | 27.8 | 8.5 | GPU 13.6, Fin 13.7 |
| **Forza**, `1-1790826491-lane.verdict433-3477700` (1,254 s) | F 31-36 | 311 | 29.9 | 33.4 | 31.2 | 2.3 | 8.6 | 10.7 | 13.3 | 9.8 | - |
| | F >= 36 (below the bar) | 316 | 20.7 | 48.3 | 46.0 | 1.7 | **20.0** | **0.0** | 16.0 | **32.3** | GPU 401-401 MHz all run |

The verdict per title:

- **Simpsons: the vCPU runs 17.2 ms and sleeps 9.4 ms per frame.** F
  tracks both of them, v_run at r = 0.95 and v_blk at r = 0.96. v_blk also
  tracks the render thread's CPU (0.66) and its fence waits (0.65).
  `[tlb68] cpu=1233` over `dt=2005` puts the vCPU on-CPU 61.5% of wall
  time. The guest itself never idles (gidle 0.65 ms). So the brief's "guest
  CPU thread is saturated" holds for the guest, which never reaches its idle
  loop. It does not hold for the host thread, which sleeps a third of each
  frame. This is the signature near30 found on Tron 2.0 (v_blk 9.8 of a
  42 ms slow frame) and BF2 (21 of 64).
- **GTA SA: at its 30 cap, and the cap is the game's.** v_run 32.0 at the
  cap includes the limiter's spin, a two-TB poll of guest `0x5f2534`
  (vcpuplan section 1.2). The spin's size is shown by lane.ibcache: freeing
  vCPU time moved the spin from 0.35% to 8.4% of samples. The 12% of windows
  below the cap add **8.2 ms of v_blk** (1.5 -> 9.7) and no v_run
  (32.0 -> 32.3). So GTA's drops are the Simpsons sleep, not slower guest
  code.
- **Nightfire: the render thread binds; the vCPU's time probably holds a
  wait.**
  - The render thread's phases fill 30.5 ms of a 33.8 ms frame: draw-path
    CPU 11.9 ms (366 draws, about 32 us each), finish waits inside the frame
    10.3, GPU 9.1.
  - From the F 31-36 band to the F >= 36 band, rcpu rises from 23.7 to 27.8
    and the GPU from 8.5 to 13.6. v_run stays flat (28.8 -> 29.5). The
    thread that grows with the frame is the renderer.
  - In the fast windows (F 24.5) v_run is 19.5. So the vCPU's 28.6 ms at
    the 30 fps median likely includes a wait the guest spends polling (the
    expert's reading, section 4; R3 decides).
  - A vCPU-only plan cannot move it past the renderer.
- **Forza: not vCPU-bound on this build, on the Nova.** In the slow half,
  the guest idles 20 ms of a 48 ms frame. The render thread is never parked
  (Ri 0.0) and is blocked 32 ms on fences, with the GPU at its 401 MHz floor
  throughout. The energy map's guest idle of 0.05 for Forza was a Thor run
  on a593d8eb85, before the `invalid_surfaces` leak fix. On this Nova run
  guest idle is 0.27 (9.6 of 36.2 ms), as lane.ibcache measured (0.23-0.29).
  lane.ibcache's Forza leg agrees: freeing vCPU time gave fps x0.98.
  **Forza is planned separately (rank 3), on the GPU side.**

### 1.3 What the existing counters cannot say

- `[rr425pc]` counts **returns** to the exec loop, not time.
  - On all three titles that log it (GTA, Nightfire, Simpsons), 84-94% of
    returns are at the kernel idle idiom `0x8001b02e/f`. That is so even
    where guest idle is 1-2% of wall time.
  - It names no hot guest routine. The time census is `[tpc787]` (in-TB
    time by entry pc, `accel/tcg/cpu-exec.c:1386`). It is printed only in
    perflog builds, and no run of these four titles has it.
  - So question 2d (a hot guest memcpy, decompressor or spin) is
    **unmeasured** for all four. Run R2 answers it for Simpsons.
- No run names **what the vCPU sleeps on** in Simpsons or GTA. The tool
  that does is vcpuwait433's off-CPU capture (`capture_offcpu.sh` +
  `waitsite.py`). On Tron's intro it named pfifo.lock in the PFIFO `USER`
  read (65%). That site is fixed on master (`bc2bced563`), and the Tron
  sleep moved to a site that is still unnamed.
- Simpsons has no `--perflog` run: no `[lock474]`, no renderer phases, no
  `[tpc787]`.

## 2. The frame budget and the arithmetic

At 60 the frame budget is 16.7 ms, and at 45 it is 22.2 ms. Required
speedups are of the median frame (F) or of the named component, with the
others held.

| title (target on file) | median F today | to 45: cut F by | to 60: cut F by | if only v_run shrinks (v_blk held) | if only v_blk shrinks |
|---|---|---|---|---|---|
| Simpsons (none; behaves as 60) | 26.7 ms (37.4 fps) | 4.5 ms (1.20x) | 10.0 ms (**1.60x**) | 45: v_run -26%. 60: v_run 17.2 -> 7.3, **-58% (2.4x)** | 45: v_blk -48%. 60: not reachable alone (v_run 17.2 > 16.7) |
| GTA SA (30, own limiter) | 33.6 at the cap; 41.0 in the slow 12% | to hold 30 in the slow windows: 7.7 ms | **not the game's rate.** Needs a limiter patch, and then the true per-frame work (about 30+ ms in busy scenes, below) cut 2x | slow windows: v_run is not what grew | slow windows: v_blk 9.7 -> 2 holds 30 |
| Nightfire (60, medium) | 33.8 (29.6) | 11.6 ms (1.52x), on **both** threads | 17.1 ms (**2.0x**) on both | blocked by the renderer at 30.5 ms | v_blk is 6.2: not enough alone |
| Forza (30, IGN) | 48.3 in the slow half | (to hold 30) 15 ms off the renderer's GPU waits | not the game's rate | inert: gidle 20 ms | inert |

**GTA's true work per frame.** lane.ibcache, under the profiler on the
Thor, measured spin at 0.35% of samples at 22.5 gfps, so that window was
nearly all work: about 44 ms on the Thor with the profiler. On the Nova at
the cap the spin is inside v_run 32.0 and its size is unmeasured. The slow
windows (v_run 32.3 with no headroom) say that busy scenes need about 30 ms
or more. 60 would need about 2x.

**The JIT arithmetic** (the brief's question, answered with a number):

| | |
|---|---|
| The vcpuplan list at face value | 30-40% of vCPU samples |
| memfast's measured ratios: removed sample share to removed time | phase 1, 21% of host instructions -> 4.3-6.2% of time (about 1/4); F1, about 9% of sampled time -> 0.6-1.5% (about 1/6 to 1/15) |
| The list, priced with them | **4-10% of v_run** |
| Simpsons with that and today's sleep | v_run 17.2 -> 15.5-16.5, F 25.0-26.0 ms, **38.5-40 fps** |
| What 60 needs | v_run -58% |

**Short by about 48-54 points of v_run.** At 45 the list is short by
16-22 points.

## 3. Candidates, priced (P x win)

Every win below is priced from a **measured removal** where one exists. A
sampled share gets the memfast discount (1/4 to 1/9) when no measured
removal exists. Fps wins are for Simpsons unless named. A v_run win alone is
worth `v_run saving / F` of the frame while the sleep stays. After rank 1
lands, v_run is most of the frame and the same saving is worth about twice
as much.

### 3a. The vcpuplan items still open, after memfast

| item | status after memfast | P | win, priced | survives? |
|---|---|---|---|---|
| Fastmem, loads | **rejected on the Nova** (memfast attempt 5: v_run -0.6 to -1.5% on Tron; two aliases lost 9-33%) | - | - | **no** |
| Fastmem, stores / lazy view swap | memfast: P 0.1; the store compare sampled 5.7%, so at most about 1% when removed | 0.1 | <= 1% v_run | **no** |
| W1, per-page watch flush | **folded** (`de396edb2a`). Its flushes are gone; vCPU CPU per wall second moved 0.3-1.5% | - | done | done |
| Inline indirect-branch probe (`HAKUX_IBC`), plus a 16-bit jump cache and a RAS | **built and opt-in** (lane.ibcache). Measured: helper calls -92.6%, sampled lookup 24.9% -> 7.3% (GTA, Thor). Profiler-on gfps 22.5 -> 27.0. At the cap no fps change (freed time went into the limiter spin). Forza with the halt off: J/frame x1.10 (Forza is not vCPU-bound, 1.2). **Never measured on a vCPU-bound title below its cap.** The RAS was never built | 0.5 that it gives >= 4% of v_run | 17.6 sampled points removed, so 2-4.5% at the discount. The profiler-on +20% gfps says more, but the profiler inflates helper-call cost. **4-8% of v_run**: Simpsons -0.7 to -1.4 ms, about +1-2 fps now, +2-4 fps after rank 1 | **yes**, as the JIT program's first step. A one-binary pair decides it |
| Scalar SSE onto fp_jit f32 ops | open | 0.7 | 4.7% sampled, so **0.5-1.2% of v_run**: +0.1-0.2 ms | yes, last: small |
| Native flags | not proposed (helpers 0.25%; flag stores are inside `body`) | 0.15 | unmeasured, inside `body` | only inside 3c's region work |
| Multi-block regions (superblocks, `XBOX_SUPERBLOCK_ENABLED 0`) | open | 0.25 | Boundaries left after phase 1: exit check 2.0%, EIP/chain 3.3%, the BTI landing pad 4.8% (TB arrival), and env traffic in `body` (23%, its split unmeasured). If host instructions per guest instruction fall from 20.6 to about 14 (-30%), phase 1's ratio says **about 7% of v_run** | yes, inside 3c |
| Park pure polling loops | energy only (GTA's limiter spin) | 0.45 | **0 fps** | not for this ask |

### 3b. Work on the vCPU thread that is not guest code

From GTA's profile (vcpuplan 1.2, R1; Thor):

| work | share of the vCPU thread | can it move off? |
|---|---|---|
| MMIO exits | 0.6-0.7% | no point |
| softmmu helpers | 7.0% (refill 2.6, `tlb_reset_dirty` 1.2) | |
| APU `voice_lock` | 1.2% | yes, but it is about 0.2 ms/frame |
| exec loop and lazy-flag helpers | 1.1% (Forza 6.3%) | |
| translation | 0.4-0.7% | |
| kernel | 2% | |

- **Simpsons.** `[rr425]` puts in-TB time at 54% of wall and the exec-loop
  gap at 10%. `[tlb68]` `rdus` (the `tlb_reset_dirty` walk) is 8.3 ms per
  2 s, or 0.4% of wall time. Simpsons' `hakuX-pages` line shows 1,098 slow
  stores per window reaching the invalidator, so some code-page churn.
  - At most about 1-2% of Simpsons' wall time is non-guest work that could
    move to another core.
- **PFIFO/PGRAPH command processing is already off the vCPU thread.** It
  runs on the render thread. **The vCPU's cost from it is the sleep, not
  CPU work:** v_blk 9.4 ms on Simpsons, 9.7 in GTA's slow windows. That is
  rank 1.
- **No measured item in this class can carry more than about 2% of v_run.**

### 3c. Structural options

| option | mechanism touches the measured cost? | P | win | note |
|---|---|---|---|---|
| **Decouple the vCPU from GPU completion** (rank 1): the vCPU never sleeps on a lock that the render thread holds across a GPU wait. Sync happens only where the guest needs a GPU result, as in Dolphin's dual-core mode | **yes**: v_blk is the largest single term on Simpsons (35% of F) and all of GTA's sub-30 excess | 0.4 (section 5) | Simpsons: half the sleep gives F 22.0, **45 fps**. All of it gives F about 17.2-18, **55-58 fps**. GTA: slow windows back to 30 | the approach that fits a multi-core host. On real hardware the NV2A runs asynchronously to the CPU |
| **FEX/Box64-class translator work inside TCG**: indirect-branch probe + RAS, then regions with register allocation across blocks, then inline SSE | partly: lookup (measured, sampled), boundaries and `body` (sampled) | 0.4 for the program to deliver >= 8% of v_run | **8-18% of v_run** with the discount: Simpsons -1.4 to -3.1 ms | owner direction (vCPU JIT, 09-28). Ranked 2 |
| **A new frontend and backend (own IR, no TCG)** | yes, all of it, but softmmu stays (full-system guest, 98.5% of pages VA != PA) | 0.15 to deliver in 6 months without a regression | 25-40% of v_run (estimate: lookup, glue and `body` density; softmmu and slow paths stay) | not first. It would also not reach 60 on Nightfire, whose renderer is at 30.5 ms |
| **Render-thread CPU for Nightfire**: draw path 11.9 ms/frame (366 draws, about 32 us a draw); finish waits inside the frame 10.3 | yes, on Nightfire | 0.3 | renderer 30.5 -> about 20 ms if the mid-frame finishes go and the draw path halves; needed for any Nightfire gain past 30 | the energy map's item 6 (Pipe.Sh/Pipe.Tx), unowned |
| **Host placement**: big-core preference (uclamp.min or a big+prime mask, not a hard pin) on the Nova | yes, if the vCPU spends time off the X3 | 0.2 | X3 3187 against A715 2803 MHz: at most 12% of v_run, and less by the time it already spends on the X3 (70-79% on the Thor) | hard pin refuted (-21.5%, #428); ADPF ignored; **no predictive governor** (owner) |
| **GPU clock floor** (Forza, and the GPU half of the Simpsons/GTA sleep): the GPU sat at 401 of 680 MHz for the whole Forza run | yes, for Forza's slow half (rblk 32 ms) and for whatever part of v_blk waits on GPU time | 0.3 (near30's lever 3: Tron GPU 22 ms at 615 MHz against 34 at 401) | Forza slow half: rblk 32 -> about 19-23 ms at 615-680 MHz | a static regimen choice (`perf_mode`), **not a predictive governor**. Whether `perf_mode=2` lifts the GPU clock on the Nova is unmeasured (R4) |

### 3d. Guest side

- **Unmeasured for all four** (1.3).
- **Known:** GTA's frame limiter, a two-TB poll of `[0x5f2534]`. It is the
  game's 30 cap, not a cost to remove.
- **Simpsons:** `[rr425pc]`'s top guest-side return is
  `g:00221ffc:b91815` (5.2% of the top-16 returns). That is a page-boundary
  exit, not a time share.
- **R2** (Simpsons perflog) prints `[tpc787]` and answers this. If one entry
  pc holds 15% or more of in-TB time and its bytes are a `rep movs`/`rep
  stos` or an SSE-per-op loop, a targeted fast path is worth pricing.
- **No prior is given:** nothing on file suggests it.

### 3e. What the data adds that the list missed

1. **The sleep is the lever** (rank 1). The brief framed all four titles as
   JIT-throughput-bound, and the decomposition says otherwise for three of
   them.
2. **The GPU clock floor.** Forza's GPU sat at 401 MHz all run. Tron's
   plain runs did too (near30). If the vCPU's sleep is partly a GPU wait, a
   faster GPU shortens it.
3. **Nightfire's renderer.** It is the second bound, and no lane owns it.

## 4. Independent expert review

A subagent took the persona of an engineer who has built an x86-to-ARM64
translator (FEX/Box64 class). It got:
- the measured facts: the decomposition table, the GTA profile split, and
  the three measured removals (preamble, fastmem loads, IBC probe);
- the code paths.

It did not get this lane's conclusions or ranking. It read code and took no
measurement, with no network. Its view, condensed:

1. **What bounds each title.**
   - Simpsons is the vCPU running plus the vCPU asleep on a host wait
     inside the emulator. Ceiling: 45-55 if the vCPU stops waiting on the
     render thread, and 60 only if that and a 10-15% v_run cut both land.
   - GTA: 30 is the game's limiter. 60 needs a game patch plus about 1.7x
     on the vCPU, which is not realistic.
   - **Nightfire is bound by the render thread, not the vCPU.**
     - v_run stays at 29.4 from the F 33.5 band to the F 36-42 band, while
       rcpu rises from 22.2 to 27.8.
     - In fast windows v_run drops to about 20. vCPU time that scales with
       the frame time looks like a guest spin or wait, not work.
     - Ceiling: 40-45 with a modest render-thread cut.
   - Forza is GPU-bound: the CPU and GPU take turns, so devfreq never ramps.
     Ceiling 30 if the GPU is kept busy.
2. **First:** remove the vCPU's wait on the render thread.
   - The guest's DMA_PUT write still takes `pfifo.lock`
     (`hw/xbox/nv2a/user.c:93`).
   - The PFIFO thread holds that lock across its pusher loop
     (`pfifo.c:2119-2163`) and across `pgraph_process_pending_reports`,
     whose stalled finish waits for the GPU.
   - Fix: a store-release DMA_PUT and a kick through an atomic flag, with
     no lock. P 0.45; 0 to 9 ms of frame time on Simpsons. The wait is
     already counted (`lock_wait_ns`, `user.c:94`).
3. **Second:** branch dispatch.
   - **A direct jump to another 4 KiB page cannot chain.** It ends the TB
     through `gen_eob(DISAS_JUMP)` into the lookup helper
     (`accel/tcg/translator.c:112-121`, `target/i386/tcg/translate.c:3124-3140`).
     With 5.6-instruction blocks, many "indirect" lookups are direct
     cross-page calls plus RETs.
   - With one page directory, cross-page links could be unlinked on
     INVLPG and CR3 writes.
   - Add a RAS and widen the 12-bit jump-cache hash (97.9% of misses are
     collisions).
   - **It argues against the discount for dispatch:**
     - lane.ibcache's two flat readings were at a cap (GTA) and on a
       GPU-bound title (Forza), where freed time cannot become frames;
     - its one vCPU-bound reading (profiler on) went 22.5 -> 27.0 gfps;
     - the helper is serial on the critical path, so it should convert at
       about 1/2, not 1/6.

     P 0.6 of at least 4% of v_run; win 5-12%.
4. **Third:** Nightfire's render-thread CPU. P 0.5 of -25%, about 40 fps.
5. **Inert or wrong scope:**
   - native flags (under 1%);
   - moving MMIO/timer/audio off the thread (0.6%), except as removing
     waits;
   - parking spins (energy and heat only);
   - big-core preference (5-8% at most, with thermal risk);
   - **a FEX/Box64-class rewrite**: those projects are user-mode, with no
     softmmu, paging or MMIO. A system-mode rewrite is years of work for
     1.3-1.5x on v_run, and it fixes neither the sleep, nor Nightfire's
     renderer, nor Forza's GPU.
6. **Ceiling for a TCG-derived translator.** About 14-16 host instructions
   per guest instruction (20.6 today), which is about -15 to -25% of v_run.
   A purpose-built system-mode translator would be about 6-10, or -35 to
   -50%. It would change its mind on PMU counters on the vCPU thread:
   - back-end/memory-bound at IPC around 1 caps every translator rewrite
     low;
   - front-end or mispredict-bound widens the gap toward 2x.
7. **Its four runs:**
   - Simpsons `HAKUX_IBC=1` against the baseline;
   - Simpsons off-CPU attribution with `lock_wait_ns`;
   - Nightfire on-CPU profile of both threads;
   - Forza with a fixed GPU minimum frequency.

   GTA gets none.

**Where I agree.**
- **The order and the class split.** It ranks the sleep first and puts
  Forza on the GPU, from the same data, and it calls the FEX-class rewrite
  wrong scope.
- **The DMA_PUT site.** I checked `user.c:92-95`: the write takes
  `pfifo.lock` and counts the wait. That makes rank 1's first candidate
  concrete. My P moves from 0.35 to 0.4. It stays below its 0.45 because
  Tron's sleep moved once already.
- **Cross-page direct jumps.** I checked `translate.c:3124-3140`. This is a
  mechanism the vcpuplan list did not have. It is added to rank 2 as its
  own counter: the share of `helper_lookup_tb_ptr` calls from cross-page
  direct jumps, against RET and true indirect.
- **Nightfire.** The flat v_run across bands, while rcpu rises, is the
  better reading of my own table than mine was. Nightfire's binding thread
  is the renderer, and its v_run probably holds a wait. Rank 4 moves up to
  rank 3, and Nightfire's ceiling is revised. R3 still decides whether the
  vCPU half is a spin.

**Where I disagree.**
- **The discount for dispatch.** Its mechanism argument (a serial call on
  the critical path converts better than an inline compare) is sound. The
  only below-cap reading is profiler-on, though, and the profiler inflates
  helper-call cost. I keep rank 2's step 1 as the decider and do not
  pre-price it at 1/2. Its own Q5 run 1 is the same test.
- **Which title for the IBC pair.** It asks for Simpsons. I keep Tron:
  - it has a route file and a measured 1% v_run resolution (memfast O/C3);
  - Simpsons needs a pathfind hold for each arm;
  - Simpsons' sleep adds noise to F, though not to v_run.

  If lane.local can hold Simpsons twice, Simpsons answers the question
  more directly.
- **The GPU floor by a sysfs write.** Memory says no raw writes to device
  nodes outside the regimen tools. R4 uses the vendor `perf_mode` first.

## 5. The ranked plan (P x win; effort breaks ties only)

Win is in fps on the title, from the arithmetic in section 2. P x win is
expressed as expected fps points on the title it is sized for. Breadth is
listed but not multiplied in.

| rank | item | P | win | P x win | titles it reaches |
|---|---|---:|---|---:|---|
| **1** | **Name and remove the vCPU's sleep on GPU-side work**. First candidate: the DMA_PUT write under `pfifo.lock` (`user.c:93`) | 0.4 | Simpsons +8 to +20 fps (to 45-58); GTA's slow 12% back to 30 | **~3-8 fps on Simpsons**, plus GTA's share at 30 from 88% toward 97% | Simpsons, GTA, Tron, BF2 (near30), every title with a v_blk signature |
| **2** | **The JIT program, FEX/Box64 class inside TCG**: IBC probe default + cross-page direct chaining + 16-bit jump cache + RAS -> regions with cross-block register allocation -> inline scalar SSE | 0.4 | 8-18% of v_run: Simpsons +2-4 fps now, **+4-9 fps after rank 1** | ~1.5-3.5 fps | every vCPU-bound title (Simpsons, Tron, near-bound ones; Nightfire only if R3 shows real work) |
| 3 | **Nightfire's render thread**: finish waits inside the frame (10.3 ms) and the draw path (11.9 ms) | 0.35 (mine 0.3, the expert's 0.5) | renderer 30.5 -> about 20-23 ms: Nightfire 30 -> 36-42 if R3 shows the vCPU's time is mostly a wait | ~2-4 fps | Nightfire; Blinx/Forza share the draw-path cost (energy map item 6) |
| 4 | **GPU clock floor as a static regimen**, Forza first | 0.3 | Forza's slow half 20.7 fps -> 25-28; share at 30 from 46% -> about 60-75% | ~2 fps on Forza's slow half | Forza; part of the sleep on Simpsons/GTA if R1 names a GPU wait |
| 5 | Big-core preference on the Nova (uclamp.min, no hard pin) | 0.2 | <= 12% of v_run, likely 0-5% | ~0.5 fps | every vCPU-bound title |
| 6 | Inline scalar SSE (inside rank 2, listed for its exactness gate) | 0.7 | 0.5-1.2% of v_run | ~0.2 fps | SSE titles |

Not proposed: fastmem (loads rejected, stores priced at 1% or less); native
flags alone; x87 (0.6%); TSO (already elided); smaller TBs (refuted, #429);
a hard pin or ADPF (refuted); a predictive governor (owner); chaining or EOB
levers against the exec loop (refuted, #425); parking polling loops for fps
(it is energy only).

### Rank 1: name and remove the vCPU's sleep on GPU-side work

- **The approach that fits the hardware, and its precedent.** The Xbox's
  CPU and NV2A run concurrently. The guest waits on the GPU only when it
  reads a GPU result: a fence or report, `DMA_GET` for ring space, or a
  surface it reads back. Dolphin's dual-core mode runs the CPU and GPU
  threads apart and syncs only at such points. PCSX2's MTGS does the same.
  The aim is that a host lock is never held across a GPU wait that the
  guest did not ask for.
- **The mechanism.** v_blk is the vCPU asleep, neither running nor
  runnable. On Simpsons it tracks the render thread's CPU and fence waits
  (r 0.66 and 0.65), as on Tron (v_blk against GPU ms, r 0.64).
  vcpuwait433 named the first layer on Tron's intro: pfifo.lock in the
  `USER` register read, held by the PFIFO thread across
  `pgraph_vk_process_pending_reports -> pgraph_vk_finish`. It removed that
  layer (`bc2bced563`), and the sleep moved. Candidates for the next layer,
  by mechanism, all unmeasured:
  - the `DMA_PUT` write, which still takes pfifo.lock;
  - the BQL;
  - a wait for a GPU result.
- **Evidence for P = 0.4.** P is roughly 0.6 x 0.65:
  - 0.6 that one off-CPU capture (R1) names a site holding 50% or more of
    the sleep. vcpuwait433 estimated the same, lowered from 0.85 because
    Tron's sleep turned out layered.
  - 0.65 that the named site can go without an accuracy cost. It must also
    not turn into guest spin, the O1 failure mode in vcpuwait433, where
    freed time became polling of GPU results.

  The second factor was raised from 0.6 after the code read: the
  DMA_PUT write (`hw/xbox/nv2a/user.c:92-95`) takes `pfifo.lock`, which the
  PFIFO thread holds across a GPU finish. That is a lock held across a wait
  the guest did not ask for, which is the removable kind. The expert puts it
  at 0.45. The 0.4 is for removing at least half of the sleep.
- **Win.**
  - Simpsons: half of the sleep (4.7 ms) gives F 22.0, **45 fps**. All of
    it gives F at v_run, about 17.2 ms, **58 fps**. That assumes the
    render chain overlaps; its busy time F - Ri is 17.2 ms, so 58 is also
    the renderer's ceiling unless its fence waits shrink too.
  - GTA: the 39 slow windows lose 8.2 ms of the 9.7 ms sleep and return to
    the cap.
- **Files and board holders** (origin/board `territory.toml`, read
  2026-10-04), all free:
  - `hw/xbox/nv2a/pfifo.c`;
  - `hw/xbox/nv2a/pgraph/pgraph.c`;
  - `hw/xbox/nv2a/pgraph/vk/reports.c`, `renderer.c` (unlisted);
  - `system/cpus.c` (unlisted), if the site is the BQL.
- **The cheap decisive first step: R1** (section 7), no code. It names the
  site.
- **Prediction legs**, registered against R1's site:
  - **(exact) goldens bit-identical**, outside the known same-build-unstable
    captures (Stencil_ZERO family, GeometrySuperscreen_0.4999/0.5626; memfast
    section "The second pixel arm").
  - **(the point)** Simpsons slow-row v_blk at most half of A's.
  - **(no spin)** v_run must not rise by the freed amount. `[tpc787]` must
    not show a new GPU-poll pc.
  - **(fps)** Simpsons median and share at 45 up. GTA share at 29.5 up.
  - **(accuracy)** a guest-visible GPU result (fence/report) is never read
    early. A selftest, as vcpuwait433's.
- **Needs device:** yes. Pathfind holds for Simpsons; the `gta-sa` route
  for GTA.

### Rank 2: the JIT program (FEX/Box64 class, inside TCG)

- **Fits the hardware, and the owner's direction (vCPU JIT, 09-28).**
  - Rosetta 2 maps CALL/RET onto BL/RET with a side stack.
  - Box64's `CALLRET` and `BIGBLOCK` are on by default.
  - FEX does multiblock and native flags.

  Sources are in vcpuplan section 2. This session could not re-reach them.
- **Order, each step gated by a measured removal, not a sample share:**
  1. **The decider: a one-binary pair, `HAKUX_IBC=1` against unset**, on
     Tron 2.0. Tron is vCPU-bound below its 60 cap, its route works with or
     without a profile, and its v_run resolves 1% (memfast's O/C3 shape).
     - If v_run per frame falls 4% or more: flip the default (pixel arm
       and goldens), then build the RAS and the 16-bit jump cache. 97.9% of
       the remaining misses are pc collisions.
     - Under 2%: the lookup is hidden latency, as the softmmu compare was.
       Demote the JIT program below rank 4.
     - In the same counter build, split `helper_lookup_tb_ptr` calls by
       source: cross-page direct JMP/CALL (`translate.c:3136`,
       `gen_eob(DISAS_JUMP)`), RET, and true indirect. If cross-page direct
       jumps are a large share, **chain them directly** and unlink on
       INVLPG, CR3 writes and TLB flushes. In gameplay there is one page
       directory, and INVLPG runs 560-927/s. That removes the lookup without
       a probe.
  2. **Regions with register allocation across blocks.** Superblocks
     exist, off (`XBOX_SUPERBLOCK_ENABLED 0`). Gate: a host
     instructions-per-guest-instruction count on a `jitmix`-class capture
     (20.6 today) and a Tron v_run pair.
  3. **Inline scalar SSE.** Exactness gate: bit-identical to today's
     native helpers (`ops_sse.h`). COMISS/UCOMISS flags must match on NaN
     and ±0. MINSS/MAXSS stay helpers. Bail to the helper under a
     non-default MXCSR. An nxdk test XBE covers NaN, denormal, ±0 and
     rounding vectors.
- **P = 0.4** that the program delivers 8% or more of v_run.
  - For: the lookup removal is built and cut helper calls 92.6%. The
    profiler-on gfps rose 20%.
  - Against: two measured removals of sampled JIT cost came in at 1/4 to
    1/15 of their sample share.
- **Files:** `tcg/aarch64/tcg-target.c.inc`, `target/i386/tcg/*`,
  `accel/tcg/cpu-exec.c`, `tb-maint.c`, `tb-jmp-cache.h`, `tb-hash.h`,
  `tcg/tier1-opt.c`. All free.
- **Prediction legs:**
  - goldens bit-identical;
  - helper calls/s down (IBC) and RAS hit rate (counter);
  - Tron v_run per frame (the point);
  - Simpsons fps after rank 1.
- **Needs device:** yes. Step 1 is 2 Nova runs.

### Rank 4: a GPU clock floor as a static regimen (Forza)

- **Mechanism.** In Forza's slow half the render thread waits 32 ms per
  frame on fences, while the GPU stays at its 401 MHz floor. That suggests
  devfreq sees a serialized GPU as lightly loaded. near30 measured Tron's
  GPU at 22 ms per frame at 615 MHz, against about 34 at 401.
- **Not a predictive governor.** This is a fixed regimen (`perf_mode`) or
  a floor for the whole gameplay session.
- **P = 0.3:** unknown whether `perf_mode=2` moves the Nova's GPU clock.
  The thermal cost is unmeasured.
- **Decider:** R4.
- **Files:** dispatcher regimen / app-side power hints. No emulator code
  if the vendor mode does it.

### Rank 3: Nightfire's render thread

- **The cost.** Finish waits inside the frame (10.3 ms) and the draw path
  (11.9 ms for 366 draws, about 32 us a draw). Both grow in the slow
  windows (Fin 13.7, Draw 13.5), while the vCPU's time does not.
- **Owner.** The energy map's item 6 is unowned. The ubershader and push
  constants work (#569, bf2push656) touches draw-path CPU.
- **Decider:** R3's phase split with `[tpc787]` on master.
- **P = 0.35.** I put it at 0.3 and the expert at 0.5. For: the cost is
  named per phase. Against: no lane has cut draw-path CPU on a title yet
  (#474's uniform-hash skip was inert on Blinx).
- **Win.** The renderer falls to about 20-23 ms. If R3 shows the vCPU's
  28.6 ms is mostly a wait, Nightfire reaches 36-42 fps. If it is real
  work, the gain is capped near 30 until rank 2 also lands.

## 6. The ceiling per title

The best credible combination is ranks 1-4 at their stated wins, for the
titles each one reaches. The expert's ceilings (section 4) agree with these
within a few fps on each title.

| title | today | best credible combination | expected fps (range) | what remains | 60? |
|---|---|---|---|---|---|
| **Simpsons** | 37.4 median; 8% of windows >= 45 | rank 1 (half to all of v_blk) + rank 2 (8-18% of v_run) | **45-58**. If rank 1 fails: **39-42** | the renderer's own busy time (17.2 ms/frame, its fence waits 10.6) caps it near 58 unless those shrink too | **only if all of the sleep goes AND the render thread's fence waits shrink**: P about 0.1. 45 is P about 0.4 (rank 1's) |
| **GTA SA** | 29.7 median, 88% of windows at the cap | rank 1 | **30, held in about 95%+ of windows** | the game's own limiter | **not the game's rate**: needs a limiter patch and about 2x the vCPU work rate. Not reachable with any listed item |
| **Nightfire** | 29.6 median, 52% at 30 | rank 3 (+ rank 2 if R3 shows real vCPU work) | **30-40 median** (the expert: 40-45) | the render thread's draw path and in-frame finishes; the vCPU's true work is unmeasured | **no**: the renderer needs about 1.8x (30.5 -> 16.7 ms) and possibly the vCPU too. A faster translator does not touch the renderer |
| **Forza** | 27.6 overall; 20.7 in the slow half | rank 3 | slow half **20.7 -> 25-28**; share at 30 from 46% -> about 60-75% | GPU work per frame (16 ms render CPU + fence waits) | **not the game's rate** (IGN: locks at 30) |

**For the owner's decision.** The data holds GTA and Forza to their own 30.
It holds Simpsons to 45 as the stepping stone and Nightfire to "30 held".

- A native-60 bar is reachable for none of them with this architecture's
  listed levers.
- Simpsons is the only one where 60 is conceivable. It would take the full
  removal of the vCPU's GPU-side sleep plus faster GPU fences.
- Nightfire at 60 needs a 2x faster renderer and a 2x faster vCPU. That is
  a different engine for both halves (a purpose-built translator and a
  rewritten NV2A command path), not a plan item.

## 7. Profile run list (at most 4; not queued: lane.local slots them)

All on the **Nova** (the device the titles were measured on). Use current
master, device defaults, on battery. R1 is held by pathfind; R2-R4 are
soaks.

| id | title, route | counters / capture | decides |
|---|---|---|---|
| **R1** (the largest unknown) | **Simpsons**, a pathfind hold to free roam as the 10-04 hold (no route file exists; the hold is the route). Record 60 s, starting 60 s after the gameplay mark | `docs/lanes/vcpuwait433/capture_offcpu.sh` adapted to a pathfind hold: `OFFCPU=1` off-CPU simpleperf on the vCPU tid, read with `waitsite.py` (per-tid holder pass). Also the DMA_PUT lock wait (`lock_wait_ns`, `user.c:94`) if a line prints it | **What the vCPU sleeps on** (9.4 ms/frame). Rank 1's go/no-go: a site at 50% or more of the sleep, and which lock or wait. Also the holder thread's state (GPU fence or CPU work) |
| R2 | **Simpsons**, the same hold, 3 minutes, `--perflog` | `[lock474]`, `hakuX-phase` (renderer GPU/Draw/Fin), `[tpc787]`, `[rr425w]`, `[idlehalt]`, `hakuX-pace`, GPU MHz from thermal.jsonl | The renderer's split under the sleep (does v_blk track Fin or GPU?); hot guest pcs by time (question 2d); the GPU clock on Simpsons |
| R3 | **Nightfire**, `docs/testing/titles/routes/nightfire.route`, 300 s, `--perflog` on master | `[tpc787]`, `hakuX-phase`, `[lock474]` | Is Nightfire's v_run 28.6 real work or a wait (a GPU-poll or vblank spin pc in `[tpc787]`)? And which renderer phase grows in its slow windows. That sets rank 2's and rank 4's reach on Nightfire |
| R4 | **Forza**, `forza.drive.route` (as `3477700`), 600 s, **regimen max** (`perf_mode=2`), on master | GPU MHz from thermal.jsonl, decompose's rblk and Ri in the slow half | Whether the vendor perf mode lifts the GPU off 401 MHz at all, and what the slow half's fence wait becomes. Rank 3's go/no-go. Compare with `3477700`. The build differs, so the clock readout is the decision, not fps |

Not profiled: GTA. Its sub-30 windows carry the Simpsons signature, so R1
decides for both. Its at-cap frame is the game's limiter.

**Rank 2's decider is not on this list**, because it is a code A/B, not a
profile: the `HAKUX_IBC=1` against unset pair on Tron (2 Nova runs, one
binary, `tron-newgame-anystate`, 750 s; memfast's O/C3 shape). It needs no
new code; the probe is on master, opt-in.

## 8. Sources

- In the tree:
  - `docs/lanes/vcpuplan/NOTES.md` (profile split, external precedents with
    their URLs, section 2);
  - `docs/lanes/memfast/NOTES.md` on `origin/lane/memfast` @ `b41a8e4c2f`
    (phase 1 on the Nova, F1 rejected, the discount);
  - `docs/lanes/ibcache/NOTES.md`;
  - `docs/lanes/near30/NOTES.md`;
  - `docs/lanes/vcpuwait433/NOTES.md`;
  - `docs/lanes/energymap507/NOTES.md`;
  - `docs/lanes/vcpuprime428/NOTES.md`, `jcache425`, `retreason425`,
    `tcgchurn`, `tcg424flip`, `tbsize429`, `dirtytlb`;
  - `docs/testing/titles/targets.toml`.
- Runs read:
  - Simpsons: the pathfind hold 2026-10-04 (`briefs/vcpu60-data/`);
  - GTA: `1790875419-autoverdict-2123622`;
  - Nightfire: `1-1790676918-lane.memfast-1478620` and
    `1-1790990048-lane.memfast-522055` (pace only);
  - Forza: `1-1790826491-lane.verdict433-3477700`.
- External: none newly reached. WebSearch was denied to this session, IGN
  refused the fetch, and GitHub is off limits. The precedents (Dolphin
  fastmem and dual-core, ESPT/HSPT, Rosetta 2, Box64, FEX) are cited from
  vcpuplan section 2's URLs. The descriptions of Dolphin's dual-core mode
  and PCSX2's MTGS are from general knowledge, with no URL.

## 9. For the next lane: do not repeat

- **Do not plan these four titles as one class.**

  | title | bound |
  |---|---|
  | Simpsons | vCPU work plus vCPU sleep |
  | GTA | its own 30 cap; drops are sleep |
  | Nightfire | render thread first |
  | Forza | GPU-bound in its slow half on the Nova |

- **Do not read energymap507's guest idle for Forza (0.05) as current.** It
  was a Thor pre-leak run. On the Nova on b1cea467c6 it is 0.27.
- **Do not price a JIT item from its sample share.** Use memfast's ratios
  (1/4 to 1/15), or run a one-binary pair.
- **Do not read `[rr425pc]` as a time census.** It counts returns. Use
  `[tpc787]` (perflog builds).
- **`decompose.py` needs `--mark` on Forza's route,** which marks `play`,
  not `gameplay`. Without it the run reads VOID.
