# mkdawhite1018: Mortal Kombat: Deadly Alliance arena floors and walls draw flat white (#1058)

State: draft

Lane: mkdawhite1018            Issue: #1058 #433
Base: master @ eb46eb2548
Files: docs/lanes/mkdawhite1018/NOTES.md, docs/lanes/mkdawhite1018/PR.md, docs/lanes/mkdawhite1018/mkda-arcade.route
Prediction: none: analysis-only (so far)
Needs device: yes    Needs NDK: no

Mortal Kombat: Deadly Alliance draws its arena floors, and the walls and pillars nearest the camera, flat
white. The fighters, the floor decals, the HUD and the far backdrop are drawn correctly. On the Kenshi
cloud platform a textured central disc sits beside a white outer ring, so the fault is per material, not
per frame.

The 10-06 sighting ran on Turnip, not on the stock driver. Its logcat reads
`[gpl569] ext=1 lib=1 fast=1 interp=1 requested=3 mode=3`, and the stock driver gives `ext=0 ... mode=0`.
That points at an emulator defect. `NOTES.md` sections 1-3 have the frames, the driver evidence and the
Already-tried table.

The first Nova run on the 10-18 build did not start, because the dispatcher could not copy the disc to the
Nova. Its staging push passes a `/mnt/d/...` path to Windows `adb.exe`, which cannot open it
(AGENTS.md:827-828). No staged-disc push has succeeded since that path was added on 10-17; Halo's request
at 06:17 failed the same way. A one-line fix to `dev_push` in `docs/testing/dispatcher.sh` would clear it,
and `NOTES.md` section 6 has the evidence and that fix. The recorded route for the run is
`mkda-arcade.route`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
