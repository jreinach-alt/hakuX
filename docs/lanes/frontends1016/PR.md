# Wire hakuX into four launchers (ES-DE, Daijisho, Pegasus, stock), tested on the Thor

State: draft

Lane: frontends1016            Issue: #433
Base: master @ 15a72e10dc
Files: docs/frontends/README.md, docs/frontends/es-de.md, docs/frontends/daijisho.md, docs/frontends/pegasus.md, docs/frontends/stock-launcher.md, docs/frontends/images/*, docs/es-de/README.md, docs/es-de/es_find_rules.xml, docs/es-de/es_systems.xml, docs/lanes/frontends1016/NOTES.md, docs/lanes/frontends1016/PR.md
Prediction: none: analysis-only + on-device verification, no pixel/perf claim
Needs device: yes (Thor, bdc158a5, by hand -- no dispatcher)    Needs NDK: no

Release note (performance|stability|rendering|other|none): none

## In progress

Starting work: reading how LauncherActivity resolves a launch (intent.data,
content:// vs file://, `rom_path` extra), then wiring and testing each of the
four frontends against the Thor by hand. Will update this PR.md as each
frontend is verified.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
