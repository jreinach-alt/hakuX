# Prebuilt test APK

`hakuX-0.3.1-esde-launchfix.apk`

hakuX 0.3.1 built from this branch, containing the frontend launch handoff
fix (commit 96e4b77) that is not present in the tagged 0.3.1 release.

## What it fixes

Two separate defects on the external-frontend launch path, both of which had to
be fixed before launching from ES-DE worked.

### 1. Stale/empty `dvdUri` (upstream commit 96e4b77)

`LauncherActivity` wrote the selected game's `dvdUri` to SharedPreferences with
the asynchronous `apply()` and then immediately started `MainActivity`, which
runs in a separate process (`android:process=":xemu"`) and reads that value back
from disk during native startup. The read could race the pending write and see
either the previous game's URI or no value at all. Fixed by using `commit()`.

### 2. Revoked URI permission (this branch)

ES-DE launches with `%DATA%=%ROMSAF%`, handing over a Storage Access Framework
`content://` URI that carries only a *transient* read grant, scoped to the
lifetime of the activity that received it. `LauncherActivity` started
`MainActivity` with a bare intent — no data URI, no grant flag — and then called
`finish()`, revoking the grant before the `:xemu` process had started far enough
to open the file. Both `openFileDescriptor` and the `openInputStream` copy
fallback threw, `out.dvd` was left empty, and the emulator booted with no disc:

```
Prefs dvdUri=content://com.android.externalstorage.documents/tree/...
JNI exception in openFileDescriptor
Failed to open DVD URI as fd, falling back to copy
JNI exception in openInputStream
Failed to sync DVD image
Config final dvd=
```

Fixed by re-granting the URI to `MainActivity`, whose grant lasts for the
emulation session. Only applied for `content://` URIs — attaching a `file://`
URI to an intent would raise `FileUriExposedException` on API 24 and above.

The forwarding is best effort. A URI the app cannot re-grant makes
`startActivity` raise `SecurityException`, which took the whole process down
and left a black screen instead of a running emulator:

```
am_crash: java.lang.SecurityException, UID 10138 does not have permission to
content://com.android.externalstorage.documents/tree/E6C6-D7AA%3AGames%2Fxbox/...
```

It now falls back to a plain intent, so a URI that cannot be forwarded still
reaches the emulator, which either opens it through a persisted grant or
reports a missing disc.

### A note on path case

SAF document IDs are case-sensitive strings even on a case-insensitive volume
such as exFAT. A persisted grant on `E6C6-D7AA:Games/XBox` therefore does not
cover a URI naming `E6C6-D7AA:Games/xbox`, though both resolve to one directory
on disk. A frontend configured with a differently-cased ROM path than the one
picked in this app will hand over URIs it has no permission for.

## Details

- Package: `com.rfandango.haku_x` (identical to the release, so ES-DE needs no
  configuration change)
- ABI: `arm64-v8a`
- sha256: `4a8f38522370f36d3e5fc3ec87584a21a7397fbe35ffaf618e3aa0d4ef1cfe98`

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
