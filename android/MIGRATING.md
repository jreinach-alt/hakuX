# Migrating from an official hakuX build

A build from this fork is signed with a different key than the official
release, so Android will not install it over the top. The existing app has to
be uninstalled first, and **uninstalling deletes the emulator's data**.

Read this before you uninstall anything. Once the app is gone, none of it can
be recovered.

## What uninstalling destroys

Under `/storage/emulated/0/Android/data/com.rfandango.haku_x/files/x1box/`:

| File | What it is |
|---|---|
| `hdd.img` | The Xbox hard disk — **every save game lives here** |
| `eeprom.bin` | The console's identity: HDD key, online key, language, video standard, aspect ratio |
| `mcpx.bin`, `flash.bin` | Copies of the BIOS files taken during setup |
| `xemu.toml` | The emulator's generated configuration |

Also removed, elsewhere under the app's storage: installed custom GPU drivers,
downloaded driver packages, texture dumps and replacements, the translation
block cache, and every app setting including per-game overrides and the
permissions granted to your BIOS files and games folder.

Your **original** BIOS files, HDD image and games survive, because they live
wherever you first picked them from. What does not survive is everything the
emulator has written since — which is to say, your saves.

## Backing up

### With a PC (recommended — captures everything)

```bash
adb pull /storage/emulated/0/Android/data/com.rfandango.haku_x/files/x1box ./hakux-backup
ls -l hakux-backup
```

Confirm `hdd.img` and `eeprom.bin` are both present and non-empty before
continuing.

### Without a PC (partial)

In hakuX: **Settings → Export HDD**, and save it somewhere outside the app's
own storage.

This captures your saves, which is the part that matters most, but **not the
EEPROM**. A reinstall will generate a fresh one, so the emulated console's
language, video standard and aspect ratio return to defaults and its identity
keys change. Set those again from the EEPROM editor afterwards.

## Installing

```bash
adb uninstall com.rfandango.haku_x
adb install hakuX-0.3.3-j1.apk
```

## Restoring

Put the files back before launching a game, then run the setup wizard.

```bash
adb push hakux-backup/hdd.img    /storage/emulated/0/Android/data/com.rfandango.haku_x/files/x1box/
adb push hakux-backup/eeprom.bin /storage/emulated/0/Android/data/com.rfandango.haku_x/files/x1box/
```

The wizard still asks for a BIOS, a HDD image and a games folder, because the
permissions granted to them were revoked with the old install. Point it at the
same files you used before. When a restored `hdd.img` is already in place the
emulator keeps it rather than copying over it — the log records `HDD image
already in app storage, skipping copy` — so your saves survive the wizard.

## Afterwards

Releases from this fork are all signed with the same key, so this is a
one-time cost: later versions install over the top with `adb install -r` and
keep everything.
