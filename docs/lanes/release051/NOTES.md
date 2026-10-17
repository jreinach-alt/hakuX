# release051 — the 0.5.1 release commit (#433)

Docs-only lane plus one line of Kotlin DSL. No device work, no device claims
made here — every player-visible claim below cites a commit or file written
by an earlier lane; this lane only decides what belongs in the release docs
and bumps dates/versions.

## Claims in the release notes, and their source

1. **Signing key rotated, in-place update, data kept.** Source: brief's
   fact 1, stated as already verified on a device by lane.local (same
   versionCode, data kept). `sign1016` (56bb989b0c) itself is build-infra
   only — its own release note says "nothing changes for a player until
   lane.local switches `android/key.properties` to the new keystore and
   ships a build made after that switch" — so the in-place-update claim
   rests on lane.local's device verification named in the brief, not on
   anything this lane can check itself (no device work, and
   `android/key.properties` / `~/keystores/` are off limits to read).
   `android/RELEASING.md` (already in the repo, untouched by this lane)
   documents the lineage mechanism that makes this possible.
2. **minSdk 33 / Android 13 minimum.** Confirmed directly:
   `android/app/build.gradle.kts:88` (`minSdk = 33`, comment cites the
   signing-key rotation and #433). README.md, android/MIGRATING.md,
   KNOWN_ISSUES.md and docs/COMPATIBILITY.md already said Android 13 before
   this lane touched them (done by `ce1016`/`compatrefresh1013`); this lane
   only bumped their date/version lines.
3. **App name "hakuX CE".** Confirmed: `ce1016` (3ceee93982) did the docs
   pass; this lane made the matching code change,
   `android/app/build.gradle.kts` line ~167, the release variant's
   `resValue("string", "app_name", ...)`, from `"hakuX (fork)"` to
   `"hakuX CE"` — the only non-doc file in this PR. Also fixed the one
   stale comment in `android/README.md` still showing the old label.
   `docs/frontends/README.md` ("About the app name") confirms the package id
   and activity name are unchanged, so this is an in-place rename, not a new
   install, for a frontend already wired up.
4. **New app icon.** Confirmed: `icon1016` (8cd408688e). Adaptive icon,
   foreground + themed/monochrome layer. Verified by that lane via
   `aapt2 dump` on a built APK (device visual check was blocked by
   `FLAG_SECURE` screen capture on the Thor, documented there, not re-tried
   here).
5. **Launcher wiring.** Confirmed: `frontends1016` (545886f9c0) and
   `frontends1016b` (fb6ebcff40). Read `docs/frontends/README.md`'s summary
   table: all four launchers (ES-DE, Daijisho, Pegasus, stock/AYN
   odinlauncher) are listed "Tested on the Thor"; the Retroid stock-launcher
   variant is explicitly "not yet tested" and the release notes say so.
6. **Quiet speech / movie audio (audio1016) — left OUT.** Read the full
   commit (2636e89f4a). Its own release note is explicitly `(none)`: the
   only things it adds are two debug switches (`HAKUX_APU_MIXLOG`,
   `HAKUX_APU_USE_DSP`), both off by default, for measurement. The actual
   candidate fix ("switch v2", `HAKUX_APU_MONVP_DOWNMIX=1`) is a patch file
   under `docs/lanes/audio1016/`, not applied to the build. Nothing changes
   for a player here, so nothing went in the notes, despite the brief
   listing it as a candidate — brief point: "if a candidate cannot be
   confirmed from a commit or file, leave it out."
7. **X1 BOX fixes.** Confirmed: `x1port1012` (3c2338eb2b). Used that
   commit's own `Release note (stability):` line verbatim (trimmed for
   voice): bad voice data skipped instead of aborting, out-of-VRAM texture
   draws blank, ADPCM step clamped, corrupt pipeline cache discarded and
   rebuilt, missing audio device not fatal, setup wizard BIOS-size check.
8. **Halo — omitted entirely**, per the brief. Checked `KNOWN_ISSUES.md`:
   it does not list a Halo rendering fault, so per the brief's instruction
   ("write that sentence only if KNOWN_ISSUES.md already lists the Halo
   fault, otherwise omit it") nothing is said about Halo or
   `HAKUX_FIST_ROUND` anywhere in the release docs.
9. **GitHub Sponsors — not a release-note line.** It's already in
   README.md's top row and "Support the project" section (`funding1016`,
   567431a77f), which this lane left untouched (no change needed there);
   not repeated in CHANGELOG.md or v0.5.1.md since the brief treats it as a
   repo feature, not a release note.
10. **Playable count.** README.md carries no digit (it links to the list);
    `docs/COMPATIBILITY.md` carries "72 Playable · 15 run below 30 fps ·
    11 not playable". The two do not disagree (README states none to
    disagree with), so no NEED. Not recomputed, not changed, not repeated
    as a 0.5.1 highlight since nothing in this release's change list
    affects a rating.
11. **Top Spin / #992 — not mentioned anywhere**, per the brief. Checked:
    no file this lane touched names Top Spin, and `fps1015`
    (fbafbac000, "measured causes for the owner's FPS defects") is not
    cited or claimed as fixed.

## versionName — not set in this lane

The brief's point 2 says "Set versionName to 0.5.1 wherever the build sets
it ... if versionName is derived elsewhere, say where." Read
`android/app/build.gradle.kts`:

```
versionName = versionedRelease ?: stampedVersionName()
```

`versionedRelease` is an unset-by-default Gradle property
(`-PversionedRelease=0.5.1`), passed only by `docs/testing/release_build.sh`
at build time — there is no literal `0.5.1` to write into this file for the
real release build. The only literal version string in this file is the
fallback inside `stampedVersionName()`'s catch branch, `"0.5.0-unknown"`,
used only if `version_stamp.sh` fails to run; `docs_freshness.py`'s own
comment says this literal is "kept in sync by hand" with
`version_stamp.sh`'s `BASE_VERSION="0.5.0"`. Both are nightly/dev-build
fallbacks, not the release version, and `docs/testing/version_stamp.sh` is
outside this lane's territory, so bumping one without the other would
desync them. Left both at `0.5.0` — this lane changed the one line the
brief named (the release variant's `app_name`) and nothing else in
`build.gradle.kts`. `docs_freshness.py --release 0.5.1` and the no-flag run
(which reads that same fallback literal, currently 0.5.0) both pass — see
below.

## Checks run

```
$ python3 docs/testing/docs_freshness.py --release 0.5.1
... 11 OK, 0 not
$ python3 docs/testing/docs_freshness.py
... 11 OK, 0 not
```

Both clean. No device work, no Gradle build, no NDK — docs-only except the
one `app_name` line, which the fold's device-run gate should cover (noted
in PR.md).

## What this lane did NOT touch, and why

- `docs/frontends/**`, `docs/lanes/**` of other lanes, `android/RELEASING.md`,
  `android/key.properties*`, `docs/testing/version_stamp.sh`,
  `docs/testing/release_build.sh` — all out of territory.
- `docs/COMPATIBILITY.md`'s title table — no new titles tested by this
  lane; only its date/version line changed.
- `ROADMAP.md`'s "0.5.0 measured 175 games and rated 52 Playable" line —
  left as is; it is a historical statement about what 0.5.0 did, not a
  current-state claim this release makes stale.
