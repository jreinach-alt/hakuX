# alwaystelemetry: measure the perflog overhead, inventory the telemetry, design the always-on tier (#433)

State: draft

Lane: alwaystelemetry        Issue: #433
Base: master @ 6c828f9860
Files: docs/lanes/alwaystelemetry/NOTES.md, docs/lanes/alwaystelemetry/PR.md, docs/lanes/alwaystelemetry/OUTBOX.md, docs/lanes/alwaystelemetry/WAITING
Prediction: none: measurement and design only, no pixel-moving change (the pre-registered rate prediction is in NOTES.md)
Needs device: yes
Needs NDK: no

Release note (none): instrumentation only, no player-visible change.

Part 1 of the brief. This PR carries the notes and the outbox only; no emulator code changes.

Status: waiting on the ToeJam perflog A/B (overnight queue rows alwaystelemetry-toejam-plain and -perflog). WAITING is `time 2026-10-03T14:00`; the overhead numbers follow in OUTBOX.md.
