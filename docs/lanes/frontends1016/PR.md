# Wire hakuX into four launchers (ES-DE, Daijisho, Pegasus, stock), tested on the Thor

State: ready

Lane: frontends1016            Issue: #433
Base: master @ 4bf47129b1 (merged in this lane; branched originally at 15a72e10dc)
Files: docs/frontends/README.md, docs/frontends/daijisho.md, docs/frontends/es-de.md, docs/frontends/pegasus.md, docs/frontends/stock-launcher.md, docs/frontends/images/daijisho-settings.png, docs/frontends/images/es-de-game-list.png, docs/frontends/images/es-de-launch-second.png, docs/frontends/images/stock-app-drawer.png, docs/frontends/images/stock-launch.png, docs/es-de/README.md, docs/lanes/frontends1016/NOTES.md, docs/lanes/frontends1016/PR.md
Prediction: none: analysis-only + on-device verification, no pixel/perf claim
Needs device: yes (Thor, bdc158a5, by hand -- no dispatcher)    Needs NDK: no

Release note (performance|stability|rendering|other|none): none

## Summary

Wired and tested hakuX against all four requested launchers on the Thor
(`bdc158a5`), by hand with adb, no dispatcher, no uninstalls or data clears.
Two are tested and working; two are blocked, each with a NEED: written up
rather than papered over.

| Launcher | Result |
|---|---|
| ES-DE | **Tested on the Thor.** Existing `docs/es-de/*` drafts were correct as written; launched a game twice (cold + after force-stop), reached the game's own loading screen both times. |
| Daijisho | **Blocked.** Its "Default player" field only accepts a tap-selection from an in-app suggestion list, never typed text ("Please select from the list"), and that list is believed hidden behind this device's fullscreen IME. No alternative (non-UI) path to define a platform was found. See `docs/frontends/daijisho.md`. |
| Pegasus | **Blocked.** Not installed; pegasus-frontend.org's own download page is a thin JS wrapper around the GitHub releases API with no independently-hosted APK, so there is no Android APK source other than GitHub, which this lane does not fetch from. See `docs/frontends/pegasus.md`. |
| Stock launcher (AYN odinlauncher) | **Tested on the Thor.** No config needed — launched twice (cold + after force-stop) via the app drawer/search. Known limit: a stock launcher can only open hakuX's own Game Library, not a specific game, since it has no ROM-scanning mechanism. The Retroid variant stays **not yet tested** (Nova, lane.local, later). |

Also attempted the 0.4.1 -> 0.5.0 in-place upgrade test the brief asked for;
it fails before touching any app data because the installed 0.4.1 build was
signed with the Android debug key, not the real release key -- a
release-pipeline defect, not a frontend-wiring issue. Full details, thermal
readings (never above 32.0 C / 320, well under the 42.0 C stop threshold),
and the one-time Setup-Wizard prerequisite are in
`docs/lanes/frontends1016/NOTES.md`.

## For lane.local (README.md is held by titlekey1016)

Please add one line to the top-level README.md pointing at
`docs/frontends/README.md` as the index of tested/blocked frontend wiring
instructions for hakuX, e.g. under whatever "docs" or "guides" section
already exists there.

## App name tracking

Every on-device or in-doc occurrence of the display name "hakuX (fork)" is
listed in `docs/lanes/frontends1016/NOTES.md` under "App name occurrences",
for a future one-grep rename. The package id `com.jreinach.hakux` and
activity `com.rfandango.haku_x.LauncherActivity` are untouched and do not
change on a rename.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
