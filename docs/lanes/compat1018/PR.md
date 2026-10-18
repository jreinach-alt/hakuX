# compat1018: the compatibility page catches up to the 95-row Playable ledger

State: draft

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

Work still in progress on this branch; see `docs/lanes/compat1018/NOTES.md`
for the full column-by-column sourcing (including a registry/ledger run
mismatch found for Mortal Kombat: Shaolin Monks, resolved in the ledger's
favor per compat1017/b/c precedent) and the `targets.toml` update.

Selftest: none -- a docs and generator catch-up; no selftest.d fragment
reads `compat_notes.tsv`, `targets.toml`, `COMPATIBILITY.md` or
`compatibility.csv`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
