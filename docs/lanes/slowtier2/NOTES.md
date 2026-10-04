# lane.slowtier2 -- #462 phase 2: why the titles under 30 fps are slow

Base: master @ 559ea2fc07. Reads existing results only; no device time, no
emulator change. The method is the first pass's (`docs/lanes/slowdown462/`),
cut down to the lines these runs actually carry (section 1). The first
pass's six titles are cited, not re-read.

Files here:
- `statusrows.py` (+ `statusrows.out`): the status page's row for each title
  (status.json, 2026-09-28 08:02 PDT), and the result id each reading came from.
- `index.py` (+ `index.out`): every result of the sixteen titles on disk.
- `condread.py`: one reading, with its conditions and the always-on counters
  over the verdict's own window. `readall.sh` runs it over every reading;
  its output is `readall.out`. **Cites below of the form `ro:N` are
  lines of `readall.out`.** (Outputs are `.out`: the repo ignores `*.txt`.)
- `levers.sh` (+ `levers.out`): which lever fold commits each reading's ref
  contains.
- `perflogscan.py`: which results of these titles carry perflog lines.
- `playsplit.py` (+ `otogi2-playsplit.out`): medians of a perflog soak's
  lines over one span, with the logcat.txt line range of each (section 7).
- `addshots.py` (+ `addshots.out`, `routes/*.shots.route`): the two frames
  added after the mark to the parked requests (section 7).

## 1. What the logs can and cannot say

**No reading of the fifteen non-Crimson titles was taken on a perflog build.**
`perflogscan.py` finds `hakuX-phase`, `xemu-gpu` and the full `hakuX-stall`
lines only in Crimson Skies' soaks. Every benchmark run on the status page
is a plain titleroutes, titlebench, titleplay or lanelocal soak. So there is
no PFIFO phase split, no GPU timestamp row, no download, texture or
pipeline-compile timer for any of them. The first pass priced these
categories with perflog soaks and simpleperf; this pass cannot, and says so
per row.

What every build logs, and what `condread.py` reads from it:

| counter | line | meaning (source) |
|---|---|---|
| fps | `hakuX-perf gfps=` | 60 flips / time between lines, title_verdict.py's windows; the median is its element `fs[n//2]` |
| `Ri` | `gfps=` line | ms per frame the PFIFO thread sat in its no-work wait for the guest's next kick (pfifo.c:2234, debug.h:156). `G - Ri` = the renderer's non-idle ms per frame: its CPU **and** its GPU waits (wall time) |
| vCPU on-CPU | `[tlb68] cpu/dt` | the vCPU thread's CLOCK_THREAD_CPUTIME over the 2 s window (cputlb.c:230). On-CPU less than 100% = the vCPU was blocked or halted |
| TLB resets | `[tlb68] rdus`, `rdous` | µs in `tlb_reset_dirty` on the vCPU thread / on any other thread (cputlb.c:135-143) |
| churn | `hakuX-pages inval ev=, di=` | code invalidations and TBs discarded per second (#424) |
| pusher | `fifoskew kicks=, backlog(mean=)` | kicks per second, bytes the PFIFO is behind at a kick |

So each reading gets a **side**: guest-side (the renderer waits: `Ri` a large
share of the frame), renderer-side (`Ri` small: the PFIFO thread is busy or
waiting on the GPU), and for guest-side, vCPU **on-CPU** vs **blocked**.
These are the first pass's top-level categories. The next level (exec loop
vs TB lookup vs guest code; PFIFO CPU vs GPU vs downloads vs compiles)
needs a profile or a perflog soak: section 4.

**The builds predate the levers.** `levers.out`: of the thirteen refs
behind the listed readings, none carries #479, #518, #528 or #536, and only
two carry #475: Arctic's (677ae13af8) and Arctic's rerun and BloodRayne's
(e884ad260e). The later MechAssault 2 and Crimson runs used for conditions
carry #475, and the MechAssault 2 ones #479 too. **Every listed reading below 30 is on a
build without the download coalescing, the display pre-download deferral,
the idle halt and the pipeline-compile fix.** Part of what follows may
already be fixed on master; the profile list runs on master for that reason.

## 2. Per-title table

Conditions: **clean** = thermal.jsonl shows no pause device above 0 over the
run, or a cold start (the device idle 20 min or more before the claim) and
no fall in fps; **paused** = a recorded pause, or the #507 shape; **unknown**
= neither can be said, with the reason. Frame = 1000 / fps median. "vCPU
off" = frame x (1 - on-CPU share). Regimen from run.log `PERF: regimen=`.

