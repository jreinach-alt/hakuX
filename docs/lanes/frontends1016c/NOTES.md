# frontends1016c notes (lane.local, 2026-10-16 evening)

## What changed

- `docs/frontends/daijisho.md`: was a test report. Rewritten as user-facing
  "add hakuX CE as an app" steps (Apps tab). The material below moved here.
- `docs/frontends/stock-launcher.md`: the Retroid section was "not yet
  tested". It is now tested on the Nova.
- `docs/frontends/README.md`, `docs/releases/v0.5.1.md`: the one status line
  each.

## Retroid launcher test (Nova, ee317437, 0.5.1-rc1)

- Launcher: `com.retroidpocket.gamelauncher/.activities.RpGameLauncher`.
  Touch only moves focus; D-pad centre (keycode 23) activates; B
  (keycode 97) opens Apps.
- hakuX CE tile opens `GameLibraryActivity`; a game boots at 59 fps; pause
  menu and Exit work; cold start after `am force-stop` works.
- The default home app was switched ES-DE -> Retroid launcher with
  `cmd package set-home-activity` and restored to
  `org.es_de.frontend/.MainActivityHomeApp` (verified with
  `resolve-activity`). The Nova screen timeout is 30 s, which loses a key
  press that follows a long gap; do the wake and the key in one on-device
  command.

## Stop hook kills a running hakuX and sleeps the screen (finding)

`docs/testing/stop-emulator.sh` runs at every session's turn end
(`.claude/settings.json`). For each device it skips only when a hold exists
whose `.why` does NOT contain the word "battery" (`held_by`: `grep -qi
battery`), or a lease is under 90 s old. Otherwise it `am force-stop`s every
hakuX package and sends `KEYCODE_SLEEP`.

- The Thor hold's `.why` said "stop above 42 C battery temp", so the hook
  treated it as a battery hold and force-stopped and slept the Thor on every
  turn end. Reworded to "cell temp" (original saved in the session
  scratchpad).
- The Nova has no standing hold, so any session's turn end force-stops
  hakuX and sleeps the Nova, including during the owner's play.
- Not an app defect. Fix options: a narrower match in `held_by` (a harness
  fold), or a standing non-battery hold on the device while someone plays
  (costs fold gates while held).

## Daijisho: what was tried and ruled out (moved from daijisho.md)

Custom "Platform" editor (Settings > Library > New platform): the "Default
player" field rejects typed text ("Please select from the list.") and the
suggestion dropdown is hidden by the fullscreen keyboard. Not needed once
the Apps tab worked. "Download platforms" is a bulk import of predefined
platforms; "Inspect platforms" is read-only; the Library carousel has no
add card. `uiautomator dump` fails against Daijisho (Flutter): screenshots
and coordinate taps only.

## Daijisho/Pegasus intermittent DocumentsUI glitch (earlier finding)

Two of four force-stop-then-relaunch attempts opened Android's Files app at
Downloads instead of hakuX's Game Library; backing out and relaunching
always worked. Screenshot: `docs/frontends/images/daijisho-documentsui-glitch.png`.
Not reproduced in the 2026-10-16 evening Thor new-user test.
