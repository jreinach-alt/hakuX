# lane.gta3fps1017 -- GTA III fps: R2 and R3, the copy-count remedies, measured on foot (#1049, #433)

Status (10-18, attempt 1): **done; PR ready.** The census on foot (desktop, `NV2A_PERF_LOG` build) reads 2.00
copies per flip, all `map`, no dups: 36x below the pilot's ~73, so it does not transfer to driving and the lane
stops at the brief's step 2: **neither R2 nor R3** (section 3). R1 folds alone: the seven pgraph suites pass with R1
on and off on the desktop (section 2.3), and the on-foot before/after on one window shows R1 removing the drain
(section 2.4). No device time used: the Nova is on the owner's hold, and the Nova step decides nothing the fold
needs (section 4). No driving fps claim.

## 0. Already tried (copied from `origin/lane/gta3drive1017` NOTES.md, sections 2, 6, 7, 8.2-8.7)

A resume reads this table first and extends it; it never repeats a row.

| tried | where | result | consequence for this lane |
|---|---|---|---|
| Six scripted drive tries, a pathfind route into the Kuruma (`gta-3-drive.route`) | gta3drive1017 NOTES 8.2-8.7; requests 1364097/1364296, 1563459, 1853100, 2035473, 2291336, 2477310 | all VOID at the same gate: the route cannot get into or stay in the car. The help-box gate never matched (8.2); the mission restarted under the throttle (8.3); the car flipped on the bridge ramp on the first steering pulse, on a third of lock and with no steering (8.4-8.6, "You flipped your wheels!"); at a slow throttle each Y got Claude out, and the flips came after re-entries (8.7) | **Do not script driving. Do not write a seventh route.** Every device run here is on foot |
| perflog pilot `1-1792275531-lane.gta3drive1017-343857` (perflog + FRAMETRACE + GPUXFR, Nova, Turnip) | NOTES 6.1-6.2 | in the < 26 band (111 windows, 21.2 fps perflog; 22.9 fps / 43.7 ms in the plain pilot 346093) the PFIFO thread waits ~11.6 ms per flip in `pgraph_vk_flush_all_frames`, the #474 drain in create_texture ahead of `copy_surface_to_texture`: 71.9 drains per flip, against 2.0 at >= 28.5 | measured; **do not re-measure it** |
| Copy count and render passes in the dips | NOTES 6.1-6.2 (txw CP 72.8 calls per flip in the < 26 band, GPUXFR s2t 30.5/frame undercounted by its ring), the owner's driving capture `captures/halo-shadow-1017-turnip/logcat-owner-5454000E-play-21488.txt` | ~73 surface-to-texture copies per flip; 22-30 render passes per frame, each copy breaking one; prun 16.7 -> 27.1 ms per flip (perflog). **Correction (this lane, 10-17):** the ~73 is the pilot's txw CP, not the owner capture's: that capture is a plain build and carries no copy count (no txw, s2c or GPUXFR line) | the copies themselves are the second cost: **what R2/R3 attack** |
| Do copies per flip track driving? (re-read of pilot 343857's logcat and frames, this lane) | `results/1-1792275531-lane.gta3drive1017-343857/` logcat txw lines against `frames/index.tsv` | Not by "driving" alone. At the garage camera (frames f00026 15:41:16, f00028 15:41:57, f00030 15:42:39; route frame 154201), while the route revved and reversed the car, the 60-flip windows ran ~75-98, ~7 and ~154 copies per flip, 3 to 174 across the stretch; the 42 windows of 15:35:09-15:37:00 ran 2.00 to 203.6, eight of them at 2.00 (15:35:30-15:35:44). Low windows recur every ~40-60 s (15:37:37, 15:38:49, 15:39:30, 15:40:12, 15:40:54, 15:41:56). **Correction (this lane, 10-18):** an earlier version of this row called 15:35:09-15:37:00 "before the route's first move (only A presses)" and gave the on-foot windows as 18.5 and 17.1 per flip. Both were wrong: the route frames show the Kuruma moving and crashing before the Y at 15:37:02, and txw `cp` reads 2.00 per flip at 15:37:03 and 32.30 at 15:37:05 | the factor-of-two test compares windows. Held on foot for 20 minutes (rows below), copies never leave 2.00 per flip; this pilot's bursts all fall while the car moves, just after a crash, or at the garage camera with the car under throttle. The high garage window's fingerprint: faf 20.45/172.25, cp 0.40/172.53, RP nd 6361 srf 186, s2tc 6359, an `[ovl1018]` 256x256 swizzled Z (f130) at +3932160 inside a 1024x1024 linear Z |
| Census on foot, desktop (this lane) | `build-linux/run/c1` (R1 on) and `c2` (R1 off, `HAKUX_S2T_DRAIN=1`), git-ignored; `tools/desk_census.py`; section 2.1 | c1: 65 windows of 60 flips held on foot beside the Kuruma on the bridge ramp (360-1540 s, a shot every 20 s): **2.00 copies per flip in every window, dup 0, reason `map` 100%** (zs 0, pad 0, fmt 0, none 0). c2, the same scene (27 windows, 360-800 s): the same | measured; **do not re-run the census on foot**, on the desktop or the Nova |
| Does the census transfer to driving? (brief step 2) | section 3 | **No.** 2.00 on foot (desktop c1/c2, and the Nova pilot's 26 windows at 2 per flip, section 2.2) against ~73 in the pilot's < 26 band: 36x, not within 2x | **Stop: no R2, no R3** (the brief: "say so and stop there; do not drive to find out"). The burst census needs driving, so it can only come from owner play (section 5) |
| Which copy site the bursts use | pilot 343857 GPUXFR; texture.c 1271-1340 | all 477 GPUXFR windows name only `s2t@1264`, never `s2t@960`. 1264 is reached only by a colour copy (zeta returns at 1276) that is not S2T_CVT (returns at 1304): exactly R1's plain copy. In the bursts drains track copies (15:37:08: faf 161.23, cp 161.62 per flip) | **R1's branch is where the bursts drain.** The other copy caller (texture.c 4006) fills a new node and never drained |
| R1 on the Nova, before this lane | gta3drive1017's arms 1364097, 1563459, 1853100, 2035473, 2291336, 2477310 (APK c6ca5296fd, PurpleVK) | all six print `[s2tdrain] first skip`, each ran its 9-10.5 min soak to the end, no `Fatal signal`/SIGSEGV/DEVICE_LOST: ~60 min of GTA III on Turnip with R1 on, driving segments included. Pair 1364097 (R1 on) / 1364296 (R1 off), same route: section 2.5, not one window | Turnip has run R1 for an hour; no Nova safety run is needed before the fold |
| Desktop pgraph suites, R1 on and off (this lane) | `build-linux/run/sA`, `sB`, `sB2`; `tools/desk_suites.py`, `tools/arm_diff.py`; section 2.3 | all three exit 0, 363 tests each, no crash dump. No `[s2tdrain]` line in any arm: **the suites do not reach R1's branch on the desktop either.** The only differences are in Texture_shadow_comparator, and they are as large within R1 on (B vs B2: 65 tests) as between arms (A vs B 64, A vs B2 73) | green, and blind to R1; do not rerun them to judge R1 |
| The lane's own C: guard (10-18) | `tools/desk_*.py` | arm A refused at 38.7 GB free under a 40 GB guard; there were no crash dumps (C: drained from outside this lane) | guard is now 20 GB, room for two ~7.8 GB qemu dumps |
| R1: skip the #474 drain ahead of a plain colour surface-to-texture copy | commits b7d7243392 (the skip), c6ca5296fd (`[s2tdrain] first skip`, once); kill switch `HAKUX_S2T_DRAIN=1` (A arm = master's behaviour); NOTES 7, 8 | built into the gta3drive1017 arms' APK (c6ca5296fd) and run there: the pixel suites never reached its branch (8.1); every drive arm was VOID by the route (8.2-8.7), so **no verdict on R1**; never folded, never in a shipped APK | **R1 is the third item in this lane, not the first.** It folds with R2/R3's pick only if its pgraph suites pass |
| R1 pixel arms (drain474's seven surface-as-texture suites, B `1361822` / A `1362137`) | NOTES 8.1 | neither arm reached R1's branch (no `[s2tdrain] first skip` in B, no `[s2tdrain] on` in A); FAIL 33/363 = run-to-run variance (shadow_comparator +-80 px, CPUWriteIgnoresSurfaceConfig's old stripe race) | these suites do not exercise R1; their totals are master's baseline. A rerun decides nothing |
| census: copy refusal reasons and dups per flip | commit bd2bf354bb (texture.c, `NV2A_PERF_LOG` builds only) | written, **never run** | **this lane runs it**, on foot |
| Sysmem render mode, a faster clock, a performance mode | NOTES 4 (D3 0.05), 7 | not remedies: the GPU is busy 21.9 ms of a 47 ms dip frame, it idles half the frame; the owner forbids clock and mode fixes | out of scope |
| Vertex hazard finishes (D6), pgraph.lock on the PFIFO side (D7), pipeline compile (D8), texture dirty walks, guest work (D4) | NOTES 3 readings 2/9, 4, 6.2 | ruled out in the same windows: `vtx_hazard` ~0.3 per flip, ft1 lw 0, dpc <= 2 ms per flip, walks in microseconds, guest 23.3 ms < 33 | not this lane's levers |
| bind_textures drain (PR #517), uniform hash skip (PR #543), per-flip dirty memo (#461 M1) | NOTES 2 | landed or neutral | not levers here |

**Stop rule (owner 10-17, about retries):** the same attempt voided twice for the same cause means stop, write what it
was and what would change, and report to lane.local. No third try.

## 1. Plan

1. Cherry-pick b7d7243392, c6ca5296fd and bd2bf354bb's texture.c hunk (its docs belong to gta3drive1017's lane dir).
   Build; desktop pgraph suites with R1 on and off.
2. Census on foot: GTA III (5454000E), Nova, `NV2A_PERF_LOG` build, a held on-foot window in the city. Transfers to
   driving if on-foot copies per flip are within 2x of the owner's ~73.
3. R2 (one dominant, safely widened refusal reason, kill switch, default off) or R3 (several nodes copy one surface
   state) from the census, or neither, which is an answer.
4. R1 with the pick, if its suites pass.
5. Proof: suites green, the census, the kill switches, an on-foot before/after on one window, each change's log line.
   No driving fps claim; that is owner play.

## 2. Measurements

All desktop runs: `build-linux/qemu-system-i386`, an `NV2A_PERF_LOG` build of this branch (R1 + the census), headless
on lavapipe, with the fast paths and `HAKUX_SURFGPU=1` set as the app sets them. Run outputs are under
`build-linux/run/` (git-ignored); the tools are in `tools/` (section 7). No device time was used.

### 2.1 The census on foot (desktop, GTA III 5454000E)

`desk_census.py`: boot, 30 A presses 6 s apart from 60 s (gta-3.route's A-train: intros, new game, the opening
cutscene), then no input; a shot every 20 s. By 360 s the player stands beside the Kuruma on the bridge ramp at
night, and stays there (shots 000360 and 000600 in both runs show the same scene; c1's runs on to 001540). Windows
counted from 360 s.

| run | R1 | 60-flip windows | copies/flip | refusal reason | dup | pairs on foot |
|---|---|---|---|---|---|---|
| c1 | on | 65 (360-1540 s) | **2.00** in every window | `map` 100% (zs 0, pad 0, fmt 0, none 0) | 0 | `#0:60 #1:60` in all 65 |
| c2 | off, `HAKUX_S2T_DRAIN=1` | 27 (360-800 s) | **2.00** | `map` 100% | 0 | the same two |

The two pairs on foot, one copy each per flip:

    [s2c] new #0 map | surf @3d04000 color1 fmt0x4 vk44 1280x480 | tex fmt0x1e vk44 1280x480 map0002
    [s2c] new #1 map | surf @3bd8000 color1 fmt0x4 vk44 640x480  | tex fmt0x1e vk44 640x480  map0002

An X8R8G8B8 surface read as a linear X8R8G8B8 texture (0x1e) whose component map forces alpha to one (map0002); the
surface's own view does not, so `surface_view_decodes_as_texture` refuses the bind and the texture is copied. Two
more pairs (128x128, tex fmt 0x7, also `map`) appear only before 360 s, during the A-train.

### 2.2 The Nova pilot's windows at two copies per flip (R1 off; re-read, not re-run)

Pilot 343857 (perflog, Nova, PurpleVK), every txw window whose `cp` count is 1.5-2.5 per flip: **26 windows** (the
cutscene, standing and on foot: 15:34:44-15:35:44, 15:37:03, 15:37:30-15:37:42, 15:38:12, 15:40:11, 15:40:40).

| windows | fps | drains/flip | drain ms/flip | copy ms/flip (CPU recording) |
|---|---|---|---|---|
| 26 | 29.63 | 1.90 | **3.41** (0.04-9.32) | 0.038 |

So on the Nova, on foot, the two copies cost ~0.04 ms per flip to record, and the #474 drain ahead of them costs
~3.4 ms per flip of PFIFO waiting, under the 30 fps cap. Turnip agrees with the desktop on the count (2.00).

### 2.3 The pgraph suites, R1 on and off (desktop)

`desk_suites.py` on drain474's seven surface-as-texture suites (Antialiasing, Color zeta overlap, Surface format,
Texture Framebuffer Blit, Texture render target, Texture render update in place, Texture shadow comparator; 363
tests; `--shutdown-on-completion --progress-log`), each arm on a fresh copy of the blank desktop HDD.

| arm | R1 | exit | wall | tests | `[s2tdrain]` lines | golden-exact | new crash dumps |
|---|---|---|---|---|---|---|---|
| sA | off (`HAKUX_S2T_DRAIN=1`) | 0 | 156 s | 363 | 0 | 16 | none |
| sB | on | 0 | 242 s | 363 | 0 | 16 | none |
| sB2 | on (rerun) | 0 | 124 s | 363 | 0 | 16 | none |

`arm_diff.py`, RGBA bit-identity per test:

| pair | bit-identical | differ | where |
|---|---|---|---|
| sA vs sB (R1 off vs on) | 299 | 64 | all Texture_shadow_comparator |
| sB vs sB2 (R1 on vs R1 on) | 298 | 65 | all Texture_shadow_comparator |
| sA vs sB2 (R1 off vs on) | 290 | 73 | all Texture_shadow_comparator |

The 75 tests outside Texture_shadow_comparator are bit-identical in all three runs. Inside it (288 tests) the
differences come in steps of 80 and 86 px and the distance to the golden swaps both ways between runs (400<->480,
430<->516), as large within R1 on as between the arms: run-to-run variance, as gta3drive1017 8.1 found on the Nova.
**Pass** here means: every arm completes with exit 0, and R1 on vs off differs nowhere beyond the R1-on rerun's own
band. The golden-exact count (16) is lavapipe's baseline, not a defect count. No arm printed `[s2tdrain]`: these
suites do not reach R1's branch (no copy into an in-flight node), on the desktop as on the Nova.

### 2.4 Before/after on one window, on foot (desktop)

Same build, same input, same scene (2.1), the kill switch the only difference. txw, mean over the windows from 360 s:

| run | R1 | log line | windows | copies/flip | drains/flip | drain ms/flip | copy ms/flip |
|---|---|---|---|---|---|---|---|
| c2 | off | `[s2tdrain] on` | 27 | 2.00 | **1.86** | **217.17** | 0.82 |
| c1 | on | `[s2tdrain] first skip` | 65 | 2.00 | **0** | **0** | 0.93 |

R1 removes the drain ahead of both on-foot copies and changes nothing else in the census. Desktop fps (c1 3.55, c2
3.89) is not a measure of R1: lavapipe rasterizes on host CPU threads, the drain there waits on work the flip
waits on anyway, and neither run had the host to itself.

### 2.5 R1 on the Nova already (gta3drive1017's drive arms, re-read)

Six arms on APK c6ca5296fd (R1 on) print `[s2tdrain] first skip` and the R1-off arm 1364296 prints `[s2tdrain] on`;
all on PurpleVK (`PurpleVK-public Adreno (TM) 740`), none with `Fatal signal`, SIGSEGV or DEVICE_LOST, each running its
9-10.5 min soak to the end. The 8.2 pair ran one route back to back, differing only in the kill switch; `hakuX-pace`,
60-flip windows after the first three:

| arm | R1 | windows | mean fps | windows < 26 fps | windows all at 2 vblanks (30 fps) | windows with a frame > 50 ms |
|---|---|---|---|---|---|---|
| 1364296 | off | 293 | 29.80 | 2 | 151 (52%) | 61 (21%) |
| 1364097 | on | 266 | 29.77 | 4 | 210 (79%) | 27 (10%) |

Not one window: the route's scenes are not aligned between the arms (it never matched its help-box gate, 8.2), so
this is consistent with R1 smoothing the pacing, not a measurement of it.

## 3. The pick: neither R2 nor R3

The brief's test: "if on-foot copies per flip are within a factor of two [of ~73], the census transfers. If they are
not, say so and stop there; do not drive to find out." On foot is 2.00 per flip (2.1, and the Nova's 26 windows in
2.2): 36x below. **It does not transfer, so the lane stops here.** What each remedy would do on foot:

- **R2** (bind the `map` pairs instead of copying them): two copies per flip at ~0.04 ms of recording on the Nova,
  plus ~3.7 MB per flip of GPU copy traffic at 1x scale (1280x480 + 640x480 at 4 bytes; GPU time not measured,
  txw `cp` is CPU time). The bind still ends the render pass (`bind_surface_as_texture`, texture.c:1175), so it saves no pass
  break. Not worth a widening that needs a pixel argument.
- **R3** (one copy shared between nodes): nothing to share on foot (dup 0, two distinct surfaces).

What drives the ~73 is the bursts, and their refusal reasons and dup counts are unknown: they need a census in a
burst, and bursts come with driving (2.0 row "Do copies per flip track driving?"). Section 5 says how to get one
without a script.

For whoever picks it up: if the burst census shows `map` dominating, R2's pixel argument is short. The copy's
texture reads the surface's RGB with alpha forced to one. A sampled view of the same surface image with
`components.a = VK_COMPONENT_SWIZZLE_ONE` reads the same RGB with alpha one, with no copy. If it shows dups, R3 removes
copies and their pass breaks; R2 removes neither pass break.

## 4. R1 folds alone

- **What:** in create_texture's binding_found branch, an in-flight node that takes a plain colour copy (colour, not
  an S2T_CVT expanded format) skips `pgraph_vk_flush_all_frames` (texture.c 3467-3542). Kill switch
  `HAKUX_S2T_DRAIN=1` (the old drain; logs `[s2tdrain] on`); default R1 logs `[s2tdrain] first skip` once.
- **Why it is safe:** the copy records into the current frame's command buffer, and its
  SHADER_READ_ONLY->TRANSFER_DST barrier (image.c:137, src FRAGMENT_SHADER/SHADER_READ) orders it after every earlier
  submission's fragment reads on the one queue; frames are submitted in recording order. The drain waited for the
  very work that the barrier already orders against.
- **Evidence:** suites green on and off (2.3); on foot the drain goes 1.86 -> 0 per flip with copies unchanged
  (2.4); an hour of GTA III on Turnip with R1 on, driving included, no fatal (2.5).
- **What it should do in the dips (not claimed here):** the pilot's < 26 band waits ~11.6 ms per flip in this drain
  (71.9 drains per flip); every burst copy is at the site R1 changes (row "Which copy site the bursts use"). The
  brief's P 0.85. The driving number comes only from owner play.
- **Scope:** R1 is default-on for every title, not only GTA III. Under the 10-17 rule the owner screens titles after a
  fix lands; this lane runs no screen.
- **No device step.** A Nova on-foot A/B would show ~3.4 ms per flip of drain going to zero under the 30 fps cap
  (2.2). It decides nothing the fold needs: the census already does not transfer, and Turnip has run R1 for an hour.
  So there is no WAITING file and no hold taken.

## 5. Next, ranked by expected impact

1. **Fold R1** (P 0.85 x ~11.6 ms per flip in the dips): this PR.
2. **A burst census from owner play.** One owner session of GTA III on an `NV2A_PERF_LOG` APK built from master
   after R1 folds gives the burst refusal reasons and dups (`[s2c] f60 ... why[...]`, `[s2c] new` pairs) and R1's
   driving effect in the same logcat. Perflog costs ~1.7 fps in the dips (pilot: 21.2 perflog vs 22.9 plain). That
   decides R2 against R3 for the bursts, which is the question this lane could not answer on foot.
3. **R3 or R2, sized by what is left after R1:** the copies themselves (prun 16.7 -> 27.1 ms per flip in the dips,
   22-30 render passes per frame). R3 is the one that can remove pass breaks.

## 6. What the next lane should not repeat

- The census on foot: 2.00 per flip, `map`, dup 0, on the desktop for 20 min and on the Nova in 26 windows.
- The pgraph suites as a test of R1: three arms, none reaches its branch.
- Scripted driving (row 1).
- Pairing logcat timestamps to txw lines with `grep -o | paste - -`: lines without a match shift the pairing and drop
  windows (it found 10 of the 26 in 2.2). Parse each line whole.
- Desktop lavapipe fps as a measure of a drain change (2.4).

## 7. Tools (`tools/`)

- `desk_census.py OUT --total S [--first S] [--train N] [--gap S] [--shot-every S] [ENV=V ...]`: GTA III on the
  desktop with an A-train and a held window; OUT/qemu.log (seconds-prefixed), census.log, shots/.
- `desk_suites.py OUT --disc ISO [--total S] [ENV=V ...]`: one pgraph suite arm on a fresh blank HDD; prints
  `SUITES_EXIT=... extract=...`, results in OUT/results.
- `arm_diff.py A_RESULTS B_RESULTS GOLDENS [--tsv OUT]`: two arms bit-for-bit and each against the goldens.

Both run tools refuse to start under 20 GB free on C: and list any new crash dump at the end.
