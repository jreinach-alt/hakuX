# routefix1002: three route checks for the overnight Nova queue (#433)

State: draft

Lane: routefix1002           Issue: #433
Base: origin/lane/titleroutes2 (merged with origin/master, 2026-10-03)
Files: docs/lanes/routefix1002/**, docs/testing/titles/routes/gunvalkyrie.route
Prediction: none: analysis-only (route and queue data; no pixels claimed)
Needs device: no (lane.local's runner queues the one line in queue.tsv)

Release note (none): route data and queue only.

## What changed
- `gunvalkyrie.route`: `# state: first-run`; play loop is v5 (forward held, 0.8 s back-off, unequal 1.5 s / 0.5 s turns, double LT boost, A every ~2.5 s). Written from replays 1-4 (NOTES.md has the table).
- `docs/lanes/routefix1002/queue.tsv`: one line, Gunvalkyrie v5 at 840 s, ref = the commit that carries v5.
- Buffy and Halo CE are not queued; NOTES.md has the evidence and the next candidates scored by P x win.

## Checks run
- `bash docs/testing/titles/route.sh --check docs/testing/titles/routes/gunvalkyrie.route`: route ok (116 lines), exit 0.
- Halo CE golden `90ebd6a27bd1`: savegame.bin has 0 nonzero bytes of 3,670,016; not past training, not queued.
- `queue.tsv`: 9 tab-separated fields.
- No emulator code changed; selftest not required (no harness files).
- No `preflight.sh` in this repo; the offline checks above are the local equivalents.

## Next
Gunvalkyrie v5's 840-s result decides: a whole-window play run confirms it; a pin on one wall makes a screen-triggered back-off the next build (NOTES.md, candidate 2). Buffy: the Options probe (about 70 s held) first. Halo: a held run past training, then a returning route.
