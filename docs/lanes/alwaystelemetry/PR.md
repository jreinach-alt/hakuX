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

Status: waiting on the ToeJam perflog A/B (overnight queue rows alwaystelemetry-toejam-plain and -perflog). Not yet submitted to dispatch (the Nova is held by lane.pathfind since 14:00 PDT); WAITING is `time 2026-10-03T16:00`. The overhead numbers follow in OUTBOX.md.

Base is now master @ 638a3f478c (merged into the branch at 14:06 PDT); the registered ref 6c828f9860 is an ancestor of it.
