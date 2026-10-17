# 0.5.1 release commit

State: ready

Lane: release051            Issue: #433
Base: master @ fb6ebcff40
Files: CHANGELOG.md, android/app/build.gradle.kts, docs/releases/v0.5.1.md, docs/releases/README.md, android/README.md, android/MIGRATING.md, README.md, KNOWN_ISSUES.md, ROADMAP.md, CONTRIBUTING.md, PRIVACY.md, docs/COMPATIBILITY.md, docs/reporting-bugs.md, docs/es-de/README.md, docs/lanes/release051/**
Prediction: none: docs-only except one Kotlin DSL resValue line (no device/pixel/perf claim to predict); see "device-run gate" note below
Needs device: no    Needs NDK: no

Release note (other): docs-only release commit, plus `android/app/build.gradle.kts`'s release-variant
`app_name` string ("hakuX (fork)" → "hakuX CE"). A player sees: the new app label, a bumped
CHANGELOG/release-notes page, and refreshed public docs (dates, versions, Android-13 wording already
landed by earlier lanes). No emulator behaviour changes.

## What this is

The 0.5.1 release commit per the brief: `CHANGELOG.md` entry, `docs/releases/v0.5.1.md`, the one-line
app-label change, and a freshness pass over every doc in `docs/testing/public_docs.txt`.

**One non-docs line**: `android/app/build.gradle.kts`'s `release` buildType's
`resValue("string", "app_name", "hakuX (fork)")` → `"hakuX CE"`. The fold's device-run gate should run
for this file per the brief ("the fold will run the device-run gate for it, say so in PR.md") — flagging
that here since this lane did no device work and did not build or verify the APK itself.

Every claim in `docs/releases/v0.5.1.md` and the `CHANGELOG.md` paragraph is sourced to a specific
commit or file, listed in `docs/lanes/release051/NOTES.md`. Notably **left out**, with reasons in
NOTES.md:
- Top Spin / #992 (per the brief: pulled from 0.5.1, not mentioned).
- Audio1016's "quiet speech" fix — its own commit's release note is `(none)`; the actual fix is an
  unapplied patch file, not in the build. Nothing changed for a player, so nothing claimed.
- Halo / `HAKUX_FIST_ROUND` — `KNOWN_ISSUES.md` does not list the Halo fault, so per the brief this is
  omitted entirely, not even as a "known issues" sentence.
- GitHub Sponsors — already in README.md (funding1016), not repeated as a 0.5.1 release note.

`versionName` is not hardcoded anywhere in this lane's territory — it's set at build time via
`-PversionedRelease=0.5.1`, passed by `docs/testing/release_build.sh` (out of territory). Detail in
NOTES.md.

## Checks

```
python3 docs/testing/docs_freshness.py --release 0.5.1   # 11 OK, 0 not
python3 docs/testing/docs_freshness.py                    # 11 OK, 0 not
```

## Do not

Per the brief: no tag, no release APK build, no publish — lane.local does those after the fold.
