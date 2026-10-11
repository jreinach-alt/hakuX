# libfolders (#433): the game library takes more than one games folder

State: ready

Lane: libfolders            Issue: #433
Base: master @ 425ffe1ad1
Files: android/app/src/main/java/com/rfandango/haku_x/GamesFolders.kt (new), android/app/src/main/java/com/rfandango/haku_x/GameLibraryActivity.kt, android/app/src/main/java/com/rfandango/haku_x/SettingsActivity.kt, android/app/src/main/java/com/rfandango/haku_x/SetupWizardActivity.kt, android/app/src/main/java/com/rfandango/haku_x/LauncherActivity.kt, android/app/src/main/res/layout/activity_settings.xml, android/app/src/main/res/values/strings.xml, docs/lanes/libfolders/NOTES.md, docs/lanes/libfolders/PR.md, docs/lanes/libfolders/OUTBOX.md, docs/lanes/libfolders/WAITING
Prediction: none: no arm, UI-only change to the game library
Needs device: yes (Thor, to look at it)    Needs NDK: no
Release note (other): you can add several games folders (for example the SD card and internal storage) in Settings; the library shows all of them together.

The Thor keeps Xbox titles on two roots, and the app took one SAF folder, so the internal ones (The Simpsons:
Hit & Run) were unreachable. The pref is now an ordered set (`gamesFolderUris`), migrated from the single
`gamesFolderUri` on first read so nobody re-picks.

* **Settings**: the Games Folder card lists each folder with Remove, plus "Add Games Folder".
* **Library**: scans every usable folder and merges. A file name already seen in an earlier folder is hidden (first
  folder wins). An unreadable or permission-less folder is skipped with a `hakuX-folders` log line; the "No folder
  selected" toast is only for the case where none is usable. Returning from Settings rescans.
* **Launcher**: `hasGamesFolder` = any folder still has a persisted read permission; only dead URIs are dropped.
* **Per-folder resolution**: each game carries the folder it came from, and convert, corrupt-xiso rebuild and the
  sibling-xiso lookup use that folder instead of "the" folder.
* **Not done**: dedupe is by file name, not title id (reading the id means parsing every image over SAF).

Every `gamesFolderUri` consumer and what became of it is in `docs/lanes/libfolders/NOTES.md`.

**Verification state.** Compiled: request `1-1791142964-lane.libfolders-796796` (ref `dfa6d4c044`) built
(`BUILD SUCCESSFUL`) and the Thor took the apk; its soak was refused for a foreign dual-screen overlay, which is
unrelated. **Not done:** the migration test and the screenshot pair (add internal `ROMS/xbox` beside the SD folder),
which need adb on the Thor under the owner's playtest hold rules; the steps are in NOTES.md Status. Marked ready so
it is folded and built; the owner's device check is the open item.
