# lane.fpsbelow1012: the below-bar titles on the Nova at master, and one fix that lifts several (#433, 0.5)

Brief: `/home/justin/hakux-work/briefs/fpsbelow1012.md`. Input: `belowbar1012.tsv` (lane.local, 10-11 23:1x),
43 titles copied on the Nova. Base: master @ 5326de78b2, merged to 00fde8afb3 (defaulton1011) on 10-12.

Device-run count (cap 30, A/B arms included): **12** run (the pilot: 2 read, 1 void before input; the A/B's six
arms on NGB, DOA3 and Buffy; the `[sdrange]` runs on MC3 and Forza; the depth pair's B), **1** running (the depth
pair's A), **3** queued (the L4a pair on MC3 and Forza's `[sdrfin]` run, section 13). 16 of 30. Ledger in section 4.

## 0c. Attempt 3, after Addendum 2 (10-12 05:57 PDT): the grants landed

Board db57d68da6 granted draw.c, vertex.c and renderer.h for L4a, and widened surface.c to L4c's split counter
(perf builds). Both are built at 67e3fcf745, the L4a prediction is registered, and the three runs that read them are
queued behind L1's depth pair (section 13).

## 0b. Attempt 3 (10-12 ~05:40 PDT): why attempt 2 did not finish

Attempt 2 read the pilot, judged NG Black, read MC3's `[sdrange]` run, and queued DOA3 B, Buffy B and Forza's
`[sdrange]` run. Its last commit was c788bb3c3c (04:33 PDT). Its session then ended with those three queued.
Attempt 1 had ended the same way: no `waiting:` line named the queued ids, so the lane came back as an idle resume
and not a resolved wait. All three runs landed by 05:32 (Addendum 1). Attempt 3 judges the A/B (9d), reads Forza
(section 11), writes the ranking (section 12) and queues the one pair the ranking still needs. It ends on a
`WAITING:` line that names the pair's ids and the grants.

## 0. Attempt 2 (10-12 ~02:30 PDT): why attempt 1 did not finish

Attempt 1 wrote the table, found L1 offline, got the surface.c grant, committed `HAKUX_ZETA_D24`, registered the
depth-pixels pair and queued the three-run pilot at sweep tier, then its session ended with the pilot still
queued behind lane.local's chain. It did not write a `waiting:` line naming the pilot ids, so it came back as an
idle resume (attempt 2), not as a resolved wait. Two things it left unresolved, found on resuming:

- The depth-pixels prediction never ran: the arms job refuses a pair with `a_ref == b_ref` ("nothing to compare",
  `arms/skipped/c543e6ac...`), so an env-only pair on one binary is queued by the lane itself, with `--expect`.
- The pilot ran overnight (00:45-02:30 PDT); its readings are section 8.

## 1. Which titles a run can reach at all (the profile gate, read before the table)

`tools/routecheck.py` asks `titlestate.admit()` (the call request.sh makes) about every route the dispatch
history ran on each title and that is still on disk, plus a no-route run. Output: `tools/routecheck.tsv`.

| admitted, and the route marks gameplay | admitted, `survey` only (never marks gameplay) | golden, but its own route is refused (R1: first-run route over a golden) | no golden: every route refused |
|---|---|---|---|
| Amped 2 (`amped2`, any), Midnight Club 3 (`midnight-club-3.returning`), Burnout Revenge (`burnout-revenge.returning`), Forza (`forza-soak1010`, `forza.drive`, `forza414`) | DOA3, Galleon, 007 AUF, Blinx, Blinx 2, Bloody Roar, Conker, Ninja Gaiden Black, SW Ep III | DOA3 `doa3`, Arctic Thunder, Galleon `galleon`, Ghoulies, Nightfire, BF2MC, DnD Heroes, NGB `bb-ngb` (and Amped 1, no route at all) | Area 51, Counter-Strike, DBZ Sagas, Fantastic 4, Demon Stone, MoH Frontline, Midnight Club II, Shaolin, MTV Music Gen 3, NBA Live 06/07/2005, NFS MW, NHL 2K3, NHL Hitz Pro, Panzer Elite, Pilot Down, Spider-Man 2, Clone Wars, Hulk UD, LOTR ROTK, Turok, Ty, Ultimate Spider-Man |

