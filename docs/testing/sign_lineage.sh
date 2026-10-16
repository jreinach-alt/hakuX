#!/usr/bin/env bash
#
# Shared signing-rotation step, sourced by release_build.sh, owner_build.sh
# and nightly_build.sh (#433).
#
# WHY THIS EXISTS. The signing key is rotating (old: hakux-release.jks, every
# APK up to and including v0.5.0; new: hakux-release-2.jks) without breaking
# in-place upgrades, via a SigningCertificateLineage file built and verified
# by the owner. Gradle only knows how to sign with whatever one keystore
# android/key.properties names; it cannot add a v3 rotation block, and a v2
# block naming only the new key would make Play/adb refuse the upgrade (v2
# requires the OLD signer to co-sign once a lineage exists). So the actual
# rotation happens in a step AFTER Gradle: re-sign Gradle's output with
# apksigner, v3-only, with the lineage attached.
#
# This must stay a no-op, byte-for-byte, until BOTH of these are true:
#   - ~/keystores/hakux-rotation.lineage exists
#   - android/key.properties' keystore is the lineage's newest (new) signer
# Before the switch (lineage absent, or key.properties still the old store)
# every caller keeps shipping exactly what Gradle produced, same as today.
#
# Never prints a password, a keystore path, or any key.properties content.
# Reads passwords into env vars and passes apksigner/keytool `env:VAR`, never
# `pass:literal` or a CLI argument (which would show up in `ps`).
set -u

