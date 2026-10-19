# fpsnext1019 NOTES (#433)

Successor to fpsdata1018. Goal: GTA III while DRIVING, Blinx 2 and Fable at the 30 fps bar (owner bar 10-19: high 20s
on average in the SAME scene, or a measured per-pass GPU ms drop that accounts for the gain).

## Attempt log

- **Attempt 0 (2026-10-19 ~07:49 PDT)**: the lane unit started twice (logs `fpsnext1019.20261019T144902Z.json`,
  `...T144953Z.json`, both 0 bytes) and left only the base merge `60601a7d76` (origin/master `5dc1218a8f` + 
  `origin/lane/fpsdata1018` `0fd255d991`, because that fold has not landed: `merge-base --is-ancestor 0fd255d991
  origin/master` is false). No NOTES.md, no PR.md, no device request. Why it did not finish: the session produced no
  transcript at all (empty log files), so it ended before its first turn completed; nothing was tried, so nothing
  here is "already tried" by this lane.
- **Attempt 1 (2026-10-19, this session)**: Step 0 (below), PR claim, then Step 1.

## Step 0: Already-tried (G1), carried from fpsdata1018

Rows 1-28 are fpsdata1018's table verbatim (`docs/lanes/fpsdata1018/NOTES.md` "Step 0"); `L/` = `docs/lanes/`.
H3 is dead (row 23), R2 and the copy theory are falsified (rows 2, 4). Rows 29+ are this lane's.

