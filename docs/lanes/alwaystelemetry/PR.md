# alwaystelemetry: measure the perflog overhead, inventory the telemetry, design the always-on tier (#433)

State: draft

Lane: alwaystelemetry        Issue: #433
Base: master @ 5426f4d874
Files: docs/lanes/alwaystelemetry/NOTES.md, docs/lanes/alwaystelemetry/PR.md, docs/lanes/alwaystelemetry/OUTBOX.md, docs/lanes/alwaystelemetry/WAITING
Prediction: none: measurement and design only, no pixel-moving change (the pre-registered rate prediction is in NOTES.md)
Needs device: yes
Needs NDK: no

Release note (none): instrumentation only, no player-visible change.

Part 1 of the brief. This PR carries the notes and the outbox only; no emulator code changes.

Status: blocked on lane.local's choice of ToeJam golden/route state. Overnight queue rows `alwaystelemetry-toejam-r3-plain` and `-r3-perflog` (ref a971c31220, GPL=0) were refused at 16:04 PDT: the route says `returning`, but golden 71a91de8b905 has no save directory (NOTES.md, attempt 3). No run id yet. The overhead numbers follow in OUTBOX.md once a run exists.

Base is now master @ 5426f4d874 (merged into the branch at 16:02 PDT as a971c31220). The earlier registered ref 6c828f9860 is an ancestor and is no longer the measured ref.
