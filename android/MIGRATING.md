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

The in-app **Settings → Export HDD** writes the HDD image to any folder you
choose, and the fork build can import it during setup. That carries your saves
but not the EEPROM, so set the language, video standard and aspect ratio again
from the EEPROM editor afterwards.

## Going back

Nothing to undo. The official build was never modified. Uninstalling the fork
removes only its own data.
