# mkdawhite1018: Mortal Kombat: Deadly Alliance arena floors and walls draw flat white (#1058)

State: draft

Lane: mkdawhite1018            Issue: #1058 #433
Base: master @ 127cf0f2c1
Files: docs/lanes/mkdawhite1018/NOTES.md, docs/lanes/mkdawhite1018/PR.md, docs/lanes/mkdawhite1018/WAITING, docs/lanes/mkdawhite1018/mkda-arcade.route
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

No run on the 10-18 build has reached the title yet. Both attempts failed while the dispatcher was
copying the disc to the Nova:

| Request | Failure | Fix |
|---|---|---|
| 1792337550 (08:33) | `adb.exe` was handed a `/mnt/d/...` path and could not open it | `wslpath -w` in `dev_push`, folded 127cf0f2c1 (lane.dispatchpush1018) |
| 1792345978 (11:05) | the disc transferred and its sha matched; then `dev_push` required mode 660 on it, and the SD card's mount pins every file at 770 (`dispatcher.log` 29392, and the doctor's retry at 29395) | not yet made: skip the 660 step for the read-only disc push in `ensure_title_staged` (`NOTES.md` 7.1) |

The 660 rule is right for the read-write titles disk on internal storage, and those pushes should keep it.
A disc is only read, and the app booted this disc from this SD path on 10-06. `NOTES.md` 7.1 has the
change and a selftest for it: a fake `adb` whose chmod does nothing and whose stat reports 770. Once the
fix is deployed, the same request is re-queued unchanged, on the recorded route `mkda-arcade.route`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
