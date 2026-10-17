# release052: the 0.5.2 release commit (#433)

State: ready

Lane: release052            Issue: #433
Base: master @ c3660fdd86 (defaulton1017's fold, merged)
Files: CHANGELOG.md, docs/releases/v0.5.2.md, docs/releases/README.md, README.md, KNOWN_ISSUES.md, docs/COMPATIBILITY.md, android/README.md, android/MIGRATING.md, ROADMAP.md, CONTRIBUTING.md, PRIVACY.md, docs/reporting-bugs.md, docs/es-de/README.md, docs/lanes/release052/PR.md, docs/lanes/release052/NOTES.md
Prediction: none: docs-only
Needs device: no    Needs NDK: no

Release note (performance): Halo: Combat Evolved's opening cinematic runs at about 29 fps through the hangar briefing (was 17 fps)

CHANGELOG entry, docs/releases/v0.5.2.md, docs/releases/README.md's new row, and a freshness pass
over every doc in docs/testing/public_docs.txt (date bumped to 2026-10-17, version to 0.5.2;
`docs_freshness.py --release 0.5.2` and the no-flag run both pass, 11 OK / 0 not). The one
player-visible change is Halo: Combat Evolved's opening cinematic, lifted from 17 fps to about
29 fps through the hangar briefing on the Retroid Pocket Nova (defaulton1017's fold, folded into
master @ c3660fdd86). KNOWN_ISSUES.md's #1018 entry is reworded to say so honestly — it is not
closed, some stretches still run under 30 fps — without calling it fixed; #938 and #939 are left
untouched. Signing, the Android 13 minimum and the app name are stated as unchanged from 0.5.1 in
docs/releases/v0.5.2.md (not re-verified here: no device work, `android/key.properties` and
`~/keystores/` are off limits). Top Spin, MKSM, Batman Begins, Prince of Persia and Halo 2 are not
mentioned anywhere, and no frame-rate claim is made for any title but Halo. Every claim traces to a
specific commit or file; see docs/lanes/release052/NOTES.md for the full source list.

Not touched: `android/app/build.gradle.kts` (the version comes from `release_build.sh 0.5.2-rc1`,
lane.local's job after the fold, not this lane's); `docs/COMPATIBILITY.md`'s title table and
Playable count (72 Playable · 15 below 30 fps · 11 not playable, unchanged — only its date/version
line moved); no tag, no APK build, no publish.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
