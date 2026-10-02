# pathclass: a local GPU screen-state classifier for pathfind (#433)

State: draft

Lane: pathclass              Issue: #433 (0.5: 50 Playable)
Base: master @ 66bce0c222
Files: docs/lanes/pathclass/PR.md, docs/lanes/pathclass/NOTES.md, docs/lanes/pathclass/OUTBOX.md, docs/testing/titles/pathclass.py, docs/testing/titles/pathclass_selftest.py
Prediction: none: no arm. Host-side test tooling only; no emulator code, no device.
Needs device: no    Needs NDK: no

Release note (none): test harness only -- no emulator code changes.

Work in progress: a local screen-state classifier (CLIP/SigLIP + trained head, OCR menu reader) with the
interface pathfind will call.
