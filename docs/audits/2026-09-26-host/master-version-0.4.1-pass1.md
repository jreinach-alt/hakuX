# Audit pass 1: PR #410 (host/master-version-0.4.1)

Release: carry v0.4.1-j1's version and notes on master. Head `285b09abcc`,
one commit over `origin/master` `11a7dbe537`.

**Verdict: no HIGH, no MEDIUM, one LOW. Nothing to verify in pass 2; fold-ready.**

## What the diff does

- `android/app/build.gradle.kts`: `versionCode` 7 → 8, `versionName`
  `0.4.0-j1` → `0.4.1-j1`.
- `docs/releases/v0.4.1-j1.md`: new, 38 lines.

## Checks made

1. **The version is the release's.** `git show v0.4.1-j1:android/app/build.gradle.kts`
   gives `versionCode = 8`, `versionName = "0.4.1-j1"`, the same as the PR.
   `v0.4.0-j1` has 7 / `0.4.0-j1`, the same as master before the PR. A master
   build at 8 installs over the release at 8 (Android allows an equal
   versionCode), so the downgrade described in the PR body no longer happens.
2. **The notes are the published notes.** `git diff v0.4.1-j1 HEAD --
   docs/releases/v0.4.1-j1.md` is empty: the file is byte-identical to the
   tag's copy. The GitHub release body differs in one link only: the body
   links v0.4.0-j1 to the release page, and the file links it to the relative
   `v0.4.0-j1.md`, which exists in `docs/releases/`. Both links resolve.
3. **"Master already contains the #311 fix."** The tag holds two commits over
   `v0.4.0-j1`: `a046da3cc8` (the `surface.c` fix) and the release commit. The
   stable patch-id of `a046da3cc8`'s `surface.c` hunk (`44996547…`) matches
   master's `d5eb83f39e`. The claim is true, and the PR adds no code.
4. **The rest of the gradle file.** `git diff v0.4.1-j1 HEAD -- build.gradle.kts`
   shows only master's later additions (the `perflog` diagnostic flag). The PR
   touches only the two version lines.
5. **Commit message and CI.** The message does not carry the retired CI
   marker, unlike the tag's release commit `1fd54c9f10`. Both `build` checks
   pass on this head.

## Findings

### LOW-1: nightlies and the release report the same version

From this PR on, a nightly built from master reports `0.4.1-j1` / 8. That is
the same as the release, even though it carries every change folded since the
tag. A bug report that gives only the About screen's version cannot tell the
two apart. This PR does not create the problem: master did the same after
v0.4.0-j1, and this is the policy the PR body describes. The next release
still has to bump to 9 or higher, and this PR does not change that. A
`versionNameSuffix` for non-release builds would tell them apart. That is a
release-process choice, not a defect in this diff, so there is nothing to
remediate here.
