# lane.gta3dip1018 -- GTA III: R2 removed every copy and fps did not move. Find what the dip frame spends its time on (#1049, #433)

Status (attempt 1): analysis-only, no device time, no code. FINDINGS.md has the decomposition, the two owner-capture
stalls, the ranked levers and the one lever to take first.

## 0. Already tried (Step 0)

Read on master: `gta3fps1017/NOTES.md`, `gta3fps1017b/NOTES.md`, `origin/lane/gta3drive1017:docs/lanes/gta3drive1017/NOTES.md`
(not present in this worktree's `docs/lanes/`), `vcpuwait433/decompose.py`, `belowbar1005/`.

| tried | where | result | consequence for this lane |
|---|---|---|---|
| Census on foot, desktop + Nova pilot | gta3fps1017 NOTES 2.1-2.2 | 2.00 copies/flip on foot, all `map`, dup 0; 36x below the pilot's driving burst (~73-133) | on-foot measurement does not stand in for driving; this lane uses only driving data (b3, pilot 343857, owner capture) |
| R2/R3 fps verdict, controlled (palindrome) batches b2/b4 | `captures/lanexbox-fps1018/README.md` | R2: -0.3 (b2), -0.9 (b4) fps. R3: dup 0, inert | **do not re-litigate R2/R3's fps verdict from any other batch, including b3 (see FINDINGS.md 1.4 on why b3 is not a controlled comparison across arms)** |
| Pilot 343857: #474 drain located and quantified | gta3drive1017 NOTES 6.1-6.2 | PFIFO thread blocked in `vkWaitForFences` inside `pgraph_vk_flush_all_frames` (draw.c:5136), called from the #474 drain ahead of `copy_surface_to_texture` (texture.c:3290-3295); 71.9 drains/flip, 11.6 ms/flip, in the <26 fps band | **R1 already removed this drain.** Do not re-propose it. The question this lane answers is what is left now that R1 (and R2/R3 on top) are in |
| Ruled out in pilot 343857's windows | gta3drive1017 NOTES 6.2 | vertex-hazard finishes ~0.3/flip flat; pgraph.lock on the PFIFO side (`lw`) = 0; pipeline compile <= 2 ms/flip; texture dirty walks in microseconds; guest work 23.3 ms < a 33 ms frame | **do not re-propose vertex hazards, pgraph.lock, pipeline compile, texture dirty walks, or "the guest is slow" as the dominant cost** |
| Sysmem render mode, a faster clock, a performance mode | gta3fps1017 NOTES 0 (row from gta3drive1017 6.2 D3), brief's established section | GPU busy only 21.9 ms of a 47 ms dip frame (idles half the frame); owner forbids clock/mode fixes | **not a lever here**: the GPU is not saturated, and clock/mode changes are out of scope regardless |
| `vcpuwait433/decompose.py` off-CPU-by-wake-vector method | `docs/lanes/vcpuwait433/decompose.py`, NOTES | needs `[rr425w]`/`[tlb68]`/`[idlehalt]`/`[rwait526]`/`[lock474]` tags from a `mark gameplay` logged run | **not runnable on this lane's data**: the b3 perflog runs and the owner capture carry perf-build counters (`hakuX-perf`, `hakuX-phase`, `hakuX-stall`) but not vcpuwait433's off-CPU trace tags. Named in FINDINGS.md as the next measurement for a lane with device access |
| `belowbar1005` / `fps20786`'s near30 decomposition method (2 s always-on windows) | `docs/lanes/belowbar1005/decompose.py`, NOTES Step 1 | a sibling methodology for a different cost (#804 occlusion-query fence wait, Buffy/NG Black/DOA3, not GTA III) | not directly applicable (different title, different suspect already ruled out for GTA III: `#804` folded 10-04, before GTA III's own dip work); confirms the "controlled window, not RT-held mean" discipline this lane follows |
| gta3drive1017's scripted driving route attempts (6 tries) | gta3drive1017 NOTES 8.2-8.7 | all VOID (help-box gate, mission restart, car flips on the bridge ramp) | **do not script driving.** This lane uses only the owner's own save-state-in-the-car protocol (already run, `captures/lanexbox-fps1018/`) and the owner's own free-play capture (`captures/owner-play-1018/`) |

