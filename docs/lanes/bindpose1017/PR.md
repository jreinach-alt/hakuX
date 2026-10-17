# bindpose1017: THPS4 and Max Payne 2 bind pose: the stock Adreno driver, not the code (#1043)

State: ready

Lane: bindpose1017            Issue: #1043
Base: master @ 5c4c24956e (merged; branched from 8d260f39fc)
Files: docs/lanes/bindpose1017/PR.md, docs/lanes/bindpose1017/NOTES.md, docs/lanes/bindpose1017/tools/cachels.py
Prediction: none: analysis-only (no emulator change; the defect is the package's GPU driver)
Needs device: no    Needs NDK: no

Root cause of the bind pose in Tony Hawk's Pro Skater 4 (41560017) and Max Payne 2 (5454000C): every bad result ran on
the stock Qualcomm Adreno driver, and every good result ran on Mesa Turnip T30 (PurpleVK, `vulkan.purple.so`). The
same 8455537f10 apk animates in `.debug` (Turnip installed since 09-11) and holds the bind pose in `debug2` (nothing in
`files/gpu_driver/`). The owner's release app on the Nova and the Thor's release app both log `GPU driver: no custom
driver installed, using system default` and `[gpl569] ext=0 ... mode=0`. Both acceptance runs logged `ext=1`, which on
this Adreno 740 only Turnip reports.

| package | driver | result |
|---|---|---|
| .debug: dispatcher 10-08 (MP2), 10-13 (THPS4); dispatcher and hand launch 10-17 13:00 (THPS4, 8455537f10) | Turnip T30 | animates |
| debug2: 0.5.1-rc1, 3c2338eb2b, the reverts, 8455537f10 | stock Qualcomm | bind pose |
| release, Nova and Thor: 0.5.2-rc1 | stock Qualcomm | bind pose |
| desktop: 0.5.2-rc1 (160728983a), the release app's default switches | lavapipe, mode 3 | animates (r4: t0225, t0286, t0301) |

No commit is implicated. The hand bisect ran in a package on stock, so its "first bad build" was an inference.
0.5.2-rc1's own code animates THPS4 on the desktop (r4) with the release app's defaults. 3c2338eb2b also animates
there, through the specialised pipelines (mode 3) and with every covered draw on the uber interpreter (mode 4).
Stock never runs the uber stage. `NOTES.md` Update 2 gives an account of every symptom, the closed hypothesis table
and the remedies. Symptom 8 is the bisect runs that booted to a black screen. Per lane.local, those runs took the Nova
while the owner was using it, and it is not a build defect.

## Release interim

**The switch that clears it: load Turnip T30 in the package** (Settings > GPU Driver). Nothing to revert or hold in
the 0.5.2 code. lane.local has it (R1):
- debug2 has T30.
- The release app's zip is staged and waits on the owner's tap.
- The Thor is out of service.

## Remedies (P × win)

1. R1: install T30 on the owner's installs. P 0.95, clears it today. Chased: lane.local, with the owner.
2. R2: Turnip by default on Adreno 6xx/7xx: bundle a driver, menu as the override, system driver elsewhere
   (turnipfork's recipe, `docs/investigations/adreno-driver-feasibility.md:214-218`). P 0.9, every release user.
   The owner's to decide, and lane.local is putting it to them. The PurpleVK build's licence isn't recorded, while our
   pinned Mesa `4c18636110` build is MIT and matched T30 on 220 captures. Turnip work was parked until after 0.5 on
   09-26.
3. R3: a launch guard and documentation naming Turnip as required. It stops silent stock runs.
4. R4: a GLSL workaround for the stock compiler. Not chased: under the owner's 10-17 rule the stock driver is never
   used or tested.

## Verification

- The owner judged it by eye on the Nova in `.debug` (Turnip): no bind pose on three builds. lane.local reports this as
  the acceptance.
- The kept-path acceptance frames on Turnip animate: THPS4 010/014/074 and MP2 030-038/040/051-099.

**Not run: the Nova kept-path named frames on 0.5.2-rc1 in a Turnip package.** The owner has asked that their Nova time
not be spent on long runs, and that these frames run only if they ask (relayed by lane.local). MP2 on rc1's code has
not been seen on a non-stock driver: the desktop has no route driver to reach Max. The owner's first play of the
release app after the driver tap covers both. The pathfind recipe for frames is in `NOTES.md` under "Verification".

Selftest fragments: none of `docs/testing/jobs/selftest.d/` reads `docs/lanes/bindpose1017/`. The ones that apply to
this change's shape are `98-lane-shape.sh` (lane files under `docs/lanes/<name>/`) and `99-release-note-line.sh` (no
emulator path changed, so no Release note line).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
