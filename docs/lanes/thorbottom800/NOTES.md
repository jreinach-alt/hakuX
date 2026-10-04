# thorbottom800 (#800): game shows as a thumbnail on the Thor's bottom screen

2026-10-04. Thor `bdc158a5`: display 0 "Built-in Screen" 1920x1080 (top, dead); display 4 "Screen-2" 1240x1080,
FLAG_PRESENTATION (bottom). Physical ids for `screencap -d`: 4630946441858561667 (0), 4630946482288158084 (4).

## Reproduction

`repro.sh <pkg> <display> <out> [secs]`: wake, `am start --display N` LauncherActivity with Amped's ISO as
`rom_path`, wait 25 s, `screencap -d <phys>`, keep the SDL/hakuX logcat lines, force-stop. The owner's session was
checked first each time (device asleep, only the game library resumed on display 4).

Installed build 0.4.1-1003-e0b22e69ad on display 4: the game is a 640x480 picture in the bottom-left corner of the
1240x1080 panel; the FPS overlay is full size (`shots/before-installed-d4.png`).

## What each stage believes the surface is (display 4, before the fix)

| stage | size | source |
|---|---|---|
| Java `SDLSurface.surfaceChanged` window | 1240x1080 | logcat `Window size: 1240x1080` |
| Java `SDLSurface` device (`getRealMetrics` of the activity's display) | 1240x1080 | logcat `Device size: 1240x1080` |
| SDL `Android_CreateWindow` | 1240x1080 | sets `window->w/h` from `Android_SurfaceWidth/Height`, whatever size was asked for |
| SDL display mode (`SDL_GetCurrentDisplayMode`) | 1240x1080 | `Android_DeviceWidth/Height` |
| xemu startup size | 1280x720 | `xemu_settings_android.cc` sets it; the toml key is not parsed on Android |
| xemu.c after the "display smaller than startup size" check | **640x480** | `SDL_SetWindowSize(m_window, 640, 480)`, because 1240 < 1280 |
| `android_blit_frame` viewport | **640x480** | `SDL_GL_GetDrawableSize(m_window)`, which on Android is the window size |

The Java side and SDL both have the right size. The one wrong stage is the xemu.c shrink, and the blit trusts the
window. Nothing grows the window back, because Android only sends a resize when the surface changes, and it does
not change during a session on one display. With the viewport at 640x480 and a 640x480 (4:3) texture, the blit
fills the viewport, which sits at the GL origin: the bottom-left corner.

Display 0 (1920x1080) and the Nova never meet `disp_mode.w < 1280 || disp_mode.h < 720`, so they have never shown it.
Any panel narrower than 1280 or shorter than 720 would.

The brief's suspects (default-display metrics in `SDLSurface`, a Presentation path) are not the cause: `SDLSurface`'s
`getDefaultDisplay()` is called on the activity's own WindowManager, which returns display 4, as the logcat shows.

## Bisect: present in 0.3.1

By reading, not by device: the shrink (`ui/xemu.c`), the window-sized blit, and an Android startup size wider than
1240 are identical at the 0.3.1 version bump e64e336d27 (2026-04-09), v0.3.2, v0.3.3-j1 = d494f1dcb4 (the commit
after 40048cc284) and master 5e4196fefd (`refscan.sh` prints each). The blit dates from b75429b103 (2026-02-06), the
1280x720 Android default from 08f6066a5a (2026-02-16). No candidate APK is in `dispatch/builds`; the 0.3.1 release
APK (`~/hakuX/hakuX.apk`, `com.rfandango.haku_x` 0.3.1) is not debuggable, so it would need the setup wizard by hand
on the owner's device. That was not worth a device session when the code is identical.

## A void falsifier, kept so nobody repeats it

I set `startup_size = '640x480'` in the Thor's `xemu.toml` (backed up and restored) expecting a full-screen game.
It was still a 640x480 corner (`shots/falsifier-640startup-d4.png`). That is not evidence against the cause: the
Android settings loader does not read `startup_size` from the toml at all (only `vsync` in `[display.window]`), so
the edit never reached xemu. A settings-file workaround for the owner does not exist for the same reason.

## Fix

`xemu_settings_android.cc`: the Android startup size is 640x480, the minimum, so the shrink cannot fire on any
panel. On Android this value has no other reader: `Android_CreateWindow` ignores the requested size and the toml
does not carry it. `ui/xemu.c` is outside this lane's territory (android/**); guarding the shrink with
`#ifndef __ANDROID__` there would be the more direct form of the same fix.

With the window at 1240x1080, the blit computes w_ratio 1.148 against a 4:3 texture, scale_y 0.861: a 1240x930
picture, letterboxed top and bottom, correct aspect.

## Verification (Thor, ddc61cb847 debug build from this worktree)

| launch | screenshot | result |
|---|---|---|
| display 4, installed 0.4.1-1003-e0b22e69ad | `shots/before-installed-d4.png` | 640x480 in the bottom-left corner |
| display 4, ddc61cb847 | `shots/after-ddc61cb847-d4.png` | full width, 1240x930 with 75 px bars top and bottom (4:3) |
| display 0, ddc61cb847 | `shots/after-ddc61cb847-d0.png` | black; unreadable, see below |

Display 0 cannot be read by screencap on this Thor: it is black with only the Daijishou launcher on it too
(`shots/d0-launcher-only.png`), powerMode On. The top panel is dead. On display 0 the game did run (MainActivity
resumed there, 1560 frames by 25 s, `Window size: 1920x1080`, `Device size: 1920x1080`). The fix only changes
behaviour where `disp_mode.w < 1280 || disp_mode.h < 720` held, and a 1920x1080 display never met it, so display
0 and any panel of at least 1280x720 take exactly the path they took before. The Nova regression screenshot is a
queued dispatcher soak (the Nova is held by lane.pathfind): request `1791128091-thorbottom800-3215528`,
Castlevania 90 s, a frame every 30 s.

## Build notes

`build.sh` builds this worktree's debug APK. A fresh worktree's glib configure fails with "Could not detect Ninja"
unless the SDK's `cmake/3.30.3/bin` is on PATH; the script adds it.

## Not to repeat

- Editing `startup_size` in the device's `xemu.toml` does nothing on Android (see the void falsifier above).
- Screenshots of the Thor's display 0 are black whatever is on it; use the logcat sizes there.
