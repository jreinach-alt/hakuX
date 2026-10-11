# lane.gtaroutes1011: routes into play for GTA III, Vice City, and a San Andreas driving route (#433, 0.5)

Dispatched directly by lane.local (#433 umbrella). Base `6d8947bb47`. Device: Nova only.

## 0. Base and the shape of gta-sa.route

`git merge origin/master` was already up to date at session start (6d8947bb47).

`gta-sa.route` (read in full): a header comment names the device, the session that played it, and the on-screen
beats in order; `wait`/`press`/`axis`/`shot` lines get to the first in-control frame; a train of 4x `press A 300`
spaced 5 s apart (times three, once per cutscene) skips cutscenes regardless of how long each one's preceding load
screen ran, because an A that lands on a load screen is a no-op; `mark gameplay` fixes the scoring start; then
`repeat forever { ... }` drives LY/LX/RX without ever touching Y, START or BACK. GTA III and Vice City routes follow
this shape: same boot structure (FMV skips, menu, cutscene-skip train, mark, movement loop), adjusted for each
game's own menu/cutscene beats.

## 1. Nova contention at session start

Checked `$DISPATCH_DIR/{queue,running}` before taking any hold, per the brief's rule not to hold the Nova while a
lane.local `gtasa1011`/`gtasagpu1011` request is queued or running:

- `running/`: `1-1791733231-lane.local-3377611` (gtasa1011 B, NFS switches, 850 s) -- already has a matching
  `results/` directory from 09:52 PDT, but `running/*.owner` still named it as of 09:53 PDT.
- `queue/`: 4 more lane.local items on `nova` -- 2x `gtasagpu1011` step 1 (600 s each), 1x `gtasagpu1011` step 2
  (320 s), 2x `nfsdefault1011` A/B (500 s each) -- about 2520 s (42 min) of further nova time after whatever is
  currently claimed.

So the Nova will not be free "about 10:15 PDT" as the brief estimated; it is still working a backlog as of 09:53.
Held off taking a hold and did prep work instead (this file, PR, route-shape notes) while polling.
