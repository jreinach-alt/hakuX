# Coming from an official hakuX build

**Nothing needs to be uninstalled, and nothing you have is at risk.**

This fork installs under its own application id, `com.jreinach.hakux`, so it
sits beside an official install rather than replacing it. Both apps can be
installed at once, each with its own storage. The official build keeps its
Xbox HDD, its EEPROM and all of its settings, untouched, whatever you do here.

Nothing on this page is required. Set the fork up from scratch and you lose
nothing; the only cost is doing the setup wizard again.

## Telling them apart

The fork appears in the launcher as **hakuX (fork)**.

## Exit the game before backing anything up

The Xbox HDD is a QCOW2 image, and its metadata — L2 tables, refcounts — is
cached in memory while a game runs. It is written out when the emulator shuts
down cleanly or the app goes to the background, not continuously.

So quit the game through the pause menu first, or at least background the app,
before exporting or copying `hdd.img`. Copying it straight after a force-stop
can capture an image whose metadata lags its data.

This is not hypothetical. The flush on terminate and background was lost
during an early edit to `ui/xemu.c` and corrupted HDD images until it was
restored in v0.2.1. The fix is present here, but it only helps if the flush
actually happens before you take the copy.

## If you want your saves in the fork build

Your save games live inside the Xbox HDD image. Copying it across takes two
files, and the originals stay where they are, so a mistake costs you nothing.

Set the fork up first — run the setup wizard, point it at your BIOS files, an
HDD image and your games folder — then quit the app and copy over the real
data:

```bash
OFFICIAL=/storage/emulated/0/Android/data/com.rfandango.haku_x/files/x1box
FORK=/storage/emulated/0/Android/data/com.jreinach.hakux/files/x1box

adb pull  "$OFFICIAL/hdd.img"    hdd.img
adb pull  "$OFFICIAL/eeprom.bin" eeprom.bin

adb push  hdd.img    "$FORK/"
adb push  eeprom.bin "$FORK/"
```

Copy `eeprom.bin` as well as the HDD, not just the HDD. The EEPROM holds the
emulated console's identity — its HDD key and online key — along with the
language, video standard and aspect ratio. Leave it behind and the fork build
generates a fresh one, so the console those saves belong to is not quite the
console reading them.

When an `hdd.img` is already in place the emulator keeps it rather than
copying over it. The log records:

```
HDD image already in app storage, skipping copy
```

Seeing that line means your data survived the wizard.

## Without a PC

Both files can be exported from inside the app, so no computer is needed:

1. In the official build: **Settings → Export HDD**, then **Settings → Export
   EEPROM**, saving both somewhere outside the app's own storage — your games
   folder does nicely.
2. Install the fork and run its setup wizard, choosing the exported `hdd.img`
   as the HDD image.
3. In the fork: use the EEPROM editor to match the settings you had, or copy
   the exported `eeprom.bin` into place with a file manager that can reach
   `Android/data`.

Export EEPROM is new in this build, so an older official install will not have
it. There, export the HDD from the app and take the EEPROM over adb as above,
or accept the settings reset and set language, video standard and aspect ratio
again by hand.

## Going back

Nothing to undo. The official build was never modified. Uninstalling the fork
removes only its own data.
