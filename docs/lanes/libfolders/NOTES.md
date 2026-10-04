# lane.libfolders (#433): more than one games folder

Owner request 2026-10-04. The Thor has Xbox titles on two roots (SD `/storage/388C-68F7/ROMS/xbox`, internal
`/storage/emulated/0/ROMS/xbox`); the app took one SAF tree, so The Simpsons: Hit & Run on internal was unreachable.

## What changed

* `GamesFolders.kt` (new, one place for the pref): `gamesFolderUris` is an ordered JSON array of tree URIs.
  `read()` migrates the old `gamesFolderUri` into it on first read and removes the old key, so there is one source
  of truth. `add` (dedupes, appends), `remove`, `pruneDead` (drops only URIs with no persisted read permission),
  `withPermission`.
* Settings: the "Games Folder" card lists each folder with a Remove button (confirm dialog, "No files are deleted")
  and the button is now "Add Games Folder". The card is otherwise unchanged. Remove does not release the SAF grant:
  a `dvdUri` may sit under the tree and still rely on it.
* Setup wizard: picking a folder now *adds* to the set (it does not replace), the label joins the folder names, and
  the wizard counts as ready when any folder is ready. Nothing else was added to the wizard.
* Library: scans every usable folder in order and merges. A folder with no persisted permission, or that is gone, is
  skipped with a `hakuX-folders` log line; a folder whose scan throws is skipped the same way. The "No folder
  selected" toast fires only when no folder is usable. `onResume` rescans when the stored set differs from what the
  screen last scanned, so returning from Settings shows the change without a pull-to-refresh.
* Dedupe: the same file name (case-insensitive, last path segment) in a later folder is hidden and logged; the first
  folder in order wins. **Title id is not compared**: reading it means parsing the XDVDFS image of every file over SAF,
  which the scan does not do today. Two differently named dumps of one title still show twice (as they already did
  inside one folder).
* Launcher: `hasGamesFolder` is true when at least one folder holds a persisted read permission; `pruneDead` removes
  only the dead URIs. Core-cleared (forcing setup) happens only when the set had entries and none survived, the same
  condition the single pref had.

## Every `gamesFolderUri` consumer in the tree (grep at base 425ffe1ad1) and what was done

| where (base) | what it did | now |
|---|---|---|
| LauncherActivity:37,47,52 | read pref, `hasGamesFolder` from one URI's permission | `GamesFolders.pruneDead(...).isNotEmpty()`; `hasDvd`'s `hasGamesFolder` leniency is unchanged (true if any folder is live) |
| LauncherActivity:91-92 | removed the pref when dead and forced setup | prune only dead URIs; force setup only if the set was non-empty and now empty |
| GameLibraryActivity:77,115 | field + read in onCreate | `gamesFolders: List<Uri>` via `GamesFolders.read` (migrates) |
| GameLibraryActivity:168 (onCreate) | toast + return if the folder is not ready | toast + return if none is ready |
| GameLibraryActivity:177 (`loadGames`) | scan the one folder | scan every usable folder, merge, dedupe (`scanFoldersForGames`) |
| GameLibraryActivity:561 (`convertIsoToXisoInFolder`) | wrote the converted xiso under "the" folder | `game.folderUri`: the output goes next to the source, in the folder the game came from |
| GameLibraryActivity:804 (`launchGame`, corrupt xiso rebuild) | looked for the original ISO under "the" folder | `game.folderUri`; the rebuilt `GameEntry` carries it |
| GameLibraryActivity:1077 (`findExistingXiso`) | looked for a sibling `.xiso.iso` under "the" folder | `game.folderUri`; the returned entry carries it |
| GameLibraryActivity scan (`scanFolderForGames`) | built entries | every `GameEntry` now has `folderUri` |
| SettingsActivity:382 (`pickGamesFolder`) | wrote the pref (replace) | `GamesFolders.add`; takePersistableUriPermission kept |
| SettingsActivity:501 | picker start location = the folder | start location = the last folder added |
| SettingsActivity:1142 (`updateGamesFolderPath`) | one label | one row per folder with Remove; "Not set" label only when empty |
| SetupWizardActivity:44,128-129,144,189,276,316 | field, replace on pick, label, ready check | list field, `GamesFolders.add` on pick, joined label, `any` ready check |
| docs/lanes/forza414, docs/lanes/perfbase NOTES | prose mentions only | untouched |

