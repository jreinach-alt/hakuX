# compat1018: the compatibility page catches up to the 95-row Playable ledger

State: ready

Lane: compat1018            Issue: #433
Base: master @ da6e8949dc
Files: docs/lanes/compat1018/NOTES.md, docs/lanes/compat1018/PR.md, docs/testing/compat_notes.tsv, docs/compatibility.csv, docs/COMPATIBILITY.md, docs/testing/titles/targets.toml
Prediction: none: analysis-only (docs and a generator, no emulator code, no pixels or speed)
Needs device: no    Needs NDK: no

Release note (none): documentation only. No emulator code changes.

The Playable ledger (`pm/playable-accepted.tsv`) gained four rows on
2026-10-18 (lane.pathfind, frame review, offline reconciliation): Mortal
Kombat: Shaolin Monks (4D570029), Cel Damage (45410011), Micro Machines
(Europe) (4947001C), Lemony Snicket's A Series of Unfortunate Events (USA)
(4156001F). Added one `playable` row per title to `docs/testing/compat_notes.tsv`
and regenerated `docs/COMPATIBILITY.md`/`docs/compatibility.csv` with
`compat_page.py`. Playable goes from 91 to 95.

Two more generator-forced changes surfaced while regenerating, both
distinct causes (not a repeat, so the Step 0 stop rule didn't trip): a
fifth title, Buffy the Vampire Slayer (45410012), had already landed in
the shared registry as a qualifying BELOW_BAR row with no `compat_notes.tsv`
entry (added it, same method compat1017 used for its four below_bar
titles); and two existing below_bar rows, Amped 2 and Forza Motorsport, no
longer qualify against the live registry (their `failing_all` moved from a
clean `fps` to a combined cause from a concurrent 2026-10-18 verdict batch)
-- removed both, per `build_below_bar_rows()`'s own hard refusal and the
compat1017c precedent for this exact shape (a combined-cause title is left
off every section, not guessed at). Final counts: 95 playable / 18
below_bar / 11 not_playable.

`docs/testing/titles/targets.toml`: updated Mortal Kombat: Shaolin Monks'
`notes` (the only one of the four with an existing entry) from "not yet
device-proven" to record its Playable ledger evidence.

`compat_page.py --check` and `compat_page_selftest.py` both pass.
`title_registry.py check --pages` passes for every page this lane's files
control (95 everywhere); the one remaining line (`STALE registry sources
changed since it was built`) is pre-existing registry-build staleness, not
a defect here. `preflight.sh`'s `territory` gate FAILS -- `territory.toml`
double-claims this lane's files against two folded, released lanes
(`compat1017c`, `topspinroute1018`) that never released their rows; filed
`dispatch/board-requests/compat1018.md` asking the board to release them,
per the lane contract. Every other preflight step passes. Full
column-by-column sourcing, including a registry/ledger run mismatch found
for Mortal Kombat: Shaolin Monks (resolved in the ledger's favor per
compat1017/b/c precedent), is in `docs/lanes/compat1018/NOTES.md`.

Selftest: none -- a docs and generator catch-up; no selftest.d fragment
reads `compat_notes.tsv`, `targets.toml`, `COMPATIBILITY.md` or
`compatibility.csv`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