| # | Lever / theory | Title | What moved (as written) | Control / spread | Verdict | Source |
|---|---|---|---|---|---|---|
| 1 | R1: skip the #474 drain (folded 4a504d9aaa; `HAKUX_S2T_DRAIN=1` restores) | GTA III | Nova parked +1.9 (b2), +2.7 (b5) fps, ~50 -> ~46 ms/frame; desktop drains/flip 1.86 -> 0 | b2 palindrome P A B C C2 B2 A2 P2; b5 W P A A2 P2 | works, small; folded | `L/gta3fps1017/NOTES.md` 2.4; README |
| 1a | R1 driving | GTA III | 29.80 vs 29.77 fps | scenes not aligned | confounded | `L/gta3fps1017/NOTES.md` 2.5 |
| 2 | R2 `HAKUX_S2T_WIDEN=1` (remove all copies/flip) | GTA III | copies 133.2/69.8 -> 0/0; fps vs R1 -0.3 (b2), -0.9 (b4) | b2, b4 palindromes | **falsified** (copy theory) | README; `L/gta3fps1017b/NOTES.md` 2.2 |
| 3 | R3 `HAKUX_S2T_SHARE=1` | GTA III | share 0.00, dup 0 | b2 | inert | README |
| 4 | Copies cause the parked dip | GTA III | RP/frame 54.6 / 52.5 / 53.5 at 133 / 0 / 0 copies | b3 arms | falsified (parked) | `L/gta3dip1018/FINDINGS.md` 1.1 |
| 5 | R1-R3 on Blinx 2 | Blinx 2 | `[s2c]` cp 0 idle and moving | bc-A | inert (nothing to act on) | README |
| 6 | Cold shader/pipeline compile | GTA III, Fable | explains GTA's 1.46 s / 3.89 s single stalls and one Fable 3.78 s frame; not the sustained dips (counters flat during them) | per-capture timeline | ruled out for sustained dips | `L/gta3dip1018/FINDINGS.md` 2; `L/fabledip1018/FINDINGS.md` 1b |
| 7 | GPU saturation | all four | busy 55-72 % GTA/R2, 25-29 % others in this capture; earlier ~34 % flat | dip/good classes | refuted (c1-A1 in-car 90/43 % tension open) | HANDOFF.md; `L/fpsdiag1018/FINDINGS.md` 2.1 |
| 8 | TLB/texture-dirty walk cost | all four | 0.3-0.6 % of render-thread CPU (this capture); 0.4-2 % earlier | 4+4 captures | falsified | HANDOFF.md; `L/fpsdiag1018/FINDINGS.md` 2.2 |
| 9 | ART GC pause | all four | 0 GC lines | 167 + this capture's dip windows | falsified | HANDOFF.md; `L/fpsdiag1018/FINDINGS.md` 2.8 |
| 10 | Fin/Fen fence wait = #796 queue depth | GTA III | parked G/Fin 48.1/14.7 ... 33.2/3.3; in car fen 15.57 = rotfen 11.03 + stale 4.00; c1-A1 Fen 13.6 vs 2.5 | within-arm windows | correlate supported; mechanism not isolated; never A/B'd | `L/gta3dip1018/FINDINGS.md` 1.5; `L/gta3car1018/NOTES.md` 4.1 |
| 10a | Fen queue depth | Fable | 1.4 vs 0.1 ms (owner-play-1018c) | 56/57 windows | refuted | `L/fpsdiag1018/FINDINGS.md` 4 |
| 10b | RalliSport 2 Fin split | RalliSport 2 | Fen 0.1-0.5 flat; Fin 11-26 ms "almost all Sub" | 36 phase lines | Sub, not Fen | ralli `FINDINGS.md` "New telemetry" |
| 11 | `hakuX-rpbrk` / `RPBreaks:` per-window breakdown | GTA III | two tids write it; ~4900 <-> ~9500 | -- | instrument racy; replaced by `[dipwin]` | `L/gta3dip1018/FINDINGS.md` 1.3; instr 1.1 |
| 12 | `[dipwin]` pass attribution, in car | GTA III | 151.65 rp/flip, 141.43 `bnd` copy_surface_to_texture; ms/flip = 30.89 + 0.1309 x rp (r^2 0.66) | 46 windows | measured: feedback-loop copy per draw | `L/gta3car1018/NOTES.md` 4.1 |
| 13 | `HAKUX_S2T_FB=1/2` (texture.c) | GTA III in car | O1 24.8 fps / 57.11 rp; F1 26.8 / 20.15; S1 27.9 / 38.20; F2 22.6 / 33.67 | one run per value, not a palindrome | cuts passes; fps confounded; 30 not reached | `L/gta3car1018/NOTES.md` 6 |
| 14 | Page-granular stale vertex copy (vtxstale1018) | GTA III | selftest bytes 891.6 M -> 118.5 M; in car stale ~4 ms | selftest only | not device-measured | `L/fpsdiag1018/NOTES.md` 0 |
| 15 | Vertex hazards (~0.3/flip), pgraph.lock (lw 0), compile <= 2 ms, guest 23.3 ms | GTA III pilot 343857 | as written | one pilot | ruled out there | `L/gta3fps1017/NOTES.md` 0 |
| 16 | redo/shc volume | Fable, Blinx 2 | Fable redo/dirty 2.0-2.8x flat; Blinx 2 3.16 -> 4.87 | counts only | cost never timed | `L/fabledip1018/FINDINGS.md` 1 |
| 17 | Df "deferred flushes" | all | VBLANK-governor retry count | code read | downstream metric, not a lever | `L/gta3dip1018/FINDINGS.md` 1.2 |
| 18 | RalliSport 2 audio (`vp.c` direct read, `HAKUX_APU_PRIO`, `prod:` model) | RalliSport 2 | starve 0.000153; fps_ok 0.8618 | pilot + 2 bar runs | audio fixed; fps not | ralli `FINDINGS.md` Status |
| 19 | RalliSport 2 fps cliff ~59 -> 25-50 at 180-240 s | RalliSport 2 | 59.0 (0-150 s) -> 38.3 (240 s) | 4 runs, prio on/off | not the audio change; thermal/sustained load suspected, handed off | ralli `NOTES.md` attempts 14-15 |
| 20 | Faster clock / governor / perf mode / sysmem | any | -- | -- | forbidden (owner) | memory `investigate-the-wait-not-the-clock` |
| 21 | Scripted gameplay navigation (6 GTA routes) | GTA III | all VOID | -- | do not repeat | `L/gta3fps1017/NOTES.md` 0 |
| 22 | texscan: GPU copy of draw-dirty whole-face CUBE surfaces into the texture instead of download + upload (`HAKUX_TEXSCAN`) | NFS MW cube | range 4.03 -> 0.00 ms/frame, but fps -1.4 / period +2.6 ms alone: the wait moved to the #804 report fence | NFS arms | works when paired with REPORT_ASYNC; default-on in fastpaths with it | `L/texscan1010/NOTES.md` 5-11 |
| 23 | Skip the per-frame STALLED finish when no report is queued (`stall_reports_only()`/`HAKUX_STALLFIN=reports`, `reports.c:1320`) -- proposed here as the shared cause of GTA III's `rotfen`/`fin=stalled` and Blinx 2's `stl`/`sd[cDefC62]` wait, both ~1 STALLED finish/frame with an empty report queue in this capture (3 "report" lines total in each of `gta3.txt`/`blinx2.txt`, all three `init:` logging, none in a gameplay window) | Simpsons (K0/K1, `gpunonrender` 0702057f25) | STALLED finishes fell to 20% (5.36->1.05/frame) **but gfps fell 30.3->25.8**, G 33.0->37.75 ms, `xemu-gpu` Xfr 7.0->13.0, vCPU pfifo.lock wait +4.3 ms/frame | K0/K1 A/B pair, same clock (401 MHz), same route | **refuted**: removing the catch-up submit lets the command buffer grow bigger before its one submit, so the GPU starts the frame's work later (at the flip) instead of overlapping with CPU recording; the overlap was worth more than the rotation wait it cost | `L/gpunonrender/NOTES.md` "K0/K1: STALLED submits fall to 20%, and fps falls" |
| 24 | `HAKUX_S2T_FB` mode 2 (GTA III in-car fix): its pixel prediction FAILed on the same lever before landing clean -- DOT_PRODUCT misclassified as a non-reading combiner mode, a real regression (Pixel FAIL #2, `Antialiasing_tests/CPUWriteIgnoresSurfaceConfig` moved) | `Antialiasing_tests` | arms `--expect`, 24/472 then 0/472 (after DOT_PRODUCT excluded; the remaining `Texture_shadow_comparator` moves are noise, see row 25) | 1 arms pair, this lever | landed once the DOT_PRODUCT mechanism was excluded; `s2t_fb_record()` also gained the shadow-comparator-format exclusion `texscan_shape_ok()` already needed (correct on the code reading, kept, but not provable by this suite's single-run arm -- row 25) | this file, "Pixel FAIL #2" |
| 25 | `Texture_shadow_comparator` as a `must_not_move` suite in a single-run `--expect` pixel prediction: used three times this lane (texscan2d, S2T_FB mode 2 x2) and FAILed every time (23/1038, 24/472, 21/472) including on an already-landed fix (17/1038 re-check of `b46f4cb8d3`) | same 4 arms pairs above, plus a 3-way same-ref sweep (`245ddc4964`, zero code change) | `sweep_agreement.py` across 3 same-ref runs: 89/1038 disagree, 100% `Texture_shadow_comparator`, zero elsewhere; one capture (`2F16_..._15.0000_GT`) reproduces the identical `480->400` transition under two unrelated fixes | 3 same-ref device runs already on disk, no new device time spent | **this suite cannot be gated by a single-run arm**: it disagrees with itself ~8.6% of the time with no code change. Drop it from `must_not_move` in any future prediction against this suite; use `--runs N` + `sweep_agreement.py` (or a majority-of-N vote) if a real claim about it is ever needed | this file, "Noise floor measured" |
| 26 | `HAKUX_S2T_FB` mode 2's depth-excluded re-registration (`b50667ac35`) still FAILed: `s2t_fb_memo[]` had no check that `pg->surface_scale_factor` matched between record and keep, so a slot could reuse a copy sized for a stale scale after a CPU-write reconfigure that never bumps `draw_time` | `Antialiasing_tests` | `ab_compare.py`, 1/184, `CPUWriteIgnoresSurfaceConfig` 0 -> 45,056 -- byte-for-byte the same capture and count as row 22's/Fix #1's `image_scale` regression, a different cache (`s2t_fb_keep`) taking the same raw-copy route (`copy_surface_to_texture`) | 1 arms pair, this lever (`1-1792404006-*`) | fixed: `s2t_fb_memo[].scale` recorded at copy time, checked at keep time, same precedent as Fix #1's `image_scale` and row 24's depth exclusion | this file, "Pixel FAIL #4" |
| 27 | `migrate_surface_image()` not copying `image_scale` from a shelved/invalid surface's old binding to its new one, found while re-checking texscan2d's own prediction for a suspected regression that turned out to be a device flake | `Antialiasing_tests` (same flake check, not this gap) | `sha256sum` across 4 existing result dirs (2 base, 2 fix): 3/4 byte-identical on bit-identical builds, 1/4 differs -- the flake, not evidence for or against this gap, which always safely under-refuses (`0 != 1`) rather than corrupts | 0 new device time (read existing results) | fixed: `dst->image_scale = src->image_scale;` added to `migrate_surface_image()`; re-registered texscan2d's prediction a fifth time since this changes texscan eligibility for migrated surfaces, a new falsifiable claim Fix #1's own registration never made | this file, "Pixel scare resolved" |
| 28 | `Antialiasing_tests/CPUWriteIgnoresSurfaceConfig` and `/FramebufferNotModifiedBySurfaceState` as `must_not_move` members in texscan2d's prediction, across the fresh `1-1792407690-*` arm pair at `245ddc4964`/`c4560f2ab4` | `Antialiasing_tests` | `CPUWriteIgnoresSurfaceConfig`: 6 runs on disk, 2 distinct sha256, the corrupted one byte-identical both times it appears -- once on fix `b46f4cb8d3`, once on base `245ddc4964` (zero #433 code); `FramebufferNotModifiedBySurfaceState`: 5/6 runs match, this pair's base alone differs by 6 bytes | 0 new device time for this finding (read 6 existing result dirs); 1 fresh arms pair queued (`fpsdata1018-texscan2d-reverify`) to get an honest post-registration verdict, since the first check against this exact pair was POST-HOC per `ab_compare.py`'s own flag | both moves are on the unmodified (A) side in this pair -- direct evidence against attribution to this lane's code, strongest yet; narrowed `must_not_move` to name the other 9 `Antialiasing_tests` captures individually (0 moves in 6 runs each) rather than dropping the whole suite, since only these 2 of 11 captures have ever moved | this file, "Attempt 3: why attempt 2 did not finish" |
| 29 | Row 20 "sysmem" ban | GTA III, Blinx 2 | -- | -- | **lifted for per-title SYSMEM as an experiment** (owner 10-19 07:0x, brief): the row was the clock rule; a render-mode experiment is not a clock change. Clock/governor/perf mode stay forbidden | brief fpsnext1019 |

## Step 1 input: lane.local's frame budget (copied from `scratch/fps-budget-1019.md`, 10-19 ~07:20 PDT)

M = measured (source named), I = inferred, U = no data. Nova, perflog build, PurpleVK, RT held 60 s.
Source C = `captures/gta3car1018/runs/c2-{O1,S1,F2}/logcat.txt`.

GTA III driving (5454000E), hold windows, ms per guest flip:

| slice | O1 S2T_FB off | S1 S2T_FB=2 (shipped) | F2 S2T_FB=1 | source |
|---|---|---|---|---|
| wall ms/flip (fps) | 40.4 (24.8) | 35.9 (27.9) | 44.2 (22.6) | M `[dipwin]` |
| render passes/flip | 57.1 | 38.2 | 33.7 | M `[dipwin]` rp= |
| vblanks/flip 1 / 2 / 3 / 4+ (%) | 15 / 42 / 32 / 10 | 17 / 53 / 24 / 4 | 10 / 35 / 38 / 16 | M hakuX-pace |
| PFIFO Draw (cmd record) | 8.1 | 7.4 | 9.7 | M hakuX-phase |
| PFIFO Fin (submit + fence wait) | 9.8 | 5.5 | 14.2 | M hakuX-phase |
|   rotation fence / stalled fin | 5.8 / 5.9 | 1.9 / 1.9 | 8.9 / 9.0 | M `[dipwin]` |
| PFIFO idle waiting for guest | 6.1 | 10.8 | 2.7 | M hakuX-phase Idle |
| PFIFO phase Tot (incl. idle) | 25.3 | 24.9 | 28.3 | M |
| PFIFO Push (pusher wall/flip) | 24.6 | 21.2 | 31.6 | M hakuX-cpu |
| GPU busy / of which render | 24.3 / 20.1 | 22.0 / 19.5 | 28.0 / 26.2 | M hakuX-phase |
| present/swap, vCPU split | U | U | U | -- |

- GPU render time did not fall with pass count (20.1 ms at 57 passes, 19.5 at 38). S2T_FB bought fence wait (stalled
  fin 5.9 -> 1.9), not GPU cost (I).
- GAP: wall minus phase Tot = 15.1 / 11.0 / 16.1 ms (O1/S1/F2): in no PFIFO phase timer and no idle. Cause U.
- vCPU is not the limiter (older build, gta3drive1017: guest idle 10-14 ms even in the slow band).
- 29 of S1's 38 passes/flip end at `copy_surface_to_texture` (texture.c:1311, via `begin_nondraw_commands`).
- Render mode: both titles run `auto` (Turnip autotune=bandwidth); which mode each pass gets is not logged.
- Blinx 2 (4D530065): no gameplay budget capture. fpsdata1018 windows: 3054 15 gfps, Surf 41.7, GPU 39.6, 45 RP;
  2682 (good) Surf 2.9, GPU 13.7, 31 RP. H4 census never read.

## Big-lever table (before any item; ranked by probability x win at full scale)

| # | Lever | Win at full scale | Probability, and its evidence | Instrument that decides it | Rank |
|---|---|---|---|---|---|
| a | Per-title SYSMEM render mode (GTA III, Blinx 2) | GTA III render 19.5 ms/flip; Blinx 2 R 39 ms at 45 RP. If GMEM bin replay + per-pass load/store is a third of that, 6-13 ms/flip: GTA III 35.9 -> ~30 ms, most 3-vblank frames back under 33.3; Blinx 2 15 -> 20+ gfps | 0.35. For: the code's own comment (xemu_android.cpp:862) records AUF 16->24 and DOA 13->21 gfps from sysmem; GTA III ends 29 of 38 passes on a copy, so each pass's tile store is paid and then read by a copy, the pattern GMEM is worst at (memory `gmem-cost-is-replay-not-loadstore`). Against: Turnip's bandwidth autotune already picks sysmem for passes it thinks are small; GPU time did not move with pass count | env `TU_DEBUG=sysmem` (env token beats the table, :949-955), same scene A/B, GPU R ms/flip + wall + vblank mix | **1** |
| d | The 11-16 ms/flip gap outside every PFIFO phase timer, and the 24% of flips at 3+ vblanks | up to 11 ms/flip in S1 (a third of the frame) if it is a wait that can be removed | 0.3 that it is one removable wait; U what it is. vCPU idle 10-14 ms says the guest is not the limiter; PFIFO Idle 10.8 says PFIFO waits for the guest. So the gap may be the render/present thread or vblank pacing, which no phase timer covers | `HAKUX_FRAMETRACE=1` (profile.h): per flip on-CPU / runnable / blocked per thread, waits by reason, GPU ms | **2** (decides what d is; runs in the same session as a) |
| b | Render-pass count/merging: the 29 passes/flip ending at `copy_surface_to_texture` | the fence wait share per pass (stalled fin 1.9 + rotfen 1.9 at 38 RP) plus any per-pass GPU fixed cost; measured GPU render did not fall 57 -> 38 RP | 0.2. GPU time is flat in pass count (M), so fewer passes buys only the wait; S2T_FB already took a third | `[dipwin]` bnd per site + GPU R per flip; the `HAKUX_GPUXFR` `XFR rpc` census for per-pass load/store | 3 |
| c | Draw/state redundancy per pass | PFIFO Draw 7.4 ms/flip is CPU record; it is off the GPU path | 0.15: Draw does not grow with the dips (8.1 / 7.4 / 9.7 across arms tracks passes, not fps) | per-draw counters in `[dipwin]`; hakuX-phase Draw | 4 |
| e | vCPU translation / TB lookup | none while the guest idles 10-14 ms/flip | 0.05 for GTA III; U for Blinx 2 and Fable | FRAMETRACE vCPU row (on-CPU vs guest idle) | 5 |

The order is a (big, plausible, needs no code: one env) and d (decides an unknown third of the frame) together in one
hold, then b on what they leave.

## Plan for this attempt

1. Blinx 2 H4 census + FRAMETRACE through the dispatcher (`gen-blinx2`, `--perflog`, `HAKUX_GPUXFR=1`,
   `HAKUX_FRAMETRACE=1`), tier `1-`.
2. GTA III in-car hold batch (gta3car1018's protocol: owner state slot 5, pause-menu load by screenshot, RT held 60 s):
   arms `S` (shipped) and `Y` (`TU_DEBUG=sysmem`), both with `HAKUX_FRAMETRACE=1`, palindrome S Y Y S.
3. Read, then the next lever from the table.
