# routefix1002: three route checks for the overnight Nova queue (#433)

State: draft

Lane: routefix1002           Issue: #433
Base: origin/lane/titleroutes2 (merged with origin/master)
Files: docs/lanes/routefix1002/**, docs/testing/titles/routes/gunvalkyrie.route
Prediction: none: analysis-only (route and queue data; no pixels claimed)
Needs device: no (lane.local's runner queues the one line in queue.tsv)

Release note (none): route data and queue only.

## What changed
- `gunvalkyrie.route`: gains `# state: first-run`. Loop unchanged (replay 2's, `685c52e514`).
- `docs/lanes/routefix1002/queue.tsv`: one line, Gunvalkyrie at 840 s.
- Buffy and Halo CE are not queued; NOTES.md has the evidence and the next candidates scored by P x win.

## Checks run
- Route file: the `# state:` line is the first line; no other content changed.
- `queue.tsv`: 9 tab-separated fields, verified by reading back.
- No emulator code changed; selftest not required (no harness files).

## Next
Buffy: the Options probe (about 70 s held) first, to read the controller map. Halo: a held run past training, then a returning route. Gunvalkyrie's 840-s result decides whether a drive.py loop is needed.
