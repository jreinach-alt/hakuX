# release052 — the 0.5.2 release commit (#433)

Docs-only lane. No device work, no Gradle build, no NDK. Every player-visible
claim below cites a commit or file written by an earlier lane; this lane only
decides what belongs in the release docs and bumps dates/versions. Started
after `fold: lane/defaulton1017` landed on `origin/master` (c3660fdd86, its
own commit message carries defaulton1017's PR.md verbatim).

## Claims in the release notes, and their source

1. **The one player-visible change: Halo: Combat Evolved's opening cinematic
   runs faster.** Source: `docs/lanes/defaulton1017/PR.md` (folded into
   c3660fdd86's commit message) and `docs/lanes/halo1016/PR.md` +
   `docs/lanes/halo1016/NOTES.md`. Measured on the Retroid Pocket Nova, over
   the opening cinematic's span: 17.0 fps (58.9 ms/f) with S2T_CVT,
   REPORT_EARLY and FLDCW_CHAIN all off (row HOFF), 28.6 fps (35.0 ms/f) with
   them on and IBC off, which is what ships (row HNI). The verbatim release
   note line from defaulton1017's PR.md: "Halo: Combat Evolved's opening
   cinematic runs at about 29 fps through the hangar briefing (was 17 fps)".
   Carried into CHANGELOG.md's v0.5.2 paragraph and docs/releases/v0.5.2.md.
2. **The three switches and their mechanism, in plain language.** Source:
   defaulton1017/NOTES.md "Verdict per switch" table and halo1016/PR.md's
   root-cause table: a slower texture path for 2-byte-colour surfaces
   (S2T_CVT), the game waiting on the GPU to confirm each occlusion/visibility
   test before moving on, answered early instead (REPORT_EARLY), and the CPU
   translator recompiling around the FLDCW instruction more than it needs to
   (FLDCW_CHAIN). `HAKUX_IBC` stays off (HIBC MISS, +0.43 ms/f, under the 0.5
   bar). I did not name the env vars or switch IDs in the public docs — only
   in this NOTES.md — since the public docs describe behaviour, not flags.
3. **REPORT_EARLY's one honest caveat.** Source: defaulton1017/NOTES.md
   "HVIS HIT (0.0055)": one early answer in 180 shows an object visible where
   its own test would have hidden it, or the reverse, for one frame; the lane
   did not look at frames for it. Stated in one sentence in both
   CHANGELOG.md's paragraph and docs/releases/v0.5.2.md ("a visual effect ...
   can show a frame late at a camera cut"). Not claimed as fixed
   or investigated further, per the brief.
4. **KNOWN_ISSUES.md's #1018 entry, reworded, not closed.** Source: the same
   PR's "What ships" line: HNI 35.0 ms/f (28.6 fps) against HOFF's 58.9
   (17.0 fps), and the 10-second windows 33.4-38.2 ms/f (about 30 to 26 fps).
   Reworded to "can still dip under 30 fps... some stretches still run as low
   as about 26 fps" (1000/38.2 ≈ 26.2). Not called fixed. #938 (quiet cutscene
   speech) and #939 (menu ring) entries are untouched, per the brief — left
   exactly as release051b wrote them, even though their "aimed at 0.5.2" text
   is now slightly stale (this lane does not touch those two lines; it is not
   this lane's call to make).
5. **"Other titles" (REPORT_EARLY acting in Simpsons Hit & Run and
   RalliSport Challenge; declined by design in Conker and Amped 2).** Read
   in defaulton1017/NOTES.md's "Title rows" and verdict table. Left out of
   every public doc: the brief permits mentioning it but does not require it,
   and none of it is a frame-rate claim a player would act on, so leaving it
   out avoids any risk of it being misread as one.
6. **Top Spin, MKSM, Batman, Prince of Persia, Halo 2 — not mentioned
   anywhere.** Checked: no file this lane touched names any of them, and
   defaulton1017's Top Spin isolation (dropped A presses, ruled out of scope
   by the owner at 07:00 10-17) is not cited or implied as fixed or broken by
   this release.
7. **Playable count unchanged.** README.md carries no digit (links to the
   list); docs/COMPATIBILITY.md still carries "72 Playable · 15 run below
   30 fps · 11 not playable", same as 0.5.1. The two do not disagree, so no
   NEED. Not recomputed: nothing in defaulton1017's diff touched a rating,
   and the Halo compatibility row is explicitly out of scope (brief).
8. **Halo's compatibility row untouched.** docs/COMPATIBILITY.md's title
   table is unchanged; only its date/version line was bumped.
9. **Signing, minSdk 33, app name — unchanged from 0.5.1.** Not re-verified
   by this lane (no device work, `android/key.properties` / `~/keystores/`
   off limits); stated as unchanged in docs/releases/v0.5.2.md's lead
   paragraph because nothing in this release touches
   `android/app/build.gradle.kts`, `android/key.properties`, or the resValue
   lines `release051`/`ce1016` set. `adb install -r` in-place-update wording
   follows the same pattern release051/NOTES.md used for 0.5.1.

## versionName — not touched

Same situation as release051/NOTES.md documented for 0.5.1:
`versionName = versionedRelease ?: stampedVersionName()` in
`android/app/build.gradle.kts` has no literal `0.5.2` to write; the real
release build gets it from `release_build.sh 0.5.2-rc1` at build time
(lane.local's job, per the brief, not this lane's). The fallback literal
(`"0.5.0-unknown"`, inside `stampedVersionName()`'s catch branch) is
untouched, same as 0.5.1 left it. `docs_freshness.py --release 0.5.2` and the
no-flag run both pass against that fallback (0.5.0 < 0.5.2).

## Checks run

```
$ python3 docs/testing/docs_freshness.py --release 0.5.2
... 11 OK, 0 not
$ python3 docs/testing/docs_freshness.py
... 11 OK, 0 not
```

Both clean.

## What this lane did NOT touch, and why

- `android/app/build.gradle.kts` — out of territory; the brief is explicit
  that the version comes from `release_build.sh 0.5.2-rc1`, not this file.
- `android/RELEASING.md`, `android/key.properties*`, `~/keystores/**`,
  `docs/testing/version_stamp.sh`, `docs/testing/release_build.sh` — out of
  territory / off limits.
- `docs/frontends/**` — not in this lane's territory list.
- `ROADMAP.md`'s "0.5.0 measured 175 games and rated 52 Playable" line, and
  KNOWN_ISSUES.md's "0.5.1 fixes the ring jumping back in bursts" line — left
  as is, same reasoning release051/NOTES.md gave: historical statements about
  what an earlier release did, not current-state claims this release makes
  stale.
- KNOWN_ISSUES.md's #938 and #939 entries — left exactly as written, per the
  brief ("keep #938 and #939 as they are").
- No tag, no APK build, no publish — lane.local's job after the fold, per the
  brief.

## Left out, and why

- No mention of Top Spin (#992), MKSM, Batman Begins, Prince of Persia, or
  Halo 2 anywhere in the release docs — the brief's explicit exclusion list.
- No "improved performance" claim for any title but Halo — the brief's
  explicit instruction; defaulton1017's screen only measured a frame-rate
  change for Halo.
- No mention of the dispatcher, lanes, predictions, or screens in any public
  doc.
