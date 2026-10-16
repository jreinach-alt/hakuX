# frontends1016 -- wiring hakuX into four launchers, tested on the Thor

## Why attempt 2 (and this session's slow restart) did not finish

Attempt 2 ended because a turn sent a backspace-loop keystroke sequence to
Daijisho's "Default player" field as a backgrounded job, and the session
ended (headless -- nothing backgrounded survives a turn ending) while that
job was still in flight. hostops checked the device afterward: no stray adb
process, no stuck dialog, battery 30.0 C (safe); the screen was just asleep,
which is normal and not evidence of a stuck dialog. Work up to that point
was safely committed at `9681af2dbe`. The fix carried into this attempt: run
everything in the foreground, inside one turn, in chunks that fit -- never
background a device-input sequence and end the turn.

This attempt (3) then spent a large share of its turn budget re-confirming
Daijisho's UI (the dual-display `-d 4` input flag was briefly dropped again
at the very start, producing three byte-identical screenshots before the
mistake was caught) and searching for a platform-creation entry point other
than the one already blocked by the "Please select from the list" error --
see the Daijisho section below for what that search found and why it was
cut off here rather than continued further.

Also merged `origin/master` in this session (branch was 8 commits behind,
2 ahead; fast-forward wasn't possible, ordinary merge, no conflicts with any
file this lane touches).

Device: Thor, serial `bdc158a5`, Android 13 (SDK 33). All work done by hand with
adb per the hold amendment in `dispatch/hold/thor.why` (2026-10-16T15:02Z);
never used `request.sh`, never uninstalled anything, never cleared app data.

## Thermal readings

Battery temperature was checked before essentially every launch/tap sequence
across the whole session. It never moved: every reading was **33.0 C**
(`temperature: 330`), from the start of Setup Wizard work through both ES-DE
launches. Nowhere near the 42.0 C stop threshold. No NEED: from heat.

## In-place upgrade test (0.4.1 -> 0.5.0): FAILS, and it is not a hakuX bug

The brief asked me to attempt `adb install -r` of
`/home/justin/hakux-work/release/hakuX-0.5.0.apk` (versionCode 9) over the
Thor's installed `com.jreinach.hakux` (0.4.1, versionCode 8) and record
whether the upgrade kept the app's data -- not to uninstall to force it.

It fails before touching any data:

```
adb.exe: failed to install hakuX-0.5.0.apk: Failure
[INSTALL_FAILED_UPDATE_INCOMPATIBLE: Existing package com.jreinach.hakux
signatures do not match newer version; ignoring!]
```

Root cause, confirmed with `apksigner verify --print-certs` on both APKs:

| | installed (0.4.1, versionCode 8) | release candidate (0.5.0, versionCode 9) |
|---|---|---|
| Signer DN | `C=US, O=Android, CN=Android Debug` | `CN=jreinach-alt, ..., C=VN` |
| SHA-256 | `b9ca1016...e69cdff28` | `2e266dfb...78c52ae2` |

The **currently-installed release build on the Thor was signed with the
Android debug keystore**, not the real release key the 0.5.0 APK uses.
Android refuses to install an update with a different signing cert over an
existing app, regardless of version codes. This is a release/CI pipeline
defect (whatever produced the 0.4.1 artifact that got pushed to the Thor
signed it with the debug key), not anything this lane's four frontends are
responsible for, and not something fixable by this lane without uninstalling
-- which the brief forbids. **NEED:** the release pipeline needs to sign
0.4.1-and-later artifacts with the real release key before the Thor (or any
device) can take an in-place upgrade; until then every frontend test in this
lane runs against the already-installed 0.4.1 release build, which is fine
functionally since it has the same package id / activity every config here
targets.

The app was left exactly as found: still 0.4.1, versionCode 8, untouched.

## One-time prerequisite: the release build had never finished Setup Wizard

The release `com.jreinach.hakux` (non-debuggable) had no BIOS files
configured and no games folder granted -- first run always lands on
`SetupWizardActivity`, which would make every frontend launch redirect there
regardless of which frontend started it. Since it's not debuggable,
`run-as` (used for the `.debug`/`.debug2` tricks in AGENTS.md) does not work
on it; the only way through is the real wizard UI.

No Xbox BIOS files existed anywhere in public storage on the Thor. Copied
them out of the already-configured `.debug` build's private app storage and
into public Downloads so the release app's SAF picker could reach them:

```
adb -s bdc158a5 exec-out run-as com.jreinach.hakux.debug cat <path> > local-file
adb -s bdc158a5 push local-file /storage/388C-68F7/Download/hakux-setup/<name>
```

