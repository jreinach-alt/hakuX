# Getting your Xbox files

_Last updated 2026-10-16, for version 0.5.1._

hakuX CE includes no Xbox system software and no games. Setup asks for four
things, and each has to come from an Xbox and discs you own. This page says
what each one is and what the app accepts. For how to copy them from your
console and discs, follow
[xemu's guide to the required files](https://xemu.app/docs/required-files/)
and its [guide to disc images](https://xemu.app/docs/disc-images/): hakuX CE
is built on xemu, so the same files work in both.

Please do not ask for these files, or for links to them, in this
repository's issues.

## What setup asks for

| File | What it is | What the app accepts |
|---|---|---|
| MCPX boot ROM | The small boot program inside the Xbox's MCPX chip | A `.bin`, `.rom` or `.img` file |
| Flash ROM (BIOS) | The contents of the Xbox's flash chip | A `.bin`, `.rom` or `.img` file of 256 KB, 512 KB or 1 MB |
| Hard disk image | A copy of an Xbox hard disk | A `.qcow2` or `.img` file |
| Games | Images of your game discs | `.iso`, `.xiso`, `.cso` or `.cci` files, in a folder you choose |

Not every BIOS can start games in an emulator. xemu's guide says which ones
work.

## After setup

- **The files are copied.** The app keeps its own copy of the boot ROM, the
  BIOS and the hard disk image. To use different ones, go to Settings →
  hakuX Data → System Files.
- **Your saves are on the app's copy of the hard disk.** Back it up with
  Settings → hakuX Data → Hard Disk → **Export HDD Image**. Also use
  **Export EEPROM**: the EEPROM holds the console's language and video
  settings and its identity keys, and it is not part of the hard disk image.
- **Starting over.** **Recreate Hard Disk**, in the same place, replaces the
  app's copy with a fresh copy of the image you chose at setup. Every save
  on it is lost, so export it first.
- **The Xbox dashboard is optional.** Games start from the library without
  it. To use **Boot Dashboard**, the hard disk image needs the Microsoft
  dashboard. You can add the dashboard files copied from your console with
  Settings → Xbox Dashboard → **Import Dashboard**, from a ZIP file or a
  folder.
