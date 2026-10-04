# thorbottom800 OUTBOX (#800)

## 2026-10-04 08:45 PDT: cause found, pre-existing in 0.3.1

**Reproduced** on the Thor with the installed build (0.4.1-1003-e0b22e69ad), launched on display 4 (bottom,
1240x1080): the game draws as a 640x480 picture in the bottom-left corner of the panel, while the FPS overlay is
full-size. Screenshot: `docs/lanes/thorbottom800/shots/before-installed-d4.png`.

**Cause.** At window creation `ui/xemu.c` compares the display mode with the configured startup window size, and if
the display is smaller in either dimension it shrinks the window to the 640x480 minimum. On Android that startup size
is always 1280x720 (`xemu_settings_android.cc` sets it, and the toml key is not read). The bottom screen is 1240 wide,
and 1240 < 1280, so the window is set to 640x480. Nothing resizes it afterwards, because Android only sends a resize
when the surface changes. The Android blit sets its viewport from that window size, so the game fills a 640x480
rectangle at the GL origin, which is the bottom-left corner. The top screen (1920x1080) and the Nova never meet the
condition, which is why it only shows on the bottom screen.

**First bad ref: none; present in 0.3.1.** The shrink and the window-sized blit are identical at the 0.3.1 version
bump (e64e336d27, 2026-04-09), v0.3.2, v0.3.3-j1 (d494f1dcb4, the commit after 40048cc284) and master. The blit
dates from b75429b103 (2026-02-06), and the 1280x720 Android startup size from 08f6066a5a (2026-02-16). This is from
the code, not a device bisect: the 0.3.1 release APK on the host is not debuggable, so it cannot be set up headless
on the Thor. Any panel narrower than 1280 or shorter than 720 will show the same thumbnail.

Workaround until the fix build: none in settings (the Android build ignores the window-size key). Fix in progress on
lane/thorbottom800.
