# The compatibility page adds NBA Live 07 (454100A1) as Playable: 90 -> 91

State: ready

Lane: compat1017c            Issue: #433
Base: master @ c42d3b00a53cd89c2172daf925fb9e9c19840116
Files: docs/lanes/compat1017c/**, docs/testing/compat_notes.tsv, docs/compatibility.csv, docs/COMPATIBILITY.md, docs/testing/titles/targets.toml
Prediction: none: docs/analysis only, no device arm
Needs device: no    Needs NDK: no

Adds NBA Live 07 (`454100A1`) to `docs/testing/compat_notes.tsv` as a new
`playable` row and regenerates `docs/COMPATIBILITY.md` /
`docs/compatibility.csv` via `compat_page.py`: 90 -> 91 Playable. The
evidence is telemetry from an owner play session on the Nova, 2026-10-17
23:28-23:42 PDT (no frames kept): 762 s of play, 618 pace windows, 98.6% of
the time at or above 28.5 fps, window median 50.8 fps, lowest window 27.5,
longest frame 161 ms, no stall over 500 ms. Banked in
`pm/playable-accepted.tsv` 2026-10-17 23:50 PDT. This run supersedes the
2026-10-06 pathfind run (median 19.99 fps) -- that run was never rendered as
a `below_bar` row on the page, since its registry `failing_all` was
`duration+fps` (a combined cause), not `fps` alone, which is
`below_bar_qualifies()`'s exact requirement; there was nothing to move, only
a new row to add.

The registry's auto-tracked numeric columns (`fps_window_median`,
`fps_ok_share`, `play_s`) for this title_id still point at the stale 10-06
run, not the owner-play session the ledger actually cites (the mismatch
pitfall documented by `docs/lanes/compat1017/NOTES.md`) -- `fps_median`,
`time_at_bar` and `gameplay_s` in the new row are the ledger's own precise
prose figures instead, never the stale registry numbers.

`targets.toml`'s `[titles."454100A1"]` note is updated from "not yet
device-proven" to record the 2026-10-17 Playable result; the rest of that
field (the `gen-nba-live-07` route description) is untouched. `README.md` is
untouched (out of scope; its Playable line stays numberless per
`host-tools/home_page.py`'s exact-text match).

`compat_page.py --check` and `compat_page_selftest.py` (19 tests) both pass.
`docs/testing/preflight.sh` passes clean (territory ok, coverage ok -- no
board request needed). `title_registry.py check --pages` exits 3 on two
items, neither in this lane's files: `status/index.html`
(`/home/justin/hakux-work/status/index.html`, outside the repo) still
reads 90, and `pm/title-registry.tsv`'s own `sources_digest` predates this
session's edit -- both close on the next rebuild of those external,
generated artifacts (same staleness shape `docs/lanes/compat1017b/NOTES.md`
hit). `README.md`, `COMPATIBILITY.md` (header + table rows) and `Wall` all
read 91/numberless correctly.

Selftest: none -- no `selftest.d` fragment reads `compat_notes.tsv`,
`targets.toml`, `COMPATIBILITY.md` or `compatibility.csv`;
`compat_page_selftest.py` is the compat page's own unit test, not a
`selftest.d` fragment, and is run directly above.

See `docs/lanes/compat1017c/NOTES.md` for the full Already-tried table,
column-by-column sourcing, and the grep of other NBA Live 07 mentions
(all historical/technical, none a stale status claim, left alone).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
