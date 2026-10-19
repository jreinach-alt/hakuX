# The compatibility page adds Pro Evolution Soccer 5 (Europe), The Wild Rings and Knights of the Temple II to Playable (94 -> 97)

State: ready

Lane: compat1019b            Issue: #433
Base: master @ 3597b72b35886d3bc5a59bf3cfa2096a5ae37962
Files: docs/lanes/compat1019b/**, docs/testing/compat_notes.tsv, docs/compatibility.csv, docs/COMPATIBILITY.md
Prediction: none: docs/analysis only, no device arm
Needs device: no    Needs NDK: no
Selftest: none -- compat_page_selftest.py is compat_page.py's own unittest file, not a selftest.d fragment the fold runs

Release note (none): documentation only. No emulator code changes.

Adds three new `playable` rows to `docs/testing/compat_notes.tsv` --
Pro Evolution Soccer 5 (Europe) (`4B4E0030`), The Wild Rings (`4D530048`),
Knights of the Temple II (`544D0013`) -- then regenerates
`docs/COMPATIBILITY.md` / `docs/compatibility.csv` via `compat_page.py`:
**94 -> 97 Playable**. All three are already in `pm/playable-accepted.tsv`
and `pm/title-registry.tsv` as PLAYABLE, dated 2026-10-19: Pro Evolution
Soccer 5 from a lane.local frame review of the 2026-10-18 pathfind run, The
Wild Rings and Knights of the Temple II from the owner's 2026-10-19 ruling
on their respective runs (both short of the usual play-share bar, both
explicitly accepted).

## Ledger and registry already current -- no numeric disagreement this round

Unlike the two previous compat promotions (`compat1018c`, `compat1018b`),
both of which hit a stale registry pointer, this round's ledger and
registry entries for all three titles are already current (2026-10-19,
matching this session), so `compat_notes.tsv`'s figures were taken directly
from the registry/brief with no stale-pointer resolution needed. See
`docs/lanes/compat1019b/NOTES.md` for the full column-sourcing table,
including how `gameplay_s` was confirmed to mean the **in-play** figure
(not the **scored** window length) by cross-checking existing rows against
the registry's own column order.

## `title_registry.py check --pages`: 3 of 4 pages fixed/confirmed, 1 is another actor's file

`python3 docs/testing/title_registry.py check --root /home/justin/hakux-work --pages`:

- `README.md`: numberless Playable line -- nothing to fix (no numeric count
  anywhere in this file; confirmed via `grep -n 94`, zero hits).
- `COMPATIBILITY.md` (header, table rows): now **match** the table (97) --
  this lane's fix.
- `Wall`: already **matches** (97), not touched.
- `status page`: still **94**, stale -- `status/index.html` lives outside
  this repo (`DEFAULT_ROOT`) and outside this lane's `Files:`; closes on
  its own next rebuild, same gap every prior compat* lane has hit.
- Registry itself reports `STALE`: pre-existing, a shared/generated file
  this lane does not rebuild.

## `targets.toml` -- untouched

None of the three titles has a block in `targets.toml` at all (checked by
title_id and by title name: zero hits for any of the three). Nothing to
change, so `targets.toml` is not in this PR's `Files:` despite being listed
in the brief's constraint section.

## Other stale references

Grepped `docs/` and `README.md` for all three titles and for any other
stale "94 Playable"/"94 games" count: none outside
`docs/lanes/compat1018c/PR.md`'s own frozen "92 -> 94 Playable" line (a
dated record of that lane's PR body, not a live claim). Two pathknow files
and `docs/lanes/pathfind/below-bar.tsv` mention Knights of the Temple II
but carry no Playable/held status language (route mechanics / per-title
verdict tracking only) and are outside this lane's `Files:`. Two older
lanes' frozen `registry.tsv` snapshots correctly show The Wild Rings and
Knights of the Temple II as UNSCREENED as of their own 10-12/10-13 dates --
historical records, not touched. Full list in
`docs/lanes/compat1019b/NOTES.md`.

## Verification

- `compat_page.py` (no flags): 97 playable / 20 below_bar / 11 not_playable.
- `compat_page.py --check`: up to date.
- `compat_page_selftest.py`: 21 tests, OK.
- `title_registry.py check --root /home/justin/hakux-work --pages`: exit 3
  (status page + registry staleness, both outside this lane -- see above).
- `preflight.sh`: passed -- territory ok, coverage ok, board files ok.
- `tomllib.load` on `targets.toml`: parses, 106 titles (unchanged).

The done-test (per the brief): `promotion_check.py` reporting master's
`COMPATIBILITY.md`/`compatibility.csv` lines as matching, once this folds.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
