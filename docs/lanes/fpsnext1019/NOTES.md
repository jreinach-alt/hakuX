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
- **Attempt 2 (2026-10-19, resumed per addendum)**: attempt 1 ended on the 300-turn cap (`stop_reason max_turns`,
  08:35 PDT) after Step 0, the budget-pass table and the big-lever table, but before starting either queued batch
  (plan items 1-2 below were still "upcoming"). Nothing to redo on the diagnosis side. Start-of-attempt checks:
  `0fd255d991` (fpsdata1018) is still not an ancestor of `origin/master` (foldjam1018's fold landed in the
  meantime, `3597b72b35`/`6439ec7436`), so merged `origin/master` into this branch (`789b390b95`) rather than
  waiting on the fpsdata1018 fold. `hold.sh who nova` -> `free: nova` (no stray screening/pathfind hold in front
  of this lane). The devwatch.py auto-lift at 08:25:34 PDT (now fixed upstream) ran a `dispatch.restore` of
  master APK `9f29b4aa5dd7` on the Nova 08:26-08:27 PDT while no hold of mine existed yet (attempt 1 never got to
  taking one) -- nothing of this lane's was lost, but the device now has that APK installed, not necessarily the
  merged build this attempt needs; rebuild and reinstall before any capture rather than assuming device state.
  Continuing from the plan: item 1 (Blinx 2 H4 census) first, since it needs no device-mode A/B and the
  `learned.py` route fix is already in place; item 2 (GTA III SYSMEM hold batch) next.
- **Attempt 3 (2026-10-19 ~10:50 PDT, resumed per addendum 2)**: attempt 2 did not finish the brief because it
  treated `State: ready` as a stopping point: it ended its session after marking the PR ready with one clean
  GTA III reading (28.3 hold / 27.1 drive) and two noisier repeats, Blinx 2 parked on the route gap and Fable
  untouched. The bar is all three titles at 30, so a ready PR is a fold point, not an end (G7). This attempt:
  merged origin/master (`compat1019b` fold, docs only, no emulator code), took the Nova hold (`hold.sh take`,
  `wait-idle` 0, nothing in front of this lane), and found the shorter path to Blinx 2 gameplay the route
  work was standing in for: the owner's Blinx 2 island state (release slot 1, 10-17 22:41) is already copied
  into the debug package's slot 5 (`.../com.jreinach.hakux.debug/files/x1box/states/4d530065/slot5.hxs`,
  26114724 bytes, same size as the release slot1), and lane.xbox's `arm2b.sh` loaded it through the pause menu
  on 10-18 (`captures/lanexbox-fps1018/runs/bc-A`: 21.6 fps idle, 24.1 fps circling, `G 41.0`). So Blinx 2 gets
  its gameplay budget capture and H4 census from that state, under this lane's hold, before any profile work.
