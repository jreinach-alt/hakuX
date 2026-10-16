# Launching hakuX from a frontend

Four frontends were tried against hakuX on a real device (Thor, Android 13,
hakuX 0.4.1, package `com.jreinach.hakux`). Status of each:

| Frontend | Status | Notes |
|---|---|---|
| [ES-DE](es-de.md) | **Tested on the Thor** | Custom system + find rule, confirmed launching a game twice |
| [Daijisho](daijisho.md) | Not wired — blocked | "Default player" field rejects typed selections; see the NEED: |
| [Pegasus](pegasus.md) | Not installed — blocked | APK has no source other than GitHub; this lane doesn't fetch from GitHub |
| [Stock launcher](stock-launcher.md) | **Tested on the Thor** (AYN odinlauncher); Retroid variant **not yet tested** | Launches hakuX's own Game Library; no ROM-passing mechanism, by design of a generic Android launcher |

Never treat an untested step as tested: "tested on the Thor" above means a
real launch was run and screenshotted on that device, in this lane. Anything
else is a hypothesis or a known blocker, written up as such on its own page.

## About the app name

The owner renamed the display name from "hakuX (fork)" to **hakuX CE**
(2026-10-16). The package id `com.jreinach.hakux` and the activity
`com.rfandango.haku_x.LauncherActivity` are not display names and did not
change — they're what every config on these pages targets. Every place the
old display name showed up is listed in
[`docs/lanes/frontends1016/NOTES.md`](../lanes/frontends1016/NOTES.md).
