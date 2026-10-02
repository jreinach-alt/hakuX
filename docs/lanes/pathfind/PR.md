# pathfind: a screen-reading agent that drives a title from boot into gameplay

State: draft

Lane: pathfind            Issue: #433
Base: master @ 66bce0c222
Files: docs/lanes/pathfind/PR.md, docs/lanes/pathfind/NOTES.md, docs/lanes/pathfind/OUTBOX.md, docs/testing/titles/pathfind.py, docs/testing/titles/pathfind_selftest.py
Prediction: none: no arm (tooling; no emulator code)
Needs device: yes (held, direct driving)    Needs NDK: no

Work in progress: pathfind.py loops screencap -> model decision (claude CLI) -> pad.sh input,
with a rule-5 gameplay confirmation and per-title recorded paths.

Release note (none): test tooling only.
