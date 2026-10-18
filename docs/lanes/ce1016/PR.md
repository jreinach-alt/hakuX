# ce1016: display name becomes hakuX CE (Community Edition) -- docs pass

State: ready

Lane: ce1016            Issue: #433
Base: master @ 2636e89f4a
Files: README.md, PRIVACY.md, ROADMAP.md, android/MIGRATING.md, docs/frontends/README.md, docs/frontends/stock-launcher.md, docs/es-de/README.md, docs/es-de/es_systems.xml, docs/lanes/ce1016/PR.md, docs/lanes/ce1016/NOTES.md
Prediction: none: analysis-only
Needs device: no    Needs NDK: no

Docs-only rename pass per the owner's 10-16 decision: the display name
"hakuX (fork)" becomes "hakuX CE" (CE for Community Edition). Only places
where the app's name is shown as a *name* (H1 titles, bold product-name
callouts, the ES-DE menu label, and the few sentences that describe the app
by name) change; the plain word "hakuX" naming the emulator/upstream/
project, and identifiers (package ids, the ES-DE `%EMULATOR_HAKUX-FORK%`
variable and `<emulator name="HAKUX-FORK">` block, branch/file names) are
untouched. README.md also picks up the 0.5.1 minSdk-33 requirement text
("Android 10 or newer" -> "Android 13 or newer", matching sign1016
`56bb989b0c`) and today's `_Last updated_` date; version stays 0.5.0.

`docs_freshness.py` still reports 11 OK / 0 not OK. `home_page.py`'s four
README-rewrite regexes and the `## Credits` anchor still match exactly once
(checked by script, since the tool has no `--check` flag). All relative
links in the changed files resolve.

Two items are out of this lane's territory and are called out in NOTES.md
for lane.xbox's 0.5.1 release commit: `CHANGELOG.md` and the app label in
`android/app/build.gradle.kts` (~line 167). `android/README.md`'s own
"Android 10" requirement text is also out of territory and now disagrees
with README.md's "Android 13" until someone updates it.

See docs/lanes/ce1016/NOTES.md for the full file-by-file list, what was
deliberately left unchanged and why, and the remaining `fork` hits with
their reasons.

Release note (other): none -- docs only, no emulator/app code touched.
