# The compatibility page adds RalliSport Challenge and Mortal Kombat: Shaolin Monks to Playable (92 -> 94)

State: ready

Lane: compat1018c            Issue: #433
Base: master @ 7e00c7cf738395537497b1cfe5f5aa8292115aa1
Files: docs/lanes/compat1018c/**, docs/testing/compat_notes.tsv, docs/compatibility.csv, docs/COMPATIBILITY.md, docs/testing/titles/targets.toml
Prediction: none: docs/analysis only, no device arm
Needs device: no    Needs NDK: no
Selftest: none -- compat_page_selftest.py is compat_page.py's own unittest file, not a selftest.d fragment the fold runs

Release note (none): documentation only. No emulator code changes.

Adds RalliSport Challenge (`4D53000F`) as a new `playable` row to
`docs/testing/compat_notes.tsv` and updates Mortal Kombat: Shaolin Monks'
(`4D570029`) existing `playable` row from its 10-06 figures to the 10-18
run, then regenerates `docs/COMPATIBILITY.md` / `docs/compatibility.csv`
via `compat_page.py`: **92 -> 94 Playable**. The evidence is the owner's
2026-10-18 ~10:10 PDT hand-play of both titles on the Nova (RalliSport:
294.8 s scored, fps_ok 0.9166; Shaolin Monks: 545.0 s scored, fps_ok
0.9939), both already appended to `pm/playable-accepted.tsv`.

## Ledger vs. registry: disagree on the numeric columns, agree on everything else

`pm/title-registry.tsv`'s `status` column for both titles already reads
`PLAYABLE` citing the 2026-10-18 ledger, so section membership was never
in question. Its per-run numeric columns (`fps_ok_share`,
`fps_window_median`, `play_s`) are a run behind for both: RalliSport's row
still points at the 2026-10-04 `hold-0816` verdict, Shaolin Monks' at the
2026-10-06 run that *failed* (`fps_ok 0.4912`, `failing_all=fps+hitch`).
Per `compat1017c`'s precedent, used the brief's own figures for
`compat_notes.tsv` rather than the registry's stale pointers; the registry
closes on its own next rebuild (outside this lane's `Files:`).

## `title_registry.py check --pages`: 3 of 4 pages fixed/confirmed, 1 is another actor's file

`python3 docs/testing/title_registry.py check --root /home/justin/hakux-work --pages`:

- `README.md`: numberless Playable line -- nothing to fix (no numeric
  count anywhere in this file since the 10-16 switch).
- `COMPATIBILITY.md` (header, table rows): now **match** the table (94) --
  this lane's fix.
- `Wall`: already **matches** (94), not touched.
- `status page`: still **92**, stale -- `status/index.html` lives outside
  this repo (`DEFAULT_ROOT`) and outside this lane's `Files:`; closes on
  its own next rebuild, same gap `compat1017c`/`compat1018b` both hit.
- Registry itself reports `STALE`: pre-existing, a shared/generated file
  this lane does not rebuild.

## `targets.toml`

Only Mortal Kombat: Shaolin Monks has a block (RalliSport Challenge has
none -- only "RalliSport Challenge 2", a different title_id, appears).
Updated its `notes` field, which cited the superseded 2026-10-06 run's
figures, to the 2026-10-18 run's own numbers, phrased like
`compat1017c`'s NBA Live 07 fix. Reparsed with `tomllib`: valid, 106
titles.

## Other stale references

Grepped `docs/` and `README.md` for both titles and for any other stale
"92 Playable"/"92 games" count: none outside the generator's own
(regenerated) line. `docs/HISTORY.md` and `docs/releases/*` carry dated
mentions of both titles, left untouched (out of `Files:`, same as
`docs/releases/` generally). `docs/testing/flicker.md` is a historical
bug-investigation record of #804 itself, not a current status claim, and
not in `Files:`. Full list in `docs/lanes/compat1018c/NOTES.md`.

## Verification

- `compat_page.py` (no flags): 94 playable / 20 below_bar / 11 not_playable.
- `compat_page.py --check`: up to date.
- `compat_page_selftest.py`: 21 tests, OK.
- `title_registry.py check --root /home/justin/hakux-work --pages`: exit 3
  (status page + registry staleness, both outside this lane -- see above).
- `preflight.sh`: passed -- territory ok, coverage ok, board files ok.

The done-test (per the brief): `promotion_check.py` reporting master's
`COMPATIBILITY.md`/`compatibility.csv` lines as matching, once this folds.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