| title | reading (status) | result, ref, device, regimen | conditions | clean window | side | where the frame goes (ms/frame) | evidence |
|---|---|---|---|---|---|---|---|
| JSRF | 24.23 | titleroutes-886445, 02299ec656, Thor, MAX | **clean**: cold (the Thor idle 22 min before the claim), no fall | 24.23 = 41.3 ms | guest, vCPU blocked | vCPU on 30.6 / off 10.7; renderer idle 23.9, busy 17.9; TLB resets 1.3 + 0.4; churn 500 inval/s | ro:1-13 |
| MechAssault 2 | 23.89 | lanelocal-1258823, c0db2c0bdc, Thor, MAX | **paused (inferred)**: claimed 5 s after GTA's 500 s soak (slowdown462-1484367) ended, no thermal record; 30 fps and ~11 fps alternate in ~10-min cycles (bins at ro:18), as the recorded pause cycles of sustain507's runs do (ro:81-107). **The 23.89 is no rate the title ran at**: 185 windows at ~11 and 185 at 30, and the median element falls in the gap between them (p25 10.9, p75 30.0, ro:22) | **29.97**: hostops-810152 (37b1b81931, 24 min at MAX, start xo-therm 46.9 C, no pause, ro:68-80); titleroutes-681960 29.97 (ro:62) | capped at 30 (Vpf 2.00) | not slow: vCPU on-CPU 98% with the renderer idle 28.7 of 33.4 ms at the cap: the guest's idle loop spinning (#525's case, inferred). In the slow mode vCPU on-CPU falls to 75% (ro:28-41), as it does in the recorded pauses (71-72%, ro:81-107) | ro:15-107 |
| Arctic Thunder | 21.37 | titleroutes-979135, 677ae13af8, Thor, MAX | **unknown, likely clean**: claimed 315 s after a 120 s run, no record, no fall. The recorded rerun (1531400, e884ad260e: start 62.4 C, no pause) reads 24.04 | 21.37-24.04 = 47-42 ms | guest, vCPU on-CPU | vCPU on 36-41 (86-87%); renderer idle 21-24; **TLB resets on the vCPU 5.3-6.0 and on other threads 2.5-2.9**; **churn 7,300-8,300 inval/s and 37,000-42,000 TBs discarded/s**, 15-20x any other title here | ro:109-136 |
| BloodRayne | 22.34 (status soak window: 93-243 s, **before** the mark at 247 s: the cutscenes) | titleroutes-1530145r, e884ad260e, Thor, MAX | **clean**: thermal.jsonl start 63.0 C, no pause | **24.90** over the verdict window (mark to end, ro:144) | renderer (idle 27%) | vCPU on 28.3 / off 11.9; renderer busy 29.0; **4,234 kicks/s** (10x the next title); TLB resets 0.3 | ro:137-162 |
| Alias | 20.80 | titleroutes-2113140, c6e2be0936, Thor, MAX | **unknown, leaning clean**: claimed 3 s after a 440 s Azurik run (warm), no record. It is flat at 20.2-21.7 for 7.7 min with no fall. The vCPU is on-CPU 95%, where MechAssault 2's recorded pauses dropped it to 71-75% | 20.80 = 48.1 ms | guest, **vCPU on-CPU** | vCPU on 45.7 (95%); renderer idle 19.6, busy 28.5; TLB resets 0.5; churn 412/s | ro:163-175 |
| DOA Xtreme Beach Volleyball | 20.0 (status soak window 93-243 s) | titlebench-2893458, a593d8eb85, **Nova**, MAX | **clean (Nova)**: no pause mechanism is known on the Nova; not measured. The window's p75 is 59.9: it mixes rallies with menus | 19.99; the pass-1 titleplay run over `mark play` to end reads 17.05 (a5b5b628f2, ro:196) | **renderer, saturated** | renderer idle 1.3-2.2 ms of 50-59 (2-4%); vCPU on 25-29 (50%); the Nova's GPU is not logged | ro:176-201 |
| Conker | 19.39 | rtdbench-3, 06e73e9f5e, Nova, regimen unrecorded | **unknown**: no route mark, so gameplay is not shown (p75 59.9: part of the window is at 60) | 19.39 = 51.6 ms | renderer (idle 20%) | vCPU on 43.8 (85%); renderer busy 41.8; TLB resets 1.3 + 1.0; 514 full TLB flushes/s | ro:202-215 |
| Crash Twinsanity | 15.72 | titleroutes-512742, a593d8eb85, Thor, MAX | **clean**: cold (idle 20 min), no fall (a dip to 8.5-11 at 240-300 s recovers) | 15.72 = 63.6 ms | renderer (idle 27%) | vCPU on 43.3 / off 20.3; renderer busy 49.4 | ro:216-229 |
| Dead or Alive 3 | 15.41 (status soak window 101-251 s) | titleplay-p1-doa3, a5b5b628f2, Thor, unrecorded | **not gameplay**: the status page's own pass-1 review says "gameplay not reached"; the window is 12-13 fps and 60 fps screens | none | (guest, in that window) | not a gameplay reading. That window has the heaviest code churn of the set: 15,490 inval/s, 158,526 TBs discarded/s, vCPU TLB resets 10.8 ms/frame (ro:237-242) | ro:230-255 |
| Project Gotham Racing | 14.27 | titleroutes-3587419, a593d8eb85, Thor, MAX | **paused after 360 s (inferred)**: cold (idle 41 min), no record. From a gate-admitted start the Thor still pauses 5-8 min in (sustain507), and the fall is at 6 min: 15.1 fps to 360 s, then 5.5 to the end (a fall to 0.36, just over the one-third test), vCPU on-CPU falling 87% -> 61% and zero-filled audio 0% -> 71% at the same point (ro:268-278) | **15.12** over 197-360 s = 66.1 ms | renderer (idle 13%) | vCPU on 57.3 (87%); renderer busy 58.4: both threads near full | ro:256-278 |
| Brute Force | 13.16 | titleroutes-1101937, 9d3656f263, Thor, MAX | **clean**: cold (idle 23 min), flat 11.3-13.9 from the mark (the 30 fps before it is the pre-mark screens) | 13.16 = 76.0 ms | guest, **vCPU blocked** | vCPU on 55.4 / **off 20.6**; renderer idle 49.4 (65%); a mean backlog of 788 KB beside an idle renderer (not understood) | ro:279-291 |
| Otogi (**on master: 29.97, at its cap; section 7**) | 12.62 | titleroutes-1129571, 9e7f8418dc, Thor, MAX | **clean (inferred)**: claimed 703 s after a 570 s run, no record; the fall 30 -> 11 is at 120 s, too early for #507 | 12.62 = 79.3 ms | **renderer, near saturated** | renderer idle 7.3 (9%), busy 74.9; vCPU on 46.7 (59%); backlog 1.4 MB (the pusher far ahead); vCPU TLB resets 2.7 | ro:292-305 |
| Burnout | 10.85 | titleroutes-1150288, 3540bf2a69, Thor, MAX | **clean (inferred)**: claimed 704 s after a 550 s run, no record; the fall 30 -> 10 is at 210 s, at the mark | 10.85 = 92.2 ms | renderer (idle 23%) | renderer busy 71.1; vCPU on 54.8 (59%); vCPU TLB resets 2.7; zero-filled audio 56% | ro:306-319 |
| Black | 7.45 | titleroutes-3358750, a593d8eb85, Thor, MAX | **clean (inferred)**: cold (idle 23 min). Frame `215235-f1.png`, 3.5 min in, shows the intro cutscene at FPS 4 before any pause could come. The 26 fps before the mark is a black "4 DAYS EARLIER" card (`215343-f2.png`); `215426-gameplay.png` shows FPS 7. A pause after 8 min is not excluded (no record) | 7.45 = 134 ms | guest (idle 42%), vCPU blocked | vCPU on 92.3 / **off 42**; renderer busy 78.6; **TLB resets on other threads 17.8 ms/frame** (#548's cost, 6x any other title) and 3.6 on the vCPU | ro:320-332 |
| Midtown Madness 3 (**on master: 17.64, guest-bound; section 8**) | 3.13 | titleroutes-1032854, 6aaa8197c5, Thor, MAX | **unknown, leaning content**: claimed 5 s after a 410 s Alien Hominid run (warm), no record. The #507 test flags the fall at 210 s (51.9 -> 3.1), but it lands on the mission load, which the route frames show: `040703-a3.png` (menu) at FPS 59, `040838-b3.png` (the static mission briefing) at FPS 3, `041030-gameplay.png` (the drive) at FPS 3 | 3.13 = 320 ms | guest, **vCPU blocked** | vCPU on 228 (71%) / **off 92**; renderer idle 260 (81%); vCPU TLB resets 9.3. The verdict's ten 12-20 s "hangs" are its steady frame: 60 flips at 3.1 fps take 19 s, as with GTA in the first pass | ro:333-345 |
| Crimson Skies (Thor 23.4 / Nova 30) | Thor 23.4 (pass-1 hand review) | titleplay-p1-crimson, a5b5b628f2, Thor, unrecorded | **paused**: the #507 shape at 270 s (25.3 -> 5.7, ro:358-368); lane.thermal507 listed this run as a probable pause | Thor **29.73** (titlebench-2601931, d0e30924f8, MAX, ro:376) and **29.72** (flip474-1819312, recorded no pause, ro:416); Nova **29.97** (titlebench-2612149, the same d0e30924f8, ro:389) | capped at 30 | **The two handhelds do not differ; the Thor's 23.4 is the pause.** On the same ref both read ~30. The Thor's lows are lower (p10 24.4 vs 27.9) with its vCPU on-CPU 90-93% vs the Nova's 94%. The Thor perflog run (flip474-1819312, before #504, so the GPU row is on the uncorrected period): renderer Tot 29.1, idle 11.5, Draw 13.7, GPU 4.5 ms (`regimes.py --from 120 --to 244`) | ro:346-421 |

The first pass's six (Nova/Thor, `docs/lanes/slowdown462/NOTES.md`
"Summary"): DOA Ultimate (the GPU plus the flip's lock-held wait, #474/#475),
AUF and Blinx (exec-loop returns, #425), Blinx 2 (at its cap), Forza
(deferred download finishes, #479/#518), GTA (the guest: JIT code, blocked
30%, TB dispatch).

## 3. Cross-title ranking

By how many titles each bounds (clean readings only; MechAssault 2 and
Crimson are at their 30 cap when clean, DOA3 and Conker have no gameplay
reading), with the ms per frame read above.

| # | cause | titles it bounds | ms/frame | lever that covers it | status |
|---|---|---|---|---|---|
| 1 | **Renderer-side, not split** (PFIFO CPU, GPU, downloads, compiles and the flip wait all sit in `G - Ri` on these builds) | 6: Otogi (busy 74.9, idle 9%), Burnout (71.1, 23%), PGR (58.4, 13%), DOAX (48-58, 2-4%, Nova), Crash (49.4, 27%), BloodRayne (29.0, 27%) | 29-75 busy of 40-92 frames | possibly #479/#518 (downloads), #530 (GMEM), #536 (compiles), #475 (the flip under `pg->lock`); **none of these readings' builds has #479, #518 or #536, and only BloodRayne's has #475** | **undecided**: needs a perflog soak on master (section 4) |
| 2 | **vCPU blocked** (guest-side, vCPU off-CPU) | 4: MM3 (92), Black (42), Brute (20.6), JSRF (10.7); GTA in the first pass (59-62, 30%) | 11-92 | #475 if it is `pg->lock` in `pgraph_read`, as the first pass found on DOA, Forza and Blinx 2; **none of these four builds has #475**. For MM3 and GTA, both open-world streaming titles, a disc read or another lock is not excluded (inference) | **undecided**: needs an off-CPU record |
| 3 | **vCPU on-CPU** (guest-side, vCPU 86-95%) | 2: Alias (45.7), Arctic (36-41) | 36-46 | #425 (the exec loop and TB lookup, the first pass's AUF and Blinx shape) if it is dispatch; #424 for Arctic's churn | Alias undecided (needs the on-CPU split); Arctic has churn on record |
| 4 | **#424 code churn** | Arctic (7,300-8,300 inval/s, 37-42k TBs discarded/s); Crimson at its cap (6,100-6,800, 46-51k); DOA3 outside gameplay (15,500, 159k) | not priced: GTA's 340-420 inval/s cost 1.6-5% of the vCPU in the first pass; Arctic runs 20x that | #424 (lane.tbchurn424) | on record, not priced |
| 5 | **TLB resets on other threads** (#548) | Black 17.8 (13% of its frame); Crimson 2.8-4.0 at the cap; Arctic 2.5-2.9 | 2.5-17.8 | #548 | Black's is the largest seen. Its renderer is not the bound (idle 42%), so it is cost, not the frame, unless the reset blocks the vCPU (inference) |
| 6 | **TLB resets on the vCPU thread** | MM3 9.3, Arctic 5.3-6.0, Black 3.6, Otogi 2.7, Burnout 2.7 | 2.7-9.3 | **no lever names it**: #548 is the render thread's. Its caller on the vCPU is not on record | **new**: name the caller from the next profile |
| 7 | **Thermal pause** | readings, not titles: MechAssault 2's 23.89, Crimson's Thor 23.4, PGR's last 135 s | a 3-5x fall | #507 (sustain507: the start temperature, not the regimen) | on record |
| 8 | **Idle-loop spin at the cap** | MechAssault 2 (vCPU 98%, renderer idle 86%), Crimson Thor (vCPU 90-93%) | heat, not fps | #525/#528 (idle halt), #526 (spin-waits) | on record, inferred |

**Update (section 7):** on master Otogi is no longer in row 1. Its renderer
is busy 5.3 ms of a 33.4 ms frame, at the 30 cap. Whether the rest of row 1
moved with it is what runs 4, 6, 7 and 8 measure.
MM3 leaves row 2 for row 3: on master its vCPU is on-CPU 92-96% and the
blocked time is gone (section 8).

New causes no lever covers: **(6)**, the vCPU thread's own `tlb_reset_dirty`
time, and **the vCPU-blocked time on #475-less builds**. That time is #475's if
it is `pg->lock`; otherwise it is new. Two single-title findings are not
causes yet: BloodRayne's 4,234 kicks/s, 10x any other title, and Brute
Force's 788 KB mean backlog beside a renderer idle 65% of the frame.

## 4. The profile list for tonight (not queued; lane.local slots them)

All six on **current master** (the levers of section 1 in the build). Each
from a **cold start**: xo-therm at or under ~50 C at the claim.
hostops-810152 started at 46.9 C and did not pause in 24 min at MAX. The
regimen is **MAX**, to match the readings. sustain507 found that the start
temperature matters and the regimen does not. Every run has the route's own
`mark gameplay`.

| # | title | device | route | kind | counters on | what it decides |
|---|---|---|---|---|---|---|
| 1 | Otogi | Thor | `otogi` | perflog soak, 550 s | `hakuX-phase`, `xemu-gpu` (the #504 measured period), `hakuX-stall`, `xemu-surf`, thermal | the renderer split for cause 1 on its purest case (renderer idle 9%): PFIFO CPU vs GPU vs downloads vs compiles |
| 2 | Burnout | Thor | `burnout` | perflog soak, 460 s | as 1 | the same for a second renderer-side title, plus whether the 56% zero-filled audio is the frame or the audio path |
| 3 | DOA Xtreme Beach Volleyball | Nova | `doax` | perflog soak, 420 s | as 1 | renderer saturated (idle 2-4%) on the DOA engine: is it DOA Ultimate's GPU-bound shape, and does #475 on master move it |
| 4 | Midtown Madness 3 | Thor | `midtown-madness-3.returning` (the reading's) | held simpleperf session, `--trace-offcpu` (read `perf:` in the session log: paranoid must be 1), `mark gameplay` + 30 s, 30 s | switch records (`offcpu.py`), `[tlb68]`, thermal | what the vCPU blocks on for 92 ms/frame (cause 2), and the vCPU's TLB-reset caller (cause 6); answers GTA's (#482) open 30% too. A cold start also settles whether the 3 fps is the title or a pause (the reading was warm) |
| 5 | Black | Thor | `black.returning` (the reading's) | held simpleperf session, `--trace-offcpu`, `mark gameplay` + 30 s, 30 s | as 4, plus the render thread's samples | the vCPU's 42 ms/frame blocked, and whether the render thread's 17.8 ms/frame of TLB resets (#548) is what it blocks on |
| 6 | Alias | Thor | `alias` | held simpleperf session, on-CPU, `mark gameplay` + 30 s, 30 s | cpu-clock samples | the vCPU on-CPU split (exec loop, TB lookup, guest code, helpers) for cause 3 |

Not on the list, and why:
- **JSRF, Brute Force**: cause 2 as MM3 and Black. Answer those first.
- **PGR, Crash, BloodRayne**: cause 1. Runs 1-3 decide it, or narrow it.
- **Arctic**: its churn is already on record for lane.tbchurn424 (#424).
- **MechAssault 2 and Crimson**: at their 30 cap when not paused. Their open
  question is sustain (#507), which lane.sustain507 owns.
- **DOA3 and Conker** need a gameplay route first (lane.titleroutes), not
  a profile.

## 5. Phase 2b: parked for hostops' cold slots (2026-09-28)

lane.local's delivery (#462 issuecomment-5873161079, 15:27Z) moved the Thor
runs to today. They go through hostops' cold slots, and none is queued by
this lane. `park.py` wrote the eight requests under
`$DISPATCH_DIR/parked/slowtier2-cold-20260928/`, and `park.out` lists them.
The directory's README is `parked-README.md` here. All eight are on the
Thor, as `-Pperflog=true` builds of master @ 97a6fa2b51, which carries #479,
#504, #518, #528 and #536. Each sets PERF_REGIMEN=max and uses its title's
own route and `mark gameplay`.

| # | id | title | s | decides |
|---|---|---|---|---|
| 1 | 1-1790609660-lane.slowtier2-otogi762702 | Otogi | 550 | the renderer split (section 4 run 1); the pilot |
| 2 | 1-1790609661-lane.slowtier2-mm3184014 | Midtown Madness 3 | 580 | title or pause from a cold start; the vCPU's pfifo.lock wait |
| 3 | 1-1790609662-lane.slowtier2-black167924 | Black | 760 | vCPU off-CPU 42 and other-thread TLB resets 17.8 ms/frame, on master |
| 4 | 1-1790609663-lane.slowtier2-burnout968727 | Burnout | 460 | the renderer split, second title |
| 5 | 1-1790609664-lane.slowtier2-alias942359 | Alias | 450 | guest-side on master |
| 6 | 1-1790609665-lane.slowtier2-pgr365442 | PGR | 420 | re-measure on master (gameplay mark at +197 s in 3587419) |
| 7 | 1-1790609666-lane.slowtier2-crash627374 | Crash Twinsanity | 420 | re-measure (route mark at ~239 s, summed from the route's waits) |
| 8 | 1-1790609667-lane.slowtier2-bloodrayne201189 | BloodRayne | 420 | re-measure (mark at +244 s in 1530145r) |

Where it departs from the section 4 plan, and why:
- **No simpleperf sessions.** The dispatcher builds perflog APKs
  (dispatcher.sh `build_ref`, `-Pperflog=true`) but has no simpleperf path.
  So MM3, Black and Alias are perflog soaks, not held `--trace-offcpu` or
  on-CPU sessions. They carry `Lw`, the vCPU's wait on `pfifo.lock` in
  `user_write` (user.c:82-85, logged on `hakuX-cpu`, profile.c:648). That
  decides the vCPU-blocked cause only if `Lw` accounts for the off-CPU time.
  `pg->lock` in `pgraph_read` has no perflog timer. If `Lw` falls short, the
  held session is still needed, and lane.local runs it by hand.
- **The idle halt is off.** `HAKUX_IDLE_HALT` is opt-in (system/cpus.c:569),
  so these runs measure master's defaults, and #528 is in the build but not
  active. The renderer-side group's renderer is the bound, not the idle
  loop, so this matters less there (inference).
- **DOAX (Nova) is not parked.** Per the delivery, it waits for tonight.

Pilot: run 1 is the pilot, and the README says runs 3-8 wait for
`pilots/lane.slowtier2.ok`. This lane writes that file after reading run 1:
the tags are present and the route reached the mark. Device time is about
80 min: 4,060 s of soak plus 8 x 90 s of setup.

## 6. The failed pilot and the route check (2026-09-28, attempt 3)

**What failed.** Run 1, `0-0-s-1-1790609660-lane.slowtier2-otogi762702`
(97a6fa2b51, Thor, MAX, cold at xo 49.6 C per hostops), has every tag
but never left Otogi's title: `route-frames/095419-intro.png` and
`095703-gameplay.png` both show "PRESS START BUTTON" at FPS 29. Its
renderer split describes the title loop, so it is not used.

**Why (timing, partly inferred).** master's `otogi.route` presses START once,
at +48 s. Times are from the route start (`routecheck.py`, from run.log's
`ROUTE` lines and the first `hakuX-perf gfps=` line in logcat.txt):

| run | ref | first frame | frame-time spike (title up) | START | START into the title | gameplay frame |
|---|---|---|---|---|---|---|
| titleroutes-1129571 | 9e7f8418dc | +12 s (05:24:07.166) | +22.5 s (05:24:17.261, G max 168.5) | +50 s (05:24:44.673) | ~28 s | play (bamboo forest, FPS 9) |
| pilot 762702 | 97a6fa2b51 perflog | +4 s (09:52:33.418) | +14 s (09:52:43.797, G max 437.3) | +51 s (09:53:20.949) | ~37 s | title |

Both runs show a transition after START: G max 172.1 at 05:24:47.492 in the good run, and 316.6 to 50.6
at 09:53:24-09:53:31 in the pilot. So in the pilot START did land on
something. My reading, which no frame confirms: by +37 s the title had given
way to its attract loop, START returned to the title, and the 40 A presses
after it never leave the title. The pilot also cleared the shader cache
(result.json `shader_cache: cleared: apk 6d334facad15 -> f2626e7ecd88`), so
the 8 s earlier boot is not obviously the perflog build's doing.

**The fix.** `routes/otogi.cold.route` (route.sh --check: ok, 154 lines)
presses START four times, 6 s apart, from +22 s. For a title at +14..+22.5 s
(the two runs above), at least one START lands on it within ~26 s. It
adds `shot title` (+20 s) and `shot menu` (+50 s) and four more intro A
presses. `mark gameplay` falls at ~+258 s, against ~+274 s on master.
master's `docs/testing/titles/routes/otogi.route` is not this lane's file:
lane.titleroutes should take the same fix there if the re-pilot's frames
show play.

**The other seven routes** (`routecheck.out`, `routecmp.py`). Every
parked route is byte-identical to the one its last run played, and every
one of those `mark gameplay` frames shows play:

| route | last run | first frame | gameplay frame |
|---|---|---|---|
| midtown-madness-3.returning | 1-1790506491-titleroutes-1032854 | +54 s (the FMV before it is uncounted; `boot30` is FMV, `s1` LOADING) | driving, pizza timer 01:37, FPS 3 |
| black.returning | 1-1790482599-titleroutes-3358750 | +5 s | first-person, HUD, FPS 7 |
| burnout | 1-1790513065-titleroutes-1150288 | +4 s | race countdown "3", 0 mph, FPS 28 (play starts seconds later) |
| alias | 1-1790519290-titleroutes-2113140 | +5 s | casino floor, player in control, FPS 19 |
| pgr.returning | 1-1790483525-titleroutes-3587419 | +22 s | race, "GO", FPS 14 |
| crash-twinsanity | 1-1790489396-titleroutes-512742 | +4 s | Crash on the beach, FPS 10 |
| bloodrayne | 1-1790548501-titleroutes-1530145r | +4 s | Rayne outside the church, FPS 26 |

The five runs that booted in +4..+6 s match the pilot's boot, so the pilot's
failure mode does not carry to them. PGR's route presses START three
times, 12-15 s apart, and MM3's START at +39 s skips an FMV that its
`boot30` frame (+32.5 s) shows still playing. Neither depends on a single
START landing in a narrow window. None of the seven needed a change.

**Re-pilot parked.** `1-1790615781-lane.slowtier2-otogi2870269.req`
(`park_otogi2.py`) is in the parked dir: the same ref, seconds, regimen and
device as run 1, with the fixed route. `readme_append.py` added the order to
the parked README. This lane writes `pilots/lane.slowtier2.ok` and deletes
`PILOT-FAILED` only after reading its `gameplay` frame.

## 7. The re-pilot read: Otogi is at its cap on master (2026-09-28, attempt 4)

Run: `0-0-s-1-1790615781-lane.slowtier2-otogi2870269` (master 97a6fa2b51,
perflog, Thor, MAX, `routes/otogi.cold.route`). Cites: `tl:N` is a line of
`otogi2-timeline.out` (slowdown462's `timeline.py`), `ps:N` of
`otogi2-playsplit.out` (`playsplit.py`, which prints the logcat.txt line
range of every median), `oc:N` of `otogi2-cond.out` (`condread.py`).

**The route reached play.** The frames, in order: `185857-title.png` is the
title ("PRESS START BUTTON"), `185931-menu.png` the main menu ("Stage"
selected), `190020-intro.png` the intro cutscene, `190330-gameplay.png` the
bamboo forest with the player and the HUD, FPS 29. The four STARTs from
+22 s did what the single START at +48 s did not. hostops wrote
`pilots/lane.slowtier2.ok` on the same frame at 02:13Z and set
`PILOT-FAILED` aside; this lane read the frames itself and agrees.

**Conditions: clean.** Start xo-therm 46.6 C, 72.0 C at the mark, max 74.0 C,
19 samples, no pause device above 0 (oc:4; run.log `THERMAL:`). The shader
cache was cleared for the new APK (result.json `shader_cache`).

**Play lasts 105 s, and the verdict's window is mostly not play.** The mark
is at +297 s (tl:146). Play runs to about +402 s. From +404 s the draws per
frame fall from 280-730 to 11-31 (tl:200-207), and the phase row becomes the
title's: over +404..+554 s Draw 0.7, Fin 1.3, GPU 1.4 ms, 26 draws (ps:35,
ps:38), against Draw 0.4, Fin 1.3, GPU 1.3 ms, 18 draws on the title at
+15..+37 s (ps:51, ps:54). No frame was taken there, so "back on the title"
is read from the counters. Why play ended is inferred: the last 10 s of play
carry three windows with Fin 10-22 ms and GPU 30-40 ms (tl:194, tl:197,
tl:198), the shape of a full-screen fade, and the route's loop fights
nothing in particular, so the player most likely died. The verdict's window
(mark to end, 257 s) is 105 s of play and 150 s of title. Every number below
is over **+297..+392 s**, which leaves the fade out.

| | old reading (9e7f8418dc, no perflog) | re-pilot (97a6fa2b51) | cite |
|---|---|---|---|
| fps median | 12.62 (p25/p75 10.7/16.1) | **29.97** (p10/p25/p75 29.9/29.9/30.0, min 24.6), Vpf 2.00: the 30 cap | ro:300, oc:7 |
| frame (G) | 82.2 ms | 33.4 ms | ro:300, ps:2 |
| renderer idle (`Ri`) | 7.3 ms (9%) | 22.5 ms (67% of G) | ro:300, ps:2 |
| `G - Ri` | 74.9 ms | 10.9 ms | ro:300, oc:7 |
| vCPU on-CPU | 59.0% | 98.2-98.5% | ro:301, ps:13, oc:8 |
| vCPU TLB resets | 2.70 ms/frame | 0.58 ms/frame | ro:301, oc:8 |
| kicks/s, mean backlog | 46, 1.40 MB | 108, 0.68 MB | ro:302, oc:9 |
| audio zero-filled | 0.8% | 0.0% | ro:304, oc:11 |

Where the 33.4 ms frame goes on master (medians of 47 windows, ps:2-15):

| part | ms/frame | cite |
|---|---|---|
| renderer thread, accounted (`Tot`) | 27.8, of which **idle 22.5** | ps:3 |
| renderer busy (`Tot - Idle`) | **5.3**: Draw 4.4 (of which its `Pipe` part 2.4), Surf 0.5, Fin 0.4 | ps:3, ps:15 |
| downloads | 0.0 ms (10 a window, all deferred: `su_deferred` 14,125) | ps:5, ps:9 |
| texture hash and upload | 0.0 | ps:3 |
| pipeline compiles | none: `pipe[ev0 pend0]`, PGen 0, SGen 0 | ps:6, ps:12 |
| GPU, from the timestamp rows | 15.7 (render 7.7, transfer 8.0) = 47% of the frame | ps:3 |
| vCPU wait on `pfifo.lock` (`Lw`) | 0.0 | ps:4 |
| `pg->lock` read wait | 0.9 ms per 2 s window | ps:10 |
| guest idle loop | **66.7% of the vCPU's time** (`[rr425w]`, idle pc 8001b02e); the idle halt is off (`[idlehalt] on=0`), so the vCPU thread spins at 98% | ps:8, ps:11, ps:14 |

**What it says.**
- On master Otogi is **not slow**. It sits at its 30 fps cap with the
  renderer idle two-thirds of the frame, the GPU under half busy and the
  guest in its idle loop two-thirds of the time. It belongs with MechAssault
  2 and Crimson Skies (at the cap when clean), not in row 1 of section 3.
- The intro cutscene moved the same way. The old run fell to 11-12 fps at
  +120 s (ro:297), where the cutscene starts. On master the cutscene runs at
  29 with the renderer idle 17.8 of 33.4 ms (ps:18-19).
- **Which change moved it is not decided by this run.** One run on one ref
  cannot say. The refs differ by #475, #479, #504, #518, #528 (off by
  default) and #536, and the old build logged no phase row. The old reading
  was probably not a thermal pause: its audio was whole (0.8% zero-filled)
  where the pauses on record starve it (PGR 71%, section 2). That is an
  inference. Pricing the old build is not worth a device run: the question
  it would answer is closed on master.
- **Heat is the open side.** From a 46.6 C start the run reached 72.0 C by
  the mark and 74.0 C at most, under MAX, with the vCPU thread at 98% on an
  idle loop even on the title. The pause is at 78 C. The lever for that is
  the idle halt (#525/#528), which is off by default. An `HAKUX_IDLE_HALT=1`
  soak is lane.idlehaltdefault's to run, not this lane's.
- **It is not a Playable reading yet.** Playable is sustained play, and
  this route holds play for 105 s. lane.titleroutes owns
  `docs/testing/titles/routes/otogi.route`. It needs the four STARTs of
  `routes/otogi.cold.route`, and a play loop that survives at 30 fps. The
  old run's loop survived because the game ran at 12 fps.

**What changed for runs 2-8.** A mark frame in play does not show that the
window after it is play. So `addshots.py` added two frames after the mark
to the six requests still parked (runs 3-8): `shot play1` near +70 s and
`shot play2` near +160 s. The route to the mark, the ref, the seconds, the
regimen and the ids are unchanged. The derived routes are
`routes/*.shots.route`, each passes `route.sh --check`, and `addshots.out`
lists them. Run 2 (MM3, `0-0-s-1-1790609661-lane.slowtier2-mm3184014`) was
queued by hostops at 19:19 PDT, before the change, and runs as parked. Its
window is read from the counters. The risk is the same for every route
timed on a slow build: MM3's mark frame shows a delivery timer at 01:37, and
the races of Burnout and PGR end.

## 8. Run 2 read: Midtown Madness 3 is guest-bound on master (2026-09-28, attempt 4)

Run: `0-0-s-1-1790609661-lane.slowtier2-mm3184014` (master 97a6fa2b51,
perflog, Thor, MAX, `midtown-madness-3.returning` as parked, without the two
added frames). Cites: `mt:N` is a line of `mm3-timeline.out`, `mp:N` of
`mm3-playsplit.out`, `mc:N` of `mm3-cond-play.out`.

**The route reached play.** `192523-drive.png` and `192539-gameplay.png`
show the drive with the HUD (timer 01:27 and 01:42, FPS 19 and 18).

**Conditions: clean over play.** Start xo-therm 49.2 C, 74.0 C at the mark,
max 77.8 C. A pause (`thermal-pause-F8`) began after +574 s, in the run's
last 24 s (mc:2, mc:4), long after play had ended.

**Play lasts 80 s after the mark.** The drive starts at +204 s, before the
mark at +315 s (mt:125, mt:161), and runs to about +394 s. From +408 s every
window to the end draws exactly 242 and runs at 29-30 fps (mt:190-283,
mp:34, mp:38): a static screen, read from the counters, most likely the end of the delivery.
The verdict's window (mark to end) reads 29.96, which is that screen. Play
is read over **+315..+394 s**.

| | old reading (6aaa8197c5, warm start) | run 2 (97a6fa2b51, cold start) | cite |
|---|---|---|---|
| fps median | 3.13 | **17.64** (p10/p25/p75/p90 15.0/16.3/18.8/20.2) | ro:333-345, mc:7 |
| frame | 320 ms | 56.7 ms | section 2, mc:7 |
| vCPU on-CPU | 71% (228 ms on, **92 off**) | 92-96% (at most 4.6 ms off) | section 2, mp:13, mc:8 |
| guest idle loop | not logged | 0.0% | mp:14 |
| renderer idle | 260 ms (81%) | 26.0 ms (46% of the frame) | section 2, mp:2-3 |
| renderer busy (`Tot - Idle`) | not logged | 24.3: Fin 12.1 (Sub 8.6, Fen 3.4), Draw 8.85, Surf 1.75 | mp:3, mp:15 |
| GPU | not logged | 13.1 ms (23% of the frame) | mp:3 |
| vCPU wait on `pfifo.lock` (`Lw`) | not logged | 0.0 | mp:4 |
| TLB resets, vCPU / other threads | 9.3 / - | 0.92 / 0.70 ms/frame | section 2, mc:8 |
| full TLB flushes | - | 408/s, about 23 a frame | mc:8 |

**What it decides.**
- **Title or pause: the title, and it is 17.6 fps on master, not 3.1.** From
  a cold start, with no pause over play.
- **The vCPU-blocked cause is gone.** The old reading had the vCPU off-CPU
  92 ms a frame. Now it is on-CPU 92-96% and never in its idle loop, and
  `Lw` is 0.0. So the `pfifo.lock` question has no time left to explain,
  and the held `--trace-offcpu` session of section 4 is not needed for MM3.
- **The bound is the guest's own work.** The renderer waits 26.0 ms of each
  56.7 ms frame for the guest, and the GPU is 23% busy. MM3 moves from row 2
  of section 3 to row 3 (vCPU on-CPU), with Alias and Arctic.
- **The on-CPU split is not in these lines.** The exec loop, TB lookup,
  guest code and helpers need cpu-clock samples: the on-CPU held session
  section 4 planned for Alias, run on MM3's drive as well (lane.local, by
  hand). Two things to look for in it, neither priced here: the 408 full
  TLB flushes a second and the refills after them, and the `[rr425pc]` rows,
  where the top pcs are guest code (`g:00167ffb`, `g:00312ffe`) and one
  exec-loop return at an `fldcw` (`e:0009b377:d96d0c`, 14,400 a second;
  logcat.txt:9233).
- **Second in line is the renderer's Fin.** 12.1 ms a frame goes to finishes:
  835 in 60 frames, 480 of them for surface downloads and 360 deferred
  completions (`hakuX-stall` `Finish:835(... sd480 ...)`, `cDef360`;
  logcat.txt:9190). It is Forza's shape (#479/#518). It does not bound the
  frame while the renderer idles 26 ms, and it will once the guest is
  faster.
- **Heat.** 49.2 C to 74.0 C by the mark and a pause at +574 s, under MAX
  with the vCPU at 92-96%.

## Do not repeat

- Do not read a benchmark soak for `hakuX-phase` or GPU rows. Only perflog
  builds log them, and none of these titles' benchmarks is one. `Ri` and
  `[tlb68]` are logged on every build: start from them.
- Do not quote a verdict median without its quartiles. title_verdict.py
  takes the element `fs[n//2]`, and on a bimodal run it falls between the
  modes (MechAssault 2: 23.89, between ~11 and 30).
- The status page's "soak" reading is 90-240 s after the first perf line,
  not gameplay. For BloodRayne it is the cutscenes before the mark (22.34 vs
  24.90 over the mark), for DOA3 menus (15.41; the review says gameplay was
  not reached). Read the verdict window instead.
- The #507 fps test flags MM3's mission load, and the frames show it. Look at
  the route frames at the fall before calling a fall a pause.
- `request.json`'s mtime in a result dir is the QUEUE time (it equals the
  id's epoch), not the claim. The first cut of `condread.py` used it and
  called Alias and MM3 cold; both were claimed 3-5 s after another soak
  ended. The claim is `route.txt`'s mtime (written at the claim), and the
  end is `DONE`'s. The reader prints the two runs before each claim.
- Do not park a route whose only good run booted at a different pace
  without reading when its first START lands against the title. Otogi's
  route was timed on a +12 s boot and failed on a +4 s one. Compare the
  first `hakuX-perf gfps=` line with the route's START lines first
  (`routecheck.py`).

- Do not take a `mark gameplay` frame in play as proof of the window after
  it. Otogi's re-pilot left play 105 s after the mark. Read the draws per
  frame and the phase row across the window (`timeline.py`), and compare
  them with the title's at the start of the same run.
- A route timed on a slow build meets a faster game on master. Its waits
  are wall time; the game's timers, races and enemies are not. Put a `shot`
  or two after the mark in any route parked for a build that may be faster.
- `--frames-every` is not the way to get those frames in an attribution
  soak: it costs frame rate (route.sh's header). A `shot` is one screencap.

## Log (PDT, 2026-09-28)

- 08:0x draft PR #556 opened.
- Indexed the results, traced each status reading to its result, wrote
  `condread.py`, and reproduced every verdict median exactly (after matching
  title_verdict's window filter and its `fs[n//2]` element).
- Found no perflog run for 15 of 16 titles. Read the always-on counters,
  the lever ancestry and the MM3 and Black frames.
- Corrected the claim time (route.txt, not request.json): Alias and MM3
  were warm starts, and PGR was cold.
- 08:1x posted the ranking and the profile list on #462
  (issuecomment-5872807130). preflight passed. No device run was queued and
  no hold was taken.

### Attempt 2 (phase 2b, branch lane/slowtier2-cold)

- Why attempt 1 did not carry on: it finished phase 2 and stopped. #556
  folded at 15:26Z. lane.local's delivery for phase 2b landed at 15:27Z,
  after that session had ended, and nothing was running to read it. This
  resume carries it.
- 08:3x parked the eight Thor requests (section 5), with `park.py`, and
  wrote the README. No hold was taken and nothing was queued.
- Do not repeat: `request.sh` has no simpleperf mode, so a profile that
  needs one cannot be parked as a request. Plan it as a held session from
  the start.

### Attempt 3 (the failed pilot, branch lane/slowtier2-routes)

- Why attempt 2 did not carry on: it finished phase 2b and stopped.
  #559 merged, and the next step was the pilot's result, which lay outside
  the session. The pilot landed at 10:01. At 10:12 hostops found its
  gameplay frame on the title and resumed this lane to fix the routes.
- 10:4x read the pilot's frames and timeline, checked all eight routes
  (section 6), wrote `routes/otogi.cold.route`, and parked the re-pilot
  `1-1790615781-lane.slowtier2-otogi2870269`. No hold was taken and nothing
  was queued. `pilots/lane.slowtier2.ok` is not written yet.

### Attempt 4 (the re-pilot's result, branch lane/slowtier2-repilot)

- Why attempt 3 did not carry on: it finished its step and stopped. #564
  merged at 17:35Z, and the next step was the re-pilot's result, which lay
  outside the session. hostops gave the re-pilot a cold slot in the evening:
  `0-0-s-1-1790615781-lane.slowtier2-otogi2870269` was claimed at 18:58 PDT
  and finished at 19:07 PDT. This resume reads it.
- 19:2x read the re-pilot (section 7): play reached, Otogi at its 30 cap on
  master, play lasting 105 s. Agreed with hostops' `pilots/lane.slowtier2.ok`.
  Added two frames after the mark to the six requests still parked
  (`addshots.py`), appended the reading to the parked README, and posted on
  #462 (issuecomment-5882425216). No hold was taken and nothing was queued.
- 19:3x run 2 (MM3) finished inside the session and is read (section 8).
- Waiting on runs 3-8, which hostops slots one at a time from cold starts:
  `1-1790609662-lane.slowtier2-black167924`,
  `1-1790609663-lane.slowtier2-burnout968727`,
  `1-1790609664-lane.slowtier2-alias942359`,
  `1-1790609665-lane.slowtier2-pgr365442`,
  `1-1790609666-lane.slowtier2-crash627374`,
  `1-1790609667-lane.slowtier2-bloodrayne201189`. Each lands in
  `dispatch/results/<id>/` with a `DONE`. Read each with `timeline.py`,
  then `playsplit.py` over the span the `play1` and `play2` frames and the
  draws show to be play.
