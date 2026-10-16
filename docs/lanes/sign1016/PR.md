# sign1016: rotate release key (lineage), minSdk 33 (#433)

State: ready

Lane: sign1016            Issue: #433
Base: master @ 0e5fab6befe57d46474095b011746855ab0e7935
Files: android/app/build.gradle.kts, android/RELEASING.md, android/key.properties.example, docs/testing/sign_lineage.sh, docs/testing/release_build.sh, docs/testing/owner_build.sh, docs/testing/nightly_build.sh, docs/testing/jobs/selftest.sh, docs/testing/jobs/selftest.d/89-sign-rotation.sh, docs/lanes/sign1016/NOTES.md, docs/lanes/sign1016/PR.md
Prediction: none: no arm
Needs device: no    Needs NDK: no

Release note (none): build-infra only; nothing changes for a player until
lane.local switches `android/key.properties` to the new keystore and ships
a build made after that switch.

## What this does

Per the owner's 10-16 ~08:40 PDT decision (rotate the key without breaking
in-place upgrades, minSdk 29 -> 33 so the new signer plus the lineage is all
a build needs):

1. `android/app/build.gradle.kts`: `minSdk = 33`, comment updated. Proved
   the native build still works with a real, non-background-truncated
   `./gradlew --no-daemon assembleRelease` run in this tree:
   `BUILD SUCCESSFUL in 8m 1s`, `52 actionable tasks: 52 executed`,
   `GRADLE_EXIT=0`.
2. `docs/testing/sign_lineage.sh` (new, sourced): `resign_with_rotation()`
   re-signs Gradle's apk with `apksigner`, v3-only
   (`--v1-signing-enabled false --v2-signing-enabled false
   --v3-signing-enabled true --lineage ~/keystores/hakux-rotation.lineage`),
   but only once that lineage file exists AND `android/key.properties`
   names the keystore whose own cert (`keytool -list -v -storepass:env`)
   matches the lineage's newest signer (`apksigner lineage --print-certs`).
   Otherwise it is a no-op: the apk Gradle produced is left byte-identical.
   When it does act, it verifies its own output
   (`apksigner verify --min-sdk-version 33 -v --print-certs`) before
   replacing the apk, and refuses (nonzero, nothing published) if that
   verify fails, reports more than one signer, or the verified signer isn't
   the keystore's own cert. Passwords are read into exported env vars and
   passed as `env:VAR`; nothing containing "pass" reaches stdout/stderr
   unredacted. `lineage_lists_both_certs()` is the sibling check used by
   the callers below.
3. Wired into `docs/testing/release_build.sh` (new exit 9),
   `docs/testing/owner_build.sh` (new exit 8), and
   `docs/testing/nightly_build.sh` (new exit 12) -- each sources
   `sign_lineage.sh`, calls `resign_with_rotation` right after confirming
   Gradle produced a *signed* apk and before the existing
   `apksigner verify` check (which already doesn't demand v2, so a v3-only
   apk passes it unchanged), then asserts `lineage_lists_both_certs` when
   `ROTATION_APPLIED=1`. `docs/testing/jobs/run-nightly.sh` doesn't sign
   anything (only symlinks `key.properties`/`local.properties` before
   calling `nightly_build.sh`), confirmed, no change needed.
4. New selftest fragment `docs/testing/jobs/selftest.d/89-sign-rotation.sh`
   (18 checks, added to `SHARD_SECS` in `selftest.sh` as `18s`, shards into
   shard 1 automatically): builds a throwaway old/new/unrelated keystore
   triple and lineage (`keytool` + `apksigner rotate`) entirely under `$T`,
   against a tiny *real* apk built with `aapt2 compile`/`aapt2 link` (a
   synthetic zip fails `apksigner verify`'s manifest read even with
   `--min-sdk-version` passed). Proves: the rotated apk verifies at 33 with
   exactly one signer (the new cert) and scheme v3 only; its lineage lists
   the old cert then the new cert; `key.properties` still naming the old
   key, or naming an unrelated key, is a byte-identical no-op;
   `apksigner sign` itself refuses a key absent from the lineage
   (mechanism-level guarantee, not my code); a mutant that reduces
   `resign_with_rotation` to `ROTATION_APPLIED=0; return 0` is caught by the
   existing `ROTATION_APPLIED=1` assertion.
5. `android/RELEASING.md` (new "## Rotating the key (#433)" section) and
   `android/key.properties.example` document the rotation: why the lineage
   must be built from both keystores while both still exist, that the old
   keystore must be kept forever, back up `~/keystores/` off the machine,
   the `apksigner rotate` command, how to verify a rotated build by hand.
   Never states the previous key's DN text -- only "the previous key" /
   "the old keystore".
6. `docs/lanes/sign1016/NOTES.md` states explicitly what was NOT converted:
   older nightly apks and v0.5.0 stay signed with the old key only and are
   not re-signed.

## Selftest results (all green, zero regressions)

| Fragment(s) | Result |
|---|---|
| `89-sign-rotation` (new) | 18 passed, 0 failed |
| `87-nightly-trunk` + `86-nightly-notes` (chain partner) | 138 passed, 0 failed |
| `88-ownersign1012` | 17 passed, 0 failed |
| `88-nightly-sign` | 17 passed, 0 failed |
| `release_build_selftest.sh` | all passed |

The three build scripts' own fixtures never supply a real keystore + a real
`key.properties` + a real lineage together, so `resign_with_rotation` stays
a no-op against every one of them -- confirming "untouched until the switch"
isn't just a claim, it held under the existing fixtures too.

## Real rotated-apk verify output (this tree's actual Gradle output, the
owner's actual new keystore and lineage -- read-only, nothing under
`~/keystores/` copied into the repo, no secret text printed)

One signer, v3 only, `CN=hakuX`:

```
Verified using v1 scheme (JAR signing): false
Verified using v2 scheme (APK Signature Scheme v2): false
Verified using v3 scheme (APK Signature Scheme v3): true
Verified using v4 scheme (APK Signature Scheme v4): false
Number of signers: 1
Signer #1 certificate DN: CN=hakuX, OU=Development, O=Open Source, L=Los Angeles, ST=CA, C=US
Signer #1 certificate SHA-256 digest: eaf0f29fdb289e02bb2171fed5395e12e88f7f3c4d6611c3e80af947a500f45d
```

Lineage lists the old signer first (its cert digest
`2e266dfbbdabdd0965077f1bfe67731e5ade2627d3a59e9a4c29f6c678c52ae2`, matching
the digest the owner gave for the previous key), then the new signer.

## Not in scope here

- Does not touch `android/key.properties` -- host-local, gitignored;
  lane.local switches it to the new keystore after folding this.
- Does not re-sign any already-published apk (see NOTES.md).
- Does not do the on-device upgrade test (lane.local's Thor test, per the
  brief) -- the Thor is currently offline (owner, ~10-27 ETA) but that is
  lane.local's hold to carry, not a blocker for folding this.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
