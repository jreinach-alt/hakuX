# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# docs/testing/sign_lineage.sh's resign_with_rotation()/lineage_lists_both_certs()
# (#433) are where the signing-key rotation actually happens: Gradle only
# knows one keystore at a time, so the v3-only re-sign with the
# SigningCertificateLineage attached is a step AFTER the build, not something
# build.gradle.kts can do. This is a crypto operation, not string matching --
# unlike every other fragment here, this one uses the REAL keytool and
# apksigner against a throwaway key pair generated in the test itself, never
# the owner's own ~/keystores/*. forge-selftest.yml (the gate that matters,
# per AGENTS.md) runs on the owner's own host with both already installed for
# the Gradle build; the generic ubuntu-latest in the disabled, manual-only
# .github/workflows/jobs-selftest.yml is not expected to have them, so a
# missing toolchain here is reported and skipped rather than treated as a
# crypto failure.
echo "== sign_lineage.sh: a throwaway key rotation, start to finish (#433)"
SR="$T/signrotation"; rm -rf "$SR"; mkdir -p "$SR/fakehome/keystores"
SIGN_LINEAGE="$TESTING/sign_lineage.sh"

SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}"
SR_APKSIGNER=$(find "$SDK_ROOT/build-tools" -maxdepth 2 -name apksigner -type f 2>/dev/null | sort -V | tail -1)
SR_AAPT2=$(find "$SDK_ROOT/build-tools" -maxdepth 2 -name aapt2 -type f 2>/dev/null | sort -V | tail -1)
SR_PLATFORM_DIR=$(find "$SDK_ROOT/platforms" -maxdepth 1 -iname 'android-*' -type d 2>/dev/null | sort -V | tail -1)
SR_PLATFORM_JAR="${SR_PLATFORM_DIR:+$SR_PLATFORM_DIR/android.jar}"
SR_KEYTOOL=keytool
[ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/keytool" ] && SR_KEYTOOL="$JAVA_HOME/bin/keytool"

if [ -z "$SR_APKSIGNER" ] || [ -z "$SR_AAPT2" ] || [ -z "$SR_PLATFORM_JAR" ] || [ ! -f "$SR_PLATFORM_JAR" ] || ! command -v "$SR_KEYTOOL" >/dev/null 2>&1; then
    bad "sign_lineage: no real apksigner/aapt2/android.jar/keytool under ${SDK_ROOT} -- this fragment needs the host's own Android SDK (forge-selftest.yml), not a generic runner"
else
    # shellcheck disable=SC1090
    . "$SIGN_LINEAGE"   # brings lineage_lists_both_certs into this shell too
    export SR_P="sign1016-selftest-throwaway"

    # A tiny REAL apk: a valid binary manifest is the one thing apksigner
    # verify cannot be told to skip (confirmed by hand: --min-sdk-version
    # overrides sign's inference, not verify's manifest read).
    cat > "$SR/AndroidManifest.xml" <<MANIFEST
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.example.sign1016">
    <uses-sdk android:minSdkVersion="33" android:targetSdkVersion="33" />
    <application android:label="t"/>
</manifest>
MANIFEST
    mkdir -p "$SR/res"
    "$SR_AAPT2" compile -o "$SR/compiled.zip" --dir "$SR/res" >/dev/null 2>&1
    "$SR_AAPT2" link -o "$SR/base.apk" --manifest "$SR/AndroidManifest.xml" -I "$SR_PLATFORM_JAR" "$SR/compiled.zip" >/dev/null 2>&1
    check "  built a tiny real apk with aapt2 (so verify's manifest read is real, not stubbed)" \
        test -f "$SR/base.apk"

    sr_genkey() {   # <keystore path> <CN>
        "$SR_KEYTOOL" -genkeypair -keystore "$1" -storetype PKCS12 -alias hakux \
            -keyalg RSA -keysize 4096 -validity 10000 \
            -dname "CN=$2, OU=t, O=t, L=t, ST=t, C=US" \
            -storepass:env SR_P -keypass:env SR_P >/dev/null 2>&1
    }
    sr_genkey "$SR/old.jks" "sign1016-old"
    sr_genkey "$SR/new.jks" "sign1016-new"
    sr_genkey "$SR/unrelated.jks" "sign1016-unrelated"

    "$SR_APKSIGNER" rotate --out "$SR/rotation.lineage" \
        --old-signer --ks "$SR/old.jks" --ks-pass env:SR_P \
        --new-signer --ks "$SR/new.jks" --ks-pass env:SR_P >/dev/null 2>&1
    check "  built a throwaway old->new rotation lineage" test -f "$SR/rotation.lineage"
    cp "$SR/rotation.lineage" "$SR/fakehome/keystores/hakux-rotation.lineage"

    "$SR_APKSIGNER" sign --ks "$SR/old.jks" --ks-key-alias hakux \
        --ks-pass env:SR_P --key-pass env:SR_P \
        --in "$SR/base.apk" --out "$SR/old-signed.apk" >/dev/null 2>&1
    check "  signed the base apk with the throwaway OLD key (simulates pre-rotation Gradle output)" \
        test -f "$SR/old-signed.apk"

    cat > "$SR/new-key.properties" <<PROPS
storeFile=$SR/new.jks
storePassword=$SR_P
keyAlias=hakux
keyPassword=$SR_P
PROPS
    cat > "$SR/old-key.properties" <<PROPS
storeFile=$SR/old.jks
storePassword=$SR_P
keyAlias=hakux
keyPassword=$SR_P
PROPS
    cat > "$SR/unrelated-key.properties" <<PROPS
storeFile=$SR/unrelated.jks
storePassword=$SR_P
keyAlias=hakux
keyPassword=$SR_P
PROPS

    # Runs resign_with_rotation from <script> (real or a mutant) against a
    # fresh copy of <src>, with $HOME pointed at our throwaway
    # ~/keystores/hakux-rotation.lineage instead of the owner's real one --
    # the function reads $HOME/keystores/hakux-rotation.lineage by design, so
    # this is the one hook a test needs, and the real call sites never set it.
    # Leaves the (possibly rotated) result at $SR/work.apk; prints "<rc>
    # <ROTATION_APPLIED>" to stdout for the caller to capture.
    sr_run_rotation() {   # <sign_lineage.sh script> <src apk> <key.properties>
        cp "$2" "$SR/work.apk"
        ( HOME="$SR/fakehome"
          export HOME
          # shellcheck disable=SC1090
          . "$1"
          resign_with_rotation "$SR/work.apk" "$3" "$SR_APKSIGNER"
          echo "$? $ROTATION_APPLIED" )
    }

    # ---- case A: key.properties names the new key (the lineage's newest) --
    # this must rotate: v3-only, single signer, the new cert, min-sdk 33.
    read -r SR_RC SR_APPLIED < <(sr_run_rotation "$SIGN_LINEAGE" "$SR/old-signed.apk" "$SR/new-key.properties")
    check "  case A: resign_with_rotation succeeds when key.properties names the new key" \
        test "$SR_RC" = 0
    check "  case A: ROTATION_APPLIED=1" test "$SR_APPLIED" = 1
    SR_VERIFY=$("$SR_APKSIGNER" verify --min-sdk-version 33 -v --print-certs "$SR/work.apk" 2>/dev/null)
    SR_VERIFY_RC=$?
    check "  case A: the rotated apk verifies at --min-sdk-version 33" \
        test "$SR_VERIFY_RC" = 0
    check "  case A: verified using v3, not v1/v2" \
        bash -c 'grep -q "v3 scheme.*true" <<<"$1" && grep -q "v1 scheme.*false" <<<"$1" && grep -q "v2 scheme.*false" <<<"$1"' _ "$SR_VERIFY"
    check "  case A: exactly one signer, and it is the new (throwaway) cert" \
        bash -c 'grep -q "^Number of signers: 1$" <<<"$1" && grep -q "CN=sign1016-new" <<<"$1"' _ "$SR_VERIFY"
    check "  case A: the rotated apk's own lineage lists both certs" \
        lineage_lists_both_certs "$SR/work.apk" "$SR_APKSIGNER"
    SR_LINEAGE_OUT=$("$SR_APKSIGNER" lineage --in "$SR/work.apk" --print-certs -v 2>/dev/null)
    check "  case A: the lineage names the old cert and the new cert, in that order" \
        bash -c 'grep -q "Signer #1 in lineage certificate DN: CN=sign1016-old" <<<"$1" && grep -q "Signer #2 in lineage certificate DN: CN=sign1016-new" <<<"$1"' \
            _ "$SR_LINEAGE_OUT"

    # ---- case B: key.properties still names the OLD key (pre-switch) -- a
    # lineage existing is not enough; it must leave the apk untouched.
    SR_BEFORE=$(sha256sum "$SR/old-signed.apk" | cut -d' ' -f1)
    read -r SR_RC SR_APPLIED < <(sr_run_rotation "$SIGN_LINEAGE" "$SR/old-signed.apk" "$SR/old-key.properties")
    SR_AFTER=$(sha256sum "$SR/work.apk" | cut -d' ' -f1)
    check "  case B: key.properties still naming the old key is a no-op (rc=0)" test "$SR_RC" = 0
    check "  case B: ROTATION_APPLIED=0" test "$SR_APPLIED" = 0
    check "  case B: the apk is byte-identical -- nothing touched it" test "$SR_BEFORE" = "$SR_AFTER"

    # ---- case C: key.properties names a key with no relation to the lineage
    # at all -- also a no-op, never a crash or a silent wrong-signer publish.
    read -r SR_RC SR_APPLIED < <(sr_run_rotation "$SIGN_LINEAGE" "$SR/old-signed.apk" "$SR/unrelated-key.properties")
    check "  case C: an unrelated key.properties is also a no-op (rc=0)" test "$SR_RC" = 0
    check "  case C: ROTATION_APPLIED=0" test "$SR_APPLIED" = 0

    # ---- case D: the underlying mechanism itself -- signing directly with a
    # key that is in neither position of the lineage is REFUSED by apksigner,
    # which is exactly what stands between a stolen or mistaken key and a
    # device accepting it as a valid upgrade.
    sr_unrelated_sign_refused() {
        ! "$SR_APKSIGNER" sign --min-sdk-version 33 \
            --v1-signing-enabled false --v2-signing-enabled false --v3-signing-enabled true \
            --lineage "$SR/rotation.lineage" \
            --ks "$SR/unrelated.jks" --ks-key-alias hakux \
            --ks-pass env:SR_P --key-pass env:SR_P \
            --in "$SR/old-signed.apk" --out "$SR/bad-rotated.apk" >/dev/null 2>&1
    }
    check "  case D: apksigner itself refuses to sign with a key absent from the lineage" \
        sr_unrelated_sign_refused

    # ---- MUTANT: a resign_with_rotation that skips the post-sign step (the
    # re-sign + verify entirely) and just reports success. Case A's checks
    # above are only evidence of anything if they go red here.
    SR_MUTANT="$SR/sign_lineage.mutant.sh"
    sed '/^resign_with_rotation() {$/,/^}$/c\
resign_with_rotation() {\
    ROTATION_APPLIED=0\
    return 0\
}' "$SIGN_LINEAGE" > "$SR_MUTANT"
    check "  MUTANT: the mutant file differs from the real one (the sed actually matched)" \
        bash -c '! diff -q "$1" "$2" >/dev/null' _ "$SIGN_LINEAGE" "$SR_MUTANT"
    read -r SR_RC SR_APPLIED < <(sr_run_rotation "$SR_MUTANT" "$SR/old-signed.apk" "$SR/new-key.properties")
    check "  MUTANT: skipping the post-sign step would be caught (ROTATION_APPLIED stays 0)" \
        test "$SR_APPLIED" = 0
fi