Nothing else resolves a game to a folder. Launch itself uses the game's own document URI (`game.uri`), not the folder.
There is no delete-a-game action in the library. Per-game settings are keyed by `relativePath`
(`PerGameSettingsManager`); after the file-name dedupe two merged games cannot share a relative path, so that key
stays unique.

## Not touched

Native code, the runner's own storage reader, the harness, the system-files / HDD / MCPX pickers.

## Attempt 2 (2026-10-04): why attempt 1 did not finish

Attempt 1 committed the code, queued the build request and stopped on a `run` WAITING line, because a lane cannot
touch a device and the build had not landed. This attempt read the result and re-read the diff.

* **Build**: request `1-1791142964-lane.libfolders-796796` (ref `dfa6d4c044`) built: `dispatch/logs/build-dfa6d4c044.log`
  ends `BUILD SUCCESSFUL`, no warnings in `GamesFolders` or `GameLibraryActivity`, and `builds/dfa6d4c044.apk` exists.
  The dispatcher recorded the new apk (`bba1e72819e2`) on the Thor and cleared its shader cache for the change.
  The compile-error worry in Status below is closed.
* **The soak itself was refused**, not run: `display-covered: a foreign full-screen overlay covers display 0 on
  bdc158a5: primaryScreenTopLayout (com.odin.dualscreen.assistant, BOOT_PROGRESS)`. That is the Thor's dual-screen
  assistant, not this change; the soak was incidental (the request was only a vehicle for the install).
* **Re-read the diff** for the four things that go wrong with this shape of change: a dedupe that hides two files in
  one folder (no: `seenNames` is extended after a folder is done, so same-named files inside one folder both show, as
  before); a dead URI dropping the whole set (no: `pruneDead` writes only the survivors); a stale library after
  Settings (covered by `onResume`); a `GameEntry` built without `folderUri` (it is a required constructor parameter, so
  the compiler would have refused it, and it compiled).
* **Still not done, and not a lane's to do**: the migration test and the Thor screenshot pair need adb on the Thor
  under the owner's playtest hold rules, and no request kind drives the library screen. Nothing was run on the device
  by this lane. The steps are under Status below; the WAITING file now carries an `owner` line for them.

## Verification

* **Compiles / installs**: dispatch request `1-1791142964-lane.libfolders-796796` (ref `dfa6d4c044`) built
  (`BUILD SUCCESSFUL`) and the Thor took the apk; the soak was refused for a foreign overlay (see Attempt 2).
* **Migration test**: not yet run (needs the device, see Status).
* **Screenshot pair on the Thor** (add internal `ROMS/xbox` beside the SD folder; a title in one folder appears, a
  title in both appears once): not yet taken (needs the device, see Status).

## Status

2026-10-04: code committed (`dfa6d4c044`), pushed, and compiled (attempt 2). **Missing from the definition of
done: the migration test and the screenshot pair**, both needing hands on the Thor.

Still to do once the build lands (hands on the Thor, under the owner's playtest hold rules, not a lane's):

1. **Migration test** with an install that already has the single pref: confirm `x1box_prefs.xml` has
   `gamesFolderUri` (debug app: `run-as com.jreinach.hakux.debug cat shared_prefs/x1box_prefs.xml`), install the
   new build over it (`adb install -r`), open the app: the library must show the same titles with no picker, and the
   pref file must now hold `gamesFolderUris` and no `gamesFolderUri`.
2. **Screenshot pair**: Settings > Games Folder > Add Games Folder > pick internal `ROMS/xbox`; library before
   (SD only) and after (merged). Expect: a title only on internal (The Simpsons) appears; a title on both appears once;
   `adb logcat -s hakuX-folders` shows the per-folder counts and the hidden duplicates.
3. Remove one folder in Settings, return to the library: it rescans and the removed folder's titles go.
