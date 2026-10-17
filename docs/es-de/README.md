# Launching from ES-DE

_Last updated 2026-10-17, for version 0.5.2._

> Verified on real hardware (Thor, Android 13, hakuX 0.4.1): see
> [`docs/frontends/es-de.md`](../frontends/es-de.md) for the tested writeup,
> screenshots, and what a successful launch looks like. The steps below were
> confirmed correct as written; nothing here needed to change.

ES-DE's built-in hakuX entry starts the official app. This build installs
under its own name so it can sit next to the official one. That means ES-DE
needs two small files to find it.

## Install

1. Copy both files in this folder into ES-DE's `custom_systems` folder.
   Create that folder if it does not exist.

   ```
   <ES-DE data folder>/custom_systems/es_find_rules.xml
   <ES-DE data folder>/custom_systems/es_systems.xml
   ```

   On a handheld the ES-DE data folder is usually next to your games, for
   example `/storage/XXXX-XXXX/Games/ES-DE/`.
2. **Check the ROM path.** `es_systems.xml` contains
   `<path>%ROMPATH%/xbox</path>`. Make it match your Xbox games folder
   exactly, including capital letters. If your folder is `XBox`, write
   `%ROMPATH%/XBox`. If the case is wrong, the emulator cannot open the game
   and reports a missing disc.
3. **Restart ES-DE.** It reads these files only at startup. If ES-DE is your
   home screen, force-stop it or reboot.
4. In ES-DE, open the Xbox system, press the menu button, choose
   **Alternative emulator**, then choose **hakuX CE (Standalone)**.

When you quit a game, you return to ES-DE.

## If you already have custom ES-DE files

Don't overwrite them. The two files work differently:

| File | In `custom_systems` it… |
|---|---|
| `es_find_rules.xml` | adds to ES-DE's built-in rules |
| `es_systems.xml` | replaces ES-DE's built-in Xbox system completely |

That is why the `es_systems.xml` here lists every Xbox emulator, not just
this one. Otherwise X1 BOX and the official hakuX would vanish from your Xbox
menu.

- **Your own `es_find_rules.xml`:** copy the `<emulator name="HAKUX-FORK">`
  block into it, inside the existing `<ruleList>`.
- **Your own `es_systems.xml`:** add this line to your `xbox` system, and keep
  your own `<path>` and other commands:

  ```xml
  <command label="hakuX CE (Standalone)">%EMULATOR_HAKUX-FORK% %ACTIVITY_CLEAR_TASK% %ACTIVITY_CLEAR_TOP% %ACTION%=android.intent.action.VIEW %DATA%=%ROMSAF%</command>
  ```

  It also needs the `HAKUX-FORK` block in `es_find_rules.xml`.

## Removing it

Delete both files and restart ES-DE. Its built-in Xbox entries come back
unchanged.

## Notes for the curious

The find rule names the full activity,
`com.jreinach.hakux/com.rfandango.haku_x.LauncherActivity`. This build has its
own package name but keeps the original code's class names, so ES-DE's
shorthand `.LauncherActivity` would point at a class that does not exist.
