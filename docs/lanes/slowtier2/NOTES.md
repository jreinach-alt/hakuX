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
| Otogi | 12.62 | titleroutes-1129571, 9e7f8418dc, Thor, MAX | **clean (inferred)**: claimed 703 s after a 570 s run, no record; the fall 30 -> 11 is at 120 s, too early for #507 | 12.62 = 79.3 ms | **renderer, near saturated** | renderer idle 7.3 (9%), busy 74.9; vCPU on 46.7 (59%); backlog 1.4 MB (the pusher far ahead); vCPU TLB resets 2.7 | ro:292-305 |
| Burnout | 10.85 | titleroutes-1150288, 3540bf2a69, Thor, MAX | **clean (inferred)**: claimed 704 s after a 550 s run, no record; the fall 30 -> 10 is at 210 s, at the mark | 10.85 = 92.2 ms | renderer (idle 23%) | renderer busy 71.1; vCPU on 54.8 (59%); vCPU TLB resets 2.7; zero-filled audio 56% | ro:306-319 |
| Black | 7.45 | titleroutes-3358750, a593d8eb85, Thor, MAX | **clean (inferred)**: cold (idle 23 min). Frame `215235-f1.png`, 3.5 min in, shows the intro cutscene at FPS 4 before any pause could come. The 26 fps before the mark is a black "4 DAYS EARLIER" card (`215343-f2.png`); `215426-gameplay.png` shows FPS 7. A pause after 8 min is not excluded (no record) | 7.45 = 134 ms | guest (idle 42%), vCPU blocked | vCPU on 92.3 / **off 42**; renderer busy 78.6; **TLB resets on other threads 17.8 ms/frame** (#548's cost, 6x any other title) and 3.6 on the vCPU | ro:320-332 |
| Midtown Madness 3 | 3.13 | titleroutes-1032854, 6aaa8197c5, Thor, MAX | **unknown, leaning content**: claimed 5 s after a 410 s Alien Hominid run (warm), no record. The #507 test flags the fall at 210 s (51.9 -> 3.1), but it lands on the mission load, which the route frames show: `040703-a3.png` (menu) at FPS 59, `040838-b3.png` (the static mission briefing) at FPS 3, `041030-gameplay.png` (the drive) at FPS 3 | 3.13 = 320 ms | guest, **vCPU blocked** | vCPU on 228 (71%) / **off 92**; renderer idle 260 (81%); vCPU TLB resets 9.3. The verdict's ten 12-20 s "hangs" are its steady frame: 60 flips at 3.1 fps take 19 s, as with GTA in the first pass | ro:333-345 |
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