`adb exec-out`, not plain `adb shell ... > file` -- the plain form corrupts
binary output (observed: flash.bin came out 1,052,496 bytes instead of
1,048,576 over plain `adb shell`, byte-exact over `exec-out`). Sizes after
the fix, matching the `.debug` build's originals exactly:

| file | bytes |
|---|---|
| mcpx.bin | 512 |
| flash.bin | 1,048,576 |
| hdd.img | 1,058,340,864 |

Freshly `adb push`ed files did not show up in the SAF "Downloads" picker
until a `MEDIA_SCANNER_SCAN_FILE` broadcast per file (MediaStore had not
indexed them yet -- `adb push` bypasses the scanner). Walked the real wizard
by hand (SAF document picker for MCPX/Flash/HDD, `OpenDocumentTree` for the
games folder) and it completed cleanly: Game Library now lists 41 titles
from `ROMS/xbox`. This only needs doing once; it is not part of any
frontend's own test and is not itself a frontend-wiring finding, just a
blocker that had to be cleared first.

Left the three BIOS files in `/storage/388C-68F7/Download/hakux-setup/` on
the device (not removed -- `rm` isn't permitted here and they're harmless,
small next to the SD card's free space, and may be useful if the wizard
needs re-running). Local copies also sit in `/tmp/frontends1016/` on the
lane host; scratch, fine to leave for now.

## Dual-display workaround (this Thor unit specifically)

This Thor reports two displays. `displayId 0` ("Built-in Screen",
`uniqueId 4630946441858561667`) is a phantom/placeholder that always renders
solid black and resolves Android's `SecondaryDisplayLauncher` onto it --
screenshots and taps against it silently do nothing useful. The real
interactive screen is `displayId 4` ("Screen-2",
`uniqueId 4630946482288158084`, `FLAG_PRESENTATION`). Every screenshot in
this lane's evidence used
`adb exec-out screencap -p -d 4630946482288158084`, and every tap used
`adb shell input -d 4 tap x y` (short id for input, long uniqueId for
screencap -- they take different id spaces). Also: the screen falls back
asleep a few seconds after waking regardless of the configured
`screen_off_timeout`, so every interaction sequence leads with
`input keyevent KEYCODE_WAKEUP` rather than relying on one wake earlier in
the session.

## ES-DE: wired and tested on the Thor -- works

App: ES-DE `org.es_de.frontend`, reported version 3.4.0-56 (from the APK
filename already on-device; not independently re-verified via an in-app
about screen). Android 13, Thor, hakuX 0.4.1-1004-40b62fd533.

ES-DE's real data folder on this device is on the SD card,
`/storage/388C-68F7/ES-DE/` -- **not** the empty
`/storage/emulated/0/ES-DE/` folder that also exists. (Worth calling out:
grepping for "ES-DE" on internal storage finds a decoy empty folder; the
live one has to be found by locating `settings/es_settings.xml`.) Pushed the
lane's `docs/es-de/es_find_rules.xml` and `es_systems.xml` as-is into
`<data folder>/custom_systems/` with `adb push`, force-stopped ES-DE
(wasn't running) and relaunched it.

Confirmed on-device, which the existing drafts only asserted:
- The ROMs folder really is `ROMS/xbox` (uppercase ROMS, lowercase xbox) on
  `THOR_SD`, matching the draft's case-sensitivity warning and the
  `%ROMPATH%/xbox` path in `es_systems.xml` as shipped -- no changes needed.
- ES-DE's default ROM directory (no `ROMDirectory` override in
  `es_settings.xml`) already resolves there; it found 41 Xbox titles
  immediately on entering the system, confirming the custom `es_systems.xml`
  replaced the built-in Xbox system without losing the folder scan.
- The custom find rule resolves the activity correctly: selecting a game and
  pressing the default select action launched
  `com.jreinach.hakux/com.rfandango.haku_x.LauncherActivity` successfully --
  confirmed via `dumpsys activity activities` showing
  `mFocusedApp=...com.rfandango.haku_x.MainActivity` within ~1s of the
  keypress, then the game's splash screen rendering at 59 FPS.

Test title: `4541005B-Burnout_3_Takedown.xiso.iso` (2.87 GB, already on the
card -- not pushed or deleted by this lane). Two full launches from ES-DE's
own UI (D-pad + ENTER, not adb intents):
1. First launch: hakuX's `MainActivity` got focus, Criterion Games splash
   rendered at 59 FPS. Screenshotted, then `am force-stop
   com.jreinach.hakux` (short launch, per the fan-dead rule).
2. Second launch, after the full force-stop (catches a first-launch-only
   path): also succeeded, and got further -- past the splash into the
   game's own "LOADING / LADEN / CARGANDO / LADDAR" screen, also at 59 FPS.
   Stopped the same way.

