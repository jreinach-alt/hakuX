# Prebuilt test APK

`hakuX-0.3.1-esde-launchfix.apk`

hakuX 0.3.1 built from this branch, containing the frontend launch handoff
fix (commit 96e4b77) that is not present in the tagged 0.3.1 release.

## What it fixes

`LauncherActivity` — the entry point external frontends such as ES-DE use —
wrote the selected game's `dvdUri` to SharedPreferences with the asynchronous
`apply()` and then immediately started `MainActivity`. `MainActivity` runs in a
separate process (`android:process=":xemu"`) and reads that value back from disk
during native startup, so it could race the pending write and observe either the
previous game's URI (wrong game boots) or no value at all (the Xbox dashboard's
"Please insert an Xbox disc" screen). The fix uses the synchronous `commit()`.

## Details

- Package: `com.rfandango.haku_x` (identical to the release, so ES-DE needs no
  configuration change)
- ABI: `arm64-v8a`
- sha256: `76a515d422f4bbb91ff8f331a635ce742a76e0ca4d5796c2668111b7c88f050c`

## Install

Debug-signed, so the existing release build must be removed first:

```
adb uninstall com.rfandango.haku_x
adb install hakuX-0.3.1-esde-launchfix.apk
```

Uninstalling deletes `Android/data/com.rfandango.haku_x/`, which holds the
copied BIOS files, the Xbox HDD image and the EEPROM. Export the HDD from
Settings first to keep saves, and re-run the setup wizard afterwards.

## Build note

`subprojects/nv2a_vsh_cpu.wrap` pins revision `561fe80da57a881f89000256b459440c0178a7ce`,
which does not exist in `xemu-project/nv2a_vsh_cpu`. A clean checkout therefore
cannot fetch that subproject and the native build fails at configure time. This
APK was built against that subproject's `main` (`1115255`) instead.
