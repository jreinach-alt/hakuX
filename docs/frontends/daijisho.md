# Daijisho

**Status: not yet wired — blocked.** Nothing below is a tested, working
config; it's a record of what was tried and where it stopped, so the next
attempt doesn't repeat the same dead ends.

| | |
|---|---|
| Frontend | Daijishō, `com.magneticchen.daijishou` (version not confirmed in-app) |
| Device | Thor (AYN handheld), Android 13 (SDK 33) |
| hakuX | 0.4.1-1004-40b62fd533, package `com.jreinach.hakux` |

## Automation note

`adb shell uiautomator dump` fails against Daijisho every time, with
`ERROR: null root node returned by UiTestAutomationBridge.` — it does not
expose a standard Android accessibility tree (it's Flutter-rendered, not
native views). Screenshot + coordinate-tap is the only automation method
that works here.

## What was tried

The goal was a custom "Platform" entry in Daijisho pointing its `launch`
command at `com.jreinach.hakux/com.rfandango.haku_x.LauncherActivity`, the
same activity ES-DE's find rule uses.

Settings > Library > **"New platform"** opens a dialog with RetroAchievements
and Player-settings sections, including a **"Default player"** autocomplete
field plus CANCEL/SAVE.

![Daijisho's Settings > Library screen](images/daijisho-settings.png)

Typing a value into "Default player" that matches a real option, then
pressing SAVE, is rejected: **"Please select from the list."** The field
requires an actual tap-selection from Daijisho's own in-app suggestion
dropdown, not typed text — however exact. That dropdown is believed to
render underneath the fullscreen/extracted IME keyboard this device uses for
text entry on a small landscape screen: the suggestion list would normally
anchor right below the field, but the whole screen goes black-keyboard while
typing, and no suggestion list has ever been visible in any screenshot taken
mid-type.

Three other routes to platform creation were checked and ruled out:
- **Settings > Library > "Download platforms"** — a 122-item checkbox list
  of predefined platforms with an IMPORT button. This is a bulk-import flow
  for known platforms, not a custom-platform editor, and the list is slow to
  scroll (short swipes barely move it; a long 2000 ms swipe didn't move it
  further and also triggered this device's screen-sleep bug).
- **Settings > Library > "Inspect platforms"** — read-only, lists the 27
  already-configured platforms, no add control.
- **The Library tab's platform-card carousel** — swiped all the way through
  on the hypothesis that a trailing "+ Add platform" card might exist past
  the last real platform. It does not: swiping past "TurboGrafx-CD, 27 of
  27" wraps back around to "Nintendo 3DS, 1 of 27."

## NEED:

Either a confirmed way to select (not type) a value into Daijisho's
"Default player" autocomplete field with the suggestion overlay hidden
behind a fullscreen IME on a small landscape screen, or a Daijisho
config/import file this lane could push directly to define a custom
platform's launch command, bypassing the UI autocomplete entirely. Without
one of those, Daijisho cannot be wired to hakuX by hand in the UI on this
device.

Daijisho was left on its Settings screen; no app data was touched, nothing
was left stuck mid-dialog.