**Stop rule (carried from gta3fps1017/gta3drive1017):** the same analysis failure twice for one cause means stop and
report. Applied once in this lane: the `hakuX-stall RPBreaks:/Finish:` per-60-flip breakdown is racy during the park
phase in all three of b3-A/B/C (two threads, 14006 and 14008, both call the same non-atomic global-struct
print-and-reset once the async render thread's deferred-finish path activates -- confirmed by grep: tid 14008 only
appears once frames slow down). This instrument cannot be trusted for quantitative per-window RPBreaks/Finish/stlDef
citations in exactly the regime asked about. Reported as a finding in FINDINGS.md rather than retried a third way;
the single reliable per-60-flip emitter (`hakuX-phase`/`xemu-gpu`/`hakuX-perf gfps=`, confirmed single-thread-emitted)
stands in for the frame decomposition instead.

## 1. What this lane did

1. Pulled every `hakuX-perf gfps=`/`hakuX-phase`/`xemu-gpu` line across the parked-phase window (by device clock, from
   each run's `arm.log` PARK_START/RT_DOWN) of `runs/b3-A`, `b3-B`, `b3-C`, and computed per-arm means over those
   windows (FINDINGS.md 1).
2. Read `draw.c`, `profile.c`, `nv2a.c` directly to find what `Df` actually is (VBLANK-deferral event count from the
   frame-pacing governor, not "deferred GPU flush" as the brief's own carried-over framing assumed -- correction in
   FINDINGS.md 1.3), what triggers an `OptBisectStats` print-and-reset, and why it races across threads once the
   deferred-finish path is active.
3. Found and quantified a confound specific to b3: arm A runs cold (shader caches cleared immediately before it;
   `[uber569] cold=`/`lib_ms=` climbs to 50.4 s of cumulative synchronous pipeline-library compile by the time A's own
   hold phase ends), while B and C reuse the same on-disk Vulkan pipeline cache A just built (same APK install, only
   env vars changed between arms) and show `lib_ms` of 0.6-0.7 ms. This fully accounts for A's park-phase mean G
   (54.9 ms) running higher than B's (38.1 ms) and C's (40.2 ms) in this one non-palindromic run, and is why this
   lane does not use b3's cross-arm G comparison as a measurement of R2/R3 (FINDINGS.md 1.4).
4. Located the owner capture's 1.46 s (07:37:23) and 3.89 s (07:37:53) single-frame stalls precisely against the same
   `[uber569]`/`[gpl569]` cold-compile counters: both stalls fall inside the one active compile window (`cold` climbing
   1 -> 18, `lib_ms` climbing to 24585.5 by 07:38:23); `cold` and `lib_ms` are flat for the rest of the capture,
   including every later dip window the brief named (07:38:34-55, 07:39:14-30) (FINDINGS.md 2).
5. Named the dominant cost and ranked levers (FINDINGS.md 3), and the one lever + confirming parked-scene measurement
   (FINDINGS.md 4).

## 2. What the next lane should not repeat

- Do not use b3's arm-to-arm park-phase G/Tot/GPU numbers as an R2/R3 fps measurement. b3 is one non-palindromic pass
  (A then B then C, one install, shader cache cleared once before A), so A pays a one-time cold-compile tax B and C
  do not; it is not a controlled comparison. Use the palindrome batches (b2/b4) for the fps verdict, as the brief's
  "already established" section already does.
- Do not take `hakuX-stall RPBreaks:`/`Finish:` numbers from a park/dip-phase window at face value; two threads write
  the same non-atomic counters once the deferred-finish path is active, and the resulting series is non-monotonic
  (confirmed in all three of A/B/C's park windows).
- Do not re-run `vcpuwait433/decompose.py` against this data; it needs tags this lane's captures do not carry.
