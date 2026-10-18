# drive: local tools only, act-observe instead of wait-and-fail, learn what to press

State: draft

Lane: localdrive1018            Issue: #433 (0.5)
Base: master @ e34f8ffa77
Files: docs/testing/titles/drive.py, docs/testing/titles/classify.py, docs/testing/titles/pathclass.py,
docs/testing/titles/classify_selftest.py, docs/testing/titles/pathclass_selftest.py,
docs/testing/titles/drive-profiles/generic.toml, docs/testing/titles/drive-profiles/gta3.toml,
docs/testing/titles/routes/gta3-drive.route, docs/testing/titles/pathknow/learned/**,
docs/testing/jobs/models.toml, docs/lanes/localdrive1018/**
Prediction: none: analysis-only so far (no device arm; Nova/Thor out per brief)
Needs device: no (this lane; the GTA III proof run is lane.local's, by hand, on the Thor)
Needs NDK: no

Owner (2026-10-18 ~13:50 PDT): the classifier was supposed to run on local tools with no API calls; it
doesn't, drive.py falls back to Haiku 4.5 on any `unknown` screen and fails the route when no key is set
(8 of 10 gen-* routes voided overnight 10-18 this way, memory `gen-routes-die-without-a-model-key`).
Fix: remove the key path entirely, replace idle-on-unknown with an act-observe ladder, add a learned
table so repeated screens get smarter, and fix GTA III's opening cutscene being scored `gameplay` at
0.716 as the proof.

Still in Step 0 / early implementation; this PR will carry the real numbers (reach-play fraction,
second-pass learned-table hit rate, held-out false-gameplay) once A+B+C land. See
docs/lanes/localdrive1018/NOTES.md for the Already-tried table and plan.