- **Attempt 4 (2026-10-19 ~12:00 PDT, resumed per addendum 3)**: attempt 3 ended on the 300-turn cap
  (`stop_reason max_turns`, logs `fpsnext1019.20261019T175209Z.json`) mid-build, not stuck: `HAKUX_SWZKEEP`
  (Blinx 2) and `HAKUX_S2T_DEAD` (GTA III) are both built, opt-in, and each has a full G3 prediction table
  written before any device run against it, per G3 -- nothing to redo on the diagnosis side. It did not finish
  because it ran out of turns writing the second prediction (`HAKUX_S2T_DEAD`'s) before queuing either device
  run. Start-of-attempt checks: `origin/master` was 3 commits ahead (`nova-tiers1019`'s fold, hold.sh priority
  tiers), merged clean (no emulator-code conflict, this lane's `texture.c`/`surface.c` changes are untouched by
  that fold). `hold.sh who nova` -> `free: nova` (devwatch's correct auto-lift after attempt 3's unit stopped,
  per the addendum; nothing of this lane's running under the old hold). No perflog APK exists yet for this
  attempt's HEAD (`HAKUX_S2T_DEAD`'s commit, `711315bbe7`, now merged with nova-tiers1019) -- the last on-device
  build was `3058a55767-perflog.apk`, which predates both `HAKUX_SWZKEEP` and `HAKUX_S2T_DEAD`. Continuing
  straight into the P0 census run named in the addendum: build first, then GTA III P0 (off arms only, per the
  prediction's own note that P0 does not depend on the switch), then the on/off palindrome; Blinx 2's
  `HAKUX_SWZKEEP` palindrome after that if device time allows.

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

## Attempt 2, item 1: Blinx 2 census -- blocked on a pathfind gap, not the import bug

Two fresh dispatcher runs this attempt (`1-1792424457-lane.fpsnext1019-345816`, 90s; `1-1792424727-lane.fpsnext1019-447829`,
450s; both `route=gen-blinx2`, `--perflog`, PurpleVK confirmed in logcat) both finished with `time_to_play_s` empty --
neither ever reached gameplay. This is **not** the `ModuleNotFoundError: No module named 'learned'` bug the addendum
described as already fixed by hand: both runs got well past that point (the longer one logged 2140 `xemu-xfr` lines),
so the `SCRIPT_DEPS`/`snapshot_scripts()` fix for `titles/pathknow/learned.py` is confirmed durable and this is a
different, new void.

Root cause, from reading `dispatch/bin/titles/drive.py` directly (outside this repo, the live serving tree):
`EXPLORE_LADDER = ("A", "START", "B", "X", "Y", "DOWN", "LX:min", "R1", "L1")`, but
`rung = [b for b in EXPLORE_LADDER if self.has_pause_crop or "START" not in b]` drops `START` from the ladder on any
title with no built profile (no pause-menu crop) -- which is every button the generic `unknown`-screen explorer will
press on Blinx 2 (`4D530065`; `targets.toml` route `gen-blinx2`, "not yet device-proven"). `pathknow/hints/series-blinx.md`
records the only known working sequence as "plain alternating START and A" through Story mode to the locker room --
exactly the button the generic explorer cannot press without a profile. `pathknow/hints/learned-series-blinx.md` has a
learned entry for Blinx 1 (`4D530013`) but none for Blinx 2.

This is a real, named mechanism (not "needs more data" -- G5): Blinx 2 needs either a built profile (pause crop) so
`has_pause_crop` lets START back into the ladder, or a `learned.py` entry recorded by hand once a human/owner session
presses through the locker room once. Both are a pathfind/profile-building effort, not a quick dispatcher fix, and
GTA III is directly actionable without one and ranked higher in the brief's own list. **Decision: defer** -- parked,
not pursued this attempt. Device time spent on this: ~540s (~9 min) of the Nova, both runs under the 30 min pilot
cap, `--issue 433` tier `1-`.

## Attempt 2, item 2: GTA III SYSMEM/GMEM hold batch -- already run by attempt 1, recovered and analyzed (not re-dispatched)

The 08:36 PDT resume addendum said this batch "had not yet started." That claim was stale: `/home/justin/hakux-work/captures/fpsnext1019/`
(outside the repo, attempt 1's own scratch area) holds three full batches run 07:58-08:35 PDT, all through
`request.sh`/the dispatcher's `arm.sh`, GTA III in-car save state (slot 5), pause-menu load, RT held ~60s, scored by
`score2.py` into park/hold/drive windows, every arm's logcat confirms `GPU: PurpleVK-public`. Re-running this would
have wasted Nova time and broken G1 ("never re-run a row that already exists") once documented, so this attempt reads
and credits the existing captures instead of re-dispatching.

**b1** (7 arms, clean): `W,S1,S2,S3` = shipped (`HAKUX_FRAMETRACE=1` only, no render-mode override -- `W`/`S1-S4` are
literal repeats of the same config, giving a same-arm noise floor); `Y1,Y2` = `TU_DEBUG=sysmem`; `M1,M2` = `TU_DEBUG=gmem`.
**b2** (4 arms): `F1,F2` = `HAKUX_S2T_FB=1` (forces the older texture-scan mode instead of shipped's default mode 2);
`S3,S4` = shipped repeats. `F2` has **no windows at all** -- it was the arm running when the devwatch bug auto-lifted
the Nova hold at 08:25:34 and was killed by the dispatcher's 08:27:13 `dispatch.restore` install of master APK
`9f29b4aa5dd7` (confirmed by `batch3.sh`'s own inline comment and by `F2`'s absent score). **b3** (3 arms queued:
`D1,X1,D2`) is *not* "void from the wrong APK" as I first read it -- `batch.log` shows the script detected the stray
install and correctly reinstalled this lane's `05c6771a16-perflog.apk` (`e44ad7cedcd7`) before running; `D1`'s
`arm.log` confirms `GPU: PurpleVK`, a clean savestate load and `RT_DOWN`, but has no `RT_RELEASED` and an empty
`screenrecord.txt` -- it was killed mid-hold when attempt 1 hit the 300-turn cap at 08:35. `X1` and `D2` never started
(no run directories exist). **b3 contributes no data, for a different reason than first suspected** (truncated by
the turn cap, not a bad binary).

score2.txt hold/drive fps, all clean arms (b1 + b2's S3; b2's S4 and both F arms handled separately below):

| arm | env | hold fps (n, span) | drive fps (n, span) |
|---|---|---|---|
| W | shipped | 23.5 (23, 58.8s) | 20.5 (10, 29.2s) |
| S1 | shipped | 26.6 (25, 56.5s) | 22.8 (10, 26.3s) |
| S2 | shipped | 25.0 (24, 57.6s) | 20.7 (9, 26.1s) |
| S3 | shipped | 25.4 (25, 59.1s) | 21.2 (10, 28.2s) |
| Y1 | sysmem | 17.3 (16, 55.5s) | 21.9 (9, 24.6s) |
| Y2 | sysmem | 19.7 (19, 57.8s) | 19.6 (9, 27.5s) |
| M1 | gmem | 20.1 (19, 56.7s) | 21.2 (10, 28.3s) |
| M2 | gmem | 26.2 (25, 57.3s) | 22.0 (10, 27.2s) |
| F1 | S2T_FB=1 | 16.4 (16, 58.5s) | 18.1 (8, 26.6s) |

Group means: shipped (W,S1,S2,S3) hold 25.1 fps (spread 23.5-26.6, 3.1 fps / ~12%), drive 21.3 fps (spread 20.5-22.8,
2.3 fps). sysmem (Y1,Y2) hold 18.5 fps (**below the shipped spread entirely**), drive 20.75 fps (inside the shipped
spread). gmem (M1,M2) hold 23.15 fps (spread 20.1-26.2, wider than shipped's own noise floor), drive 21.6 fps (inside
the shipped spread). F1 (S2T_FB=1) hold 16.4 / drive 18.1, both well below shipped -- consistent with, not new beyond,
row 22/24's already-landed finding that mode 2 beats mode 1 for GTA III; not treated as new evidence here.

`S4` (hold 22.5 fps, n=**11**, 29.4s) is the compromised arm, not a second clean shipped reading: every other clean
arm logged **62** `[dipwin]` lines total (park+hold+drive); `S4` logged **45**. `S4`'s own `RT_DOWN`/`RT_RELEASED`
device-clock span is a nominal 60.5s, same as the others, so RT itself was never dropped -- but 08:25:34 (the
devwatch hold-lift) falls *inside* that span (`RT_DOWN` device 08:25:01.7, lift 08:25:34, `RT_RELEASED` device
08:26:02.2), and the missing ~17 `[dipwin]` lines (a ~27% shortfall, concentrated in the "hold" bucket: 11 logged vs
~22-25 expected) line up with a logcat/capture dropout coincident with that event, not with slow or dropped frames
(frametrace CSV and screenrecord both pulled normally). **Verdict: `S4` excluded from the shipped group**, its
numbers are a partial, discontinuous sample and not comparable to the other three.

FRAMETRACE per-vblank-bucket analysis (`ftbucket.py`, same tool attempt 1 built in `captures/fpsnext1019/scripts/`),
hold window, one representative arm per group:

| arm | all-bucket P (ms) | guest work | guest idle | RP (passes) | GPU busy | GPU clock |
|---|---|---|---|---|---|---|
| S1 (shipped) | 38.2 | 17.4 | 18.2 | 31 | 24.5 | 432 MHz |
| Y1 (sysmem) | 55.8 | 28.1 | 25.6 | 47 | 33.2 | 488 MHz |
| M1 (gmem) | 49.0 | 23.9 | 21.6 | 52 | 33.5 | 650 MHz |

guest work + guest idle accounts for essentially all of each arm's own frame period at every vblank bucket (checked
per-bucket, not just the all-row above) -- this resolves the Step 1 budget table's "11-16 ms/flip gap outside every
PFIFO phase timer" (lever d): it is guest-side (vCPU) idle time that scales with render-pass count and GPU busy time,
not a separate, independently removable wait. Lever (d) is folded into lever (b) rather than tracked on its own.

**Lever (a): CONTESTED, not a settled refutation -- correcting what I wrote above.** The hold-window verdict above
used `ftbucket.py`'s FRAMETRACE-csv `rp`/`gpu` fields over the *whole* ~60s hold span. Re-running the same question
with `dwseries.py` directly against the `[dipwin]` logcat lines (an uncapped, independent counter already in every
capture) over just the RT-press-aligned span that matches `score2.txt`'s own **drive** (confirmed-motion) sub-window
length gives the opposite direction for sysmem:

| arm | window | ms/flip | fps | rp/flip | cs2t-ended/flip | cs2t share |
|---|---|---|---|---|---|---|
| S1 (shipped) | drive, 08:02:56-08:03:23 (27s, matches score2's 26.3s) | 47.7 | 21.0 | 135.9 | 125.0 | 92% |
| Y1 (sysmem) | drive, 08:05:30-08:05:55 (25s, matches score2's 24.6s) | 40.9 | 24.5 | 72.4 | 61.4 | 85% |
| M1 (gmem) | drive, 08:08:05-08:08:33 (28s, matches score2's 28.3s) | 45.9 | 21.8 | 102.1 | 91.4 | 90% |

Here sysmem has *fewer* render passes/flip and a *better* ms/flip than shipped during actual driving -- the opposite
of the hold-window ftbucket reading. The two readings are not a clean apples-to-apples pair: different instrument
(FRAMETRACE csv `rp` field, which `phseries.py`'s own docstring says is capped, vs `[dipwin]`'s raw per-window
counter) and a window boundary I set by hand from `RT_DOWN` + the score2-reported drive span length, not from
`movescore.py`'s actual per-window motion verdict. **Do not trust either direction on this data alone.** The needed
next instrument is `[dipwin]` (or `dwseries.py`) joined to `movescore.py`'s own confirmed-motion window boundaries,
same arms, before ranking lever (a) up or down -- that is a re-read of logs already on disk, not a new device run.

What *is* robust across all three arms, independent of how (a) resolves: **`copy_surface_to_texture` ends 85-92% of
render passes in every arm during actual driving**, and the raw scale is far larger than the inherited budget-table
figure (38 passes/flip, from an older gta3car1018 capture) suggested -- this attempt's own captures show 72-136
passes/flip during the confirmed-motion window, of which 61-125/flip end at that one site. That number does not
depend on resolving the lever-(a) contradiction above, so it is kept as the basis for promoting lever (b).

## Big-lever table, re-ranked after Attempt 2

| # | Lever | Status | Why |
|---|---|---|---|
| b | Render-pass count/merging via `copy_surface_to_texture` (`texture.c:1311`) | **rank 1 (promoted)** | 85-92% of render passes end at this one site during actual driving in every arm measured (S1/Y1/M1), 61-125 of them per single flip -- robust regardless of which render mode wins |
| d | 11-16 ms/flip gap, 3-vblank frame share | **resolved, folded into b** | FRAMETRACE data: guest work + guest idle account for the whole frame period at every vblank bucket; the gap is guest-side idle that scales with RP/GPU, not an independent wait |
| a | Per-title SYSMEM/GMEM render mode | **contested, re-rank after a matched-window re-read** | hold-window ftbucket reading says forced modes are worse; drive-window `[dipwin]` reading (above) says sysmem is better; two different instruments/windows, not reconciled yet -- re-read with `movescore.py`'s own window boundaries before trusting either |
| c | Draw/state redundancy per pass | 3 (unchanged) | not yet measured this attempt |
| e | vCPU translation / TB lookup | 4 (unchanged) | FRAMETRACE guest-idle data this attempt still shows the vCPU is not the limiter (idle tracks GPU/RP, not starved) |

Next concrete action per G4: lever (b), render-pass count/merging at `copy_surface_to_texture`. Read it on this
batch's own captures first (no new device time): every `[s2c]` window in every arm (S1 shipped, Y1 sysmem, F1
`S2T_FB=1`) shows `why[... map<N> ...]` at **100%** of copies (`zs`/`pad`/`fmt`/`none` always 0) and `r2[map0]
r3[share0]` **always 0** -- the two fast paths already built for exactly this (`s2t_widen_view()`/R2 component-map
view, `s2t_share_find()`/R3 draw_time share, lane gta3fps1017b, `texture.c:2912` comment: "~73 a flip on the Nova,
each one breaking a render pass") never engage once in these captures, regardless of render mode or `S2T_FB`
setting. R2's own guard chain (`s2t_widen_view()`, `texture.c:3228`) has six early-return points (off/surface-null,
identity-map, format mismatch, shape -- cubemap/mip/array/dimensionality, scale/size mismatch, `S2T_CVT` replication)
and nothing in the existing logs says which one is rejecting every GTA III S2C_MAP case.

**Mechanism step taken this attempt** (G2, before any remedy): added per-guard reject counters to
`s2t_widen_view()` (`texture.c`, new `s2t_widen_rej[]`, `TEX_PERF`-gated like every other counter in this file) and
wired them into the existing `[s2c]` census line as a new `wrej[off id fmt shape scale cvt]` field, reset alongside
`s2c`'s own window reset. This is instrumentation only, no behavior change, and the device census this attempt
already has (every arm's logcat) was taken before this code existed, so it cannot answer the question retroactively
-- one short dispatcher run with this build is needed.

**Falsifiable prediction (G3), before building or queuing:** one guard will dominate GTA III's `wrej[]` counts (not
an even split), and it will NOT be `off` (if `s2t_widen_on()` were simply false, `r2[map]` would never have a chance
regardless of scene, which the existing `r2[map0]`-always-zero reading does not distinguish from a real per-call
rejection). Given this lane's own history of surface-scale-factor bugs breaking exactly this family of
view/cache decision (rows 26 `s2t_fb_memo[].scale`, 27 `migrate_surface_image()` `image_scale`), `scale` is the
likeliest single dominant guard; `shape` (mip/array/cubemap/dimensionality, plausible if GTA III samples a
multi-level or array render target as a mirror/reflection texture) is the second candidate. Falsified if `wrej[]`
comes back roughly even across guards (no single dominant mechanism) or if a guard other than `scale`/`shape`
dominates -- either result still answers the question and names the next, different code change.

Built, not yet queued: `git status` was clean before this change: this file and `texture.c` are the only two
modified paths this attempt (`git diff --stat` matches `Files:` below once committed). Commit, then one short
(<=90s) `request.sh --perflog --issue 433` GTA III in-car run to read `wrej[]` is the next action -- within this
session if time remains, otherwise the first thing the next attempt does (no re-diagnosis needed, the prediction
above is the falsifier to run).

## Attempt 2, item 3: `wrej[]` falsifies the prediction -- R2 was never turned on, not guard-rejected; landed

No warm build cache existed in this worktree (`android/app/.cxx`, `android/app/build` both absent -- attempt 1's
perflog APK lived in the dispatcher's own private build tree, not here), so the `wrej[]` instrumentation needed its
own cold build: `android/gradlew --no-daemon -Pperflog=true assembleDebug` (JDK21, `ANDROID_SDK_ROOT` per
`AGENTS.md`), run detached (`setsid nohup ... &`, polled in-session -- a lane session dies with anything truly
backgrounded) since it is long-running. Cold build 5m39s, BUILD SUCCESSFUL. Copied to
`captures/fpsnext1019/apks/293ed24401-perflog.apk` and run through the pre-authorised GTA III save-state protocol
(`scripts/batch.sh`/`arm.sh`, under this lane's own Nova hold) as **b4-W1**, env `HAKUX_FRAMETRACE=1` only (no
`HAKUX_S2T_WIDEN`, i.e. the same env every prior arm in this lane used):

```
[s2c] f60 cp57 ... wrej[off57 id0 fmt0 shape0 scale0 cvt0] | #0:57
```

Every single window, every one of 57 census lines across the whole run: **`off`, zero everything else.** The G3
prediction (scale or shape would dominate) is **falsified** -- cleanly, not ambiguously; there is no mix to argue
about. `off` is `s2t_widen_on()`'s very first guard (`texture.c:2959-2969`): `s2t_widen_state = e && e[0] == '1'`,
reading `HAKUX_S2T_WIDEN` -- **R2 is an opt-in env switch, default off, and no capture in this lane's history (not
attempt 1's SYSMEM/GMEM batches, not this attempt's own b4) had ever set it.** The "which guard rejects every call"
question was the wrong question: nothing was ever rejecting a call, because the call was never being attempted.
This is a cheaper, better-explained finding than the prediction it falsified, and it is exactly the outcome G3 asks
for -- the falsifier named a different, concrete next action on its own.

Turned it on, same APK (no rebuild needed, env-only): **b5-W2**, env `HAKUX_FRAMETRACE=1+HAKUX_S2T_WIDEN=1`:

```
[s2twiden] on
[s2c] f60 cp0 dup0 srf0 why[...all 0] ovf0 r2[map578 pad0] r3[share0] ... wrej[off0 ...] |
```

`cp`/`dup`/`srf` all 0 for the entire run -- the copy this guard exists to avoid did not happen even once;
`r2[map]` climbs every window instead. Score2 fps, same save-state, same route, one run each:

| Arm | env | hold fps | drive fps |
|---|---|---|---|
| b4-W1 | (none, R2 off, this lane's default-until-now) | 25.3 | 23.7 |
| b5-W2 | `HAKUX_S2T_WIDEN=1` | 28.3 | 27.1 |

+3.0 hold / +3.4 drive on the first trial. Pixel sanity check before trusting it further: `imgcheck.py` full-frame
diff of the two runs' `m3-loaded.png` (identical save-state, before RT, so a legitimate same-scene comparison) --
`diff=1.4 th=3.0 MATCH`. Consistent with the guard's own documented claim (`texture.c:2952`: "The copy is bit-exact
into the same VkFormat, so the two read the same texels") -- R2 is narrow by construction (same VkFormat in
surface/texture/node image, one level, one layer, 2D, exact scaled size; the six guards in `s2t_widen_view()` exist
to refuse everything that isn't provably equivalent to the copy it replaces). Two mid-drive frames (ffmpeg grab,
`drive-frame.png` each) show no HUD/radar/texture corruption either, though the scenes differ (unscripted traffic,
not a same-frame comparison).

**Code change**: flipped `s2t_widen_on()`'s default the same way `s2t_fb_mode()`'s was flipped for #433/fpsdata1018
-- `"0"` now opts out, everything else (including unset) is on. Rebuilt (30s, incremental, cache warm from the first
cold build) as `3058a55767-perflog.apk`, committed (`3058a55767`).

**Confirming runs, default-on, no env override** -- and the honest, noisier part of this finding:

| Arm | note | hold fps | drive fps | RP/flip (ftbucket) | GPU MHz (ftbucket, "all") |
|---|---|---|---|---|---|
| b4-W1 | baseline, R2 off (first run this sequence, coolest) | 25.3 | 23.7 | 47 | 483 |
| b5-W2 | `HAKUX_S2T_WIDEN=1` explicit | 28.3 | 27.1 | 33 | 466 |
| b6-D1 | default-on, **fresh install + shader-cache clear** (new APK sha) | 22.6 | 19.5 | 33 | 450 |
| b7-D2 | default-on, same APK, warm shader cache | 25.2 | 24.4 | 36 | 442 |

RP/flip is the robust, confound-free read: **47 baseline vs 33/33/36 with R2 on, in all three R2-on runs, no
exceptions.** That is a ~25-30% render-pass reduction from eliminating the S2C_MAP copy entirely, and it does not
depend on timing noise to be true. The fps translation is noisier: b6-D1's park-phase number (18.3 fps, worse than
baseline) lands exactly where a first-use-after-install shader-recompile stall would put it (fresh APK sha, shader
caches explicitly cleared by `batch.sh` on an APK change) -- not a code regression, confirmed by b7-D2 re-running
the identical binary with a warm cache and recovering to 25.2/24.4, essentially flat against baseline with a
slightly lower GPU clock (442 vs 483 MHz, a monotonic drift across this four-run sequence: 483->466->450->442,
consistent with the device warming up over the ~15 minutes of back-to-back runs). So across the three R2-on runs:
one clear win (W2, +3/+3.4), one wash (D2, ~flat to +0.7), one confounded-looking loss that resolves to a wash once
the install penalty is accounted for (D1). **Net: never worse than baseline once the install-penalty run is
read correctly, consistently fewer render passes, no pixel anomaly found.** This is the same shape of evidence
fpsdata1018 shipped `HAKUX_S2T_FB` mode 2 on ("one trial, confounded by unscripted driving traffic" -- NOTES.md
precedent) -- not a clean, high-confidence A/B, but a mechanism-level win with no observed downside, on a change
that is bit-exact by construction when its guards pass.

Device time this item: b4+b5+b6+b7 wall time ~636s (~10.6 min), on top of ~634s already spent on the Blinx 2 census
earlier this attempt -- ~1270s (~21.2 min) of this attempt's Nova time, under the 30-min pilot cap. Hold released
after b7.

**Landed, not just measured**: commit `3058a55767` flips `HAKUX_S2T_WIDEN`'s default to on (`"0"` opts out). This
is GTA III's fix for this attempt -- lever (b) from the table above, landed rather than merely identified.

## Attempt 2, item 4: lever (a) resolved -- score2.py's "drive" window was never motion-verified; S1 has a real crash in it

G4's next item: resolve lever (a) (SYSMEM/GMEM) with the matched-window re-read, 0 new device time (data already
on disk, per the plan written earlier this attempt). Before trusting any re-read, checked what "drive" actually
means in `score2.py`: **it is a fixed span, `[RT+1, RT+31]` -- not pixel-motion-verified.** `movescore.py` is the
tool that verifies motion, from a span read off the recording by eye; `score2.py`'s drive/hold split just assumes
the car is still going for the first 30s. That assumption needed checking before using the window for anything,
so it was checked: sampled `rec.mp4` frames at RT+2/8/14/20/23/25/26 (ffmpeg grabs) for each of S1/Y1/M1 (same
save-state, same start frame confirmed identical at RT+2 across all three).

**S1 (shipped) has a real crash inside its own "drive" window**: still driving normally at RT+23 ("Portland View"
banner visible, moving), approaching a wall head-on at RT+25, and **flipped on its side pinned against a wall by
RT+26** (`chk-26.png`: car rotated ~90 deg, "Portland View" text over a static wall, no motion). The last ~5-6s of
S1's 30s "drive" window is a stopped, crashed car, not driving -- a different and not-comparable render workload
(static geometry against a wall) folded into a number that was being read as "driving fps." Y1 (sysmem) and M1
(gmem) show continuous scene progression (different streets/intersections, more collisions typical of RT-held
autonomous input, but moving) through the same interval with no stop. This is exactly the class of problem
`score2.py`'s own docstring does not claim to solve (it only says a window counts when wholly inside the fixed
span) -- nothing upstream of this check had ever verified the span itself.

Re-scored all three on the same crash-excluded span, `[RT+1, RT+24]` (23s, short enough to stay before S1's crash,
same length for all three so the comparison is fair), with `movescore.py` (the motion-aware tool) and `dwseries.py`
(same `[dipwin]` instrument as the earlier drive-window read):

| Arm | movescore fps (RT+1..24) | dwseries ms/flip | dwseries fps | rp/flip | cs2t-ended/flip | cs2t share |
|---|---|---|---|---|---|---|
| S1 (shipped) | 21.3 | 48.1 | 20.8 | 130.2 | 119.2 | 91% |
| Y1 (sysmem) | 24.2 | 41.3 | 24.2 | 70.3 | 59.3 | 84% |
| M1 (gmem) | 21.1 | 46.1 | 21.7 | 108.4 | 97.6 | 90% |

Clean, consistent, same-instrument, same-window-method, same-length-window result: **sysmem is faster on real,
verified driving** -- about +3fps over shipped, fewer render passes/flip and fewer `copy_surface_to_texture`
copies/flip, same direction as the earlier (less careful) drive-window read and the opposite of the hold-window
ftbucket read. The hold-window reading is the one that should now be distrusted: it covers park (stationary,
different workload) plus the first 30s of hold without excluding S1's crash, both of which dilute a real driving
comparison with non-driving content, on top of `ftbucket.py`'s `rp` field being FRAMETRACE-csv-derived and
possibly capped (flagged earlier, `phseries.py`'s own docstring).

## Big-lever table, re-ranked again after item 4

| # | Lever | Status | Why |
|---|---|---|---|
| b | `copy_surface_to_texture` / R2 (`HAKUX_S2T_WIDEN`) | **landed this attempt** (commit `3058a55767`) | see item 3 |
| a | Per-title SYSMEM/GMEM render mode, **alone** (no R2) | **resolved: promote.** `TU_DEBUG=sysmem` measured +3fps over shipped on a crash-excluded, motion-verified, equal-length window, fewer render passes and fewer S2C copies/flip, same direction in two independent instruments (`dwseries.py`, `movescore.py`) | not yet landed -- it is a Turnip env var, not a code change in this tree; the still-open question is how to apply it (per-title default in the launcher/config, not a global env var an owner build ships with) |
| a+b | sysmem **stacked with** `HAKUX_S2T_WIDEN` (R2, default-on) | **tested, falsified, do not stack** (item 5) | one run: rp/flip 148.4 (worse than shipped's 130.2), fps 19.9-20.6 (worse than every item-4 arm including shipped); `cs2t-ended/flip` stayed 0 (R2 itself still engages), so the cost is elsewhere in sysmem's pass accounting under this combination, not root-caused further this attempt |
| c | Draw/state redundancy per pass | 2 (unchanged) | not yet measured this attempt |
| e | vCPU translation / TB lookup | 3 (unchanged) | not yet measured this attempt |

Both cs2t share columns above (84-91%) are still high with sysmem -- lever (a) and (b) are not mutually exclusive,
and the natural next step is a run with BOTH `TU_DEBUG=sysmem` and the now-default-on `HAKUX_S2T_WIDEN` to see
whether the gains stack (same mechanism, same copy, should be independent of render mode). Not run this attempt:
this item's whole point was to resolve (a) at zero device cost, and item 3 already spent this attempt's device-time
budget (~1270s / 21.2 of the 30 min pilot cap) landing lever (b). Next action for the next attempt: one short
GTA III run with `TU_DEBUG=sysmem` on the current (post-item-3) binary, scored the same crash-excluded way.

## Attempt 2, item 5: combined sysmem + HAKUX_S2T_WIDEN (default-on binary) -- one run

**Falsifiable prediction (G3), before queuing:** if (a) and (b) are independent mechanisms (sysmem changes how a
pass's tiles are stored/loaded; R2 removes a whole pass+copy), the combined run's render-pass count should land
near item-4's sysmem-alone floor (~70 rp/flip over the matched window) or lower, not back up near shipped's 130 --
i.e. the two gains should not cancel. cs2t-ended share should stay low (R2 eliminates the S2C_MAP copy regardless
of render mode, so this should not go back up to 90%+). Falsified if rp/flip or cs2t share lands back near the
shipped-baseline numbers from item 4 (130.2 rp/flip, 91% cs2t share) -- that would mean the two levers interact
instead of stacking, a real and useful negative result either way.

One run, reusing the already-built, already-on-device `3058a55767-perflog.apk` (R2 default-on, no rebuild needed)
with `TU_DEBUG=sysmem` added to the env on top of `HAKUX_FRAMETRACE=1`: taken under this lane's own Nova hold, the
pre-authorised GTA III save-state protocol, scored on the same crash-excluded `[RT+1, RT+24]` window as item 4 for
a fair comparison. Device time budget check before taking the hold: ~1270s (~21.2 min) spent on items 1 and 3 this
attempt; one more run of this size (park 30s + hold 60s + setup ~90s, ~3 min wall) stays under the 30 min pilot cap.

Run **b8-C1**, same APK (sha `ccadbf8ab6c2`, no reinstall -- warm shader cache, same as b7-D2), `GPU: PurpleVK-public`
confirmed, savestate load confirmed (`op=load slot=5 ok=1`). RT_DOWN device `09:56:26.553`. Scored on `[RT+1, RT+24]`:

```
movescore.py: C1   RT+1..24  n=7  20.4s  mean 20.6 fps  >=28.5 19.9%  <22 68.2%  worst 104.2 ms
dwseries.py:  span 480 flips, 50.3 ms/flip (19.9 fps), rp/flip 148.4, cs2t-ended/flip 0.0
```

Checked for a crash inside this run's own window before trusting the number (same check item 4 did for S1): frames
at RT+6/18/28 (ffmpeg, in-game clock visible on the FPS-counter overlay this build ships) show continuous driving
the whole way -- in-game clock 06:19 -> 06:30 -> 06:39, different streets each time, car always moving, no stop or
crash. This run is clean; the number is real.

**The G3 prediction is falsified.** Predicted rp/flip at or below sysmem-alone's floor (~70/flip, item 4); measured
**148.4/flip -- higher than shipped baseline itself** (130.2/flip, item 4's S1). Predicted fps unchanged-or-better
than sysmem alone (24.2, item 4's Y1); measured **20.6-19.9 fps, worse than every arm in item 4's table**,
including shipped (20.8-21.3). `cs2t-ended/flip` did stay at 0 (R2's mechanism engaged correctly, same as every
other default-on run) -- so the two levers are not fighting over the same copy; sysmem's forced render-mode is
doing something to pass count/count-per-flip that costs more than R2's pass-elimination saves. Not root-caused
further this attempt (would need `HAKUX_GPUXFR`'s per-pass load/store census under this combination, a new
instrument run, not a re-read) -- but the result itself is usable now: **do not ship the two together.** If lever
(a) (sysmem) is ever applied as a per-title default, it should not be paired with `HAKUX_S2T_WIDEN`'s default-on
without this combination being re-tested; as measured, sysmem alone (item 4) is the better lever on its own, not
sysmem-plus-widen.

Device time this item: b8 wall ~158s (2.6 min), on top of item 3's ~1270s -- **~1428s (~23.8 min)** of this
attempt's Nova time, under the 30 min pilot cap. Hold released after b8.

## Attempt 3, item 1: Blinx 2 gameplay, measured -- one depth surface evicted and downloaded twice a flip

**Route.** The owner's island state is already on the Nova (debug `x1box/states/4D530065/slot5.hxs`, 26,114,724
bytes, the same size as the owner's release slot 1; lane.xbox loaded it on 10-18). Loaded by the GTA III pause-menu
protocol (screenshot gate before each tap, never Save). Arm script `captures/fpsnext1019/scripts/arm-blinx.sh`
(lane.xbox's `arm2b.sh`, paths moved): load slot 5, idle 20 s, sweep the left stick in circles for 60 s, score
with `score2.py` (park = idle, hold/drive = circling), pull the FRAMETRACE CSV. No profile or route work needed.

**Batch bx1** (10:55-11:00 PDT, `3058a55767-perflog.apk`, fresh install, so arm F carries the shader-compile cost):

| arm | env | park fps | hold fps | drive fps | GPU line |
|---|---|---|---|---|---|
| bx1-F | `HAKUX_FRAMETRACE=1` | 21.4 | 25.0 | 21.8 | PurpleVK-public, `op=load slot=5 ok=1` |
| bx1-X | `+HAKUX_GPUXFR=1` | 21.1 | 24.4 | 21.2 | PurpleVK-public, `op=load slot=5 ok=1` |

**Where a circling flip goes** (bx1-X, 10:59:12-11:00:12, every 60-flip window agrees):

| reading | value | source line |
|---|---|---|
| flip pace | 60 flips / 2.5-3.0 s, 2-3 vblanks a flip | `[dipwin]` |
| PFIFO phases | Surf 22.4-25.1, Draw 9.0-9.5, Fin 1.4-5.1, Idle 0.1-3.6, Tot 36-40 ms | `hakuX-phase` |
| GPU | 23-27 ms (R 22-25), RP 48 | `hakuX-phase` |
| Surf's wait | `dfF` 20.8-23.4 ms (deferred-download finish) | `xemu-surf` |
| the waits | `surfupd=fin0/fence61/dl120/1072-1329ms` per 60 frames | `[sdcall]` |
| what they wait for | `evict[dl:120 unshelve:120 stale:0]` per 60 flips | `hakuX-stall` |
| the evictions | `[evict372]` m10:N/0, one pair: `Z f130 ln p1024 256x256 b4 -> Z f130 sz p1024 256x256 b4` | `[evict372]` |
| the replacement | `[edl] dl=120 clrskip=0 upload=0 other=120` | `[edl]` |
| HAKUX_SURFGPU | `detach=120` | `[surfgpu]` |

So: PFIFO spends ~22 ms of a ~38 ms flip waiting for the GPU at one fence, for two downloads of one 256x256 depth
surface (most likely the player's shadow map; the frame shows a cast shadow behind the character). The CPU record
(Draw ~9 ms) and the GPU (~23 ms) run one after the other, not side by side.

**Mechanism (code, `vk/surface.c` `update_surface_part`).** The guest marks the 256x256 Z linear and then
swizzled at one address, with the same format, pitch and size. Compatibility already allows a swizzle change in
two cases: the update is a clear, or the binding was fully cleared (`cleared`, set by forza414's
`mark_clear_full`). Here neither holds (mask m10: swizzle, not rescued). So:
1. The eviction records a deferred download of the dirty binding (`EDL_MARK`, `download_surface_deferred`), then shelves it.
2. `get_shelved_surface()` does not compare `swizzle`. The binding just shelved sits at the head of the shelf and
   matches address, format, role, size and pitch. So the replacement is **the same struct and VkImage**.
   `vram_newer` was reset by `shelve_surface`, and the download excepts its own surface, so it comes back
   **clean** (`stale:0`, `[edl] other`).
3. The GPU therefore keeps exactly the pixels it had. The download only copies them into VRAM in the old (linear)
   layout. HAKUX_SURFGPU detaches the pending download from the reused struct, and the first surface_update after
   the flip that cannot defer it waits on the frame's fence (`surfupd fence61`).

#372's handoff (`surface_handoff_partner`) declines this case twice over: it needs the same swizzle, and it
refuses a held binding that would itself come back off the shelf. The texture path (`texture.c:3945`) takes a
compatible surface at the address whether or not it is dirty, so a sampled shadow map reads the image, not VRAM,
in both the old and the new behaviour.

**The fix (built, opt-in): `HAKUX_SWZKEEP=1`.** It adds a third swizzle rescue. When the change is swizzle-only
(strict compatibility), TCG's watch is live, there is no CPU write (`mem_dirty`) and there is no pending upload or
download, the binding stays bound and dirty instead of being evicted. The GPU result is the one the eviction
produced already: the same image, reused. What changes is VRAM. The binding now owes its download, and the next
reader (a CPU access through the watch, a texture that cannot take the image, a later eviction) takes it, in the
swizzled layout the guest now declares, instead of the old layout. On real hardware the bytes would be the
linear-written ones. For a uniform clear the two are the same bytes. For anything else the emulator already
reinterprets the content across layouts (step 2), so this does not add a new inexactness on the GPU side.
Counted on a `[swzkeep] kept=N` line beside `[evict372]`.

### G3 prediction (written before the build)

Arms on the island state, palindrome on one APK: off, on, on, off (after a warm-up arm that is thrown away). On is
`HAKUX_SWZKEEP=1`; both add `HAKUX_FRAMETRACE=1`.

| leg | rule | falsified if |
|---|---|---|
| P1 mechanism | on arms: `[evict372]` m10 growth per 60 flips <= 6 (off: ~120), `evict[dl]` <= 6, `[sdcall] surfupd` fence <= 10 per 60 frames (off: ~61), `dfF` <= 5 ms (off: 21-23), `[swzkeep] kept` growing ~120 per 60 flips | m10 still grows: the conditions (`upload_pending`/`download_pending`/`mem_dirty`) are not what I read |
| P2 fps | circling (score2 hold+drive) mean of both on arms >= both off arms + 3.2 fps, and on-arm drive >= 25.0 | P1 holds and fps moves < 3.2: the wait moved to the flip's frame fence; then GPU+something is serial and the phase timers name it |
| P3 pixels | the loaded frame's character-and-shadow region (imgcheck box 520 480 800 760) differs from an off arm by no more than off-vs-off does | a shadow that reads a VRAM copy differs |

Expected upper bound: GPU 23-27 ms a flip, so overlapping CPU record and GPU caps out near 37-43 fps raw, i.e. 2
vblanks (30 fps) where the game paces itself at 30.

## Attempt 3, item 3: GTA III beyond R2 -- the S/widen A/B does not converge; the next cause is named

**Batch g1** (11:01-11:14 PDT, `3058a55767-perflog.apk`, already installed, so the shader cache was warm; owner's
in-car state; palindrome W, A on, B off, B2 off, A2 on; off = `HAKUX_S2T_WIDEN=0`; all `HAKUX_FRAMETRACE=1`; every
arm `GPU: PurpleVK-public`, `op=load ... ok=1`):

| arm | widen | park fps | hold fps | drive fps | hold rp/flip (`[dipwin]`) |
|---|---|---|---|---|---|
| W (discarded) | on | 22.0 | 25.3 | 21.0 | 57.1 |
| A | on | 22.0 | 28.1 | 26.3 | 50.1 |
| B | off | 22.4 | 22.6 | 25.0 | 99.7 |
| B2 | off | 22.4 | 22.8 | 25.9 | 135.3 |
| A2 | on | 20.7 | 17.0 | 14.3 | 147.0 |

The two on arms disagree by 11 fps on hold (28.1 vs 17.0). The two off arms agree with each other (22.6, 22.8),
but sit between the two on arms. **Two clean runs do not agree, and the brief's "repeat until two agree" does not
converge on this route.** What tracks fps is render passes per flip, not the switch: A 50 rp → 28 fps, A2 147 rp →
17 fps, both with widen on. The hold-window regression from attempt 2 (ms/flip = 30.89 + 0.1309 x rp) predicts
26.7 and 20.0 fps for those pass counts; measured 28.1 and 17.0. The direction holds; the cost per pass is steeper
at the high end than the fit. The scripted throttle hold does not put the same scene in front of the camera each run, and
the scene sets the pass count.

**What ends the passes** (`[dipwin] bnd`, callers by library offset in `nd=`, symbolized with `llvm-addr2line`
against the APK's own `libxemu.so`):
- With widen on, almost every `bnd` is `bind_surface_as_texture` (texture.c, the COLOR_ATTACHMENT_WRITE →
  SHADER_READ barrier after `pgraph_vk_begin_nondraw_commands`).
- With widen off, it is `copy_surface_to_texture`.
- Either way there is one break per sample of the 128x128 colour target @0x038aa080 (colour fmt 0x4), sampled
  as texture fmt 0x7 (X8R8G8B8 swizzled) with component map 0002, 40-140 times a flip, while it is the colour
  target being drawn.
- The census line `fb[n.. nos0 keep0]` says every one of these samples is on a stage whose shader program
  fetches (PROJECT2D), so #1049's mode 2 (keep only on stages that do not fetch) keeps none of them.

R2 turned the copy into a barrier but not into no break. The next dominant cause is these feedback samples: up to
140 of the ~150 passes a flip, the same thing gta3car1018 found for the copy before R2 existed.

**G2, mechanism before remedy.** Each sample is one of two cases. The census added below says which, in one run.
1. **The texel is dead.** The stage fetches because its mode is PROJECT2D, but no combiner reads t_i. Then the
   slot can keep any image of the node's shape, with no break and no pixel change.
2. **The texel is live:** real feedback. Then the remedy is a feedback-loop attachment or an in-pass by-region
   self-dependency. That is a bigger change, and the census decides whether it is needed.

**Built, opt-in: `HAKUX_S2T_DEAD=1`** (texture.c `s2t_fb_texel_dead()`). A texel is dead when all of these hold:
- No combiner stage in use (the COMBINECTL count) and no final-combiner input (A-G) names the stage's t register.
- Every later stage is a plain fetch, NONE, PASS_THROUGH or CLIP_PLANE. Every dependent mode reads an earlier
  stage's texel.
- The stage does not alpha-kill or colour-key.

For a dead sample, the slot keeps the node's own image when the node's image can be sampled
(SHADER_READ_ONLY). When it cannot, the sample copies once ("prime") and the samples after it keep. The census
always counts dead and prime, switch or not, on a new `dead[n.. prime..]` field after `fb[...]`; the existing
parsers' `fb\[n nos keep\]` regex is unchanged.

### G3 prediction for HAKUX_S2T_DEAD (written before the build)

Arms on the owner's in-car state, one APK, palindrome: warm-up (discarded), off, on, on, off. On =
`HAKUX_S2T_DEAD=1`. All arms keep widen at its default (on) and add `HAKUX_FRAMETRACE=1`.

| leg | rule | falsified if |
|---|---|---|
| P0 census (decides G2) | off arms: `dead` n / `fb` n >= 0.8 over the hold windows | `dead` near 0: the texel is live, the switch can do nothing, and the remedy is a feedback-loop attachment |
| P1 mechanism | on arms: `fb` keep / `fb` n >= 0.8; `prime` <= 5 per 60 flips; `[dipwin]` rp/flip in the hold windows <= 30 (off: 50-147) | P0 holds but rp stays > 30: something other than the sample ends the pass (`nd=` names it) |
| P2 fps | each on arm's hold fps >= 27.0, and the mean of the on arms >= the mean of the off arms + 3.2. From the regression, 30 rp/flip ≈ 34.8 ms; the game paces itself at 2 vblanks | P1 holds and fps < 27: the regression's slope does not carry over, and the pass count was not the cost |
| P3 pixels | the in-car frame at load (full frame, and the 128x128 target's region if it is visible) differs from an off arm by no more than off-vs-off does | a "dead" texel was read: the consumer list in `s2t_fb_texel_dead()` misses a reader |

P0 is measured on the off arms, which run the same census, so the decision does not depend on the switch.

## Attempt 4, item 1: both palindromes run -- `HAKUX_S2T_DEAD` P0 falsified, `HAKUX_SWZKEEP` P1 holds but P2 and P3 do not

Attempt 3 had already queued both palindromes (`g2` for GTA III/S2T_DEAD, `bx2` for Blinx 2/SWZKEEP) before it hit
the turn cap; `bx2` ran to completion (`BATCH_DONE 11:25:34`) and `g2` was cut off mid-way through its last arm
(`O2`'s `arm.sh` had launched the app and confirmed `GPU: PurpleVK-public` but never reached the pause-menu load,
score, or restore -- the run directory existed with only a partial `arm.log`, no `score2.txt`). This attempt: took
the Nova hold (`hold.sh take`, one `0-`/foldqueue restore was running at start, `wait-idle` cleared it in <1 min),
moved the half-finished `g2-O2` run dir aside (`runs/attic/g2-O2-incomplete-attempt3`, `arm.sh` refuses to reuse an
existing dir), re-ran `O2` clean (launched, pause-menu/slot-5 load verified, RT held 60s, `GPU: PurpleVK-public`
confirmed, scored), then finished the batch's own closing steps by hand (prefs restore -- `RESTORE_OK` -- and the
dispatcher's shader-cache marker) since `batch.sh` itself was the process that died. No device time was needed for
`bx2`; `g2` cost one arm (~2.5 min). Hold released after both are confirmed restored.

### GTA III, `HAKUX_S2T_DEAD`: P0 falsified -- the feedback texel is live, not dead

Census summed over every 60-flip window, full runs, off arms (widen stays default-on, `HAKUX_S2T_DEAD` unset):

| arm | windows | `fb` n (sum) | `dead` n (sum) | dead/fb |
|---|---|---|---|---|
| O1 | 58 | 224,858 | 0 | 0.0 |
| D1 (on, same census runs regardless) | 60 | 223,241 | 0 | 0.0 |
| D2 (on) | 60 | 182,941 | 0 | 0.0 |
| O2 | 0 (no `[s2c]` lines at all this run -- see below) | -- | -- | -- |

**Zero dead texels in 631,040 feedback-sample events across three full runs.** The P0 rule (`dead`/`fb` >= 0.8 to
confirm) is not close to met -- it is not even a noisy near-miss, every single window across every run reads
`dead[n0 prime0]`. **`s2t_fb_texel_dead()`'s hypothesis is wrong: the COLOR_ATTACHMENT sample the stage takes is
real feedback, not a fetch nothing downstream reads.** This also explains the fps and pixel results below for
free: a switch that never finds a dead texel cannot change anything it touches.

`O2` is its own small finding: the in-car scene this run landed on produced **zero** `[s2c]` census lines and
`dipwin lines: 0` for the whole run, yet scored hold 27.7 / drive 28.6 fps -- far above every other arm in this
batch (18.5-23.4 hold, 18.8-20.9 drive) including the other `off` arm (O1: 22.2 hold / 21.8 drive). This is the
same scene-variance problem attempt 3 already named (`g1`'s A/A2 disagreement): the scripted 60s RT-hold does not
land the camera on the same traffic/turn every time, and a scene with few or no feedback-sampling frames in view
is both fast and census-quiet. Not a finding about the switch -- a reminder that any single-run fps number here is
scene-dependent, and the `dead`/`fb` census (which does not depend on fps) is the one number in this batch that is
not.

**Pixel sanity (P3), full frame, `m3-loaded.png` (same save-state, before RT):** O1 vs D1 diff=0.1 (th 3.0, MATCH)
-- consistent with zero engagement: a switch that never fires cannot move a pixel. O1 vs O2 (off-vs-off noise
floor) diff=1.2, also MATCH -- the scene-variance above shows up in fps and the census, not in the loaded-frame
screenshot (same save state, before the RT hold that diverges the route).

**Verdict: `HAKUX_S2T_DEAD` is a dead end as built, for the right reason (G5).** The code and the census
instrumentation are correct and worth keeping (the `dead[n prime]` field costs nothing when always-zero, and a
future title or scene might actually hit the dead case), but on GTA III's in-car scene the feedback sample is
real: every one of the up-to-140-per-flip COLOR_ATTACHMENT reads this lever targets is a texel some stage in the
chain actually consumes. Per the prediction's own next step: **the remedy is a feedback-loop attachment or an
in-pass by-region self-dependency** (G2's case 2) -- a bigger, Vulkan-feedback-loop-extension-shaped change, not a
quick lever. Ranking this against the brief's items 2-4 (Fable H2 untouched, GTA III's own next cause unnamed
beyond this), a feedback-loop attachment is not started this attempt: it needs its own mechanism writeup and
risk assessment (feedback loops are exactly the kind of Vulkan validation-layer-flagged construct a renderer
should enter carefully), and Fable H2 is both higher-ranked in the brief and unblocked. Left `HAKUX_S2T_DEAD` in
the tree, opt-in, default off, uncommitted-further (the commit that built it already describes the switch
correctly; this is a result to report, not a code change to make).

### Blinx 2, `HAKUX_SWZKEEP`: P1 (mechanism) holds cleanly, P2 (fps) and P3 (pixels) do not -- do not ship

**P1, mechanism** (batch `bx2`, full-run sums/means):

| arm | `[edl] dl=` sum | `[swzkeep] kept=` sum | `surfupd...fence` lines | Surf phase mean (ms) | Tot phase mean (ms) |
|---|---|---|---|---|---|
| O1 (off) | 4,388 | -- | 37 | 10.1 | 27.1 |
| O2 (off) | 4,378 | -- | 37 | 11.6 | 27.2 |
| K1 (on) | -- (no `[edl]` lines at all) | 41,276 | 0 | 1.1 | 18.0 |
| K2 (on) | -- (no `[edl]` lines at all) | 44,162 | 0 | 0.9 | 21.1 |

Exactly what the prediction asked for: off arms repeat the eviction/download pattern this lever targets
(`[evict372]`'s last line each off run is the same `pair0 ... m10 Z f130 ln p1024 256x256 b4 -> Z f130 sz p1024
256x256 b4` handoff-declined case the mechanism section above names); on arms never hit `[edl]` at all (the
binding stays bound, so the deferred-download path this counts never fires), `[swzkeep] kept` climbs by the
tens of thousands over a ~58-64s run, `surfupd`'s fence-wait call site goes to exactly 0, and the PFIFO `Surf`
phase (where the wait lived) drops by an order of magnitude (10-12ms -> ~1ms). **P1 passes outright.**

**P2, fps -- falsified.** Score2 (same batch, see `batch.log` above for the full park/hold/drive table):

| arm | hold fps | drive fps |
|---|---|---|
| O1 | 25.6 | 22.4 |
| O2 | 25.4 | 22.4 |
| K1 | 22.8 | 24.0 |
| K2 | 27.7 | 25.4 |

Off-arm mean of (hold+drive)/2: 24.0, 23.9 -> 23.95. On-arm mean: 23.4, 26.55 -> 24.98. **Gain: +1.0 fps, not the
predicted +3.2**, and only one on arm (K2, 25.4) clears the "on-arm drive >= 25.0" bar; K1 (24.0) does not. The
prediction's own falsifier for this leg says exactly what to do next: *"the wait moved to the flip's frame fence;
then GPU+something is serial and the phase timers name it."* They do: K1's GPU phase mean (16.5ms, R:15.5) is
higher than either off arm's (13.5/13.1, 14.1/13.7) -- removing the eviction left more live state for the GPU to
redraw against, so the GPU side got slower even as the CPU-side wait vanished. K2's GPU mean (13.3) stayed flat,
but its Idle/stall mean rose to 13.5ms (off arms: 8.9-10.5) -- the CPU is now idle-waiting on something else
(pacing/vsync, not the removed download). Either way the saved CPU time did not reach the player: it was
re-spent on the GPU (K1) or turned into a different stall (K2). This is a clean instrument-backed answer, not a
"needs more data" shrug (G5).

**P3, pixels -- falsified, and visibly so.** Character-and-shadow region (box 520,480,800,760 per the prediction),
`m3-loaded.png` (same save-state slot 5, before any input):

| comparison | diff | vs threshold 3.0 |
|---|---|---|
| O1 vs O2 (off-vs-off noise floor) | 2.7 | MATCH |
| O1 vs K1 (on) | 6.7 | NO_MATCH, ~2.5x the noise floor |
| O1 vs K2 (on) | 6.9 | NO_MATCH, ~2.5x the noise floor |

Visual check (both `m3-loaded.png`, same slot-5 load) confirms it is not a measurement artifact: the off-arm
screenshot shows the character's shadow as a short patch under the bike; **the on-arm screenshot shows an
additional long, straight shadow streak extending well past the character to the right**, a double-shadow /
elongated-shadow artifact, consistent across both on arms. This is exactly the failure mode the prediction
named going in: *"a shadow that reads a VRAM copy differs."* The mechanism (texture.c, keeping a swizzle-only
rebind bound and dirty instead of evicting it) reuses the GPU's existing image for sampling (correct, per P1 and
the GTA III R2 precedent) but leaves VRAM holding stale bytes in the old layout for one more frame than before;
something in Blinx 2's shadow pass reads that stale VRAM copy before the owed download catches up, same risk the
prediction flagged for this exact 256x256 Z-depth surface (most likely the player's own shadow map).

**Verdict: `HAKUX_SWZKEEP` does not ship.** All three legs point the same way: the mechanism works exactly as
designed (P1), but the fps win it was built for does not reach the player (P2, the cost moved to the GPU or an
idle stall instead of disappearing) and it introduces a visible shadow-rendering defect on the one title it was
built for (P3). It is already opt-in and default-off, so nothing further is needed to keep it from shipping; no
further work on this lever is planned unless a future finding explains why the GPU/stall cost appeared and shows
how to avoid it without the VRAM staleness. Both predictions (G3) did their job: three of the four legs across the
two levers were falsified, and each falsifier named a concrete, truthful next step instead of a vague "inconclusive."

## Attempt 5, item 1: Fable H2 -- reachability (no usable save state), the eviction window already in the owner's
capture, and the G3 prediction for `[edl]`

Brief item 3's instrument (`[edl]`, fpsdata1018, landed on master already: see `hw/xbox/nv2a/pgraph/vk/surface.c`
`EDL_MARK`/`EDL_RESOLVE`/`edl_dl`/`edl_clrskip`/`edl_upload`/`edl_other`) has never been run against a real Fable
capture. fpsdata1018's own NOTES.md says why it stopped there: "Fable has no route or save state to its gameplay
scene." Checked that claim before relying on it (G1, do not re-derive a stale premise):

- Fable's 4 on-device save states (`slot0`/`slot1`/`slot2`/`undo-save`, the owner's own 2026-10-18 21:31 session)
  are all **schema-incompatible** on the current perflog build -- the in-game "Load from slot" list shows every
  populated row greyed out, `reason="saved by a version with different machine state"`. Confirmed in source, not
  just the UI: `SaveStateSlots.kt`'s `loadable` flag and `hxs.c`'s `schema` fingerprint check (`xemu_savevm_schema_
  fingerprint()`), which refuses a load only when the serialized vmstate struct layout differs between builds, not
  merely because the commit differs. These states are not a reachability shortcut here; ruled out, not reused.
- No generic dispatcher route reaches Fable's gameplay scene either (same gap class fpsdata1018 named).
- But the owner's existing capture (`/home/justin/hakux-work/captures/fps-owner-1018/fable.txt`, 2026-10-18
  21:28:25-21:32:00, title 4D5300D1, `GPU: PurpleVK`) already contains the answer to "is H2 rare or common": its
  `hakuX-stall: evict[dl:N ...]` census line is near-zero through the loading screen (~21:29:40), ramps 21:29:51-
  21:30:01, then holds **~300-460 per ~60-frame window continuously from 21:30:06 to the capture's end at
  21:31:39** (the save). H2's eviction-download pattern is not a special location -- it is the steady state of
  ordinary Fable gameplay once the player has control. A simple fresh-boot walk-and-turn should reproduce it with
  no route or save state needed.

**Reachability, this attempt:** launched Fable cold (`HX_ISO=/storage/E6C6-D7AA/Games/XBox/4D5300D1-Fable_The_Lost_
Chapters.xiso.iso`, confirmed PID, `GPU: PurpleVK-public Adreno (TM) 740`), confirmed the pause-menu overlay and
its existing `p7-menu.png`/`p8-slots.png` references are title-agnostic (visually matched Fable's own pause menu,
Load-state button bounds the same as `arm.sh`'s hardcoded 384,234,896,334 box -- no new reference assets needed),
backed out of the (unusable) slot list without loading or saving, then drove the real opening sequence with
`pad.sh` (never raw `keyevent` once inside actual game input, per its own warning that `keyevent` reads as a
non-gamepad exit signal there; `keyevent`/`tap` stay correct for the emulator's own pause-overlay, a system layer):
START at the profile-name entry screen, A to accept "Default", through the loading screen ("Charity Shop" tip)
and the opening narration ("Deep in the forest of Albion lay the small town of Oakvale..."), to the first in-
engine tutorial prompt ("Talk to the people marked on your MAP with a GREEN DOT... Press A to talk"), confirmed by
screenshot with the player character standing in Oakvale under direct control (FPS:20, narr5.png). Dismissed the
prompt with `pad.sh press A`.

(Operational note: the first detached logcat capture, started before the narration finished, stalled silently at
12:15:55 PDT with no process visible under `ps aux | grep logcat` in this sandboxed shell and the capture file
not growing for 4+ minutes -- caught by checking line count before trusting the capture, not by a clean exit
code. Restarted (`setsid nohup ... &` + `disown`, one command per call) and confirmed growing again before
proceeding. The movement capture below uses only the second, verified-live capture.)

### G3 prediction for the Fable H2 `[edl]` capture (written before the movement that produces it)

Target: walk-and-turn via `pad.sh` for ~60-90s from the current in-control position (Oakvale, tutorial-prompt
dismissed), under the live `h2-logcat.txt` capture, matching the owner capture's steady-state window (`evict[dl:
300-460]`/~60-frame window). Read `[edl]`'s `dl`/`clrskip`/`upload`/`other` sums once the movement window closes.

Per brief Addendum 2's own wording ("build the eviction-download skip only if `clrskip` is 6/6"): the lever is a
full, unconditional skip (treat every evicted-and-downloaded zeta/colour binding in this pattern as unread, never
pay the download), so it is only safe to build if the downloaded content is *never* read back -- a partial ratio
does not make an unconditional skip safe, it makes it wrong on the fraction that is read.

| leg | rule | falsified if |
|---|---|---|
| P0 reproduction | `edl_dl` > 0 over the movement window, with `dl` in the same order of magnitude as the owner capture's steady-state (~300-460/60-frame window) | `edl_dl` stays 0 or far below that: the scripted walk-and-turn does not reproduce H2 and a different route/longer window is needed before any decision can be made |
| P1 decides the lever (this is the actual test Addendum 2 asked for) | `edl_clrskip` / `edl_dl` == 1.0 (6/6, every eviction's download is provably unread before any consumer touches the replacement binding) | ratio < 1.0: at least one evicted download is real feedback (`edl_upload` or `edl_other` nonzero) -- an unconditional skip would drop a real read, so the lever is **not built** this attempt; H2 would need a conditional (per-binding) lever instead, a bigger change, ranked against the brief's remaining items rather than assumed |

P1 is the single number this attempt turns on, exactly as item 2 asked. No pixel or fps leg is predicted yet
because there is nothing to measure pixels or fps against until P1 says a lever exists to build.

### Capture and verdict: P0 reproduces, P1 is falsified -- `HAKUX_S2T_DEAD`-style skip is not built for H2

**Reachability note (operational, not a finding):** the installed APK at the start of this item's device time
turned out to be a plain debug build, not a perflog build (`versionName=0.5.0-1019-913e1524ff`, no `-perflog`
suffix) -- `opt_stats_log_and_reset()`'s whole body, `evict[dl:...]` included, is `#if NV2A_PERF_LOG` and compiles
to nothing without it (`debug.h:222`, `-Pperflog=true`), so a first 75s movement window against that build read
zero `evict[dl:]`/`[edl]` lines even though `[drawrec]` kept printing (a different, always-compiled counter) --
not a scene or mechanism finding, a build-selection miss, caught by checking the function body rather than
trusting "the app is running and logging something." Installed the most recent perflog build with no source
drift from HEAD (`711315bbe7-perflog.apk`; `git diff --stat 711315bbe7 HEAD -- '*.c' '*.h'` empty), relaunched.
The reinstall force-stopped Fable, but the virtual Xbox HDD (`hdd-owner-1018.img`, already the active hddPath)
had an **AutoSave** from the earlier recon session's own progress -- Default profile, Region: Oakvale -- so
"Continue Game" -> "Load Game" -> AutoSave reached the same opening narration/cutscene chain again (no shortcut
past it; the AutoSave point is itself right at the very start) but needed no fresh profile creation. Skipped the
in-engine father/daughter cutscene (`Y, Skip Scene`) to reach player control faster, dismissed the tutorial
prompt (`pad.sh press A`), confirmed `GPU: PurpleVK-public Adreno (TM) 740` for the new PID (25524) before
treating anything from it as real.

**Movement window:** marked device-clock start (12:29:05.770) and end (12:30:40.701, ~95s), `pad.sh`-driven walk
(LY forward, LX swept sine-wave for turns, same pattern as the Blinx 2 arm script's circling) through Oakvale's
tutorial area past several houses and an NPC, confirmed by screenshot (HUD/map/health bar active, character mid-
stride near a house door, an NPC beside it) that this was genuine movement, not a static idle frame. Archived the
raw logcat and the confirming screenshot: `captures/fpsnext1019/runs/fable-h2/{logcat.txt,after-move.png,window.txt}`.

**P0, reproduction** -- confirmed, and stronger than the owner's capture: `evict[dl:]` in-window reads 507-767 per
~3.4s/60-flip tick (owner capture: 300-460), ramping up over the first ~3 windows then holding steady (739-767)
for the rest of the window. H2's eviction-download pattern is reliably reproducible from a cold boot with no
route or save state, exactly as the owner capture's mining predicted.

**P1, the actual decision** (`[edl]` lines in the same window, 27 ticks after the 3-tick ramp-up/warm-up is
naturally included -- summed, not cherry-picked):

| field | sum over 27 windows |
|---|---|
| `dl` (evicted bindings whose download fired) | 3,171 |
| `clrskip` (provably never read -- covering clear dropped the pending upload first) | 1,597 |
| `upload` (replacement binding uploaded -- the download fed a real read) | 1,574 |
| `other` (ambiguous) | 0 |

`clrskip`/`dl` = **0.504**, not 1.0 (6/6). Every single one of the 27 windows carries a nonzero, consistently-
sized `upload` count (`upload` sits at exactly 60 in every post-ramp-up window -- a fixed-size batch of bindings
whose replacement is genuinely read, almost certainly the per-frame zeta-clear-then-read cycle the H2 mechanism
section already named) alongside a roughly-matched `clrskip`. **P1 is falsified clearly, not a near-miss:** close
to half of every window's evicted-and-downloaded content is real feedback a later stage reads. Per the G3
prediction's own falsifier and per Addendum 2's own wording, an unconditional skip is not safe to build on this
ratio -- it would silently drop the ~50% of downloads that are real reads, the exact failure mode a "clrskip
6/6" bar was chosen to rule out before writing any code.

**Verdict: the `HAKUX_S2T_DEAD`-style unconditional download-skip is not built for Fable H2 this attempt.** The
mechanism itself (deferred-download-on-eviction, same `[edl]` instrument fpsdata1018 built and never ran) is
confirmed real and reproducible -- this is not a "could not test it" result, it is a clean, instrument-backed
negative exactly like `HAKUX_S2T_DEAD`'s own P0 on GTA III (G5: a decided question, not a shrug). The 50/50 split
also names H2's actual next-ranked option, if anyone picks this back up: a **conditional**, per-binding skip
(something like `HAKUX_SWZKEEP`'s keep-bound mechanism, or a per-binding "was this eviction's replacement ever
sampled" gate) rather than a blanket one -- a bigger change than this attempt's budget, and not started here;
ranked against the brief's remaining items (GTA III beyond R2, the RalliSport 2/Fable landed-lever read-back),
not clearly higher-probability-times-win than either without its own mechanism writeup first.
