# relnotes1017 -- release notes carry only features and bug fixes (#433)

## Attempt 1 (stopped externally, 48s in)
Did the four edits under "What to change" and was stopped before running Checks or
writing NOTES.md/PR.md/OUTBOX.md. Per the brief's addendum, hostops (jam duty, 09:32 PDT)
judged the edits complete and correct and committed+pushed them as-is to
`origin/lane/relnotes1017` (`6978ebb405`) rather than discard real work.

## Attempt 2 (this session)
Picked up from "## Checks" per the addendum -- did not redo any edit. Verified the
existing commit, ran the freshness check, and wrote this file, OUTBOX.md and PR.md.

## Edits already on `6978ebb405` (verified this session, not re-done)

### docs/releases/v0.5.1.md
- Removed the "Three things to know before installing" block: signing-key rotation,
  the Android 13 minimum, and the rename-as-install-advice paragraph. All three are
  process/compatibility notes, not a feature or a fix -- the owner's rule excludes them.
- Removed "Launching from a frontend, confirmed on a real device." It reports a test
  result (what was confirmed to still work), not something new or fixed.
- Removed the "Carried over from X1 BOX, the project this one is ported from:" line.
  It's provenance commentary; the five bug-fix bullets under it stay (they are fixes).
- Removed "Reporting a bug" and "Known residuals" sections -- process/support pointers,
  not release content.
- Kept: New = new app icon + "the app is now named hakuX CE" as one plain line with no
  install advice. Fixed = Halo's menu ring + the five carried-over fixes, now directly
  under Fixed with no provenance preamble.
- Rewrote the opening line to "A new icon and a handful of stability fixes." (was "A
  signing, naming and launcher-compatibility release...").

### CHANGELOG.md (`## v0.5.1`)
- Same cuts as the release note: dropped the signing-key-rotation sentence, the Android
  13 minimum sentence, and the frontend-confirmation sentence.
- Kept: app renamed hakuX CE + new icon, Halo's menu ring fix, and the five carried-over
  fixes (reworded "Also fixed:" to replace the dropped "Carried over from X1 BOX:" lead-in,
  since that lead-in was itself provenance, not a fix description).
- Kept the `See [docs/releases/v0.5.1.md]` line unchanged.

### docs/releases/v0.5.2.md
- Removed the sentence "Signing, the Android 13 minimum and the app name are unchanged
  from 0.5.1: `adb install -r` installs this build in place..." -- compatibility/install
  advice, not a feature or fix.
- Removed "Reporting a bug" and "Known residuals" sections, same reasoning as v0.5.1.
- Kept the Halo Fixed bullet exactly as written, including the frame-late caveat, the
  "still under 30 fps" sentence, and the #1018 link -- the brief said keep it exactly.
- `CHANGELOG.md`'s `## v0.5.2` entry was already fix-only; left untouched.

### docs/releases/README.md
- Shortened the 0.5.1 highlights cell from "Signing key rotated (in-place update over
  0.5.0), Android 13 minimum, renamed hakuX CE, new icon, launcher compatibility
  confirmed" to "Renamed hakuX CE, new icon, Halo's menu ring fixed" -- drops the
  signing/minSdk/frontend mentions, keeps the feature/fix content, and adds the Halo fix
  since that's the release's other real content.
- 0.5.2's row already read as fix-only (Halo cinematic fps); left untouched.

## Not touched
KNOWN_ISSUES.md, README.md, COMPATIBILITY.md, android/RELEASING.md and every other doc
are untouched, per the brief -- signing and minSdk facts stay documented where they
already live. No fix claim, number or issue link was changed; this lane only deleted or
shortened existing text.

## Checks
- `python3 docs/testing/docs_freshness.py` (no flag): `public docs: 11 OK, 0 not` --
  every public doc still reports OK after the cuts. Nothing needed fixing to satisfy it.
- `git diff --stat origin/master...HEAD`: exactly `CHANGELOG.md`, `docs/releases/README.md`,
  `docs/releases/v0.5.1.md`, `docs/releases/v0.5.2.md` (plus this lane's own
  `docs/lanes/relnotes1017/**`, added this session). No other file touched.
