# Releasing an Android build

## Why signing matters here

Android identifies an app by its `applicationId` *and* its signing key. Installing
a build signed with a different key than the one already on the device is
refused, and the only way through is to uninstall first — which deletes
`Android/data/com.rfandango.haku_x/`, taking the Xbox HDD image, the EEPROM and
every per-game setting with it.

So the key is not a formality. Sign every release with the **same** key and
users upgrade in place with `adb install -r`. Sign each release with a fresh
key — which is what happens by default, since an unsigned release build falls
back to an ephemeral debug key — and every release costs your users their saves.

**If the keystore is lost, it cannot be recreated.** Nobody who installed a
previous build can ever upgrade again; they must uninstall and start over. Back
it up before you build anything with it.

## Creating the keystore, once

Run this on your own machine. Keep the keystore outside the repository.

```bash
mkdir -p ~/keystores
keytool -genkeypair -v \
  -keystore ~/keystores/hakux-release.jks \
  -alias hakux \
  -keyalg RSA -keysize 4096 \
  -validity 10000 \
  -storetype PKCS12
```

`keytool` ships with the JDK. It will ask for a password and for name and
location fields; the fields are cosmetic for a sideloaded build and may be left
blank, but the password is not — use a strong one and record it in a password
manager. `-validity 10000` is about 27 years, which is the point: a key that
expires strands the same users a lost key does.

Then back the file up somewhere durable and separate from the machine that
built it.

## Wiring it in

```bash
cp android/key.properties.example android/key.properties
```

Fill in the absolute path to the keystore, the store password, the alias
(`hakux` above) and the key password. `android/key.properties` is gitignored.

`android/app/build.gradle.kts` picks it up automatically: it looks for
`key.properties` beside `settings.gradle.kts`, and only defines a release
signing config when all four values are present. With the file absent, a
release build is simply unsigned — which is the current behavior.

## Before tagging a release

A tagged release is also whatever the public docs say it is — README.md,
KNOWN_ISSUES.md, and the rest of `docs/testing/public_docs.txt` — so tag
only after both of these pass for the version you are about to tag:

1. Read every public doc start to finish and bump its date line to today,
   in Pacific time, with the version it now describes.
2. `python3 docs/testing/docs_freshness.py --release X.Y.Z`

A doc the checker calls stale is a doc nobody has reviewed for this release;
fix the doc, not the check.

## Building and verifying

```bash
cd android
./gradlew assembleRelease
apksigner verify --print-certs app/build/outputs/apk/release/app-release.apk
```

Check the printed certificate digest against the previous release. Identical
digest means users upgrade in place. A different digest means every user has to
uninstall — so confirm it *before* publishing, not after.

## Rotating the key (#433)

The key can be rotated — replaced with a new one — without costing users their
saves, but only if you plan for it before you need it.

**Keep every retired keystore forever.** A `SigningCertificateLineage` is built
from the *old* keystore and the *new* one together; if the old one is gone,
there is no way to build a lineage from it later, and rotating becomes exactly
as destructive as losing a key outright. Back up `~/keystores/` as a whole,
off this machine, every time you add one.

To rotate:

```bash
mkdir -p ~/keystores
keytool -genkeypair -v \
  -keystore ~/keystores/hakux-release-2.jks \
  -alias hakux \
  -keyalg RSA -keysize 4096 \
  -validity 10000 \
  -storetype PKCS12
apksigner rotate --out ~/keystores/hakux-rotation.lineage \
  --old-signer --ks ~/keystores/hakux-release.jks \
  --new-signer --ks ~/keystores/hakux-release-2.jks
```

(Name the new file and the lineage file whatever you like; `docs/testing/
sign_lineage.sh` only cares that `~/keystores/hakux-rotation.lineage` exists
and that `android/key.properties` names the keystore the lineage's newest
signer belongs to.)

Switch `android/key.properties` to the new keystore once the lineage exists.
From then on, `release_build.sh`, `owner_build.sh` and `nightly_build.sh` all
re-sign Gradle's output with `apksigner`, v3-only, with the lineage attached —
that is what lets a device that already has the app, signed with the previous
key, accept an update signed with the new one. Before the lineage exists, or
while `key.properties` still names the previous key, every build script is a
no-op here and nothing changes.

Verify a rotated build by hand with:

```bash
apksigner verify -v --print-certs app/build/outputs/apk/release/app-release.apk
apksigner lineage --in app/build/outputs/apk/release/app-release.apk --print-certs -v
```

The first should show exactly one signer (the new key) verified under scheme
v3; the second should list two signers in lineage order, the previous key
first and the new key last.

## The first signed release

It will not install over an existing build, because those were signed with
either rfandango's release key or an ephemeral debug key. That uninstall is
unavoidable and happens exactly once. Say so in the release notes, and point
users at Settings → Export HDD first so they keep their saves.

## Later, in CI

Do not commit the keystore to run CI. Base64-encode it into a repository
secret, decode it into the runner at build time, and pass the passwords as
separate secrets. The keystore never enters git, and a compromised runner
cannot leak a file that was never there.