# resign_with_rotation <apk> <key.properties> <apksigner>
#
# Sets ROTATION_APPLIED=1 and re-signs <apk> IN PLACE (same path) when the
# rotation applies; sets ROTATION_APPLIED=0 and leaves <apk> untouched
# otherwise (no lineage yet, key.properties missing/incomplete, or
# key.properties still names a keystore that isn't the lineage's newest
# signer -- e.g. the old key, pre-switch).
#
# Returns 1 (nothing published) only when the lineage DOES apply but the
# re-signed result fails to verify at --min-sdk-version 33, or its verified
# signer is not that same keystore's own certificate -- a rotation that
# doesn't verify must never reach a release.
resign_with_rotation() {
    local apk=$1 keyprops=$2 apksigner=$3
    ROTATION_APPLIED=0

    local lineage="$HOME/keystores/hakux-rotation.lineage"
    [ -f "$lineage" ] || return 0
    [ -f "$keyprops" ] || return 0

    local store alias
    store=$(sed -n 's/^storeFile=//p' "$keyprops" | tail -1)
    alias=$(sed -n 's/^keyAlias=//p' "$keyprops" | tail -1)
    [ -n "$store" ] && [ -n "$alias" ] || return 0
    # storeFile is resolved relative to android/app/ when it isn't absolute --
    # the same rule android/app/build.gradle.kts applies (key.properties.example).
    case "$store" in
        /*) : ;;
        *) store="$(cd "$(dirname "$keyprops")" && pwd)/app/$store" ;;
    esac
    [ -f "$store" ] || return 0

    export SIGN_LINEAGE_STOREPASS SIGN_LINEAGE_KEYPASS
    SIGN_LINEAGE_STOREPASS=$(sed -n 's/^storePassword=//p' "$keyprops" | tail -1)
    SIGN_LINEAGE_KEYPASS=$(sed -n 's/^keyPassword=//p' "$keyprops" | tail -1)
    if [ -z "$SIGN_LINEAGE_STOREPASS" ] || [ -z "$SIGN_LINEAGE_KEYPASS" ]; then
        unset SIGN_LINEAGE_STOREPASS SIGN_LINEAGE_KEYPASS
        return 0
    fi

    local keytool=keytool
    [ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/keytool" ] && keytool="$JAVA_HOME/bin/keytool"

    # The keystore's own cert digest, normalized to bare lowercase hex so it
    # compares equal to apksigner's digest format (keytool prints
    # "SHA256: AA:BB:...", apksigner prints "aabb...").
    local store_digest
    store_digest=$("$keytool" -list -v -alias "$alias" -keystore "$store" \
            -storepass:env SIGN_LINEAGE_STOREPASS 2>/dev/null \
        | sed -n 's/^.*SHA256: *//p' | tr -d ':' | tr 'A-Z' 'a-z' | head -1)
    if [ -z "$store_digest" ]; then
        echo "sign_lineage: could not read a certificate from key.properties' keystore; leaving the apk as Gradle produced it" >&2
        unset SIGN_LINEAGE_STOREPASS SIGN_LINEAGE_KEYPASS
        return 0
    fi

    # The lineage's newest (last) signer -- a standalone lineage file works
    # directly with `apksigner lineage --in`, same as one read back out of a
    # signed apk.
    local lineage_newest
    lineage_newest=$("$apksigner" lineage --in "$lineage" --print-certs -v 2>/dev/null \
        | sed -n 's/^Signer #[0-9]* in lineage certificate SHA-256 digest: *//p' | tail -1)
    if [ "$lineage_newest" != "$store_digest" ]; then
        # Lineage exists, but key.properties doesn't (yet) name its newest
        # signer -- e.g. still the old keystore, pre-switch. Not our turn.
        unset SIGN_LINEAGE_STOREPASS SIGN_LINEAGE_KEYPASS
        return 0
    fi

    local out err
    out=$(mktemp "${apk}.rotatedXXXXXX")
    err=$(mktemp "${apk}.rotatelogXXXXXX")
    if ! "$apksigner" sign --min-sdk-version 33 \
            --v1-signing-enabled false --v2-signing-enabled false --v3-signing-enabled true \
            --lineage "$lineage" \
            --ks "$store" --ks-key-alias "$alias" \
            --ks-pass env:SIGN_LINEAGE_STOREPASS --key-pass env:SIGN_LINEAGE_KEYPASS \
            --in "$apk" --out "$out" >"$err" 2>&1; then
        echo "sign_lineage: REFUSING -- apksigner could not re-sign $(basename "$apk") with the rotated key; nothing published" >&2
        sed -E 's/(pass|Pass|PASS)[A-Za-z:= ]*/[redacted] /g' "$err" >&2
        rm -f "$out" "$err"
        unset SIGN_LINEAGE_STOREPASS SIGN_LINEAGE_KEYPASS
        return 1
    fi
    unset SIGN_LINEAGE_STOREPASS SIGN_LINEAGE_KEYPASS

    # Verify the re-signed result before it ever replaces the apk callers are
    # about to publish: wrong minSdk coverage or the wrong signer must refuse
    # here, not be discovered by a device that can't install the upgrade.
    local verify_out
    verify_out=$("$apksigner" verify --min-sdk-version 33 -v --print-certs "$out" 2>"$err")
    if [ $? -ne 0 ]; then
        echo "sign_lineage: REFUSING -- the rotated $(basename "$apk") does not verify at --min-sdk-version 33; nothing published" >&2
        cat "$err" >&2
        rm -f "$out" "$err"
        return 1
    fi
    local verified_digest
    verified_digest=$(echo "$verify_out" | sed -n 's/^Signer #1 certificate SHA-256 digest: *//p' | head -1)
    local signer_count
    signer_count=$(echo "$verify_out" | sed -n 's/^Number of signers: *//p' | head -1)
    if [ "$signer_count" != "1" ] || [ "$verified_digest" != "$store_digest" ]; then
        echo "sign_lineage: REFUSING -- the rotated $(basename "$apk") verifies with the wrong signer (expected the keystore's own cert, found ${signer_count:-0} signer(s)); nothing published" >&2
        rm -f "$out" "$err"
        return 1
    fi
    rm -f "$err"

    mv -f "$out" "$apk"
    ROTATION_APPLIED=1
    echo "sign_lineage: $(basename "$apk") re-signed with the rotated key (v3-only, lineage attached), verified at --min-sdk-version 33" >&2
    return 0
}

# lineage_lists_both_certs <apk> <apksigner>
#
# True (0) only when <apk>'s embedded lineage names 2 or more signers --
# the rotation's whole point (an in-place upgrade needs the old cert in the
# lineage, not just the new one in the signature). Callers gate this on
# ROTATION_APPLIED=1; it is meaningless on an apk resign_with_rotation left
# untouched.
lineage_lists_both_certs() {
    local apk=$1 apksigner=$2
    local n
    n=$("$apksigner" lineage --in "$apk" --print-certs -v 2>/dev/null \
        | grep -c '^Signer #[0-9]* in lineage certificate SHA-256 digest:')
    [ "${n:-0}" -ge 2 ]
}
