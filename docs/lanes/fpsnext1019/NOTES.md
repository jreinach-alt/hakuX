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
| a | Per-title SYSMEM/GMEM render mode | **resolved: promote.** `TU_DEBUG=sysmem` measured +3fps over shipped on a crash-excluded, motion-verified, equal-length window, fewer render passes and fewer S2C copies/flip, same direction in two independent instruments (`dwseries.py`, `movescore.py`) | not yet landed -- it is a Turnip env var, not a code change in this tree; the still-open question is how to apply it (per-title default in the launcher/config, not a global env var an owner build ships with) |
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
