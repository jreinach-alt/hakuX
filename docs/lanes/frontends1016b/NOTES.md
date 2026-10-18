# frontends1016b notes

Follow-up to lane.frontends1016 (folded as 545886f9c0). Read
`docs/lanes/frontends1016/NOTES.md` and `docs/frontends/*.md` first per the
brief; this file only records what's new in this lane.

## Resume (attempt 2)

The first attempt ended mid-task, not blocked: Pegasus was finished and
committed (`deb99b09e2`), and Daijisho's Apps-tab integration had already
been found and was sitting as an uncommitted edit to `daijisho.md` plus four
uncommitted screenshots (`daijisho-apps-tab.png`,
`daijisho-documentsui-glitch.png`, `daijisho-launch-cold.png`,
`daijisho-launch-second.png`) when the turn/session cap cut the session off
before it could commit, update `README.md`, verify links, or mark the PR
ready. Nothing needed to be redone — the working tree still had the
in-progress Daijisho content intact. This attempt commits that work,
updates `README.md`'s index, verifies links and `docs_freshness.py`, and
marks the PR ready.

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

Installed on the Thor: Daijishō 1.8.1, versionCode 426
(`dumpsys package com.magneticchen.daijishou`).

Integration found directly in Daijisho's own UI, without touching the
custom "Platform" editor the first lane got stuck on: Daijisho has its own
**Apps** tab (top nav: Library / Widgets / Apps / Settings) — a generic
Android app list, the same mechanism as Pegasus's built-in "Android"
collection. hakuX CE shows up there under its installed display name
(still cached as "hakuX (fork)" from before the rename, same stale-label
finding as Pegasus). A single tap launches
`com.jreinach.hakux/com.rfandango.haku_x.LauncherActivity` directly,
confirmed via `dumpsys activity recents` — no separate select-then-confirm
step, unlike Pegasus.

Per the brief's "stop at the first [integration attempt] that gets a game
launched from Daijisho's own UI": the Apps tab was tried before the
keyboard-dismissal fix (step 2a) or file-import route (step 2b) because it
surfaced first while re-exploring Daijisho's nav after the first lane's
NOTES; since it worked, 2a/2b were not attempted. No hakuX-side change
needed — no NEED: for Daijisho, same as Pegasus.

Launched twice from Daijisho's own UI, same pattern as Pegasus:
- Cold: Apps tab → hakuX icon → Game Library → Play → Atlus splash at
  29 FPS (`images/daijisho-launch-cold.png`).
- After `am force-stop com.jreinach.hakux`, relaunched from the Apps tab
  again → Game Library → Play → Atlus splash at 29 FPS
  (`images/daijisho-launch-second.png`).

### Finding: the DocumentsUI glitch is not Pegasus- or Daijisho-specific

Across four force-stop-then-relaunch attempts made through Daijisho and
Pegasus combined this lane, two landed cleanly on the Game Library and two
opened Android's `DocumentsUI` Files app at Downloads instead
(`images/daijisho-documentsui-glitch.png`). `dumpsys activity
recents`/`activities` confirmed both times that this was hakuX's own
`LauncherActivity` re-triggering a games-folder recovery/re-grant flow on a
fresh cold start, not something either frontend caused. Backing out with
Back and relaunching always reached the Game Library on the next attempt.
Written up in `daijisho.md`'s "Known limits / findings" as a note for
whoever next touches hakuX's Setup Wizard / SAF-permission code — out of
scope for this lane to fix, and it self-resolved every time.

The custom "Platform" editor investigation from the first lane (blocked on
the "Default player" autocomplete field hiding its suggestion list behind
the fullscreen keyboard) is kept in `daijisho.md` under "What was tried and
ruled out" for whoever wants the fuller platform-card integration later —
not needed to satisfy this lane's brief, since the Apps tab already
launches hakuX from Daijisho's own UI.

## Device

Thor, serial `bdc158a5`. Battery temperature checked before every launch,
stayed in the 30-31°C range throughout (well under the 42.0°C stop
threshold). Device lease held via `docs/testing/hold_device.sh 90` for the
duration of hands-on work; released at the end of the session.
