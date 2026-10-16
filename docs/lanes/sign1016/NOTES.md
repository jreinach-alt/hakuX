# lane.sign1016 -- sign every release and nightly with the rotated key, minSdk 33 (#433)

## What changed

- `android/app/build.gradle.kts`: `minSdk` 29 -> 33, comment updated to explain
  why (the rotation needs only the new signer plus the lineage at build time;
  29 was the ELF-TLS/`ANDROID_PLATFORM` floor from #427, which 33 stays above).
  Proved the native build still works with a real `./gradlew assembleRelease`
  run in this tree: `BUILD SUCCESSFUL in 8m 1s`, `52 actionable tasks: 52
  executed`, `GRADLE_EXIT=0`.
- `docs/testing/sign_lineage.sh` (new, sourced, not executable): the shared
  `resign_with_rotation()` / `lineage_lists_both_certs()` functions.
  `resign_with_rotation` is a no-op (`ROTATION_APPLIED=0`, apk untouched)
  unless BOTH `~/keystores/hakux-rotation.lineage` exists AND
  `android/key.properties` names a keystore whose own certificate digest
  (`keytool -list -v`) matches the lineage's newest signer
  (`apksigner lineage --print-certs`). When both hold, it re-signs with
  `apksigner sign --min-sdk-version 33 --v1-signing-enabled false
  --v2-signing-enabled false --v3-signing-enabled true --lineage ... --ks ...`,
  then verifies the result itself (`apksigner verify --min-sdk-version 33 -v
  --print-certs`) before replacing the apk, refusing (nonzero return, apk
  left alone) if the verify fails, if more than one signer comes back, or if
  the verified signer isn't the keystore's own cert. Passwords are read into
  exported env vars and passed as `env:VAR`; nothing with "pass" in it reaches
  stdout/stderr unredacted.
- `docs/testing/release_build.sh`, `owner_build.sh`, `nightly_build.sh`: each
  now sources `sign_lineage.sh` and calls `resign_with_rotation` right after
  confirming Gradle produced a signed (not `-unsigned.apk`) artifact and
  before the existing `apksigner verify` check, so the existing verify step
  also covers the rotated output. Added a `lineage_lists_both_certs` check
  gated on `ROTATION_APPLIED=1`. New refusal exit codes: `release_build.sh`
  exit 9, `owner_build.sh` exit 8, `nightly_build.sh` exit 12 -- none
  collided with that script's existing codes. `jobs/run-nightly.sh` does not
  sign anything (it only symlinks `key.properties`/`local.properties` into
  place before calling `nightly_build.sh`), so it needed no changes, per the
  brief.
- Existing `apksigner verify` calls in all three scripts already ask for
  `--print-certs`/`-v` without asserting a v2 block, so a v3-only APK (what
  minSdk 33 + the rotation produces) passes them unchanged; nothing had to
  be loosened.
- Selftest: new fragment `docs/testing/jobs/selftest.d/89-sign-rotation.sh`,
  18 checks, builds a throwaway old/new/unrelated keystore triple and a
  throwaway lineage entirely inside `$T` (never touches `~/keystores/`),
  against a tiny *real* APK built with `aapt2 compile`/`aapt2 link` (a
  synthetic zip fails `apksigner verify`'s manifest read even with
  `--min-sdk-version` passed -- that flag overrides `sign`'s inference, not
  `verify`'s manifest parse). Proves: rotation applies and verifies at 33
  with one signer (the new cert) when `key.properties` names the new key;
  is a byte-identical no-op when it still names the old key or an unrelated
  key; `apksigner sign` itself refuses a key absent from the lineage
  (mechanism-level, not my code); the rotated apk's own lineage lists both
  certs in order. A mutant that reduces `resign_with_rotation` to
  `ROTATION_APPLIED=0; return 0` (skips the post-sign step) is asserted to
  fail the "ROTATION_APPLIED=1" check -- proving that check isn't vacuous.
  Added `89-sign-rotation:18` to `SHARD_SECS` in `selftest.sh`; it shards
  into shard 1 automatically, no `SHARD_CHAINS` entry needed (nothing else
  reads its state). Ran `SELFTEST_ONLY="89-sign-rotation"`: 18 passed, 0
  failed. Ran `SELFTEST_ONLY="87-nightly-trunk 86-nightly-notes"` (138
  passed), `SELFTEST_ONLY="88-ownersign1012"` (17 passed), and
  `SELFTEST_ONLY="88-nightly-sign"` (17 passed), and `release_build_selftest.sh`
  directly: all green, zero regressions, because none of those fixtures
  provide a real keystore + `key.properties` + lineage combination, so
  `resign_with_rotation` stays a no-op against them exactly as designed.
- `android/RELEASING.md`: new "## Rotating the key (#433)" section --
  why the lineage must be built from both keystores while both still exist,
  that the old keystore must be kept forever, back up `~/keystores/` off the
  machine, the `apksigner rotate` command, and how to verify a rotated
  build by hand. Never states the previous key's DN text, only "the
  previous key" / "the old keystore".
- `android/key.properties.example`: a short added comment pointing at
  `RELEASING.md`'s rotation section, noting `storeFile` only takes effect
  for the new keystore once the lineage exists and the old keystore must be
  kept. No secrets, no old DN text.

## What this does NOT do

- **Does not touch `android/key.properties` itself.** That file is
  host-local and gitignored; lane.local switches it to the new keystore
  after folding this, per the brief.
- **Does not re-sign anything already published.** Every nightly APK built
  before this lands, and the v0.5.0 release APK, stay signed with the old
  key only (`2e266dfb...c52ae2`) and are not retroactively converted --
  they predate the lineage and this script never runs against artifacts
  that already shipped. A device that already has one of those installed
  upgrades fine once a build made *after* this fold and *after*
  `key.properties` points at the new key is installed over it, because
  that build carries the lineage; it does not change anything about the
  already-published files themselves.
- **Does not change `jobs/run-nightly.sh`**: confirmed it never signs, only
  stages `key.properties`/`local.properties` before invoking
  `nightly_build.sh`, so the brief's "if it signs" condition doesn't apply.
- **Does not do the on-device upgrade test.** That's lane.local's job per
  the brief (Thor upgrade test), not this lane's -- this lane had no device
  work in scope.

## Verification included in PR.md

Real end-to-end proof, built from this tree's actual Gradle output and the
owner's actual new keystore + lineage (read-only; nothing under
`~/keystores/` copied into the repo, no secrets printed): one rotated APK,
v3-only, single signer `CN=hakuX`, SHA-256
`eaf0f29fdb289e02bb2171fed5395e12e88f7f3c4d6611c3e80af947a500f45d`; its
lineage lists the old signer (`2e266dfbbdabdd0965077f1bfe67731e5ade2627d3a59e9a4c29f6c678c52ae2`,
matches the brief's stated old-key digest) then the new one.
