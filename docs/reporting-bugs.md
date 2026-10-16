# Reporting a bug

_Last updated 2026-10-13, for version 0.5.0._

A report that has the details below can be worked on straight away.

Use the **Title / Compatibility Report** form for a problem with one game, or
to report how well a game runs. Use **Bug Report** for anything else.

## Before you file

- Read [Known issues](../KNOWN_ISSUES.md).
- Search the [issue tracker](https://github.com/jreinach-alt/hakuX/issues).
- If you can, update to the latest release.

## What to include

- **Device:** the make and model, chip, Android version and RAM.
- **hakuX version:** shown in a small label on the library screen, and under
  Android Settings → Apps → hakuX (fork).
- **Which build:**

  | Build | Launcher name | Package |
  |---|---|---|
  | Release | hakuX (fork) | `com.jreinach.hakux` |
  | Test build | hakuX (test builds) | `com.jreinach.hakux.debug` |

  The two are separate apps, each with its own settings, hard disk image and
  saves.
- **Game:** the title, its region, and its title ID if you know it.
- **What happened:** what you did, what you expected, and what you saw. A
  screenshot or screen recording helps.

## A log (optional, very useful for crashes)

With the device connected over USB and `adb` installed:

```bash
adb logcat -c                    # clear old lines
# reproduce the problem
adb logcat -d > hakux-log.txt    # save everything since the clear
```

Attach the whole file. The emulator's own lines are tagged `hakuX` and
`hakuX-stderr`. A crash in the Android app is tagged `AndroidRuntime`.

## A graphics capture (optional, for rendering problems)

1. Turn on Settings → Debug → **Debug Tools**.
2. In the game, open the pause menu and choose **Debug Capture**, then
   **Capture 1 Frame** (or 5, or 10).
3. Copy the capture off the device, using your build's package name:

   ```bash
   adb pull /sdcard/Android/data/com.jreinach.hakux/files/rt_dumps ./rt_dumps
   ```

4. Zip the `diag_session_*` folder and attach it.
