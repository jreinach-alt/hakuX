# lane.gta3fps1017 -- GTA III fps: R2 and R3, the copy-count remedies, measured on foot (#1049, #433)

Status (10-17, attempt 1): Step 0 committed (this table). Host-side work next: the three commits from
`lane/gta3drive1017`, the desktop suites with R1 on and off, then the census on foot on the Nova once the owner's hold
lifts.

## 0. Already tried (copied from `origin/lane/gta3drive1017` NOTES.md, sections 2, 6, 7, 8.2-8.7)

A resume reads this table first and extends it; it never repeats a row.

| tried | where | result | consequence for this lane |
|---|---|---|---|
| Six scripted drive tries, a pathfind route into the Kuruma (`gta-3-drive.route`) | gta3drive1017 NOTES 8.2-8.7; requests 1364097/1364296, 1563459, 1853100, 2035473, 2291336, 2477310 | all VOID at the same gate: the route cannot get into or stay in the car. The help-box gate never matched (8.2); the mission restarted under the throttle (8.3); the car flipped on the bridge ramp on the first steering pulse, on a third of lock and with no steering (8.4-8.6, "You flipped your wheels!"); at a slow throttle each Y got Claude out, and the flips came after re-entries (8.7) | **Do not script driving. Do not write a seventh route.** Every device run here is on foot |
| perflog pilot `1-1792275531-lane.gta3drive1017-343857` (perflog + FRAMETRACE + GPUXFR, Nova, Turnip) | NOTES 6.1-6.2 | in the < 26 band (111 windows, 21.2 fps perflog; 22.9 fps / 43.7 ms in the plain pilot 346093) the PFIFO thread waits ~11.6 ms per flip in `pgraph_vk_flush_all_frames`, the #474 drain in create_texture ahead of `copy_surface_to_texture`: 71.9 drains per flip, against 2.0 at >= 28.5 | measured; **do not re-measure it** |
| Copy count and render passes in the dips | NOTES 6.1-6.2 (txw CP 72.8 calls per flip in the < 26 band, GPUXFR s2t 30.5/frame undercounted by its ring), the owner's driving capture `captures/halo-shadow-1017-turnip/logcat-owner-5454000E-play-21488.txt` | ~73 surface-to-texture copies per flip; 22-30 render passes per frame, each copy breaking one; prun 16.7 -> 27.1 ms per flip (perflog) | the copies themselves are the second cost: **what R2/R3 attack** |
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