So 4 of 43 titles have a gameplay route this lane may run, and 9 more have the survey route (START/A x14, then a
blind play loop). The survey route reaches a playable scene on AUF and Blinx (other lanes used it as their benchmark
scene for weeks) and on Bloody Roar (titleroutes2 built its fight route from the survey's frames); on the rest it is
unproven. The fpstelemetry1008 generated routes (Pilot Down, Spider-Man 2, LOTR, Hulk, NHL 2K3, NGB) were deleted
after use, and those titles have no golden, so R2 refuses any first-run route on them now. **The largest measured
classes (guest vCPU: Pilot Down, Hulk, NFS MW, NHL 2K3, LOTR; renderer: Spider-Man 2, Midnight Club II; the NBA trio)
are "no route" in this lane.** Unlocking them is profile/pathing work (a profileconv1011-style re-head to `any` for
the eight R1 titles; a golden for the rest), not this lane's.

## 2. The offline table (written before the first run)

What each folded master switch acts on (from the fold commits and lane PRs):

- **SURFGPU** (surfgpudefault1009, on since 10-09): the `reuse`/`surfupd` display-surface rebind, done on the GPU.
  NBA Live 07 gfps 22 -> 47. On Forza the wait moved to `range` (5.8 -> 9.7 ms/flip) and a new `tobuf` (3.5).
- **fastpaths1010** (on since 10-11 09:13): `REPORT_ASYNC` (occlusion-report fence waits, reports.c), `TEXSCAN`
  (create_texture's range scan, **cube-map faces only**), `DRAWREC`, `UNI_BULK`/`UNI_UBERCACHE`/`UNI_FOGCACHE`
  (render-thread CPU per draw).
- **nfsdefault1011 + lockwake1011**: `POSTED_PUT` (the vCPU's DMA_PUT no longer waits on pfifo.lock),
  `LOCKFREE_WAKE`, Submit frame buffering 3. These act on the vCPU's *wait* for the PFIFO thread, which pmucounters
  measured as the growth in Amped 2's slow frames (about 11 ms more off-CPU, mostly DMA_PUT on pfifo.lock while PFIFO
  waited report fences). They do not change the JIT's code.
- **Render mode**: `kTitleRenderModes` puts AUF, DOA Ultimate and NFS MW in sysmem. `TU_AUTOTUNE_ALGO=profiled` is
  NOT the default (`kAutotuneProfiledDefault = false`; profileddefault1008: Fuzion Frenzy WINS 38.7 -> 58.0, Forza
  LOSES 28.9 -> 26.6). gpunonrender measured the GMEM replay class: DOA3 attract 31-34 -> 59 gfps in sysmem, NG Black
  32.5 -> 59, DOA Ultimate 20 -> 42; profiled chose sysmem on both DOA3 and NGB by itself.
- Not on master: `HAKUX_IBC` (opt-in, no fps gain with the idle halt off), defaulton1011 (`VTX_HAZARD`, `APU_PACE`,
  folding tonight).

Predicted share is fps_ok share at the title's bar, for the scene its last reading measured. "No route" rows are listed
and left (brief step 1).

| # | title (tid) | last reading: fps / share / mode / date (source) | last cause class (source) | master switch acting on it | predicted share at master | route here |
|---|---|---|---|---|---|---|
| 1 | Dead or Alive 3 (4D53002D) | 29.96 / 0.44 / unrec / 10-04 (retro-doa3); 0.81 on another fight (fpstelemetry1008) | GPU, GMEM replay: tail GPU triples, Xfr/Tot 0.48 (fpstelemetry1008 §7); GMEM 31-34 vs sysmem 59 gfps (gpunonrender) | none (bandwidth autotune, not in the sysmem table) | 0.45-0.8, unchanged | survey |
| 2 | Arctic Thunder (4D570002) | 30.2 / 0.64 / REST / 09-30 | none known; 1.00 on fpstelemetry1008's route (not reproduced) | n/a | >= 0.9 | no route (`arctic-thunder` R1) |
| 3 | Galleon (41540004) | 24.71 / 0.10 / MAX / 09-30 | none known | unknown | 0.1-0.3 | survey |
| 4 | Grabbed by the Ghoulies (4D530053) | 29.96 / 0.59 / MAX / 09-27 | none known | unknown | 0.6 | no route (`ghoulies` R1) |
| 5 | Midnight Club 3 (54540079) | 25.4 / 0.006 / MAX / 10-03 (fps20786) | none known (pathfind guessed "20-fps class, like Top Spin/CS", unconfirmed) | SURFGPU, TEXSCAN if it is the surface-download class | 0.1-0.5 | `midnight-club-3.returning` |
| 6 | 007: Nightfire (45410026) | 40.03 / 0.89 / unrec / 10-06 | render thread (vcpu60: 30.5 of a 33.8 ms frame) | DRAWREC, UNI_* | >= 0.9 | no route (`nightfire` R1) |
| 7 | Battlefield 2: MC (45410062) | 29.9 / 0.67 / REST / 10-01 | per-draw render CPU (perdraw1009's title) | UNI_BULK/UBERCACHE/FOGCACHE | 0.8-0.95 | no route (`bf2mc` R1) |
| 8 | Burnout Revenge (45410076) | 31.66 / 0.72 / REST / 10-01 | none known | fastpaths | >= 0.9 (lane.local reads 0.972 at REST; its MAX run is queued) | `burnout-revenge.returning`, left to lane.local's queued run |
| 9 | D&D Heroes (49470013) | 12.51 / 0.00 / REST / 10-06 | none known | unknown | 0.0 | no route (`dnd-heroes` R1) |
| 10 | 007: Agent Under Fire (4541000D) | 22.09 / 0.00 / REST / 09-30 (sustain507 survey) | GPU, GMEM replay (Xfr/Tot 0.51 class); in the sysmem table since flip474 (16 -> 24 gfps) | sysmem table (already in that reading), fastpaths | 0.0-0.2 | survey |
| 11 | Amped 2 (4D530041) | 28.44 / 0.44 / unrec / 10-04; 0.38 fresh (fpstelemetry1008) | guest vCPU, gidle 0.00 (fpstelemetry1008); slow slices are waits, not slower code (pmucounters) | POSTED_PUT, LOCKFREE_WAKE, REPORT_ASYNC act on the measured wait | 0.55-0.75 | `amped2` (any; gameplay at ~484 s, so 900 s) |
| 12 | Amped (4D530005) | 20.64 / 0.09 / unrec / 10-04 | none known | unknown | 0.1 | no route |
| 13 | Area 51 (4D570005) | 29.96 / 0.73 / unrec / 10-08 (pathfind) | median at the 30 cap; the share loss reads as loads/cutscenes in a pathfind hold | n/a | >= 0.9 in play | no route |
| 14 | Blinx 2 (4D530065) | 29.28 / 0.57 / MAX / 09-27 (survey) | none known (memfast: 58 full TLB flushes/s, fixed by W1, no fps change) | memfast W1 | 0.6 | survey |
| 15 | Blinx (4D530013) | 14.8 / 0.00 / unrec / 09-26 | none known (ZPASS reports, guarded from profiled, #527) | unknown | 0.0 | survey |
| 16 | Bloody Roar: Extreme (48550001) | 9.84 / 0.00 / MAX / 10-02 (fight route) | none known, the worst reading in the table | unknown | 0.0 | survey (its fight route is gone) |
| 17 | Conker (4D530051) | 15.84 / 0.16 / MAX / 10-03 (memfast, no gameplay route) | none known (memfast: 287 full TLB flushes/s, fixed) | memfast W1 | 0.2 | survey |
| 18 | Counter-Strike (4D530036) | 25.86 / 0.00 / MAX / 10-03 (fps20786) | surface download, `range` caller (fps20786) | TEXSCAN only if the faces are cube faces | 0.0-0.3 | no route |
| 19 | DBZ Sagas (4947007A) | 29.18 / 0.57 / unrec / 10-07 | median near the cap (pathfind hold) | n/a | >= 0.8 in play | no route |
| 20 | Fantastic 4 (4156001A) | 59.88 / 0.43 / unrec / 10-07 | route defect: cutscene-heavy (fpstelemetry1008 §10) | n/a | n/a | no route |
| 21 | Demon Stone (49470074) | 28.9 / 0.51 / unrec / 10-08 | median near the cap | n/a | >= 0.8 in play | no route |
| 22 | Forza Motorsport (4D53006E) | 29.04 / 0.45 / REST / 09-30 | surface download: `range` 9.7 + `tobuf` 3.5 ms/flip with SURFGPU on (forzasurf1010); GPU at 401 MHz in the slow half (vcpu60) | SURFGPU, REPORT_ASYNC; TEXSCAN only if cube | 0.5-0.7 | `forza-soak1010` |
| 23 | MoH Frontline (4541001A) | 59.88 / 0.86 / unrec / 10-07 | 60-fps median, dips | n/a | 0.9 | no route |
| 24 | Midnight Club II (54540008) | 23.13 / 0.00 / unrec / 10-05 | GPU 34.6 ms/frame over the ceiling, plus `range` 8.0 ms (surfdl1008) | TEXSCAN if those are cube faces; nothing for the GPU cost | 0.0-0.2 | no route |
| 25 | MK Shaolin Monks (4D570029) | 45.91 / 0.49 / unrec / 10-06 | none; 1.00 on fpstelemetry1008's route | n/a | >= 0.9 | no route |
| 26 | MTV Music Gen 3 (434D0029) | 29.97 / 0.88 / unrec / 10-07 | route defect (menu-sitting, fpstelemetry1008 §5) | n/a | n/a | no route |
| 27 | NBA Live 06 (4541007A) | 19.98 / 0.00 / unrec / 10-06 | 3-vblank pin; `reuse` surface-download finish-wait (surfgpu1009) | **SURFGPU** | >= 0.8 | no route |
| 28 | NBA Live 07 (454100A1) | 19.99 / 0.011 / unrec / 10-06 | same; surfgpu1009 measured 22 -> 47 gfps | **SURFGPU** | >= 0.9 | no route (`nbalive07` R2) |
| 29 | NBA Live 2005 (45410050) | 19.97 / 0.00 / unrec / 10-03 | one `reuse` finish per flip, Fin 13.1 ms (fpstelemetry1008 §4a) | **SURFGPU** | >= 0.8 | no route |
| 30 | NFS Most Wanted (4541007B) | 25.76 / 0.19 / unrec / 10-05 | guest vCPU + the PFIFO thread as critical path (nfs30plan1010) | POSTED_PUT, LOCKFREE_WAKE, fastpaths, sysmem table | 0.3-0.6 | no route (R2; lane.local's NFS chain owns it) |
| 31 | NHL 2K3 (53450017) | 35.03 / 0.69 / unrec / 10-05; 0.89 fresh | guest busy doubles + Xfr/Tot 0.64 + 3 downloads/flip | POSTED_PUT etc., SURFGPU | 0.85-0.95 | no route |
| 32 | NHL Hitz Pro (?) | 37.41 / 0.75 / unrec / 10-05 | none known | unknown | 0.8 | no route |
| 33 | Ninja Gaiden Black (5443000D) | 39.4 / 0.75 / MAX / 10-02; 0.83 fresh | GPU, GMEM replay: ph_GPU tracks rblk (fpstelemetry1008); GMEM 32.5 vs sysmem 59 (gpunonrender) | none (not in the sysmem table; needs the #527 ruling) | 0.75-0.85, unchanged | survey (`bb-ngb` R1) |
| 34 | Panzer Elite (4A570009) | 30.41 / 0.90 / unrec / 10-07 | at the bar already | n/a | 0.9 | no route |
| 35 | Pilot Down (4F580002) | 23.31 / 0.23 / unrec / 10-07; 0.66 fresh | guest vCPU, gbusy doubles at p10 | POSTED_PUT etc. | 0.65-0.8 | no route |
| 36 | Spider-Man 2 (4156002B) | 25.8 / 0.29 / unrec / 10-05; 0.86 fresh | renderer (Ri falls) + Xfr/Tot 0.39 + 4.5 downloads/flip | SURFGPU, fastpaths | >= 0.85 | no route |
| 37 | SW Clone Wars (4C410004) | 29.38 / 0.61 / unrec / 10-08 | median near the cap | n/a | >= 0.8 in play | no route |
| 38 | SW Ep III (4C410017) | 28.5 / 0.47 / REST / 10-06 | none known | unknown | 0.5 | survey (`star-wars-ep3` gone) |
| 39 | Hulk UD (56550039) | 29.25 / 0.64 / unrec / 10-05; 0.91 fresh | guest vCPU (gbusy +65% at p10) | POSTED_PUT etc. | >= 0.9 | no route |
| 40 | LOTR ROTK (4541003E) | 27.7 / 0.33 / unrec / 10-05; 0.93 fresh | guest vCPU (pathfind) + Xfr/Tot 0.49 | POSTED_PUT etc. | 0.5-0.9 (route-dependent) | no route |
| 41 | Turok Evolution (41430004) | 29.85 / 0.84 / unrec / 10-07 | median at the cap | n/a | 0.9 | no route |
| 42 | Ty 3 (41560055) | 47.81 / 0.79 / unrec / 10-07 | none known | unknown | 0.8 | no route |
| 43 | Ultimate Spider-Man (41560035) | 29.37 / 0.89 / unrec / 10-07 | at the bar already | n/a | 0.9 | no route |

Reading the table as classes, with the titles this lane can actually run:

| class | titles (Nova list) | runnable here |
|---|---|---|
| GPU, GMEM replay (Xfr/Tot ~0.4-0.6; sysmem measured 1.5-2x on matched scenes) | DOA3, NGB, AUF (already sysmem), LOTR, NHL 2K3, Spider-Man 2 (partial) | DOA3, NGB, AUF (survey) |
| guest vCPU / its wait on PFIFO | Amped 2, Pilot Down, Hulk, NFS MW, NHL 2K3, LOTR | Amped 2 |
| surface download not covered by SURFGPU/TEXSCAN (`range` on non-cube textures, `tobuf`) | Forza, MC II, Counter-Strike, Spider-Man 2, NHL 2K3 | Forza |
| `reuse` surface download (SURFGPU fixed) | NBA 05/06/07 | none |
| render-thread CPU (fastpaths fixed) | Nightfire, BF2MC | none |
| unknown | MC3, Galleon, Bloody Roar, Blinx, Blinx 2, Conker, SW Ep III, DnD, Amped 1, Ghoulies, Ty, Hitz | MC3, Galleon, Bloody Roar, Blinx, Blinx 2, Conker, SW Ep III |
| at the bar, or a route/scene artifact | Arctic Thunder, Shaolin, Panzer, USM, Turok, Area 51, DBZ, Demon Stone, Clone Wars, MoH, F4, MTV | none |

## 3. Telemetry plan (step 2)

Every request: `--device nova --priority sweep --perflog --env HAKUX_GPUXFR=1 --env HAKUX_FRAMETRACE=1
--no-expect "telemetry survey"`, at most 4 of mine queued. Order by what a run decides:

1. Midnight Club 3 (`midnight-club-3.returning`, 600 s: gameplay at ~158 s): the biggest unknown with a real route.
2. Amped 2 (`amped2`, 900 s: gameplay at ~484 s): the control for the largest class; did POSTED_PUT/REPORT_ASYNC
   remove the wait pmucounters measured?

These two are the pilot (16.5 + 11.5 min, under the 30 min gate). Then, after the pilot verdict:

3. Bloody Roar (survey, 480): 9.84 fps, no class known.
4. Forza (`forza-soak1010`, 480): what is left of the surface-download wait with TEXSCAN and REPORT_ASYNC on.
5. DOA3 (survey, 480), 6. NGB (survey, 480), 7. AUF (survey, 480): the GMEM-replay class at master.
8. Galleon, 9. Conker, 10. Blinx 2, 11. Blinx, 12. SW Ep III (survey, 480): unknown classes; the survey's reach is
   unproven on Galleon, Conker and SW Ep III, so their frames are read before their numbers.

Readers: `docs/lanes/near30/decompose.py` (guest/renderer split), `docs/lanes/belowbar1005/xfrsurvey.py` (Tot, Rnd,
Xfr), `docs/lanes/fps20786/sdsurvey.py` and `docs/lanes/surfdl1008/postmark_sdsurvey.py` (surface downloads).
perflog costs ~1.2 ms/frame of render thread (alwaystelemetry), so fps from these runs is pessimistic.

## 4. Device-run ledger

| # | request id | title | route | seconds | state | read |
|---|---|---|---|---|---|---|
| - | z-1791786704-fpsbelow1012-2329412 | Midnight Club 3 | midnight-club-3.returning | 600 | withdrawn before it started (ref 5326de78b2; defaulton1011 folded at 00fde8afb3 while it queued) | not counted |
| - | z-1791786704-fpsbelow1012-2329507 | Amped 2 | amped2 | 900 | withdrawn, same reason | not counted |
| - | z-1791787431-fpsbelow1012-2456548 | Midnight Club 3 | midnight-club-3.returning | 600 | withdrawn before it started: the pilot was re-cut so its first runs decide L1 (section 5) | not counted |
| - | z-1791787432-fpsbelow1012-2456706 | Amped 2 | amped2 | 900 | withdrawn, same reason (Amped 2 reads in/out 0.87, not the class; it waits for batch 2) | not counted |
| 1 | z-1791787896-fpsbelow1012-2551124 | Dead or Alive 3 | survey | 480 | VOID 10-12 00:46: not-foreground before the route's first input (`com.android.settings` held display 0; `am start` re-issued, then no focused window); 8 logcat lines | none: the harness's foreground guard, not the title |
| 2 | z-1791787896-fpsbelow1012-2551219 | Ninja Gaiden Black | survey | 480 | done 10-12 01:01, ref 00fde8afb3 | section 8: two-tile class at 240-510 s |
| 3 | z-1791787897-fpsbelow1012-2551411 | Midnight Club 3 | midnight-club-3.returning | 540 | done 10-12 02:18, ref 00fde8afb3, gameplay marked | section 8: share 0.006 -> 0.81; `range` downloads 14/frame |
| 4 | z-1791797921-fpsbelow1012-1777822 | Ninja Gaiden Black | survey | 480 | done 10-12 03:01, ref be0239bac8, **B** (`HAKUX_ZETA_D24=1`; init line reads 0x81) | section 9: NGB passes every leg |
| 5 | z-1791797927-fpsbelow1012-1778929 | Ninja Gaiden Black | survey | 480 | done 10-12 03:33, same ref, **A** (no switch) | section 9: class window 240-510 s |
| 6 | z-1791797928-fpsbelow1012-1779675 | Dead or Alive 3 | survey | 480 | done 10-12 04:12, same ref, **A** | section 9b: IN THE CLASS (240 s); fps_ok 0.70 |
| - | (refused at queue time) | ToeJam & Earl III | uberdefault569's `toejam-earl-3` | 540 | request.sh refused it: the route declares no `# state:` line, and the file is uberdefault569's, not this lane's to edit | not counted; Buffy takes its slot, as the prediction names |
| 7 | z-1791798044-fpsbelow1012-1807480 | Buffy the Vampire Slayer | survey | 480 | done 10-12 04:22, same ref, **A** | section 9c: IN THE CLASS (450 s); fps_ok 0.79; a 30-fps title |
| 8 | z-1791799077-fpsbelow1012-2104673 | Midnight Club 3 | midnight-club-3.returning | 540 | done 10-12 04:32, ref dbf9dd40cc, `--env HAKUX_RANGELOG=1` (+ the telemetry env), gameplay marked 04:25:44 | section 10a: **H1**, one surface, ex 0 |
| 9 | z-1791801220-fpsbelow1012-2906178 | Forza Motorsport | forza-soak1010 | 480 | done 10-12 04:40, ref dbf9dd40cc (apk 64dbb3082354), `--env HAKUX_RANGELOG=1` (+ the telemetry env) | section 11: not H1; fps_ok 0.51; `range` 16.6 ms/frame is batch completion of eviction downloads |
| 10 | z-1791803606-fpsbelow1012-3255578 | Dead or Alive 3 | survey | 480 | done 10-12 04:57, ref be0239bac8, **B** (`HAKUX_ZETA_D24=1`; init line 0x81) | section 9d: V M P pass, W fails (as 9b said); a different fight from A |
| 11 | z-1791804165-fpsbelow1012-3514899 | Buffy the Vampire Slayer | survey | 480 | done 10-12 05:32, ref be0239bac8 (apk 47e99f5db99c), **B** (`HAKUX_ZETA_D24=1`; 0x81) | section 9d: V M P pass, W fails at the 30 cap (as 9c said); fps_ok 0.79 -> 1.00 |
| 12 | z-1791809103-fpsbelow1012-286227 | pgraph: 10 depth suites | - | - | queued 10-12 05:45 PDT, ref c1112f2c1a, **B** (`HAKUX_ZETA_D24=1`), `--expect fpsbelow1012-zetad24-pixels.json` | section 7's cost, measured |
| 13 | z-1791809107-fpsbelow1012-286943 | pgraph: 10 depth suites | - | - | queued 10-12 05:45 PDT, same ref, **A** (no env), queued last | the same pair |

The depth-exactness pair (rows 12-13) is the one registered as `docs/testing/predictions/fpsbelow1012-zetad24-pixels.json`
(sha256 c543e6ac..., refs c1112f2c1a on both arms, B queued first), 10 depth suites, one run per arm. It was planned
after the pilot verdict and queued in attempt 3, because the ranking (section 12) puts L1 first and section 7 says the
switch should not reach the cross-title screen until this pair is read. It is not a retest: nothing has measured
the switch's pixels yet. The master commits since c1112f2c1a change no file under `hw/xbox/nv2a`
(`git diff --stat HEAD...origin/master -- hw/xbox/nv2a` is empty on 10-12), so the pair measures master's renderer
with and without the switch. The queue output is in `tools/queue-pixels.log`, which is untracked because *.log is
ignored.

The pilot is 3 x (seconds + 90 s) = 29.5 min, under the 30 min gate. DOA3 and NGB are the two titles whose GMEM
replay was measured before (section 5); at master they say whether the class is still there after fastpaths1010,
nfsdefault1011 and defaulton1011. MC3 is the biggest unknown with a gameplay route.

## 5. Why the GMEM-replay class replays: Z24S8 as D32_SFLOAT_S8_UINT (offline, before any run)

gpunonrender measured the class on matched scenes: "The GMEM pass's last tile (`in`, 13.5 ms) equals the whole
sysmem pass (13.5 ms). The pass has two bins, and each bin executes the whole draw stream" (its NOTES, DOA3 P1,
lines 1586-1596; NG Black P2 the same at 1696-1702). Sysmem took DOA3 from 34.0 to 59.0 gfps and NG Black from 32.5
to 59.0, but sysmem stalls Kabuki's fight and changes the ZPASS report (#527), so it went per title. Nobody asked
why a 720x480 pass needs two bins in 3 MiB of GMEM. The answer is the depth format.

**The mechanism**, read from the Turnip fork the app ships (`mesa-turnipfork/src/freedreno`):

1. hakuX maps Z24S8 to `VK_FORMAT_D32_SFLOAT_S8_UINT` when the device has it (vk/surface.c, since a33fa42bc3,
   09-10, #16). Every Nova logcat says so: `nv2a: Z24S8 host format 0x82, depth stored as float` (0x82 = 130 =
   D32_SFLOAT_S8_UINT; seen in every recent result, e.g. `1-1791785130-lane.local-2108844`).
2. In GMEM, Turnip keeps that format's stencil as a separate cpp-1 plane (tu_pass.cc, "take into account the
   separate stencil"), so a pixel of a colour + Z24S8 pass costs 4 + 4 + 1 bytes.
3. A cpp-1 allocation doubles `tile_align_w` when it is not a multiple of 64: 96 -> 192 on the A740
   (tu_pass.cc: "texture pitch must be aligned to 64 ... for cpp==1 attachment to work as input attachment").
   hakuX uses no input attachments.
4. Tile widths are walked in steps of `tile_align_w` (tu_util.cc). At 192 the only widths that cover 640 or 720 are
   768 (then 344064 px / 768 = 448 rows < 480) or 576 (two columns): **two tiles**, though 720x480 = 345600 px is
   97% of what the pass could hold.
5. `binning_useful = tiles > 2` (tu_util.cc). Two tiles get no HW binning, so each tile executes every draw.
   That is the replay gpunonrender measured, and it is why the replay costs about one whole pass.

`tools/tilesim.py` re-does steps 2-5 in Python (A740: 3 MiB GMEM, `tile_align` 96x32, gen2 CCU fractions):

| pass (colour cpp) | zeta | align_w | gmem px | tiles | HW binning | draws executed |
|---|---|---|---|---|---|---|
| 640x480 (4) | D32S8 (today) | 192 | 344064 | 2 | no | whole stream x2 |
| 640x480 (4) | D24S8 | 96 | 393216 | **1** | no | whole stream x1 |
| 720x480 (4) | D32S8 (today) | 192 | 344064 | 2 | no | whole stream x2 |
| 720x480 (4) | D24S8 | 96 | 393216 | **1** | no | whole stream x1 |
| 640 or 720x480 (2, R5G6B5) | D32S8 | 192 | 442368 | 1 | no | whole stream x1 |

The AVOID_CCU layout gives the same counts (D24S8 387072 px, still one tile). The census agrees on DOA3's scene
pass: ckb 1350 + zkb 2700 KiB, that is 720x480 at 4 bytes of colour and 8 of host zeta (draw.c `xfr_census_begin`
counts host bytes; in GMEM it is 4 + 1). The tile divisor is 1 unless `TU_AUTOTUNE_FLAGS` has PREEMPT_OPTIMIZE
(tu_autotune.cc `get_tile_size_divisor`), which the app does not set.

**So the class is most 32-bit-colour titles that render 640/720x480 in GMEM**, not a few heavy ones: the replay
costs every such title the per-draw work once more per scene pass. It only shows as frames where the GPU is the
wait, which is DOA3 (~700 draws/pass), NG Black (~90), Otogi and Black (gpunonrender line 484), and what is GMEM
among LOTR, NHL 2K3 and Spider-Man 2. AUF, DOA Ultimate and NFS MW are sysmem by `kTitleRenderModes` and do not
change; R5G6B5 titles are already one tile.

**Why D24S8, and not the alternatives:**

| option | what it does to a 720x480 32-bit pass | against it |
|---|---|---|
| **Z24S8 as D24_UNORM_S8_UINT** (`HAKUX_ZETA_D24`) | one tile, GMEM kept: no replay, no change to ZPASS or Kabuki's mode | the depth round trip of #16 for fixed Z24: on Adreno a D24 clear of 0x800007 reads back 0x800008 over the whole surface (2 of 18 z24 clears on 09-10); the float formats' fix, which removed #16's blanks, stays (section 7) |
| fork: no 64-alignment doubling for a separate stencil that is never an input attachment | 640x480 fits one tile; **720x480 still two** (345600 > 344064 px at align 96) | misses DOA3 (720x480); a fork change |
| fork: HW binning at 2 tiles | a binning pass plus each tile's visible draws | gmem474: forcebin never won on the Nova |
| sysmem per title (`kTitleRenderModes`) | no tiles | one-offs; Kabuki stalls; #527 ZPASS |

D24S8 is the maintained fallback, not new code: `zeta_stored_as_float=false` selects the 0xFFFFFF scale in
glsl/common.c (a uniform), the ULP nudge in glsl/psh.c (`float_depth_storage` is in the psh key, vk/shaders.c), the
readback in pgraph.c, and the compute pack/unpack in vk/surface-compute.c handles both formats. Before 09-10 it was
the first choice (a33fa42bc3^ tried D24 first, as upstream xemu does), so every Nova GMEM measurement since 09-10
(gmem474, gpunonrender, profileddefault1008) saw two tiles where the August builds saw one.

The switch (commit ede7c891c5, on 00fde8afb3): `HAKUX_ZETA_D24=1`, read once at renderer init,
takes D24_UNORM_S8_UINT first when the device has it; the init line becomes `nv2a: Z24S8 host format 0x81, depth
stored as unorm (HAKUX_ZETA_D24)`, which is what proves a B arm live. Off by default; nothing changes without the
env.

GRANTED: `hw/xbox/nv2a/pgraph/vk/surface.c`, by lane.local on origin/board 9dbc5b2242, default off. Its conditions:
(1) the A/B titles come from this lane's own telemetry at master 00fde8afb3 showing the signature, not from pre-fix
readings; (2) the prediction is registered before the first A/B run, with per-title figures and what refutes the
mechanism; (3) the depth-exactness cost is named here (section 7) before the switch goes near the cross-title
screen; (4) A/B arms count in the 30-run cap, all sweep tier. The switch is committed at ede7c891c5 (the draft
unchanged), with `nv2a_index.json` regenerated in c29c31ea5e from the fold-pins trees (tests 6743b6ab16,
104 suites, as on master).

Checked on the committed state: surface.c compiles with the NDK clang line from `compile_commands.json` (rc 0;
two warnings on lines the switch does not touch), `check_android_guards.py` is clean, `preflight.sh` passes.
Not built: a full APK on this host (the dispatcher builds the ref for its first run) and the desktop target.

### 5a. The class in runs already on disk (D32S8 throughout, read with `tools/zread.py`)

Every past Nova run with `HAKUX_GPUXFR=1` on disk, read the same way: the scene pass's census in/out (mean in-pass
span over mean outer span) and the perf lines' median gfps and G. All of them say `Z24S8 host format 0x82`.

| title | route | ref | gfps med | G med (ms) | in/out | reading |
|---|---|---|---|---|---|---|
| Dead or Alive 3 | bb-doa3 / doa3 | d946e1ba44 .. 4ea49d12e7 (4 runs) | 49-54 | 17.7-19.7 | 0.51-0.62 | two tiles |
| Ninja Gaiden Black | bb-ngb / ngb | d946e1ba44 .. 4ea49d12e7 (4 runs) | 42-59 | 17.0-22.9 | 0.54-0.57 | two tiles |
| NBA Live 06 / 07 | nbalive06/07 | 93fbc525fc, 1e5b1af818, 1b1fec978d | 22.5-26 (47-49 with SURFGPU) | 20.1-43.9 | 0.50-0.52 | two tiles |
| Buffy | buffy | 7960e78e20 | 29 | 34.1 | 0.50 | two tiles |
| LOTR: Return of the King | lotr-rotk | 4ea49d12e7 | 29 | 33.4 | 0.51 | two tiles |
| Fantastic 4 | fantastic4 | 37543ff004 | 59 | 16.9 | 0.52 | two tiles, GPU not the wait |
| MechAssault 2 | mechassault-2 | 7960e78e20 | 29 | 33.4 | 0.63 | mostly two tiles |
| ToeJam & Earl III | gnr-toejam | d946e1ba44, 5c35880d0a | 27 | 35.7-35.9 | 0.65-0.67 | mostly two tiles |
| Spider-Man 2 | spiderman2 | 4ea49d12e7 | 29 | 33.5 | 0.69 | mixed |
| DOA1 Ultimate, `TU_DEBUG=gmem` | survey | bf85412b88 | 33 | 29.8 | 0.48 | two tiles when forced to GMEM |
| DOA3 / NGB, `TU_DEBUG=sysmem` or autotune `prof` | bb-doa3, bb-ngb | bf85412b88 | 59 | 16.7-16.8 | 0.97-1.0 | sysmem: no tiles |
| Amped 2, NHL 2K3, NFS MW, Pilot Down, Hulk, Shaolin, Arctic Thunder | own routes | various | 29-59 | 16.7-34.5 | 0.78-0.99 | one tile or sysmem: not the class |

So the class is wider than the four titles gpunonrender named: NBA Live 06 and 07 (which SURFGPU took to 47-49 gfps),
Buffy, LOTR and MechAssault 2 are two-tile passes too. `G` is the guest's flip-to-flip interval (profile.c
`game_frame_ms`), so it is frame time, not GPU time; where a title already runs at its own period (Fantastic 4 at
59, Buffy and LOTR at 29) the replay costs GPU time that the frame rate does not show.

**Read it over the stretch where the class shows, not the whole run.** The census's `out` is the GPU span of the
render passes per command buffer, which is what the replay costs. Over whole runs DOA3 reads out 8.90 ms on GMEM
against 8.33 on sysmem (gpunonrender `-1511854` / `-1511368`, bf85412b88), because the menus are one-tile on
both. In 30 s buckets the fight is plain:

| DOA3, seconds after the first perf line | GMEM in / out (ms) | in/out | gfps | sysmem out (ms) | gfps |
|---|---|---|---|---|---|
| 0-60 (boot, menus) | 1.24 / 1.26, 0.76 / 0.79 | 0.97-0.99 | 37, 59 | 1.23, 0.69 | 39, 59 |
| 150-210 | 6.31 / 6.96, 6.31 / 6.76 | 0.91-0.93 | 37-39 | 10.88, 10.69 | 42-47 |
| 240-270 (fight) | 13.09 / 26.07 | 0.50 | 33 | 16.86 | 59 |
| 270-300 | 9.87 / 19.72 | 0.50 | 54 | 11.27 | 59 |
| 300-330 | 7.38 / 14.84 | 0.50 | 59 | 9.85 | 59 |

In the two-tile stretch, out is twice in (two tiles, each the whole draw stream) and 1.5-1.75x sysmem's whole
pass. A one-tile pass runs the draw stream once over the whole screen: no less than the last tile's `in` (the
same draws over half the screen) and about sysmem's whole pass (the same draws, plus tile loads and stores but
without sysmem's bandwidth). That puts B's out at 0.5-0.65x of A's in the two-tile stretch, which is what
`zread.py`'s P leg tests. So each title's A/B is judged over a window where its A arm reads in/out <= 0.6, taken from this lane's
master telemetry of that title.

## 6. Lever ranking (draft: titles x win x P; the telemetry in section 3 firms up the titles column)

Superseded by section 12, which is the ranking after the A/B and the two `[sdrange]` runs. The draft is kept as it
was written before any run.

| # | lever | titles it reaches | win where it acts | P | why that P |
|---|---|---|---|---|---|
| L1 | `HAKUX_ZETA_D24` (section 5) | every 32-bit 640/720x480 GMEM title; it shows in frames where the GPU is the wait. Two-tile on disk (5a): DOA3, NG Black, NBA Live 06/07, Buffy, LOTR, Fantastic 4, MechAssault 2, ToeJam, Spider-Man 2 (mixed); named by gpunonrender: Otogi, Black | up to sysmem's matched-scene gain without its costs: DOA3 34 -> ~59, NG Black 32.5 -> ~59; NBA Live 06/07 47-49 at G ~20 ms with SURFGPU, where the replay is the next cost | 0.6 | For: the mechanism is read from the driver source and agrees with four measured numbers (two bins; last tile ~ whole sysmem pass; 9 B/px; out = 2 x in in the fight, 5a). Against: a one-tile GMEM pass still loads and stores colour and depth, which sysmem does not; the autotune may then pick sysmem for some passes; and the D24 round trip is a unit off near z = 2^23 on Adreno (section 7), which a title that reads depth back may show |
| L2 | profiled autotune by default (`kAutotuneProfiledDefault`) | GMEM titles where the GPU is the wait | Fuzion 38.7 -> 58.0 | 0.45 | Forza loses 28.9 -> 26.6 with no named cause (profileddefault1008); lane.local's decision. If L1 holds, L2's gain shrinks: it was choosing sysmem to escape the replay |
| L3 | DOA3, NG Black to `sysmem` in `kTitleRenderModes` | one title each | DOA3 34 -> 59; NG Black 32.5 -> 59 | 0.85 / 0.75 | measured on matched scenes; one-offs, the owner's rule ranks them below a lever that reaches several |
| L4a | NOSCAN `range`: surface downloads from the vertex-RAM sync or a blit, no texture scan (section 10) | MC3, Forza runnable; Nightfire unroutable | MC3 up to 12.3 ms/frame of render wait at 0.08 under the bar; Forza 2.8-9.3 ms/frame | 0.45 x the fix's own P | the `[sdrange]` run (`-2104673`) says H1/H2/H3. Only H1 (false overlap from page rounding) is a cheap, safe fix; it needs draw.c and vertex.c granted |
| L4b | SCAN `range` and `tobuf` (TEXSCAN's caller on non-cube textures) | NFS MW, Spider-Man 2, MC II, Burnout, PGR; most unroutable | unknown at master | 0.2 | TEXSCAN already covers cube faces; nothing runnable here reads this as the top cost |
| L5 | guest vCPU / PFIFO | Amped 2 runnable; Pilot Down, Hulk, NFS MW, NHL 2K3, LOTR unroutable | small per prior lanes after POSTED_PUT | 0.2 here | vcpuplan/memfast/ibcache own it; Amped 2 pilot says what is left |

L1 goes first: it reaches the most titles, it keeps GMEM's semantics (no Kabuki stall, no ZPASS change), and its
mechanism is in hand before any device time. What would refute it is a B arm where the scene pass's census in/out
stays near 0.5, or gfps does not move on a title whose GPU is the wait.

## 7. What D24 costs in depth exactness (lane.local's condition 3; offline, before any run of the switch)

**Where it can show at all.** Only where a Z24S8 word is read back or compared at one unit. Z16 is D16_UNORM
either way; stencil is 8 bits either way (D24S8 packs it in the same texel; the compute pack/unpack handles both,
surface-compute.c). So every z16 row is a control: the switch moves only the Z24S8 map.

**What #16 fixed, and which half of it the switch undoes.** a33fa42bc3 (`docs/investigations/
depth-readback-scale.md`, scores in `docs/testing/run-2026-09-10-depth-scores.tsv`) did two separate things:

1. **Fixed Z24 (FZn) moved to D32_SFLOAT_S8_UINT with one 2^24 scale.** On D24 the four places keep their old
   pairing, which is what `zeta_stored_as_float=false` selects and what the switch brings back unchanged: the
   fragment shader divides by 2^24 and adds one ULP (psh.c `z24_open`/`z24_close`), the vertex clip range, the
   clear (pgraph.c) and the readback (surface-compute.c) use 0xFFFFFF. The commit says it in as many words: "D24
   stays as the fallback, still with the ULP nudge that the unorm scale needs, so nothing changes for a device
   without the float format." So for fixed Z24 the switch is the pre-#16 behaviour, not a bound on it.
2. **The float zeta formats (F24, F16) store their encoding.** Before, F24 fell through to `zvalue / f24_max`
   and every drawn pixel read back zero: those were the 10 Depth_buffer blanks and the 24 W_buffering blanks. That
   fix lives in the shader's F24/F16 cases and does not depend on the host format, so **the switch does not bring
   the blanks back.**

**What the D24 half costs: the unorm quantiser.** In the top octave (z >= 2^23) the float32 grid (2^-24) and the
unorm grid (1/(2^24-1)) are half a unit out of phase, and no float32 lands safer (the investigation's derivation:
the nearest float to Z decodes to Z + 1 - (Z+1)/2^24, which tends to Z + 0.5 as Z tends to 2^23). Correctly
rounded the round trip is exact; Adreno rounds the half up, so a buffer cleared to 0x800007 read back 0x800008 on
304,284 of 307,200 pixels. On 09-10 that was 2 of the 18 z24 fixed clears (16/18 exact before, 18/18 after).
Near 0xFFFFFF the phase error goes to zero, so a far-plane clear, which is what titles mostly clear to, is exact.

**Today's baseline on the Nova (D32S8)**, the rows the switch can move:

| suite / rows (run) | captures | differing px today | nonzero |
|---|---|---|---|
| Depth_buffer z24 FZn `_ZB` (drawrec1010 `-3709316`, b10dcdb737) | 18 | 43,690 (all off-by-one) | 16 |
| Depth_buffer z24 FZy `_ZB` | 18 | 12,816 | 16 |
| Depth_buffer z24 FZn colour | 18 | 437,740 (equal to z16 FZn colour: not depth-format) | 16 |
| Depth_buffer z24 FZy colour | 18 | 26,176 | 10 |
| Depth_buffer_fixed_function z24 FZn `_ZB` (surfgpu1009 `-2098499`, 1b1fec978d) | 10 | 99,114 | 8 |
| Depth_buffer_fixed_function z24 FZn colour | 10 | 93,086 | 8 |
| Depth_buffer_fixed_function z24 FZy `_ZB` / colour | 10 / 10 | 240 / 240 | 10 / 10 |
| Clear `C*_Depth_y_ZB` (depth clear read back) | 6 | 0 | 0 |
| Color_zeta_overlap `ZetaIntoColor`, `ColorIntoZeta_ZB`, `Swap_ZB` | 3 | 71,663, 10,766, 0 | 2 |
| controls: Depth_buffer z16 `_ZB` FZn / FZy | 18 / 18 | 0 / 1,436 | 0 / 12 |

Depth_buffer's z24 FZn `_ZB` rows grow with the depth cutoff (M055564 5 px, M40000b 227, M800007 654, Mc00003 1,221,
Mf55555 6,177, Mffffff 6,770), all off-by-one: that is the float32 interpolation a33fa42bc3 named as what still
differs, and it is the floor D24 starts from.

**Expected cost, stated before measuring** (corrected 10-12 after reading a33fa42bc3 and the investigation: an
earlier draft of this paragraph said the switch kept the one-scale fix, which is true only of the float formats):

- the z16 rows do not move (D16 on both arms, and F16 on a Z16 surface never asks the Z24S8 scale);
- **two Depth_buffer z24 FZn `_ZB` captures go off by one over nearly the whole surface**, the ones whose clear
  lands on the half as 0x800007 does: about 300,000 px each, so ~0.6M px on that row group against 43,690 today.
  This is the dominant term, and it is a return to the 09-10 "before" for those clears, not a new defect;
- the other z24 FZn `_ZB` rows move by off-by-one pixels where drawn depth sits near 2^23 (the shader's ULP nudge
  and the unorm rounding against the 0xFFFFFF readback), and the float32 interpolation error that remains today
  (`UNRESOLVED` in the investigation) stays on both arms;
- z24 FZy (F24) rows: the encoding is now quantised through unorm too, so a unit of F24 encoding can flip near
  2^23; small;
- a colour row moves only where a depth test compares two values a unit apart (a draw at exactly the cleared
  value); DBFF and W_buffering move the same way as Depth_buffer, on their fixed-Z24 rows;
- **no row goes blank**: the blanks were the float formats' fall-through, fixed independently of the host format.

So the size is of the order of 10^5 to 10^6 differing px on the z24 FZn rows, most of it in two whole-surface
clears, and not the pre-#16 11.7M (which included the blanks). That is a reading of the code and of the 09-10
measurement, not a measurement of the switch.

**What a title sees.** One unit in 2^24 of depth. A title that redraws geometry with depth EQUAL quantises both
passes the same way and is unaffected. A title that clears to a mid-range value and then tests a draw against it
with EQUAL or LEQUAL at that exact value could flip a pixel, which is the case the clear rows test; a far-plane
clear is exact. A title that reads its depth buffer back as a texture sees a unit near the middle of the range.
Every title the Nova ran before 09-10 ran on D24 (a33fa42bc3 changed the order); a33fa42bc3 cites test captures,
not a title.

**Measuring it exactly** is one pgraph env pair at the A/B ref on the depth suites (Depth buffer, Depth buffer fixed
function, Clear, Color zeta overlap, W buffering, ZPass pixel count, Stencil, Stencil func, Depth function, Depth
clamp): about a minute of device time each, judged by `ab_compare.py --a --b` (which treats an `--env` pair on one
binary as the design). It is planned after the pilot verdict and counted in the cap (section 4). Until it is read,
the cost above is a bound and a mechanism, and the switch should not reach the cross-title screen on speed alone.

## 8. Telemetry at master: the pilot (00fde8afb3, perflog + `HAKUX_GPUXFR=1` + `HAKUX_FRAMETRACE=1`)

Readers: `tools/zread.py --buckets` (census, gfps, G), `title_verdict.judge()` called read-only (no verdict.json
written), `near30/decompose.py`, `surfdl1008/postmark_sdsurvey.py`.

**Ninja Gaiden Black** (`-2551219`, survey route; the survey never marks gameplay, so the verdict reads the whole
run). fps_ok share at the 30-fps bar **0.913** (was 0.75 on 10-02), own target 60: **0.169**; window median 44.4.
The class is plain in 30-s buckets:

| s after first perf line | gfps med | G med (ms) | in/out | out (ms/cb) | draws/cb |
|---|---|---|---|---|---|
| 0-30, 150-240 (menus, attract) | 59 | 16.6-16.7 | 0.95-0.98 | 0.9-1.2 | 230-450 |
| 240-270 | 59 | 16.7 | 0.57 | 11.3 | 445 |
| 270-300 | 32 | 30.1 | 0.54 | 29.2 | 365 |
| 300-480 | 36-46 | 21.3-26.9 | 0.52-0.53 | 18.8-20.9 | 211-260 |

The scene pass is two-tile (in/out ~0.53) and its outer span (18.8-29 ms per command buffer) is longer than a
60-fps frame: the GPU is the wait, and the replay is half of it. No surface downloads after the start (sd/flip 0).
Over the class window zread.py reads gfps 42, G 24.1 ms, out 19.6 ms. **NG Black is the A/B's first title.**

**Midnight Club 3** (`-2551411`, `midnight-club-3.returning`, gameplay marked 02:21:24). fps_ok share **0.815**
(0.006 on 10-03 at fps20786), window median 29.4, min 17.7: fastpaths/SURFGPU took it from 25 fps to a 30-fps pin.
Not the GMEM class (in/out 0.92-0.95 in play, ~30 draws per command buffer, ~250 command buffers per 30 s).
decompose.py over the scored window:

| rows | fps | F (ms) | guest busy | guest idle (timer) | Ri | ph_Draw | ph_Fin | ph_Tot |
|---|---|---|---|---|---|---|---|---|
| all 191 | 29.3 | 34.1 | 15.6 | 18.8 (13.1) | 8.8 | 5.4 | 12.8 | 28.4 |
| below bar 31 | 27.7 | 36.1 | 16.2 | 20.4 (14.7) | 9.2 | 5.7 | 14.4 | 30.9 |
| below-bar p10 8 | 18.7 | 53.4 | 23.5 | 30.0 (23.2) | 9.1 | 12.8 | 15.4 | 40.1 |

and postmark_sdsurvey: **14.0 surface downloads per flip, all from the `range` caller, 14.1 finishes per frame,
11.9 ms per frame of render-thread wait**; `reuse` 0. So MC3 is a surface-download class that SURFGPU and TEXSCAN
did not reach. **Corrected 10-12 (section 10):** an earlier version of this paragraph said "`range` on non-cube
textures, the same caller as Forza, Midnight Club II and Counter-Strike". That is wrong. MC3's texture-scan
downloads read 0 (`scdl0`, `[tsc] dl0`), so its `range` comes from the vertex-RAM sync or a blit. Forza's
pre-SURFGPU runs share that signature; Midnight Club II's is the scan. The render thread spends 28.4 of 34.1 ms per frame in its phases, 12.8 of
them finishing for downloads; the guest paces itself on a timer at 30. MC3 is now 0.08 under the bar, with the
render thread the closest resource to the frame budget.

**Dead or Alive 3** (`-2551124`): VOID before any input (section 4). Re-run as the A/B's DOA3 A arm, which is its
telemetry at master.

What the pilot changes in the ranking (section 6): L1 is confirmed at master on NG Black, with no folded switch
having touched it. L4 (`range`) is no longer a single runnable title: MC3 and Forza are both runnable here, and MC3
now sits within 0.08 of the bar with `range` as its largest render-thread cost.

## 9. The A/B: `fpsbelow1012-zetad24.json` (registered 2026-10-12T09:38:07Z, sha256 ec352c20...)

One binary on both arms, be0239bac8 (master 00fde8afb3's emulator code plus the switch, off by default). A has no
switch; B adds `--env HAKUX_ZETA_D24=1`. Both arms run perflog with `HAKUX_GPUXFR=1` and `HAKUX_FRAMETRACE=1`, sweep
tier, one run each. The arms job skips a pair whose two refs are the same (`a_ref == b_ref`), so this lane queues the
arms itself with `--expect` naming the prediction.

**The window is fixed before B is read.** A survey route never marks gameplay, and "gameplay" in these titles is
whatever the attract or demo loop shows when the pass reaches the scene. So `zread.py` takes the window from the A arm
alone: the 30-s buckets where A reads census in/out <= 0.60 with >= 100 draws per command buffer, at least 60 s of
them. It reads B over the same seconds. An A arm under 60 s of such buckets reads NOT IN THE CLASS (exit 3), and that
title is not judged. On the pilot's NG Black run this picks 240-510 s (270 s), the stretch section 8 shows by hand.

**Order and substitutes.** NGB B, then NGB A, DOA3 A, ToeJam A. request.sh refused ToeJam's route (uberdefault569's
`toejam-earl-3`) because it declares no `# state:` line. The route starts a new story from the title screen, so it needs
no profile, but adding the header is uberdefault569's edit, not this lane's. ToeJam also read 98.8% at 30+ on its
confirm (`1790951866-titleroutes2-46925`), so it was the weakest of the three as a below-bar title. Buffy, the
substitute the prediction names, takes its slot (`-1807480`). DOA3 B and Buffy B are queued only after their A arms
read IN THE CLASS. The lane's last request is a no-switch run, so the Nova is not left with the switch set. (The
dispatcher also queues its own `dispatch.restore` run at master after an env arm: `1791799321-dispatch.restore--1777822`
followed NGB B.)

### 9a. NG Black: every leg passes (judged 10-12 03:34 PDT)

`zread.py z-1791797927-fpsbelow1012-1778929 z-1791797921-fpsbelow1012-1777822 --expect ... --key NGB`, exit 0.
The class window read off A is 240-510 s, 270 s, the same stretch the pilot showed.

| arm | zfmt | gfps median (share >= 55) | G median | in/out | outer span per cb | draws/cb |
|---|---|---|---|---|---|---|
| A `-1778929` | 0x82 | 40 (0.20) | 25.6 ms | 0.53 | 21.54 ms | 308 |
| B `-1777822` | 0x81 | 59 (0.68) | 16.9 ms | 0.99 | 12.34 ms | 325 |

V passes (draws within 6%). M passes: the pass is one tile. P passes: x0.57, inside section 5's 0.5-0.65. W passes:
G x0.66, gfps +19. The figures stated before the run were gfps >= 50 and outer span <= 13 ms; B read 59 and 12.34.
Hand-read, not judged (title_verdict, whole run, generic route): fps_ok 0.847 -> **0.960**, energy per frame
0.192 -> 0.164 J. Both arms' frames show Ryu's HUD at the same cliff walls, with no visible depth fault in B. The
switch takes NG Black over the 30-fps bar on this route, and to 59 gfps in the scene that was 40. Not a Playable
reading: the survey never marks gameplay, so lane.local would need a confirmation on a gameplay route.

### 9b. DOA3 A: in the class, and why its W leg cannot pass (read 10-12 04:14 PDT)

`zread.py -1779675 -1779675 --expect ... --key DOA3` (A against itself, to read the class rule before queueing B):
**240 s in the class** (buckets 60-120, 300-450, 480-510 s), so DOA3 counts toward the A/B and B is queued
(`z-1791803606-fpsbelow1012-3255578`). Whole run, title_verdict read-only: fps_ok share **0.70** (0.44 on 10-04),
window median 46.1, min 13.2. Not at the bar, so it is not an OUTBOX candidate.

| s after first perf line | gfps med | G med (ms) | in/out | out (ms/cb) | draws/cb |
|---|---|---|---|---|---|
| 60-120 | 59 | 16.7 | 0.47-0.57 | 8.3-23.2 | 176-197 |
| 120-240 (one-tile, 19 gfps at G 50 ms: not this class) | 19 | 50.0 | 0.89-0.95 | 12.8-14.6 | 328-365 |
| 300-330, 390-450 | 59 | 16.7 | 0.50-0.52 | 12.1-14.2 | 239-262 |
| 330-360 | 32 | 31.6 | 0.51 | 31.6 | 360 |
| 360-390 | 46 | 22.7 | 0.50 | 23.1 | 404 |
| 480-510 | 38 | 26.8 | 0.51 | 27.6 | 417 |

Over the class window zread reads gfps median 58 (share >= 55: 0.55), G 16.9 ms, in/out 0.51, out 15.98 ms. **The
registered W leg cannot pass on this title**: it asks B's median G <= 0.85 x 16.9 = 14.4 ms, or median gfps >= 66,
and both are past the 60-Hz flip cap. The class window is half buckets already at 59 (two-tile, but the GPU fits
in the frame) and half where the outer span is 23-32 ms and gfps 32-46. The lever acts on the second half, and the
median does not see it. This is a limit of the registered threshold, found before B ran. The prediction is not
re-registered: B runs as registered, and DOA3 will be reported as W FAIL with M and P read as the mechanism at
720x480. B's share >= 55 and its slow buckets (330-390, 480-510 s) will be hand-read beside it, not judged. The A/B's
win now needs Buffy to pass every leg, as well as NG Black.

What the scenes are (route-frames; the first perf line is 04:03:15). 120-240 s, the one-tile stretch at 19 gfps
and G 50 ms, is the fight's PAUSED menu: the survey's START/A presses opened it, and frame 040600 shows it with the
overlay at 14 fps. It is a 3-vblank period with a 13-15 ms outer span, so the GPU is not the wait there. It is outside
the class and outside this lever, and it is not gameplay. From 233 s on, the survey's play loop sits on the title
screen and its attract demo (frame 040916, "PRESS START BUTTON", overlay 21 fps). So the class window is a fight
before the pause (60-120 s) and the attract stretch. B on the same route reaches the same scenes.

### 9c. Buffy A: in the class for the whole run, and a 30-fps title (read 10-12 04:23 PDT)

`zread.py -1807480 -1807480 --expect ... --key Buffy`: **450 s in the class** (every bucket from 60 s), in/out 0.49,
outer span 21.3 ms per command buffer at ~1000 draws, gfps median 29, G 33.4 ms. Whole run (title_verdict read-only):
fps_ok **0.79**, window median 29.9, min 24.5, 0.278 J/frame. Frames: real play from the pause menu on (Spanish
Mission, Canyon, frame 041937), overlay 29.

Buffy paces itself at 30: G is 33.4 ms in every bucket, including 60-90 s where the outer span is 7 ms. So the
registered W leg (median G <= 28.4 ms, or median gfps >= 37) can only pass if the title is not capped, which
this reading says it is. The buckets where Buffy drops (90-120, 210-270 s: G 37-38 ms, outer span 28-30 ms) are the
frames this lever reaches. Buffy B is queued as registered (`z-1791804165-fpsbelow1012-3514899`).

**What this does to the A/B, said before either B arm reads.** Two of the three counted titles (DOA3, Buffy) sit
at a frame cap for most of their class window, and the W leg is a median against that cap. Both will likely read
W FAIL even if M and P pass and the slow buckets lift. If so, the registered judgement (2 of 3 pass every leg) is a
**loss**, and it is reported as one. What the B arms can still show, hand-read beside the legs and not judged:
M and P (the mechanism on a 720x480 and a ~1000-draw pass), the slow buckets, fps_ok share, and J/frame. The
prediction is not re-registered on the same arms. The W leg should have been a share, not a median (fps_ok share,
or share of frames at the title's own cap). A title that is below the bar only in its slow buckets needs a
share-based leg, registered before a new pair.

### 9d. The A/B judged: a LOSS by its own rule, and the mechanism holds on all three titles (10-12 05:50 PDT)

`zread.py <A> <B> --expect docs/testing/predictions/fpsbelow1012-zetad24.json --key <title>`, one run per title,
full output in `tools/ab-zread.out`. Each class window is read off its A arm alone (section 9):

| title | A / B | window | V | M: in/out A -> B | P: outer span per cb A -> B | W: G median, gfps median A -> B | legs |
|---|---|---|---|---|---|---|---|
| Ninja Gaiden Black | `-1778929` / `-1777822` | 270 s | PASS | 0.53 -> 0.99 | 21.54 -> 12.34 ms (x0.57) | 25.6 -> 16.9 ms (x0.66), 40 -> 59 | **every leg passes** |
| Dead or Alive 3 | `-1779675` / `-3255578` | 240 s | PASS | 0.51 -> 0.97 | 15.98 -> 10.16 ms (x0.64) | 16.9 -> 16.7 ms (x0.99), 58 -> 59 | W FAIL |
| Buffy | `-1807480` / `-3514899` | 450 s | PASS | 0.49 -> 1.00 | 21.29 -> 12.58 ms (x0.59) | 33.4 -> 33.4 ms (x1.00), 29 -> 29 | W FAIL |

**The registered verdict is a LOSS.** The prediction's rule is a win when at least two of the three counted titles
pass every leg. One does (NG Black), so the switch did not win its A/B, and it is reported that way. The prediction
is not re-registered on these arms.

Both failures are the W leg, and both were written down before their B arms ran (9b, 9c). W tests a median of G
against A's, and on DOA3 and Buffy that median already sits at a frame cap: the 60-Hz flip for DOA3, the title's own
30 for Buffy.

**The three legs that read the mechanism pass on every title.** With the switch the scene pass is one tile on a
640x480 pass (NG Black), a 720x480 pass (DOA3) and a ~1000-draw pass (Buffy), and the GPU's outer span per command
buffer falls to x0.57-0.64. That is inside the 0.5-0.65 that section 5 derived before any run. The outcome that
would have refuted it, B's in/out staying near 0.5 or the outer span not falling, did not happen on any title.

**Hand-read beside the legs, not judged.** `title_verdict.judge()` was called read-only over the whole run, since a
survey route never marks gameplay; output in `tools/ab-handread.out`. The B buckets are in `tools/ab-bbuckets.out`.

| title (bar) | fps_ok A -> B | window median | window min | J/frame | late/100 | like for like? |
|---|---|---|---|---|---|---|
| NG Black (30) | 0.847 -> **0.960** | 43.7 -> 58.6 | 10.4 -> 13.4 | 0.192 -> 0.164 | 33.6 -> 7.9 | yes: both arms show Ryu at the same cliff walls |
| Buffy (30) | 0.793 -> **1.000** | 29.94 -> 29.97 | 24.5 -> 29.2 | 0.278 -> 0.261 | 11.5 -> 4.0 | yes: the same level. A's slow buckets (90-120 and 210-270 s, G 37-38 ms, outer span 28-30 ms) read G 33.2-33.4 in B, and every B bucket is 33.2-33.6 |
| DOA3 (60) | 0.698 -> 0.961 | 46.1 -> 59.9 | 13.2 -> 21.1 | 0.210 -> 0.170 | 12.0 -> 1.2 | **no**. The arcade draws the opponent: A fought Bayman in the dojo, B fought Hitomi on the cliff (frames 040600 and 045121, both on the PAUSED menu). A's paused stretch was one tile at 19 gfps, outside the class; B's was 45-59 |

DOA3's share gain is a different fight, so DOA3 contributes M and P and nothing more.

NG Black and Buffy are like for like. Buffy is the case the W median could not see: every 30-s bucket at the
30 cap, and the drops gone. NG Black rises to 59 gfps in its scene. Energy per frame falls on all three
(x0.81-0.94), which is what removing one replay of the draw stream should do. These are readings, not a judged
result.

**What this leaves for the switch.**
- The lane's case for it rests on M and P (3 of 3) and on two like-for-like shares.
- The leg that failed was the wrong instrument for capped titles. A later prediction on this switch should judge a
  share, registered before its pair: fps_ok share at the title's bar, or the share of class-window buckets at the
  title's own cap. That pair is lane.local's cross-title screen, not this lane's.
- The depth-pixels pair (section 4, rows 12-13) is read first.

**Candidates for lane.local, with `HAKUX_ZETA_D24=1`.**
- Buffy 1.000, NG Black 0.960, DOA3 0.961 (confounded).
- All three are on the survey route, which never marks gameplay, so each needs a gameplay-route confirmation with
  the switch.

## 10. MC3's `range` is not the texture scan: the vertex-RAM sync or a blit (offline, 10-12 ~03:00 PDT)

**Correction to section 8**, which called MC3's downloads "`range` on non-cube textures, the same caller as Forza".
The census says otherwise: on the pilot run (`-2551411`) hakuX-stall's `txr[... scdl0]` and the frametrace's
`[tsc] dl0` read zero texture-scan downloads in every window, while `[sdcall] range=` reads 927 per 60 frames. So
these downloads come from one of the function's other callers, `pgraph_vk_download_surfaces_in_range_if_dirty()`
(surface.c:922): the vertex-RAM sync (vertex.c:173, the first statement of `pgraph_vk_update_vertex_ram_buffer`, called
from draw.c's `sync_vertex_ram_buffer`), or blit.c's image blit (558, 560) and solid line (900). The census cannot split
those: `dif blt` counts only blits whose source starts at a surface base.

**Which runs on disk carry the same signature** (`tools/vtxrange.py`, `tools/vtxrange.out`: medians over the busy
half of each run's windows, per 60 frames; NOSCAN = `range` downloads with scan downloads under 10% of them):

| title | runs | range dl | range fin | wait ms | scan dl | reading |
|---|---|---|---|---|---|---|
| Midnight Club 3, 10-03 (fps20786) | `-2878057` | 60 | 60 | 430 | 0 | one download per frame, 7.2 ms each |
| Midnight Club 3, master (this lane) | `-2551411` | 927 | 927 | 736 | 0 | 15.5 per frame, each its own finish, 0.79 ms each, 12.3 ms/frame |
| Forza (forzadecay414, gpunonrender, profileddefault1008, ibcache) | 7 | 60-78 | 60 | 166-555 | 0-6 | one per frame, 2.8-9.3 ms/frame |
| Nightfire (memfast) | 5 | 556-699 | 60 | 95-488 | 0 | ~10 surfaces per call, one call per frame |

The SCAN rows (scan dl at least half of `range`) are NFS MW, Spider-Man 2, Midnight Club II, Burnout Revenge, PGR
and the early Forza runs (forza414): TEXSCAN's caller, not this one.

**Forza with SURFGPU on**, as master runs it since fastpaths: its forzasurf1010 B arms (`-1663501`, `-2254415`) read
`range` 429-430 downloads per 60 frames, but only 93-94 finishes, and 713-753 ms of wait (11.9-12.6 ms/frame).
Scan downloads are 147-164 of those, so ~280 per 60 frames come from another caller. The A arms of the same pairs
read 68-73 downloads and 4.5-5.4 ms/frame. SURFGPU roughly sextupled Forza's `range` downloads, and two-thirds of
the added ones are not the scan. That makes Forza at master likely the second title of the NOSCAN class, at about
MC3's cost. Forza's master telemetry (step 2) will say so directly.

**What changed for MC3 between 10-03 and master.** The count went from 1 per frame to 15.5, and total wait from
7.2 to 12.3 ms/frame. Already ruled out by reading the code: SURFGPU's reuse path (`reuse` 0), HAKUX_VTX_HAZARD (it
narrows the hazard test, not the sync) and #262's `vertex_range_gpu_stale` (74ac01608d, in both builds). What did
change is the number of vertex syncs that pass `has_dirty_vertex_pages`. With DRAWREC VTX on (fastpaths, 10-11), a
sync passes when an owed page needs it re-copied: `[drawrec]` reads redo 8347 and dirty 2501 per 60 frames, against
5334 dirty syncs on 10-03. That is about 2x, not the 15x of the downloads.

**Correction to my own first reading.** `[rdc] vtx=` (1067 per 60 frames at master) is not a sync count. It counts
DIRECT TLB walks from `physical_memory_dirty_bits_cleared`: one per dirty sync without DRAWREC VTX, one per owed run
in `drawrec_vtx_walk` with it (1045 runs in the same window). That it lands near the 927 range downloads is a
coincidence. vtxrange.py's vtx column is labelled as walks.

**Where the vertex sync can download a surface the draw never reads.** The early exit and the loop test different
ranges:
- `has_dirty_vertex_pages` (draw.c ~8598) tests DRAWREC redo, `vertex_range_gpu_stale` and the CPU dirty bits on
  the draw's ranges.
- `sync_vertex_ram_buffer` (draw.c 9540) then rounds each range out to whole pages (9586-9599) and merges ranges
  that overlap or abut (9605-9620).
- The loop tests `gpu_stale || cpu_dirty || redo` on the ROUNDED, MERGED range (9651-9667). A dirty range calls
  `pgraph_vk_update_vertex_ram_buffer`, which first downloads every draw_dirty surface overlapping that whole range
  (vertex.c:173).
- So a surface that shares a page with a vertex buffer, but none of its bytes, is downloaded whenever anything
  else in the merged range is CPU-dirty or owed. That is every guest write to the vertex buffer, and every owed
  page DRAWREC re-arms.
- The generation is then recorded (9682), so the same surface is not stale again until the GPU writes it again: once
  per render pass, which is the "each with its own finish" shape.

**Three hypotheses, and what the instrument shows for each.** `HAKUX_RANGELOG=1` (surface.c, perf builds,
committed dbf9dd40cc, off by default) prints an `[sdrange]` line every perflog period: per surface downloaded, its
dims, pitch, size, colour or zeta, whether it is bound, the caller (`by=vtx`, or the return offset into the range
function's caller), `n`, and two counts. `ex` is how many of those downloads overlap the draw's EXACT vertex byte
ranges (`vtxhz_cur`, HAKUX_VTX_HAZARD's list). `edge` is how many lie only in the first or last page of the
requested range.

| outcome | hypothesis | fix | where |
|---|---|---|---|
| `by=vtx`, `ex` << `n`, `edge` ~ `n - ex` | H1: false overlap from page rounding or merging | download and test gpu_stale only over the exact ranges; copy the rounded pages as now | draw.c, vertex.c (not granted) |
| `by=vtx`, `ex` ~ `n` | H2: the draw really reads bytes a surface wrote (render to vertex buffer), or the surface's recorded size overstates what it covers (dims tell which) | a GPU-side surface-to-vertex-buffer copy, no CPU round trip; or the size fix | draw.c, vertex.c, surface.c |
| `by=<offset>` (not vtx) | H3: blits or lines | per call site | blit.c (not granted) |

**A hint already on disk.** In MC3's play window (`-2551411`, `[surf92]` `held=`, after 02:21:24), 6 of the 9
non-zero surfaces it binds start mid-page: 0x026bdc00, 0x02fe5980, 0x02e16e00, 0x02dd6d80, 0x026fdc80 and
0x02f32780. The main colour and depth targets are page-aligned (0x03cb0000, 0x03b84000, 0x03a58000). A surface that
starts mid-page shares its first page with whatever the game allocated just before it. If that is a dynamic vertex
buffer, every write to the buffer rounds into the surface.

P(H1) 0.5: the 10-03 to master jump tracks the extra syncs, which only matters if the downloads are not tied to the
bytes, and the mid-page surfaces give the rounding something to catch. H2 0.3, H3 0.15, H4 0.05. The instrument run is `z-1791799077-fpsbelow1012-2104673` (MC3, ref dbf9dd40cc,
`--env HAKUX_RANGELOG=1`, sweep).

**What the lever would reach, if H1.**
- MC3: up to 12.3 ms/frame of render-thread wait, at 0.08 under the bar, with the render thread its closest resource.
- Forza: one per frame, 2.8-9.3 ms/frame.
- Nightfire: one call per frame of ~10 surfaces; it has no route here.

That is a multi-title lever behind L1. Section 6's L4 row is split on this reading.

**A fourth outcome, from the same line.** `pgraph_vk_update_vertex_ram_buffer` is also called over the whole of
VRAM, by the render thread's RCMD_FLUSH and pending-flush paths (render_thread.c 279, 322). A download from there
also reads `by=vtx`, but `last=0+<VRAM size>` and `edge` 0. That would be H4, a PGRAPH flush per download, a
different fix again.

**The H1 fix, drafted and not applied** (`drafts/vtxexact.diff`; it compiles clean against the desktop build's
flags). It adds `HAKUX_VTX_EXACT=1`, off by default.
- draw.c: `sync_vertex_ram_buffer` keeps the draw's exact ranges before rounding. For each merged range it tests
  gpu_stale, downloads and records generations only over the parts inside them. The copy still covers the rounded
  pages, and the CPU dirty bits are still cleared there.
- vertex.c: `pgraph_vk_update_vertex_ram_buffer` skips its own download when the sync has done it
  (`r->vtx_exact_downloaded`, one bool added in renderer.h).
- Why it is safe: a skipped surface's bytes go into the buffer stale, but this draw does not read them. They also
  stay unrecorded, so the first draw that does read them sees `vtx_surface_stale` (draw_dirty, or a generation
  never recorded) over its own exact range, and re-fetches.
- Files it needs granted: hw/xbox/nv2a/pgraph/vk/draw.c, vertex.c, renderer.h. It is requested only once the
  `[sdrange]` run reads H1.

### 10a. MC3's `[sdrange]` run reads H1: one render target, caught by the page rounding (read 10-12 04:33 PDT)

`tools/sdrange.py z-1791799077-fpsbelow1012-2104673 --after 04:25:44` (the gameplay mark), 142 periods, 8520 frames,
`hz=1` throughout (HAKUX_VTX_HAZARD on, its default, so `ex` is measured):

| per 60 frames | value |
|---|---|
| range-function calls from the vertex sync / from other callers | 24,676 / 25,463 |
| downloads, by=vtx | **973** |
| of them `ex` (the draw's exact vertex ranges overlap the surface) | **0** |
| of them `edge` (overlap inside the requested range's first or last page) | **973** |
| downloads by any other caller; shelved; invalidated; slot overflow | 0; 0; 0; 0 |

Every download is the same surface: **0x02fe5980, 256x256 swizzled colour, pitch 1024, 262,144 bytes, bound** (the
current colour target when the download is asked). It starts mid-page, one of the six section 10 listed. The
requested range is `0x2fe4000+0x2000` in every period: the vertex sync's two pages, rounded and merged. The overlap
is the surface's first 0x680 bytes, the tail of page 0x2fe5000. The game keeps a dynamic vertex buffer in
0x2fe4000-0x2fe597f and renders to a 256x256 target that starts right after it. Every vertex sync after the target
was drawn to rounds into that page and downloads the target, with a finish, mid-pass. No draw reads those 0x680
bytes as vertices (`ex` 0 in 8520 frames). The whole run reads the same (648 per 60 frames over 13,140 frames,
ex 0, edge 648). **H1 holds on MC3**, and the drafted `HAKUX_VTX_EXACT` removes exactly this download.

**This run's frame rate is not a baseline.** fps_ok **0.0**, window median 23.0, against the pilot's 0.815 and 29.4 on
the same route and the same scene at the mark (frames 022124 and 042543 match: the same street, FPS 18-19 at the
mark). decompose.py: the render thread's phases rose together (ph_Draw 5.4 -> 8.8, ph_GPU 6.8 -> 9.9, ph_Fin 12.8 ->
17.0 ms per frame), and so did BE (453 -> 682). That is a heavier view, not the instrument. RANGELOG adds a branch per
range call and a 12-slot scan per download, ~16 a frame. The route's play is blind throttle with no steering
(`axis RT max` 2.5 s, release 1 s, forever), so where the car ends up after the mark differs run to run, and with it
the scene. **So MC3's fps varies 23-29 between runs at one ref.** An A/B on it needs legs that do not ride on the
scene: `range` downloads and finishes per 60 frames, and ph_Fin per frame. fps_ok is hand-read beside them, not
judged.

## 11. Forza at master: not H1. Its `range` wait is batch completion of downloads the lookups did not record (10-12 05:55 PDT)

Run `z-1791801220-fpsbelow1012-2906178`: `forza-soak1010`, ref dbf9dd40cc, 480 s, perflog with `HAKUX_GPUXFR=1`,
`HAKUX_FRAMETRACE=1` and `HAKUX_RANGELOG=1`, gameplay marked 04:33:55. This is Forza's step-2 telemetry at master.
title_verdict (read-only): fps_ok **0.506** (0.45 on 09-30), window median 29.14, min 18.9, late/100 23.6, worst
stall 1.85 s, 0.304 J/frame. It is 0.39 under the bar.

**The `[sdrange]` reading** (`tools/sdrange.py`, in `tools/rangefin.out`), over 205 periods and 12,300 frames. Per 60
frames:
- range-function calls: 209 from the vertex sync, 38,722 from other callers;
- downloads the lookups recorded on live surfaces: 0 (`by=vtx` 0, `by=oth` 0);
- shelved: 0;
- invalidated-surface downloads: 53.

The tool's last line says "reading: H1", but that comes from three surfaces seen about four times in the whole run
(each 0.0 per 60 frames), and it is not reported as H1. The vertex sync downloads nothing on Forza, so
`HAKUX_VTX_EXACT` does nothing for it.

**The `range` line itself**, read with `tools/rangefin.py`. Each value is the median over the busy half of a run's
periods, per 60 frames. The full survey is in `tools/rangefin-all.out`.

| run | SURFGPU | range fin | range dl | dl/fin | wait ms | scan dl | su_deferred |
|---|---|---|---|---|---|---|---|
| profileddefault1008 `-4023363` (10-08) | off | 60 | 60 | 1.0 | 293 | 0 | 13,214 |
| forzasurf1010 A `-1663010`, `-2253823` (10-10) | off | 60 | 61-62 | 1.0 | 385-397 | 3 | ~13,500 |
| forzasurf1010 B `-1663501`, `-2254415` (10-10) | on | 93 | 427-428 | 4.6 | 718-788 | 118-123 | ~42,500 |
| **master, `-2906178`** | on (default) | **114** | **785** | **6.9** | **995 (16.6 ms/frame)** | 46 | 41,528 |
| Midnight Club 3 at master `-2551411`, for contrast | on | 927 | 927 | 1.0 | 745 | 0 | 26,624 |

**The mechanism.** At master the range lookups complete 785 downloads per 60 frames in 114 finishes. They record
no more than about 100 of those themselves: the 53 invalidated surfaces and the 46 the texture scan counts. So at
least ~690 were recorded somewhere else.

The recorder is the eviction path. Since forza414 (94f002d309), `pgraph_vk_surface_update` leaves an evicted
binding's download pending until the next finish. `su_deferred` counts about 41,500 updates per 60 frames that did
so, three times what it counted before SURFGPU. A range lookup then completes the whole pending batch
(`download_surface_complete_deferred(d, SDC_RANGE)`, surface.c:995-1003) on either of two conditions:

1. `found_overlap && r->num_deferred_downloads > 0`. The looked-up range overlaps any surface on the live list, or
   a dirty one on the shelved or invalidated list, whether or not it is draw_dirty. This rule predates forza414
   (59729d180a): then, the only pending downloads were the ones the lookup had just recorded. Since forza414 it
   also completes the evictions' batch whenever a texture or vertex range touches a *clean* live surface.
2. `deferred_downloads_overlap_range`. The range overlaps a pending download's destination, so the reader really
   needs those bytes.

The instrument cannot tell which condition fires, and that split decides the lever.

**If (1) dominates**, a precise rule removes those finishes without changing what any reader sees: complete only when
this lookup recorded a download, or when the range overlaps a pending destination. This is L4c,
`HAKUX_RANGE_EXACT`.

**If (2) dominates**, the readers do read the evicted bytes. Forza's race evicts its zeta binding twice a frame
between 640x480 and 1280x480 at one address (forza414 NOTES 29). The fix would then be a SURFSPLICE-like GPU path for
the reader, a larger change.

**The bound, even if (1) is all of it.** The 53 lookups per 60 frames that record an invalidated surface's download
must finish, and each completes the batch. So finishes fall from 114 to no fewer than ~53 per 60 frames, which is at
most about half of the 16.6 ms/frame. Forza has other costs:
- the GPU clock in the slow half (vcpu60);
- a 1.85 s worst stall;
- `tobuf` and `prerec` waits.

**The cheap step that decides.** A counter in the range function: per 60 frames, which condition completed the
batch, and how many of the completed downloads the lookup recorded itself. It is surface.c instrumentation beyond
the `HAKUX_ZETA_D24` grant, so it is requested in section 12, not written. One Forza run reads it.

**No other title on disk shows this.** The only other runs whose range batches complete more than 1.5 downloads per
finish are Spider-Man 2 (2.0, all of them scan downloads), one pre-SURFGPU Forza run (2.0, 90 of 120 scan) and NFS
MW. NFS MW reads 240 downloads in 60 finishes per 60 frames and `su_deferred` 0. Over the 30 runs from
fpstelemetry1008b to fastpaths1010 with at least 120 ms of wait, the wait is 129-241 ms (2.2-4.0 ms/frame). On the one run with texture-scan counts (fpstelemetry1008b
`-1823645`) scan downloads equal range downloads (240). So NFS MW is TEXSCAN's caller recording four surfaces per
lookup (L4b), not an eviction batch.

## 12. Ranking (step 3, final for this lane): expected impact = titles x gain x P

| order | lever | titles: measured here; on disk | gain where it acts | P | state, and the next step |
|---|---|---|---|---|---|
| 1 | **L1 `HAKUX_ZETA_D24`** (section 5) | measured: NG Black, Buffy, DOA3 (one tile on all three). On disk, two-tile: NBA Live 06/07, LOTR, MechAssault 2, ToeJam, Fantastic 4, Spider-Man 2 (mixed). Named by gpunonrender: Otogi, Black | GPU outer span x0.57-0.64 in the class. Hand-read: NG Black fps_ok 0.85 -> 0.96, Buffy 0.79 -> 1.00, 6-19% less energy per frame | 0.7 that it takes the measured titles over the bar on gameplay routes. The open risk is the depth cost (section 7) | committed, off by default. Registered A/B: **LOSS** on its W leg (9d). The depth pair is queued (rows 12-13). Then lane.local's cross-title screen, judged on a share leg |
| 2 | **L4a `HAKUX_VTX_EXACT`** (10, 10a) | measured: Midnight Club 3 (H1: ex 0 of 973 downloads per 60 frames). On disk: Nightfire's NOSCAN calls, with no route and its H unread | MC3 up to 12.3 ms/frame of render-thread wait (ph_Fin 12.8 of 34.1 ms). MC3 is 0.08 under the bar at 0.815 | 0.85 that the downloads go; 0.55 that MC3 then reads >= 0.9 on its route (its fps varies 23-29 run to run, 10a) | drafted (`drafts/vtxexact.diff`); **WAITING** on draw.c, vertex.c, renderer.h |
| 3 | **L4c `HAKUX_RANGE_EXACT`** (11) | measured: Forza. No other run on disk shows eviction batches | at most ~half of 16.6 ms/frame. Forza is 0.39 under the bar | 0.4 that rule (1) is most of the batches; ~0.15 that Forza reaches 0.9 by this alone | **WAITING** on surface.c for the split counter, then one Forza run. A switch and a pair follow only if (1) dominates |
| 4 | L2 profiled autotune by default | GMEM titles where the GPU is the wait | Fuzion 38.7 -> 58.0 | 0.45 before, lower now: L1 removes the replay that profiled was escaping by choosing sysmem | lane.local's decision; nothing here |
| 5 | L4b TEXSCAN's caller on non-cube textures | NFS MW (4 per finish, 2.2-4.0 ms/frame), Spider-Man 2, MC II | a few ms per frame | 0.2 | none runnable here; NFS MW is lane.local's chain |
| 6 | L5 guest vCPU / PFIFO | Amped 2 runnable; Pilot Down, Hulk, NFS MW, NHL 2K3, LOTR unroutable | small after POSTED_PUT | 0.2 here | vcpuplan's lanes own it; not run here |
| - | L3 `sysmem` for DOA3 and NG Black in `kTitleRenderModes` | 2 one-offs | 59 gfps | superseded | L1 takes NG Black to 59 gfps in GMEM, without sysmem's Kabuki stall or its ZPASS change (#527). Dropped |

**Why L4a is above L4c, when each reaches one title:**
- L4a's cause is measured to the byte (ex 0, `edge` = n), and its fix removes exactly that download.
- L4a's win is the whole 12.3 ms, on a title 0.08 from the bar.
- L4c's mechanism is not split yet, its win is at most half, and Forza is 0.39 from the bar.

**Why L1 stays first after a LOSS.** The loss is the W leg's median against a frame cap, and both failures were
foreseen before their B arms ran (9b, 9c). The legs that read the mechanism passed 3 of 3, on the widest class the
runs on disk show.

**Runs the ranking still needs (nothing else is queued, and nothing is a retest):**
- The depth pair, 2 runs, queued.
- L4a, after its grant: register `fpsbelow1012-vtxexact.json` on a ref past the master merge, with scene-robust
  legs (B's `by=vtx` range downloads per 60 frames <= 5% of A's; B's `range` wait per frame <= 25% of A's; fps_ok
  hand-read). One MC3 pair, 2 runs.
- L4c, after its grant: one Forza run with the split counter, then a pair only if rule (1) dominates.

That is at most 13 + 2 + 1 + 2 = 18 of the 30-run cap.

Resolved (Addendum 2, board db57d68da6): the grant for draw.c, vertex.c and renderer.h (L4a), and surface.c widened
to the split counter. Both are built at 67e3fcf745 (section 13). `HAKUX_RANGE_EXACT` itself is not granted, and it
is requested only if Forza's counter reads rule (1) dominant.

The depth pair's waiting line moved to section 13, with the runs queued since.

## 13. L4a and L4c built; checks; the runs that read them (10-12 06:10 PDT)

**L4a, `HAKUX_VTX_EXACT=1`** (draw.c, vertex.c, renderer.h; off by default) is `drafts/vtxexact.diff` applied
unchanged at 67e3fcf745. Section 10 describes it. It prints `HAKUX_VTX_EXACT=0|1` at the first vertex sync, so each
arm's init line says which arm it ran.

**L4c's counter, `[sdrfin]`** (surface.c, perf builds only, always on, no env) is one line per `[sdcall]` period. It
is printed only when a `range` completion happened in that period. Each completion is counted under why it
completed the batch:
- `own`: the lookup recorded a download of its own. A precise rule completes these too.
- `dest`: it recorded none, but the range overlaps a pending download's destination (rule 2). The reader needs the
  bytes.
- `clean`: it recorded none and overlaps no pending destination, only a live surface with nothing to download. Only
  rule (1) completes it, and `HAKUX_RANGE_EXACT` would not.
- `tscan`: `pgraph_vk_texscan_complete_range`, which is always dest.

For each class the line gives the completions, the downloads retired, and the wall time. For `own` it also gives how
many downloads the lookups recorded (`rec`). The time covers the whole completion, the copies into VRAM included,
so it reads a little above `[sdcall] range=...ms`. The cost is one overlap test per completion: about 100 per 60
frames on Forza.

`tools/rfread.py` reads both after the gameplay mark. On the runs at master it reproduces the `range` figures:
- MC3 `-2104673`: 1,020 downloads, 979 ms median per 60 frames (16.2 ms/frame over the window);
- Forza `-2906178`: 101 completions, 710 downloads, 799 ms.

Neither run has `[sdrfin]` lines: they predate the counter.

**Checks on 67e3fcf745:**
- `docs/testing/preflight.sh --allow-tracker`: passed (nv2a index ok, territory ok, board files ok).
- `check_android_guards.py`: ok.
- `tools/ndkcheck.py` on draw.c, vertex.c and surface.c compiles each file `-fsyntax-only` with its NDK clang line
  from the newest Release `compile_commands.json`, as a release build and as a perf build (`-DNV2A_PERF_LOG=1`).
  All six compiles return rc 0. The only warnings are the existing `TARGET_PAGE_MASK` shift on lines this change does
  not touch. renderer.h is compiled through all of them.
- `docs/testing/jobs/selftest.sh`: stopped by me after 5 of 137 fragments (10-50, every check `ok`, 0 FAIL, ~10 min).
  The forge-selftest workflow runs only on `docs/testing/jobs/**`, `request.sh`, `lane.sh` and `nv2a_index.py`. This
  lane touches none of those, and the full run is 1-2 h. Its tmpdir `/tmp/hakux-selftest.ORd4sH` is left behind,
  because the sandbox refused the `rm`.
- Not built here: the APK, which the dispatcher builds for the first run on the ref, and the desktop target.

**The runs** (`--ref 67e3fcf745 --device nova --priority sweep --perflog --env HAKUX_GPUXFR=1 --env
HAKUX_FRAMETRACE=1`), queued behind the depth pair's A in this order:
1. MC3 B, `--env HAKUX_VTX_EXACT=1`, route `midnight-club-3.returning`, 540 s. An arm of
   `fpsbelow1012-vtxexact.json` (registered 13:10:03Z, sha256 eb30dbad...).
2. MC3 A, no switch. The other arm. Judge: `tools/rfread.py <A> <B> --expect
   docs/testing/predictions/fpsbelow1012-vtxexact.json --key MC3`.
3. Forza, route `forza-soak1010`, 480 s, no switch. This is a measurement, not an arm. Its `[sdrfin]` split decides
   L4c.

**What the Forza run decides, written before it runs.** Each class's share of the split's time, after the mark:
- `clean` >= 50%: rule (1) is the cost. Request `HAKUX_RANGE_EXACT` (surface.c), register a Forza pair. The gain is
  at most `clean`'s ms per frame.
- `dest` >= 50%: the readers need the evicted bytes. A precise rule saves little. The lever becomes a GPU-side path
  for the reader, as SURFSPLICE does for uploads, a larger change, and L4c drops below L2.
- `own` >= 50%: the lookups record their own downloads, and the evictions' batch rides along at no extra finish.
  L4c drops, and the next question is why Forza's lookups record so many.
- No class reaches 50%: report the split, and act on `clean`'s ms per frame only if it is at least 4.

Section 11 put P 0.4 on rule (1) dominating.

