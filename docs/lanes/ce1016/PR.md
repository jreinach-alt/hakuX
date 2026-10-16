# ce1016: display name becomes hakuX CE (Community Edition) -- docs pass

State: draft

Lane: ce1016            Issue: #433
Base: master @ 2636e89f4a
Files: README.md, PRIVACY.md, ROADMAP.md, android/MIGRATING.md, docs/frontends/README.md, docs/frontends/stock-launcher.md, docs/es-de/README.md, docs/es-de/es_systems.xml, docs/es-de/es_find_rules.xml, docs/lanes/ce1016/PR.md, docs/lanes/ce1016/NOTES.md
Prediction: none: analysis-only
Needs device: no    Needs NDK: no

Docs-only rename pass per the owner's 10-16 decision: the display name
"hakuX (fork)" becomes "hakuX CE" (CE for Community Edition). Only places
where the app's name is shown as a *name* (H1 titles, bold product-name
callouts, the ES-DE menu label) change; the plain word "hakuX" naming the
emulator/upstream/project, and identifiers (package ids, ES-DE
`%EMULATOR_HAKUX-FORK%` variable, branch/file names) are untouched.

In progress -- see docs/lanes/ce1016/NOTES.md for the worklist and what was
deliberately left alone.
