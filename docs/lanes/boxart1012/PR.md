# boxart1012: box-art lookup is opt-in, asked at setup (#433, 0.5)

State: ready

Lane: boxart1012          Issue: none (#433 umbrella)
Base: master @ 3d41440129 (merged; was lane/debugcap1012 @ 151c06cb47 + lane/pubdocs1012 @ 13756ce96a)
Files: android/app/src/main/java/com/rfandango/haku_x/GameLibraryActivity.kt, android/app/src/main/java/com/rfandango/haku_x/SetupWizardActivity.kt, android/app/src/main/res/layout/activity_setup_wizard.xml, android/app/src/main/res/values/strings.xml, PRIVACY.md, docs/lanes/boxart1012/PR.md
Prediction: none (UI and default change; no measurement)
Needs device: no (the fold's boot gate)    Needs NDK: no

## What changed

Box-art lookup was on by default, with a switch in the library to turn it
off; nothing asked first. It is now off until the user chooses it:

- **Setup wizard.** `SetupWizardActivity` gained a 5th page ("Box Art") with
  a `MaterialSwitch` (`switch_setup_box_art_lookup`, unchecked by default)
  and one sentence saying exactly what a lookup sends and to whom. The
  returning-user skip-ahead logic (`startStep`) and the Next-button enable
  logic (`updateButtons`) both used to assume the disc page was the wizard's
  last page (`pages.size - 1`); both now name the disc page explicitly
  (`pages.indexOf(pageDisc)` / an explicit `when` branch), so the new box-art
  page doesn't break either. `finishSetup()` now writes
  `library_box_art_lookup` from the switch's state alongside `setup_complete`.
- **Library.** `GameLibraryActivity` now reads `library_box_art_lookup` with
  a default of `false` (was `true`) — the only place in the codebase that
  reads or writes that key, confirmed by grep. The library's own switch
  (`switch_box_art_lookup`) still exists and still lets you change the
  choice at any time.

## Every fetch path, and how it is gated

Two things in `GameLibraryActivity.kt` can touch the network for box art, and
one thing cannot:

1. **`ensureCoverIndexLoaded()`** reads `assets.open("X1_Covers.txt")` — a
   file bundled in the APK. This is the "cover index" the brief asked me to
   confirm; it is a local asset read, never a network request, with or
   without the pref. I'm flagging this because the brief's phrasing assumed
   it might need gating as a fetch — it doesn't, since it never leaves the
   device.
2. **`lookupBoxArtUrl(...)`** matches a game's file name against that local
   index and returns a `raw.githubusercontent.com/izzy2lost/X1_Covers/...`
   URL string. Also no network call by itself — it just builds a string.
3. **`coverView.load(url) { ... }`** (Coil) is the one real network GET,
   inside `bindCoverArt()`. `bindCoverArt()` opens with
   `if (!boxArtLookupEnabled) return` before calling `ensureCoverIndexLoaded()`
   or `lookupBoxArtUrl()`, so with the pref false nothing downstream runs,
   including the local-asset read. `bindCoverArt()` is only ever reached from
   `renderCoverGrid()`, which only runs from `renderGames()` when
   `useCoverGrid` is true — there is no other call site.

`boxArtLookupEnabled` is assigned straight from
`prefs.getBoolean("library_box_art_lookup", false)` in `onCreate`, before any
of `loadGames()` / `renderGames()` / `renderCoverGrid()` run, so a freshly
installed or freshly upgraded instance can't race its way into a fetch before
that line executes. The field's class-body initializer is `false` too (fixed
in review — it read `true` before `onCreate` ever ran), so nothing can read a
`true` value before the pref does.

`SetupWizardActivity.kt` makes no network call anywhere; its new switch only
ever writes a `Boolean` into `SharedPreferences`.

## Upgrade behaviour

An install that finished the wizard before this question existed
(v0.4.1-j1 and earlier) has `setup_complete = true` but never wrote
`library_box_art_lookup` — under the new default that would now silently
turn off box art it had been fetching. `maybeAskAboutExistingBoxArtLookup()`
asks once with a non-cancelable `MaterialAlertDialogBuilder` dialog, gated on
`!prefs.contains("library_box_art_lookup") && prefs.getBoolean("setup_complete", false)`
— `setup_complete` is the same flag `SetupWizardActivity` already uses to
decide whether to skip straight to the library, reused rather than invented.

**Fixed in review:** this call is now reached only when the cover grid is
the thing on screen — from `onCreate` when `useCoverGrid` is already true,
and from the view-mode toggle's handler when the user switches to the grid
— not unconditionally from `onCreate` as in the first pass. List mode
fetches nothing and also hides `switchBoxArtLookup` (`syncDisplayModeUi()`
only shows it when `useCoverGrid`), so asking there was both pointless and
pointed at a switch the user couldn't see. The `prefs.contains` check still
keeps the dialog to one time total, however many times the user flips
between list and grid.

Either button ("Keep it on" / "Turn it off") writes the key through
`setBoxArtLookupEnabled(...)`, so the dialog never fires again for that
install. A fresh install with the key absent and `setup_complete` still
false (mid-wizard) is not asked here — it gets the wizard's own page instead.
Because `boxArtLookupEnabled` starts `false` and only the dialog's own button
taps can flip it, nothing fetches while the dialog is open, even if the
library's background folder scan finishes and calls `renderGames()` before
the user answers.

## Launch-path check

Grepped every `docs/testing/*.sh` harness script (`boot-test.sh`,
`run_disc.sh`, `run_one_disc.sh`, `sweep_queue.sh`, `soak_title.sh`): all of
them launch with
`adb shell am start -n com.rfandango.haku_x/com.rfandango.haku_x.LauncherActivity --es rom_path '<iso>'`
(or equivalent), never a component inside `GameLibraryActivity` or
`SetupWizardActivity`. Read `LauncherActivity.kt` in full: when a ROM
URI/extra is present it hands off to `MainActivity` directly (or to
`SetupWizardActivity` first, only if setup isn't complete) — it never reaches
`GameLibraryActivity` on that path. Neither the library's upgrade dialog nor
the wizard's new page can appear on an automated title-launch run.

## Compile result

`JAVA_HOME=/home/justin/toolchains/jdk21 ./gradlew -p android --no-daemon :app:compileDebugKotlin`
against all five edited files:

First pass:

```
BUILD SUCCESSFUL in 1m 46s
16 actionable tasks: 16 executed
```

Second pass, after the review fixes above (grid-gated upgrade ask, the
`boxArtLookupEnabled` initializer, and the PRIVACY.md/release-note wording):

```
BUILD SUCCESSFUL in 23s
16 actionable tasks: 6 executed, 10 up-to-date
```

The only compiler warnings in the log are pre-existing (`GpuDriverHelper.kt`,
one deprecated call in `MainActivity.kt`), in files this lane did not touch.

Release note: Box art lookup is now off until you turn it on. New installs
are asked during setup; if you set up hakuX earlier, the cover grid asks
once. You can change it later with the switch in the library.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG

## Master merge (lane.local, 10-12)

debugcap1012 and pubdocs1012 folded, so master is merged in and this branch
changes only its own files. No conflicts; no code change in the merge. The
new head needs the fold's Nova boot gate.
