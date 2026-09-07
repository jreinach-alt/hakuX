# Launching the fork build from ES-DE

ES-DE ships a `hakuX (Standalone)` entry that targets the official package,
`com.rfandango.haku_x`. This fork installs under its own id so it cannot
disturb an official install, which also means ES-DE will not find it on its
own. Two files fix that.

## Install

Copy both files from this directory into ES-DE's `custom_systems` folder:

```
<ES-DE data folder>/custom_systems/es_find_rules.xml
<ES-DE data folder>/custom_systems/es_systems.xml
```

On a handheld the data folder usually sits beside your ROMs, for example
`/storage/XXXX-XXXX/Games/ES-DE/`. Create `custom_systems` if it is not there.

**Restart ES-DE.** It reads these once at startup, so the new option does not
appear until it has been relaunched. If ES-DE is your home app, that means
rebooting or force-stopping it.

Then pick the emulator: in ES-DE, open the Xbox system, press the menu button
and choose **Alternative emulator**, then **hakuX fork (Standalone)**.

## Check the ROM path first

`es_systems.xml` declares `<path>%ROMPATH%/xbox</path>`. **This must match your
ROM directory exactly, capitalisation included.** If your folder is `XBox`,
write `%ROMPATH%/XBox`.

Getting it wrong does not produce a helpful error. ES-DE hands the emulator a
Storage Access Framework URI built from that path, and SAF document ids are
case-sensitive strings even on a case-insensitive card such as exFAT. A URI
naming `Games/xbox` is not covered by permission granted on `Games/XBox`,
though both name one directory on disk, so the emulator cannot open the file
and reports a missing disc.

## Why the entry looks the way it does

The find rule names the activity in full:

```
com.jreinach.hakux/com.rfandango.haku_x.LauncherActivity
```

The fork changes its application id but keeps the original code namespace, so
the launcher class is still `com.rfandango.haku_x.LauncherActivity` while the
package is `com.jreinach.hakux`. ES-DE's bundled rule uses the shorthand
`.LauncherActivity`, which resolves relative to the package — here that would
be `com.jreinach.hakux.LauncherActivity`, which does not exist.

`es_systems.xml` repeats every launch option the bundled definition carries,
because a custom system replaces the bundled one of the same name rather than
adding to it. Installing this must not cost you the emulators you already had.

## Removing it

Delete both files and restart ES-DE. The bundled definition takes over again
and the official hakuX entry works exactly as before.
