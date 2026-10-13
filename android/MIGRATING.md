# Moving from the official hakuX

_Last updated 2026-10-13, for version 0.5.0._

**You don't need to uninstall anything, and nothing you have is at risk.**

This build installs as its own app, **hakuX (fork)**, next to the official
hakuX. Each app keeps its own hard disk image, settings and saves. Nothing
you do in this build changes the official one.

Moving your saves across is optional. If you skip it, all you need to do is
run setup again.

## Can your device run it?

This build needs Android 10 and a Snapdragon 845-class chip or newer. On an
older chip (Snapdragon 835, 660, 665 or 460) it says so and exits. The
official build supports those chips, so keep using it there.

## First: quit the game

Your saves live in the Xbox hard disk image, `hdd.img`. While a game runs,
some of its changes are held in memory. They are written to the file when
you quit through the pause menu or switch away from the app. Do one of those
before you copy the file.

## Bringing your saves across

You copy two files. The originals stay where they are, so a mistake costs
nothing.

### Without a computer

1. In the official app, use **Settings → Export HDD** and, if your version
   has it, **Settings → Export EEPROM**. Save them outside the app's own
   storage; your games folder works.
2. Install this build and run setup. When it asks for a hard disk image,
   choose the exported `hdd.img`.
3. For the EEPROM, either copy the exported `eeprom.bin` into this build's
   folder with a file manager that can open `Android/data`, or set your
   language, video standard and aspect ratio again in the EEPROM editor.

### With a computer (adb)

Run setup in this build first, then quit it and copy the files over:

```bash
OFFICIAL=/storage/emulated/0/Android/data/com.rfandango.haku_x/files/x1box
FORK=/storage/emulated/0/Android/data/com.jreinach.hakux/files/x1box

adb pull "$OFFICIAL/hdd.img"    hdd.img
adb pull "$OFFICIAL/eeprom.bin" eeprom.bin
adb push hdd.img    "$FORK/"
adb push eeprom.bin "$FORK/"
```

If the hard disk image is already in this build's folder, the app uses it as
it is and doesn't copy the one you chose in setup over it. So the image you
pushed is the one it runs.

### Why copy the EEPROM too

The EEPROM is the emulated console's identity: its hard disk key and online
key, plus language, video standard and aspect ratio. Without it, this build
makes a new one, and the saves end up on a console that is not quite the one
that wrote them.

## Going back

There is nothing to undo. The official app was never changed. Uninstalling
this build removes only its own data.
