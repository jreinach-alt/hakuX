# lane.fpsbelow1012: the below-bar titles on the Nova at master, and one fix that lifts several (#433, 0.5)

Brief: `/home/justin/hakux-work/briefs/fpsbelow1012.md`. Input: `belowbar1012.tsv` (lane.local, 10-11 23:1x),
43 titles copied on the Nova. Base: master @ 5326de78b2, merged to 00fde8afb3 (defaulton1011) on 10-12.

Device-run count (cap 30, A/B arms included): **0** run, 3 queued (the pilot). Ledger in section 4.

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
| 1 | z-1791787896-fpsbelow1012-2551124 | Dead or Alive 3 | survey | 480 | queued (pilot), ref 00fde8afb3 | |
| 2 | z-1791787896-fpsbelow1012-2551219 | Ninja Gaiden Black | survey | 480 | queued (pilot), ref 00fde8afb3 | |
| 3 | z-1791787897-fpsbelow1012-2551411 | Midnight Club 3 | midnight-club-3.returning | 540 | queued (pilot), ref 00fde8afb3 | |

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

| # | lever | titles it reaches | win where it acts | P | why that P |
|---|---|---|---|---|---|
| L1 | `HAKUX_ZETA_D24` (section 5) | every 32-bit 640/720x480 GMEM title; it shows in frames where the GPU is the wait. Two-tile on disk (5a): DOA3, NG Black, NBA Live 06/07, Buffy, LOTR, Fantastic 4, MechAssault 2, ToeJam, Spider-Man 2 (mixed); named by gpunonrender: Otogi, Black | up to sysmem's matched-scene gain without its costs: DOA3 34 -> ~59, NG Black 32.5 -> ~59; NBA Live 06/07 47-49 at G ~20 ms with SURFGPU, where the replay is the next cost | 0.6 | For: the mechanism is read from the driver source and agrees with four measured numbers (two bins; last tile ~ whole sysmem pass; 9 B/px; out = 2 x in in the fight, 5a). Against: a one-tile GMEM pass still loads and stores colour and depth, which sysmem does not; the autotune may then pick sysmem for some passes; and the D24 round trip is a unit off near z = 2^23 on Adreno (section 7), which a title that reads depth back may show |
| L2 | profiled autotune by default (`kAutotuneProfiledDefault`) | GMEM titles where the GPU is the wait | Fuzion 38.7 -> 58.0 | 0.45 | Forza loses 28.9 -> 26.6 with no named cause (profileddefault1008); lane.local's decision. If L1 holds, L2's gain shrinks: it was choosing sysmem to escape the replay |
| L3 | DOA3, NG Black to `sysmem` in `kTitleRenderModes` | one title each | DOA3 34 -> 59; NG Black 32.5 -> 59 | 0.85 / 0.75 | measured on matched scenes; one-offs, the owner's rule ranks them below a lever that reaches several |
| L4 | surface-download remnants (`range`, `tobuf`) | Forza runnable here; MC II, Counter-Strike, Spider-Man 2, NHL 2K3 unroutable | unknown at master | 0.3 | needs the Forza telemetry first |
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
