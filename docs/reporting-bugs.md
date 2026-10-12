# Reporting bugs

A report with the details below usually gets looked at faster, because
nobody has to ask for them. This page explains how to gather each one.

Use the issue tracker's **Bug Report** form for a problem that isn't tied to
one game, or **Title / Compatibility Report** for a problem with -- or a
compatibility rating for -- a specific title.

## Before you file

- Check [`KNOWN_ISSUES.md`](../KNOWN_ISSUES.md) -- a few user-facing
  behaviours are documented there rather than tracked as bugs.
- Search the [issue tracker](https://github.com/jreinach-alt/hakuX/issues)
  for an existing report.
- Update to the latest release if you can; the problem may already be fixed.

## Device

Make and model, SoC/GPU, Android version, and RAM. All four matter: hakuX
needs a 64-bit ARMv8.2 CPU with LSE atomics, and GPU driver quirks are often
specific to one SoC family.

## hakuX version and install type

The Game Library screen shows the running build's version in a small label
in one corner. If you can't find it, open Android Settings, then Apps, then
hakuX, then App info -- the version is shown there too.

Install type matters because a release build and a test (debug) build are
separate apps with separate settings, HDD images and saves:

| Install | Package | Launcher label |
|---|---|---|
| Release | `com.jreinach.hakux` | hakuX (fork) |
| Test build (debug) | `com.jreinach.hakux.debug` | hakuX (test builds) |

## Game

Title, region/version, title ID if you know it, and the image format
(`.iso`, or `.xiso.iso` once hakuX has converted it). These narrow down
whether a problem is title-specific or general.

## Capturing a logcat

```bash
adb logcat -c                     # clear old lines so the capture is just this run
# reproduce the problem on the device
adb logcat -d > hakux-log.txt     # dump everything captured since the clear
```

Most of hakuX's own logging is tagged `hakuX` or `hakuX-<component>` (for
example `hakuX-stderr`, which is where the native emulator core's error
output lands -- nv2a prints the value it is about to abort on there before
it aborts). A crash from the Android side shows up under `AndroidRuntime`.
To filter rather than attach the whole file:

```bash
adb logcat 'hakuX:V' 'hakuX-stderr:V' 'AndroidRuntime:E' '*:S'
```

When unsure, attach the unfiltered dump -- it is more useful to have too
much than to have filtered out the one line that mattered.

## Screenshots and video

A normal Android screenshot (power + volume-down) or screen recording works
fine and needs no setup.

## Debug Capture (in-app)

For a rendering problem, a per-draw capture is often more useful than a
screenshot.

1. Settings, then Debug, then Debug Tools -- turn this on.
2. Pause the game, press Debug Capture, then Capture 1/5/10 Frames.

The captured frames are written under the app's external files directory,
in `rt_dumps/diag_session_<frame>/`. Pull them with:

```bash
adb pull /sdcard/Android/data/<package>/files/rt_dumps ./rt_dumps
```

using the package for your install type (`com.jreinach.hakux` for release,
`com.jreinach.hakux.debug` for a test build). Attach the relevant
`diag_session_*` folder (zip it first) to your issue.

## Putting it together

Fill in the Bug Report or Title / Compatibility Report form on the issue
tracker. Attach whatever you gathered above -- you don't need all of it for
every report, but the more of it you have, the less back-and-forth it takes
to get your issue looked at.
