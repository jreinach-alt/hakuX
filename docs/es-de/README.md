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

## The two files behave differently

This catches people out, so it is worth stating plainly:

| File | Behaviour in `custom_systems` |
|---|---|
| `es_find_rules.xml` | **Complements** the bundled file. A minimal file adding one emulator is safe — everything else keeps working. |
| `es_systems.xml` | A system with the same `<name>` **replaces** the bundled one entirely. |

That is why the find-rules file here contains a single `<emulator>` block while
the systems file repeats every Xbox launch command: dropping in a systems file
listing only the fork would remove X1 BOX and Xenra from your Xbox menu.

## If you already have a custom es_find_rules.xml

Do not overwrite it. Copy the `<emulator name="HAKUX-FORK">` block into your
existing file, inside the `<ruleList>` element, and do not duplicate the
`<ruleList>` and `</ruleList>` lines.

## If you already have a custom es_systems.xml

Do not overwrite it. Copy the single `<command>` line for the fork into the
`xbox` system you already have, keeping your own `<path>` and your other
commands:

```xml
<command label="hakuX fork (Standalone)">%EMULATOR_HAKUX-FORK% %ACTIVITY_CLEAR_TASK% %ACTIVITY_CLEAR_TOP% %ACTION%=android.intent.action.VIEW %DATA%=%ROMSAF%</command>
```

`es_find_rules.xml` still needs the `HAKUX-FORK` block, since that is what
`%EMULATOR_HAKUX-FORK%` resolves against.

## What the command line does

ES-DE turns that line into an Android intent:

| Token | Effect |
|---|---|
| `%EMULATOR_HAKUX-FORK%` | Resolves through `es_find_rules.xml` to the package and activity to start |
| `%ACTION%` | The intent action — `android.intent.action.VIEW` |
| `%DATA%` | The intent's data URI |
| `%ROMSAF%` | Expands to the Storage Access Framework `content://` URI for the selected game |
| `%ACTIVITY_CLEAR_TASK%`, `%ACTIVITY_CLEAR_TOP%` | Start fresh rather than resuming a task left over from a previous session |

The two activity flags are optional. The emulator drops its own task when a
game launched from a frontend exits, so there is usually nothing to clear, but
they cost nothing and cover a session left behind by a crash.

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
