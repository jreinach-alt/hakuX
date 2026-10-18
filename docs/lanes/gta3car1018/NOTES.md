# lane.gta3car1018 -- GTA III in the car: what the extra render passes are, and removing them (#1049, #433)

The bar is 30 fps while driving. On-foot numbers are not evidence about it and are not reported as progress here.

## 0. Already tried

A resume reads this table first and extends it; it never repeats a row.

| tried | where | result | consequence for this lane |
|---|---|---|---|
| `[dipwin]` line: race-free per-60-flip render-pass-break counters (`bsnb`, `bnd` by caller, `bclre`, finish by reason ...) and timed vertex copy / shader bind / fence split | `docs/lanes/gta3instr1018/` (lane/gta3instr1018 9eabf6a463, merged here) | only ever run on foot (run 1792340293-gta3instr1018-503029): 7.64 passes/flip, `bsnb` 4.02, `bnd` 1.99, `bclre` 1.01; `fen` 2.36 ms/flip of which `stale` 2.19 | the instrument this lane runs in the car; **not rebuilt**. On-foot numbers are a cost at a capped frame, not the dip |
| Parked dip scene, three perflog arms (R1, R1+R2, R1+R3), old `hakuX-phase` line | `docs/lanes/gta3dip1018/FINDINGS.md` 1.1-1.5 (lane.xbox b3) | B (R1+R2, 0 copies/flip): G 38.1 ms, GPU 25.1 (render ~20), Fin 7.8; RP/frame 52-55 in every arm | copies are not what holds the pass count. **Do not re-run copy arms** |
| `hakuX-stall RPBreaks:` / `hakuX-rpbrk` as the break breakdown | gta3dip1018 FINDINGS 1.3 | two tids, 2x swing, not citable | read `[dipwin]` only |
| Arm A's parked window after a shader-cache clear | gta3dip1018 FINDINGS 1.4 | cold pipeline compile (lib_ms 50 s) in the window | first arm after an install is a warm-up (W), not scored; check `lib_ms` flat before reading a window |
| R2 (direct-bind the forced-alpha copy), R3 (share one copy per surface state) | `docs/lanes/gta3fps1017b/NOTES.md`; lane.xbox b2/b4 palindromes | R2 copies to 0, fps -0.3/-0.9; R3 dup 0, nothing to share | not levers |
| R1 (skip the #474 drain ahead of a plain colour copy) | `origin/lane/gta3drive1017` NOTES 6.2, 7-8; folded via gta3fps1017 | +1.9/+2.7 fps parked (lane.xbox b2/b5) | folded; the baseline here |
| Six scripted drive routes into the Kuruma | gta3drive1017 NOTES 8.2-8.7 | all void | **no scripted driving**; the car comes from the owner's in-car state (slot 0, copied to debug slot 5) with RT held |
| pgraph.lock, vertex hazards, pipeline compile as an ongoing cost, guest work, sysmem mode, a faster clock, the TLB walk | gta3drive1017 NOTES 3-4, 6.2; fabledip1018 | ruled out | not levers |
| Stale vertex-RAM copy by page, not by span | `docs/lanes/vtxstale1018/` (lane/vtxstale1018 4507b8f2fa, draft; measured branch lane/vtxstale1018-m 54c0b3ee95) | selftest byte-identical, 7.5x fewer bytes on scattered writes; on foot ~2 ms/flip of PFIFO time; in the car unmeasured | merge it here only if the in-car `stale` share is real (brief step 3) |
| Per-draw recording census; `HAKUX_DRAWREC=1` (one TLB re-arm per flip; clear the stale `shader_bindings_changed`) | `docs/lanes/drawrec1010/NOTES.md` 5, 8, 16-17 | the stale flag sends 31% of NFS draws down the full path; -1.5 ms/frame warm at NFS; default off | a candidate for the full-path bind cost if the car shows it; the recorder thread is NOT to be built |
| Perflog runtime switch (pause-menu toggle) | `origin/lane/perflog1016:docs/lanes/perflog1016/NOTES.md` | not on master | this lane's instrument is compile-time `NV2A_PERF_LOG` (debug perflog APK) |

**Stop rule:** the same failure twice for one cause means stop, write what it was and what would change, and
report. No third try.

## 1. Base

`lane/gta3car1018` started at master 343221f6fc. The `[dipwin]` line is not on master, so the branch merges
lane/gta3instr1018: first `origin/lane/gta3instr1018` (25915ae59e, the instrument), then the lane's local head
9eabf6a463 (FINDINGS.md and `dipwin_read.py`, committed in its worktree but not pushed). Both are plain merges, so
master's history and gta3instr1018's are both ancestors and nothing was rebased.

## 2. Territory

Board at 9edbaaa813 (lane.local's row for this lane, 10:41 PDT): `docs/lanes/gta3car1018/**`, `captures/gta3car1018/**`.
The pgraph/vk files are claimed on the board when an edit needs them (section 5 says who holds each).

## 3. Device window

The owner released the Nova for the in-car work only (hakux-0b, 10-18): no on-foot runs, no parked-for-its-own-sake
runs. Hold `lane.gta3car1018` taken 10:45 PDT (device clock), wait-idle passed. The release app was alive at its
library screen with the display asleep; it was left alone.

Protocol: lane.xbox's (`captures/lanexbox-fps1018/scripts`), copied to `captures/gta3car1018/scripts` with paths and
hold name changed only: owner state in debug slot 5 (md5 c1978f47... equal to the release slot 0), pause-menu load
with an image check before every tap, 28 s parked (P+2..P+30), then RT held 60 s, screenrecorded. APK: the
dispatcher's perflog build of 25915ae59e (sha256 67f93c3b4c86), installed with `install -r`, shader caches cleared,
so the first arm (W) is a warm-up.
