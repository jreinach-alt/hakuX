# GPU driver

_Last updated 2026-10-17, for version 0.5.2._

hakuX is tested with one GPU driver and no other: the **Turnip Adreno Driver
T30 (@Mr_Purple_666)**, a Mesa Vulkan driver (version 26.3.0-T30-1.4.359,
library `vulkan.purple.so`). Every rating on the
[compatibility page](COMPATIBILITY.md) and every release was checked with it,
on a Retroid Pocket Nova and an AYN Thor (Snapdragon 8 Gen 2, Adreno 740).

Install it before you judge how a game looks or runs.

## Other drivers are untested

The phone's own Qualcomm driver and other Turnip builds have not been tested,
and some games render wrongly on them. The clearest case is the skinned
characters in Tony Hawk's Pro Skater 4 and Max Payne 2, which freeze in their
bind pose (arms out, standing still) on the Qualcomm driver and animate
normally on T30. If a game looks broken, check the driver first.

## A new install has no driver

hakuX starts on the phone's own driver. A new install, a reinstall, a cleared
app or a second copy of the app (each package keeps its own driver) has no
custom driver until you give it one. Updating the app in place keeps the
driver you installed.

## Installing it

1. Get the driver's zip file (`Turnip Adreno Driver T30 (@Mr_Purple_666)`,
   which contains `meta.json` and `vulkan.purple.so`) onto the device. It is
   published at [MrPurple666/purple-turnip](https://github.com/MrPurple666/purple-turnip).
2. In hakuX, open **Settings → Graphics → GPU Driver**.
3. Tap **Install Driver from ZIP** and choose the file. A zip that is already
   in the app's driver folder shows up under **Select Driver** instead.
4. The line at the top of the card reads **Active driver: Turnip Adreno Driver
   T30 (@Mr_Purple_666)**. Start a game to use it.

Custom drivers need an Adreno GPU. On other chips the setting says it is not
supported and the phone's own driver is used.

## Checking it loaded

If you send a log with a bug report, these two lines show the driver was in
use:

```
Custom Vulkan driver loaded successfully via adrenotools
GPU: PurpleVK-public Adreno (TM) 740 (git-62ac221a33)
```

A log that instead names `Qualcomm Technologies Inc. Adreno Vulkan Driver`
was made on the phone's own driver, and a graphics fault in it may not be a
hakuX fault. See [reporting bugs](reporting-bugs.md).