No NEED: for ES-DE. The existing `docs/es-de/*` drafts turned out to be
correct as written; this lane's job here was turning "untested hypothesis"
into "verified on hardware," documented in `docs/frontends/es-de.md` with a
pointer added from `docs/es-de/README.md`.

ES-DE's own select-game confirmation dialog on the games-folder grant step
read **"Allow hakuX (fork) to access files in xbox?"** -- see app-name
occurrences below.

## App name occurrences ("hakuX (fork)")

The owner may rename the app later. Every place this lane's new docs or the
device itself shows the name "hakuX" / "hakuX (fork)", for a one-grep rename
later:
- Android's own SAF permission dialog text: *"Allow hakuX (fork) to access
  files in xbox?"* (not ours to edit -- comes from the installed app's
  label, `android:label` in the manifest / build config).
- hakuX's own Setup Wizard screen title: *"Welcome to hakuX"*.
- `docs/frontends/README.md`, `docs/frontends/es-de.md`,
  `docs/frontends/daijisho.md`, `docs/frontends/pegasus.md`,
  `docs/frontends/stock-launcher.md` -- see each file; kept to short,
  greppable headings/labels rather than repeating the name in prose.
- `docs/es-de/README.md`, `es_find_rules.xml`, `es_systems.xml` -- unchanged
  from the existing drafts, which already use the name sparingly (mostly in
  the `HAKUX-FORK` emulator id and command labels, which **must not change**
  since they're keyed to the package/activity, not the display name).
- Package id `com.jreinach.hakux` and activity
  `com.rfandango.haku_x.LauncherActivity` are NOT display names and do not
  change on a rename; left alone everywhere per the brief.

## Daijisho: blocked -- cannot complete custom-platform creation on this build

App: Daijisho (Flutter-based), already installed on the Thor per the owner's
note. Goal was a custom "Platform" entry pointing its `launch` command at
`com.jreinach.hakux/com.rfandango.haku_x.LauncherActivity`, same as ES-DE's
find-rule.

**Automation note**: `uiautomator dump` returns "ERROR: null root node
returned by UiTestAutomationBridge." against Daijisho every time -- it does
not expose a standard Android accessibility tree (consistent with it being
Flutter-rendered, not native views). Screenshot + coordinate tap is the only
automation method that works here; this is a real exception to the general
uiautomator-first guidance, not a shortcut taken for convenience.

**Blocker**: Settings > Library > "New platform" opens a dialog with a
"Default player" autocomplete field (plus "Search additional player to be
added", CANCEL/SAVE). Typing a value that matches a real option and pressing
SAVE is rejected: **"Please select from the list."** -- the field requires
an actual tap-selection from Daijisho's own in-app suggestion dropdown, not
typed text, however exact. That dropdown is believed to render underneath
the fullscreen/extracted IME overlay this device uses for text entry on a
small landscape screen (the field's own anchored suggestion list would
normally appear right below it, but the whole screen goes black-keyboard
while typing, and no suggestion list has ever been visible in any
screenshot taken mid-type). A DPAD/Tab-navigation-into-the-hidden-overlay
approach was planned (type, then DPAD_DOWN or TAB while still focused, then
keyevent-select) but not executed before the turn budget ran out.

Spent the rest of this launcher's turn budget looking for a second route to
platform creation that might avoid the free-text field, with no success:
- Settings > Library > "Download platforms" opens a 122-item checkbox list
  of predefined platforms with an IMPORT button -- this is a different flow
  (bulk-import known platforms, not add-one-custom), and scrolling the list
  to find an Xbox-like entry was itself slow (short swipes barely moved it;
  one long 2000 ms swipe didn't move it further and also triggered the
  screen-sleep bug, requiring a re-wake). Cancelled out of it rather than
  keep fighting the scroll.
- Settings > Library > "Inspect platforms" is read-only (lists the 27
  already-configured platforms, ends at TurboGrafx-CD, no add control).
- The Library tab's own platform-card carousel (top of the Library screen,
  showing "platform N of 27") was swiped all the way through on the
  hypothesis that a trailing "+ Add platform" card might exist past the
  last real one. It does not: swiping past "TurboGrafx-CD, 27 of 27" wraps
  back around to "Nintendo 3DS, 1 of 27" with no special card in between.

**NEED:** either a confirmed way to select (not type) a value into
Daijisho's "Default player" autocomplete field with the suggestion overlay
hidden behind fullscreen IME on a small landscape screen, or a Daijisho
config/import file this lane could push directly (bypassing the UI
autocomplete entirely) to define a custom platform's launch command. Without
one of those, Daijisho cannot be wired to hakuX by hand in the UI on this
device. Left Daijisho on its Settings screen, no app data touched, nothing
stuck mid-dialog.

`docs/frontends/daijisho.md` documents this as "not yet wired -- blocked",
not "tested".

## Pegasus: not installable without GitHub -- NEED:, skipped per the brief

Pegasus is not installed on the Thor (confirmed: `pm list packages` has no
`org.pegasus_frontend`/similar). Per the brief, checked whether
pegasus-frontend.org itself hosts the Android APK (as opposed to only
linking to GitHub) before touching GitHub at all.

It does not. Fetched the live homepage HTML and its `js/app.js`: every
platform's "Downloads" row (Windows, Linux, Android, etc.) is a `loading...`
placeholder filled in at runtime by client-side JS that calls
`https://api.github.com/repos/mmatyas/pegasus-frontend/releases/latest` (and
`.../tags/continuous`) and pulls `browser_download_url` straight out of the
GitHub API response -- there is no independently-hosted file anywhere on
pegasus-frontend.org. The site's own fallback text even says so: on API
failure it prints "See all releases HERE" linking straight to
`github.com/mmatyas/pegasus-frontend/releases`. The APK's only real source
is GitHub, full stop.

**NEED:** Pegasus's Android APK cannot be fetched without hitting GitHub,
which this lane is not permitted to do. Skipping Pegasus entirely per the
brief ("If the only source is GitHub, write NEED: and carry on with the
other three; do not hit GitHub"). `docs/frontends/pegasus.md` documents this
as "not installed -- blocked on APK source", not "tested". If the owner (or
a lane with GitHub access) can place the APK somewhere else reachable (e.g.
`/home/justin/hakux-work/release/` or a non-GitHub mirror), this can be
revisited without re-doing the above check.

## Stock launcher (AYN odinlauncher, `com.odin.odinlauncher`): tested -- works, with a known limit

No configuration needed: hakuX's release build ("hakuX (fork)") already
appears in odinlauncher's app drawer and its Search apps box, same as any
installed Android app, alongside `.debug` and `.debug2`.

Tapping the icon starts `com.jreinach.hakux/com.rfandango.haku_x.GameLibraryActivity`
(confirmed via `dumpsys activity activities`), landing on hakuX's own Game
Library screen -- not a specific game. From there, picking
`41540002-Shin_Megami_Tensei_Nine` and pressing its play control took focus
to `MainActivity` and rendered the Atlus splash at 29 FPS. Confirmed twice:
once cold, once after a full `am force-stop com.jreinach.hakux` and
re-opening via the same search-and-tap path. Both launches reached the same
state. Stopped both short (fan-dead rule); battery held at 32.0 C
(`temperature: 320`) throughout, well under the 42.0 C stop threshold.

**Known limit, not a bug:** a stock Android launcher has no mechanism to
scan a ROM folder or pass a specific game file as a launch argument (no
custom-system or find-rule equivalent exists in a generic app drawer) -- it
can only start an app's default activity. So the stock launcher can only
ever open hakuX's own in-app Game Library; the user picks the specific game
from inside hakuX, never from the launcher itself. Documented in
`docs/frontends/stock-launcher.md`, which also notes the Retroid-launcher
variant (on the Nova) stays "not yet tested" -- that's lane.local's job
later, not this lane's.

## Summary table (per the attempt-3 addendum)

| Launcher | Configured | Launched | Failed |
|---|---|---|---|
| ES-DE | `es_find_rules.xml` + `es_systems.xml` pushed to `custom_systems/` (already-correct drafts, unchanged) | Yes, twice (cold + after force-stop), reached the game's own loading screen | No |
| Daijisho | Not completed -- blocked before a platform could be saved | No | "Default player" field rejects any typed selection ("Please select from the list"); no non-UI config path found |
| Pegasus | Not attempted | No | APK has no source other than GitHub; this lane does not fetch from GitHub |
| Stock launcher (AYN odinlauncher) | None needed (standard app-drawer entry) | Yes, twice (cold + after force-stop), reached `GameLibraryActivity` then the game's splash | No -- but can only open hakuX's own library, never a specific game directly |

## Deliverables written this session

`docs/frontends/README.md` (index), `es-de.md`, `daijisho.md`, `pegasus.md`,
`stock-launcher.md`, and five screenshots under `docs/frontends/images/`
(sourced from this session's and the prior session's `/tmp/frontends1016/`
captures, not re-shot). Added a pointer from `docs/es-de/README.md` to
`docs/frontends/es-de.md`. Did not touch the top-level `README.md`
(titlekey1016 holds it) -- the one-line link for lane.local to add there is
in `PR.md`.

Restored `svc power stayon false` at the end of the device session (it had
been set to `true` for this session's work).

## Still in progress / pending

All four frontends have been attempted and written up (two tested, two
blocked with a NEED:). Nothing further is planned for this lane; see PR.md
for the ready state and the one-line README.md link request.
