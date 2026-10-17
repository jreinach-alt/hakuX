# drivernotice1017: every release note names the one tested GPU driver (#433)

State: ready

Lane: drivernotice1017          Issue: #433
Base: master @ 5c4c24956e
Files: docs/gpu-driver.md, docs/testing/public_docs.txt, README.md, CHANGELOG.md, docs/COMPATIBILITY.md, docs/releases/README.md, docs/releases/v0.4.0-j1.md, docs/releases/v0.4.1-j1.md, docs/releases/v0.5.0.md, docs/releases/v0.5.1.md, docs/releases/v0.5.2.md, android/RELEASING.md, docs/testing/release_build.sh, docs/testing/release_build_selftest.sh, docs/testing/docs_freshness.py, docs/testing/docs_freshness_selftest.py, docs/testing/nightly_build.sh, docs/testing/jobs/selftest.d/86-nightly-notes.sh, docs/lanes/drivernotice1017/NOTES.md, docs/lanes/drivernotice1017/PR.md, docs/lanes/drivernotice1017/OUTBOX.md
Prediction: none: analysis-only
Needs device: no    Needs NDK: no
Selftest: 55-localtime 86-nightly-notes 86-release-build 87-nightly-trunk 88-nightly-sign 99-release-note-line -- the change edits nightly_build.sh (one echo line), release_build.sh and docs_freshness.py; these six fragments are the ones that run or read those scripts. docs_freshness_selftest.py is not a fragment and was run by the lane (green).

Per the owner's 2026-10-17 instruction: hakuX is tested only with the Turnip Adreno Driver
T30 (@Mr_Purple_666), and every release note links a page that says so.

New public page `docs/gpu-driver.md`: which driver, that the phone's own driver and other
Turnip builds are untested and draw some games wrongly, that a new install has no driver
until one is installed, how to install it (Settings > Graphics > GPU Driver), and how to
see in the log that it loaded. It has no download link yet; that is an open item for the
owner.

A one-paragraph notice linking it is added to every release note (v0.4.0-j1 through
v0.5.2), the CHANGELOG, the releases index, README and COMPATIBILITY.

This is the owner's explicit exception to the relnotes1017 rule that release notes carry
only features and bug fixes. It is one short paragraph per note and nothing else from that
rule is relaxed.

Kept in place for later releases: `release_build.sh` refuses a plain X.Y.Z build (exit 10)
whose release note is missing or does not link `docs/gpu-driver.md`; `docs_freshness.py`
reports `NO-DRIVER-LINK` for any release note without it; `android/RELEASING.md` lists it
under "Before tagging"; the nightly body carries the same notice.

Checks: `release_build_selftest.sh` green, and its three new cases fail against master's
`release_build.sh`; `docs_freshness_selftest.py` green; `docs_freshness.py --release 0.5.2`
reports 12 public docs OK and 5 of 5 release notes linking the page;
the selftest fragments that read the changed scripts (86-nightly-notes, 87, 86-release-build,
88, 99) pass, 139 checks, in a partial run; details in NOTES.md.

Release note (performance): none.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01QjK9KDoS6St9aU1269xDrG
