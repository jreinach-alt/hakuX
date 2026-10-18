# compat1018b: drop GTA III and Vice City from Playable (#433, #1049)

State: ready

Lane: compat1018b           Issue: #433 [#1049]
Base: master @ 1b3b3db8f4
Files: docs/lanes/compat1018b/**, docs/testing/compat_notes.tsv, docs/testing/compat_page.py, docs/testing/compat_page_selftest.py, docs/compatibility.csv, docs/COMPATIBILITY.md
Prediction: none: analysis-only (docs and a generator, no emulator code, no pixels or speed)
Needs device: no    Needs NDK: no
Selftest: none -- compat_page_selftest.py is compat_page.py's own unittest file, not a selftest.d fragment the fold runs

Release note (none): documentation only. No emulator code changes.

Owner 2026-10-18 ~08:30 PDT took GTA III (5454000E) and GTA: Vice City
(5454000F) off the Playable wall: both drop into the teens while driving
(#1049). lane.local had already moved their ledger rows, added `below_bar`
holds, and rebuilt the registry; this lane brings the generated docs in
line.

## What changed

- `docs/testing/compat_notes.tsv`: both titles moved from `playable` to
  `below_bar`, with `notes` stating only what's true (plays, drops into the
  teens while driving in the city, #1049). `fps_median`/`time_at_bar`/
  `gameplay_s` are left blank rather than carrying the on-foot confirmation
  run's numbers next to a driving-fps note that contradicts them -- see
  NOTES.md, "Why the fps columns are blank."
- `docs/testing/compat_page.py`: added `BELOW_BAR_OVERRIDES` (same shape as
  the existing `RED_OVERRIDES`) for these two title_ids. Both are BELOW_BAR
  in the registry only via the manual hold path (`status_rule = "hold
  gta3/gtavc-driving-below-bar"`), with `failing_all` empty -- their last
  *scored* run is a clean on-foot pass, so `below_bar_qualifies()`'s
  automatic `failing_all == "fps"` gate doesn't admit them on its own.
  Checked `pm/owner-holds.tsv`'s other `below_bar`-kind holds before writing
  this: several are route/menu/stuck titles correctly left off today, so the
  fix is a narrow override, not a loosened gate. Two new
  `compat_page_selftest.py` cases cover it (21/21 passing, up from 19).
- `docs/COMPATIBILITY.md` / `docs/compatibility.csv`: regenerated.

## The count: 92, not the brief's predicted 93

`pm/playable-accepted.tsv`, the registry's own PLAYABLE count, and this
lane's regenerated page all agree at **92**, not the 93 the brief expected
from 95 - 2. A third, unrelated title -- Mortal Kombat: Shaolin Monks
(4D570029) -- separately dropped off the ledger via the already-folded
`pathfind` lane (`failing_all=fps+hitch`, correctly excluded from every
section). Its stale `playable` row in `compat_notes.tsv` is now a harmless
orphan (the generator silently ignores it, confirmed via `--check`, the
selftest, and `title_registry.py check --pages`); not touched here since
it's outside this lane's brief (#1049 names only the two GTA titles) and not
this lane's call to make. **Flagging to lane.local**: this is a third
Playable regression that likely needs its own hold/board item.

## Not touched, and why

- `README.md`: already carries the numberless Playable line
  (`title_registry.py check --pages` confirms it matches `home_page.py`'s
  expectation); no stale count anywhere in it.
- `docs/testing/titles/targets.toml`: both titles' notes are route-proving
  technical text with no "Playable"/"confirmed" wording to fix.
- `docs/HISTORY.md`, `docs/releases/**`, `docs/lanes/*/NOTES.md` or `PR.md`,
  pathfinding files under `docs/testing/titles/{routes,pathknow}/**`: dated
  historical records or mechanics-only text naming the titles, same category
  as the explicitly-protected `docs/releases/`; no Reddit/announcement draft
  naming either title was found anywhere under `docs/`. Full grep results in
  NOTES.md, "Step 5."

## Territory

`preflight.sh`'s `territory` gate fails: `territory.toml`'s `[free]` still
lists these same 4 files (`compat_notes.tsv`, `compatibility.csv`,
`COMPATIBILITY.md`, `targets.toml`) from the predecessor `[lane.compat1018]`'s
folded-and-released claim, even though `[lane.compat1018b]`'s own row
(created after that release) already claims them correctly. Board request
filed: `dispatch/board-requests/compat1018b.md` -- asks only that the 4 paths
be dropped from `[free]`'s array; this lane's own row needs no change. Did
not edit `territory.toml` directly. `coverage` fails only on issue #1071,
unrelated to this lane. `board files` passes.

## Verification

- `compat_page.py --check`: up to date.
- `compat_page_selftest.py`: 21/21 OK.
- `title_registry.py check --root /home/justin/hakux-work --pages`:
  `COMPATIBILITY.md` header and table rows both match the live table (92).
  Status page (94) and Wall (93) remain stale against files outside this
  lane's Files list -- not this lane's defect, same pattern
  `compat1017`/`compat1018` documented for the same two surfaces.

Full narrative, the rejected blanket-fix alternative, and the pitfalls
table: `docs/lanes/compat1018b/NOTES.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
