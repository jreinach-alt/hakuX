# thorbottom800: full-screen game on the Thor's bottom screen (#800)

State: draft

Lane: thorbottom800            Issue: #800
Base: master @ 5e4196fefd
Files: android/app/src/main/cpp/xemu_settings_android.cc, docs/lanes/thorbottom800/.gitignore, docs/lanes/thorbottom800/NOTES.md, docs/lanes/thorbottom800/OUTBOX.md, docs/lanes/thorbottom800/PR.md, docs/lanes/thorbottom800/build.sh, docs/lanes/thorbottom800/refscan.sh, docs/lanes/thorbottom800/repro.sh, docs/lanes/thorbottom800/shots/after-153d7ad370-d4.activities.txt, docs/lanes/thorbottom800/shots/after-153d7ad370-d4.logcat.txt, docs/lanes/thorbottom800/shots/after-153d7ad370-d4.png, docs/lanes/thorbottom800/shots/after-153d7ad370-d4.windows.txt, docs/lanes/thorbottom800/shots/after-ddc61cb847-d0.activities.txt, docs/lanes/thorbottom800/shots/after-ddc61cb847-d0.logcat.txt, docs/lanes/thorbottom800/shots/after-ddc61cb847-d0.png, docs/lanes/thorbottom800/shots/after-ddc61cb847-d0.windows.txt, docs/lanes/thorbottom800/shots/after-ddc61cb847-d4.activities.txt, docs/lanes/thorbottom800/shots/after-ddc61cb847-d4.logcat.txt, docs/lanes/thorbottom800/shots/after-ddc61cb847-d4.png, docs/lanes/thorbottom800/shots/after-ddc61cb847-d4.windows.txt, docs/lanes/thorbottom800/shots/before-installed-d4.activities.txt, docs/lanes/thorbottom800/shots/before-installed-d4.logcat.txt, docs/lanes/thorbottom800/shots/before-installed-d4.png, docs/lanes/thorbottom800/shots/before-installed-d4.windows.txt, docs/lanes/thorbottom800/shots/d0-launcher-only.png, docs/lanes/thorbottom800/shots/falsifier-640startup-d4.activities.txt, docs/lanes/thorbottom800/shots/falsifier-640startup-d4.logcat.txt, docs/lanes/thorbottom800/shots/falsifier-640startup-d4.png, docs/lanes/thorbottom800/shots/falsifier-640startup-d4.windows.txt
Prediction: none: no arm (window sizing on a secondary display; no golden or capture covers a 1240x1080 panel)
Needs device: yes    Needs NDK: yes

Release note (rendering): a game started on a screen smaller than 1280x720 in either dimension, such as the Ayn Thor's bottom screen, now fills the screen instead of a 640x480 corner.

A game launched on the Thor's bottom screen (display 4, 1240x1080) drew as a 640x480 picture in the bottom-left
corner. At window creation `ui/xemu.c` shrinks the window to 640x480 when the display is smaller than the startup
size. Android forces that startup size to 1280x720, and 1240 < 1280. The Android blit sizes its viewport from the
window, and nothing resizes the window again. Present in 0.3.1: the code is identical at e64e336d27, v0.3.2,
v0.3.3-j1 and master.

Fix: the Android startup size is 640x480, the minimum. On Android SDL's window always takes the surface's size,
so the shrink check is this value's only reader. It cannot fire now, and displays of at least 1280x720 take the
same path as before.

| Thor display 4 | result |
|---|---|
| before (0.4.1-1003-e0b22e69ad) | 640x480 corner, `shots/before-installed-d4.png` |
| after (153d7ad370) | 1240x930, 4:3, `shots/after-153d7ad370-d4.png` |

The display 0 screencap is black on this Thor whatever is shown, because the panel is dead; logcat shows the game
at 1920x1080 there. The Nova regression screenshot is queued (`1791128091-thorbottom800-3215528`). Preflight:
every code gate ok. `coverage` fails on six open issues with no tracker row on origin/board (#794-#801, #800
included); that is board bookkeeping, which this lane may not edit.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
