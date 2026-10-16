# frontends1016b notes

Follow-up to lane.frontends1016 (folded as 545886f9c0). Read
`docs/lanes/frontends1016/NOTES.md` and `docs/frontends/*.md` first per the
brief; this file only records what's new in this lane.

## Pegasus

Installed on the Thor: `alpha16-82-gc3462e68`, versionCode 1945
(`dumpsys package org.pegasus_frontend.android`).

Pegasus's "Android" collection is a built-in pseudo-platform that auto-lists
every installed app (confirmed via its grid showing Firefox, Chrome,
Daijisho, RetroArch, hakuX's three variants, etc.) — there is no per-game
metafile or hand-written `launch:` line to configure for this path. Selecting
hakuX and confirming targets `com.jreinach.hakux/com.rfandango.haku_x.LauncherActivity`
(confirmed via `dumpsys activity recents`, same component the stock launcher
and ES-DE use).

hakuX version actually running on the release build: `0.5.0-1016-2636e89f4a`
(read off the Game Library footer) — not the brief's assumed "0.4.1,
debug-signed." Recorded the real version in `pegasus.md`.

Completed hakuX's own Setup Wizard on this device for the first time this
lane (previously blocked — see "UI finding" below), reaching a working Game
Library with `41540002-Shin_Megami_Tensei_Nine` (2.1 GB) visible.

Launched the game twice from Pegasus's own UI, not adb, per the brief:
- Cold: Game Library → Play → Atlus splash at 29 FPS
  (`images/pegasus-launch-cold.png`).
- After `am force-stop com.jreinach.hakux`, relaunched from Pegasus (still
  showing hakuX selected in the left detail panel) → Game Library → Play →
  actual gameplay rendering at 26 FPS (`images/pegasus-launch-second.png`).

Both confirmed via `dumpsys activity activities` showing the expected
`topResumedActivity` before screenshotting.

### UI finding: hakuX's Setup Wizard Next/Finish button can render below the fold

On at least one render of the wizard (seen after a force-stop/relaunch), the
Back/Next button row sits mostly or fully below the visible screen edge —
only a thin sliver was visible at first. The wizard card is vertically
scrollable; a swipe-up inside the card (e.g.
`input -d 4 swipe 620 700 620 400 300`) brings the full button row into view
at roughly y≈778-787. This blocked progress for a while before being
diagnosed — worth knowing for any future lane that hits an apparently
dead-ended wizard step on this device/build.

### Finding: one-time transient DocumentsUI glitch after Setup Wizard completion

Immediately after finishing the Setup Wizard and force-stopping hakuX, the
very next launch (via Pegasus) landed on Android's `DocumentsUI` folder
picker at the ROMS root instead of the Game Library.
`dumpsys activity recents` showed this picker was opened by hakuX's own
`LauncherActivity` in the same task — not a stray leftover window — meaning
hakuX re-ran its games-folder recovery flow on that one launch. Backing out
(`KEYCODE_BACK` x2) and launching again from Pegasus a second time went
straight to the Game Library, and every launch since has been clean. Treated
as a recorded finding, not a blocker: no hakuX code was touched (out of
scope for this lane), and it did not reproduce on retry.

No NEED: for Pegasus — it wires up with zero hakuX-side config.

## Daijisho

(To be filled in as this work proceeds.)

## Device

Thor, serial `bdc158a5`. Battery temperature checked before every launch,
stayed in the 30-31°C range throughout (well under the 42.0°C stop
threshold). Device lease held via `docs/testing/hold_device.sh 90` for the
duration of hands-on work; released at the end of the session.
