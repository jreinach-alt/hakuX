# gtaroutes1011: routes into play for GTA III, Vice City, and a San Andreas driving route (#433, 0.5)

State: draft

Lane: gtaroutes1011        Issue: none (#433 umbrella)
Base: master @ dba7ca0649
Files: docs/lanes/gtaroutes1011/NOTES.md, docs/lanes/gtaroutes1011/PR.md, docs/testing/titles/routes/gta-3.route,
docs/testing/titles/routes/gta-vc.route, docs/testing/titles/routes/gta-sa-drive.route,
docs/testing/titles/targets.toml, docs/testing/titles/pathknow/paths/5454000E.json,
docs/testing/titles/pathknow/paths/5454000F.json, docs/testing/titles/pathknow/hints/learned-pub-5454.md,
docs/testing/titles/pathknow/hints/learned-series-grand-theft-auto.md (the last two are `pathfind.py`'s own
side-effect files, not in the territory list, but every prior pathfind-running lane has committed them the same
way -- checked via git history before including them)
Prediction: none: route data (inputs) and notes, no emulator code; route checks are --no-expect dispatch runs
Needs device: yes (Nova only, via request.sh/pathfind.py; no direct hold held across more than one title)

## Results so far

| Title | Route | Golden | Proof result id | gameplay_s | fps_ok | frames showing movement |
|---|---|---|---|---|---|---|
| GTA III (5454000E) | gta-3 | 9153c63300da | `1-1791747431-gtaroutes1011-1129784` | 453.6 | 0.9804 | 4 (f00009/f00010/f00015/f00021 -- different place/pose, minimap marker moved each time) |
| Vice City (5454000F) | gta-vc | 77a5f0908dce | queued `1-1791751023-gtaroutes1011-1901311`, release tier on #433 | pending | pending | pending |
| San Andreas drive (54540082) | gta-sa-drive | 7da19befd45b | not yet queued | pending | pending | pending |

GTA III's proof soak's post-mark frames briefly (t=120-240s) showed a static "Load Game" menu instead of the
expected cutscenes -- the golden carries the pathfind session's own save, so `START` at the title opens a
save-aware menu on this disk that the true first-run disk never showed. The same A-press train written to skip
cutscenes also cleared this menu (by t=270s); gameplay then ran uninterrupted through the full window, in a
different on-screen place each sampled frame from t=270s on. Passes the brief's criteria as written -- no
fix/rerun needed. Full frame-by-frame account in NOTES.md section 4.

`targets.toml`: added rows for both new titles. Neither has a sourced `target_fps` (no documented cap, no
#482-style XBE disassembly done this session) -- both note that and fall through to the 30 default, as the brief
allows.

## Remaining

- Vice City's 600s proof soak is queued (release tier, `#433`) and has not completed -- the Nova's queue had ~20
  release-tier `nfsdefault1011`/`profileconv1011`/`lane.local` items ahead of it when queued. Waiting on
  `dispatch/results/1-1791751023-gtaroutes1011-1901311/result.json`.
- `gta-sa-drive.route` is written (boots identically to `gta-sa.route`, which is untouched; after the alley-walk
  beat, presses Y to mount the blue-cone BMX, then pedals/steers for the rest of the window) and parse-checked, but
  its 600s proof soak has not been queued yet.
- PR.md's results table and `State:` need a final pass once both remaining proofs land, plus a release-note line if
  they pass, plus a final `git merge origin/master` before marking ready.

Full session history, including why attempt 1 did not finish, in NOTES.md.
