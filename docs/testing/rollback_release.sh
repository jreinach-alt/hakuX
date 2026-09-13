#!/usr/bin/env bash
#
#   rollback_release.sh <serial> <apk>          install an APK over the release build
#   rollback_release.sh <serial> --backup-only  just save the user's data
#
# Put a different build of the RELEASE package on a device without risking the
# user's disk.
#
# What is at stake
# ----------------
#
# The release package's guest data lives in external app-specific storage:
#
#     /sdcard/Android/data/com.jreinach.hakux/files/x1box/
#         hdd.img   eeprom.bin   flash.bin   mcpx.bin   xemu.toml
#
# On the Nova that hdd.img is **1.18 GB of the owner's saves**. Android deletes
# that directory when the package is uninstalled. So the single rule here is:
#
#     NEVER `pm uninstall`. Not to "clean up", not to get past an error.
#
# An in-place install keeps it. `adb install -r` preserves app data when the
# signing key matches, and `-d` additionally permits a lower versionCode, which
# is what a rollback is. The installed release reports `past signatures:[]`,
# meaning no key rotation, so every build from this keystore satisfies that.
#
# The failure this guards against is the tempting one: `install -r -d` fails
# with INSTALL_FAILED_UPDATE_INCOMPATIBLE because an APK was signed with a
# different key, and the obvious next step -- uninstall and reinstall -- is
# exactly the step that destroys the saves. This script refuses to take it, and
# takes a verified backup first so that even a mistake made by hand afterwards
# is recoverable.
set -u

SERIAL="${1:?usage: rollback_release.sh <serial> <apk|--backup-only>}"
APK="${2:?usage: rollback_release.sh <serial> <apk|--backup-only>}"
PKG="${PKG:-com.jreinach.hakux}"
GUEST="/sdcard/Android/data/$PKG/files/x1box"
STORE="${ROLLBACK_BACKUP_DIR:-/home/justin/hakux-work/backups}"

a() { adb -s "$SERIAL" "$@"; }

a shell true >/dev/null 2>&1 || { echo "device $SERIAL not reachable" >&2; exit 2; }

STAMP=$(date +%Y%m%d-%H%M%S)
DEST="$STORE/$PKG-$SERIAL-$STAMP"
mkdir -p "$DEST"

echo "== backing up $GUEST -> $DEST"
files=$(a shell "ls -1 $GUEST 2>/dev/null" | tr -d '\r')
[ -n "$files" ] || { echo "nothing at $GUEST; is $PKG installed with data?" >&2; exit 3; }

for f in $files; do
    want=$(a shell "stat -c %s $GUEST/$f 2>/dev/null" | tr -d '\r')
    echo "   $f ($want bytes)"
    a pull "$GUEST/$f" "$DEST/$f" >/dev/null 2>&1 || { echo "   PULL FAILED for $f" >&2; exit 4; }
    got=$(stat -c %s "$DEST/$f" 2>/dev/null || echo 0)
    # Verified by size, because a truncated pull of a 1.2 GB image is exactly
    # the backup that looks fine and is not.
    [ "$want" = "$got" ] || { echo "   SIZE MISMATCH $f: device $want, host $got" >&2; exit 5; }
done
echo "== backup verified: $(du -sh "$DEST" | cut -f1) in $DEST"

[ "$APK" = "--backup-only" ] && { echo "backup only, nothing installed"; exit 0; }
[ -f "$APK" ] || { echo "no such APK: $APK" >&2; exit 6; }

echo "== installing $(basename "$APK") over $PKG (keeping data)"
out=$(a install -r -d "$APK" 2>&1)
echo "$out" | sed 's/^/   /'

if printf '%s' "$out" | grep -q 'Success'; then
    echo "== installed. Data left in place; backup kept at $DEST"
    exit 0
fi

cat >&2 <<MSG

== INSTALL FAILED and nothing was removed.

The user's data is untouched and a verified copy is at:
    $DEST

DO NOT uninstall the package to get past this. Uninstalling deletes
$GUEST, including hdd.img.

If the failure is INSTALL_FAILED_UPDATE_INCOMPATIBLE the APK was signed with a
different key than the installed build. Rebuild it with the same keystore
rather than removing the app. If the app genuinely must be replaced, push the
backup back into $GUEST afterwards and chmod 660 -- adb push leaves 0644 and
the app reaches those files through a group, so it will report "Could not open
hdd.img: Permission denied" and then crash in the GPU driver during teardown,
which reads as a graphics bug.
MSG
exit 7
