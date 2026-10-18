# lane.gta3fps1017b -- GTA III fps: R2 and R3 written, default off, for the owner's driving session (#1049, #433)

Status (10-17, attempt 1): Step 0 committed; code not yet written.

## 0. Already tried (copied from `origin/lane/gta3fps1017` NOTES.md sections 0-3 and 5, extended)

A resume reads this table first and extends it; it never repeats a row.

| tried | where | result | consequence for this lane |
|---|---|---|---|
| Six scripted drive tries, a pathfind route into the Kuruma (`gta-3-drive.route`) | gta3drive1017 NOTES 8.2-8.7; requests 1364097/1364296, 1563459, 1853100, 2035473, 2291336, 2477310 | all VOID at the same gate: the route cannot get into or stay in the car (help-box gate never matched; mission restarted under throttle; the car flipped on the bridge ramp; Y got Claude out) | **Do not script driving. No seventh route.** The driving numbers come only from the owner's session |
| On-foot census (gta3fps1017 NOTES 2.1, desktop c1/c2, and the Nova pilot's 26 windows, 2.2) | `[s2c]` census, `NV2A_PERF_LOG` build | **2.00 copies/flip**, reason `map` 100%, dup 0, two surface pairs: `surf @3d04000 color1 fmt0x4 vk44 1280x480 -> tex fmt0x1e vk44 map0002` and the same at 640x480 (`@3bd8000`) | measured; it does not transfer to driving (~73/flip, 36x). **Do not re-run it on foot** except as R2's before/after (the brief's step 7) |
| perflog pilot `1-1792275531-lane.gta3drive1017-343857` (Nova, Turnip) | gta3drive1017 NOTES 6.1-6.2 | < 26 fps band: PFIFO waits ~11.6 ms/flip in the #474 drain (71.9 drains/flip); ~73 copies/flip; 22-30 render passes per frame; every burst copy at `s2t@1264` (R1's plain colour copy branch) | measured; **do not re-measure** |
| Do copies per flip track driving? (gta3fps1017 re-read of pilot 343857) | that lane's NOTES row 4 | the bursts (3 to 203 per flip) fall while the car moves, just after a crash, or at the garage camera under throttle; on foot never leaves 2.00. The high garage window: cp 172.5/flip, srf 186, an `[ovl1018]` 256x256 swizzled Z inside a 1024x1024 linear Z | the burst's refusal reasons and dups are **unknown**; R2/R3 are written blind to them, switchable, for the owner's session to read |
| R1 (merged from lane/gta3fps1017: b7d7243392, c6ca5296fd; census bd2bf354bb) | gta3fps1017 NOTES 2.3-2.5, 4 | removes the ~11.6 ms/flip #474 drain ahead of a plain colour copy; desktop pgraph suites pass on and off (363 tests, diffs only in Texture_shadow_comparator, within its own rerun band); ~60 min of GTA III on Turnip with R1 on, no fatal | **do not rewrite it; build on it.** Its switch `HAKUX_S2T_DRAIN=1` restores the drain |
| The pgraph suites as a test of R1 | gta3fps1017 NOTES 2.3, gta3drive1017 8.1 | no suite reaches R1's branch (no `[s2tdrain]` line in any arm) | blind to R1. For R2/R3 they are run on and off **and** checked for the switches' own log lines, so a green run says whether it reached the branch |
| R2 / R3 (gta3fps1017 NOTES 3) | that lane's pick | not written: the on-foot census does not transfer to driving | right for a census-first plan, wrong for the owner's ask (10-17 ~23:00 PDT): **this lane writes both, off by default** |
| Pairing logcat timestamps to txw lines with `grep -o \| paste - -` | gta3fps1017 NOTES 6 | lines without a match shift the pairing and drop windows | parse each line whole |
| Desktop lavapipe fps as a measure of a renderer change | gta3fps1017 NOTES 2.4 | lavapipe rasterizes on host threads; neither run had the host | report counts on the desktop, never fps |
| Sysmem render mode, faster clock, performance mode | gta3drive1017 NOTES 4, 7 | not remedies: the GPU idles half of a dip frame; the owner forbids clock and mode fixes | out of scope |
| Vertex hazard finishes (D6), pgraph.lock (D7), pipeline compile (D8), dirty walks, guest work (D4) | gta3drive1017 NOTES 3, 4, 6.2 | ruled out in the dip windows | not levers here |
| bind_textures drain (#517), uniform hash skip (#543), per-flip dirty memo (#461 M1) | gta3drive1017 NOTES 2 | landed or neutral | not levers here |

**Stop rule (owner 10-17):** the same attempt voids twice for the same cause means stop, write what it was and
what would change, and report to lane.local. No third try.

## 1. Plan

1. Merge `origin/lane/gta3fps1017` (R1 + census). Build the desktop tests.
2. R2: widen `surface_view_decodes_as_texture` for the forced-alpha component map; `HAKUX_S2T_WIDEN=1` on.
3. R3: share one copy between nodes that sample the same surface at the same draw_time with the same decode;
   `HAKUX_S2T_SHARE=1` on.
4. Census: R2 binds and R3 shares per 60 flips beside the refusal reasons.
5. Desktop proof: pgraph suites with each switch on and off, the log lines, on-foot copies/flip before/after.
6. The perflog APK, built in a private worktree; path in PR.md. Env strings for the owner's session.
