# relnotes1017: release notes carry only features and bug fixes (#433)

State: ready

Lane: relnotes1017          Issue: #433
Base: master @ 160728983a
Files: CHANGELOG.md, docs/releases/README.md, docs/releases/v0.5.1.md, docs/releases/v0.5.2.md, docs/lanes/relnotes1017/NOTES.md, docs/lanes/relnotes1017/PR.md, docs/lanes/relnotes1017/OUTBOX.md
Prediction: none: analysis-only
Needs device: no    Needs NDK: no

Per the owner's 2026-10-17 rule: a release note says what is NEW or what is FIXED, in
the user's words, and nothing else. Stripped internal process/compatibility notes out
of the two most recent release notes and their CHANGELOG/README summaries, without
touching any fix claim, number or issue link.

`docs/releases/v0.5.1.md`: removed the "Three things to know before installing" block
(signing-key rotation, Android 13 minimum, rename-as-install-advice), the "Launching
from a frontend, confirmed on a real device" bullet (a test result, not a change), the
"Carried over from X1 BOX" provenance line (its five fix bullets stay, under Fixed), and
the "Reporting a bug" / "Known residuals" sections. Kept New = new app icon + "the app is
now named hakuX CE" as a plain line, Fixed = Halo's menu ring + the five fixes. Opening
line now reads "A new icon and a handful of stability fixes."

`CHANGELOG.md` `## v0.5.1`: same cuts (icon, name, Halo's menu ring, the five fixes;
dropped key rotation, minimum Android, frontend confirmations). Kept the
`See [docs/releases/v0.5.1.md]` line.

`docs/releases/v0.5.2.md`: dropped the signing/Android 13/app-name/`adb install -r`
sentence and the "Reporting a bug" / "Known residuals" sections. Kept the Halo Fixed
bullet exactly as written (frame-late caveat, "still under 30 fps" sentence, #1018
link). `CHANGELOG.md` `## v0.5.2` was already fix-only; untouched.

`docs/releases/README.md`: shortened the 0.5.1 highlights cell to drop signing/minSdk/
frontend mentions, keeping rename + icon + the Halo fix. 0.5.2's row was already
fix-only; untouched.

Did not touch KNOWN_ISSUES.md, README.md, COMPATIBILITY.md, android/RELEASING.md or any
other doc -- the signing and minSdk facts stay documented where they already live.

Checks: `python3 docs/testing/docs_freshness.py` reports `public docs: 11 OK, 0 not`
(unchanged). `git diff --stat origin/master...HEAD` touches only the four files above
plus this lane's own `docs/lanes/relnotes1017/**`.

Attempt 1 was stopped externally 48s in, before Checks or these lane docs; its edits
(all four files) were already complete and correct, so hostops (jam duty, 09:32 PDT)
committed+pushed them as-is (`6978ebb405`). This session verified them against the
brief, ran Checks, and wrote the lane docs -- no edit was redone. Details in NOTES.md.

Release note (performance): none.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
