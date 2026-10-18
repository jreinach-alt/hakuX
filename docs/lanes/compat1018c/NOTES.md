# compat1018c (#433, Playable 92 -> 94: RalliSport Challenge + Mortal Kombat: Shaolin Monks)

## Step 0: Already-tried table

Read `docs/lanes/compat1018b/NOTES.md` (GTA III/VC drop: the
`BELOW_BAR_OVERRIDES` pattern, the "blank the fps columns rather than
publish a number that describes a different scene" rule, the discovery that
Mortal Kombat: Shaolin Monks had silently fallen off the ledger between
briefs, and the `title_registry.py check --pages` scope split -- fix
`COMPATIBILITY.md`/README, leave `status/index.html` and the Wall to other
actors) and `docs/lanes/compat1017c/NOTES.md` (NBA Live 07 add: cross-check
every ledger number against the ledger row's own prose rather than the
registry's auto-tracked columns when the two disagree, splice a new row by
exact line index rather than a blind text split to avoid a row-ordering
bug, and the precedent for what `targets.toml` wording counts as "stale"
even when it isn't literally "excluded/held/below the bar").

| Column | Source used this session | Confirmed |
|---|---|---|
| `title_id` join | `compat_page.py`'s `build_playable_rows()` joins the ledger to `compat_notes.tsv` by `title_id` only, raising `SystemExit` on a ledger row with no matching notes row | confirmed by reading the function before editing; RalliSport Challenge (`4D53000F`) is in `pm/playable-accepted.tsv` (line 94, 2026-10-18) with no `compat_notes.tsv` row yet -- running `--check` now would name exactly that gap |
| `fps_median`/`time_at_bar`/`gameplay_s` | the brief's own figures (RalliSport: median 59.58, share 0.9166, 295 s; Shaolin Monks: median 59.94, share 0.9939, 545 s), **not** the registry's numeric columns | checked `pm/title-registry.tsv` for both title_ids first: RalliSport's row still points at the 2026-10-04 `hold-0816` verdict (median 59.94, share 0.9026, 605.9 s -- a different run, and coincidentally shares Shaolin's new median digit-for-digit, a pure coincidence not a transcription of one into the other); Shaolin Monks' row still points at the 2026-10-06 failing run (`fps_ok 0.4912`, median 45.91, `failing_all=fps+hitch`). Per `compat1017c`'s rule (use the ledger/brief's own prose number when the registry's `last_run` pointer is stale), used the brief's figures as given, not the registry's |
| `region`/`region_source` | left `?`/`none` for the new RalliSport row | `ls /mnt/d/hakux-staging/xiso \| grep -i ralli` and `grep -i shaolin`: no local copies to confirm a region from a filename; same "no evidence, stays `?`/`none`" precedent `compat1017c` used for NBA Live 07 |
| `notes` | RalliSport: "Car flicker (#804) fixed." (brief explicitly permits this). Shaolin Monks: left blank, unchanged -- the brief gives numeric updates only, no note content, and no other `playable` row narrates a past failing run in this column | — |

Stop rule honored: no generator failure repeated twice for the same cause
(zero `SystemExit`s hit; the join gap above was identified by reading
`build_playable_rows()`, not by running `--check` twice for the same
reason).

## `compat_notes.tsv` edit

Edited with a small Python script that splits the file on `\n` (not
`\r\n`) and preserves each line's own trailing `\r`, after discovering the
file mixes line endings -- lines 52-56, 102 and 105 are LF-only, the rest
CRLF (`data.count(b"\n")`=125 vs `data.count(b"\r\n")`=118 before the edit).
A first attempt that split on `\r\n` directly misaligned indices past line
52 and was caught by an assertion before any write, not by a second
generator failure. The Shaolin Monks row was edited in place (line 91);
RalliSport Challenge was spliced in after the last playable row (line 94,
Lemony Snicket's), before the `below_bar` section starts (line 95) -- same
method `compat1017c` used for NBA Live 07.

## The ledger vs. registry disagreement (expected, same shape as compat1017c)

`pm/title-registry.tsv`'s numeric columns for both title_ids are stale
against the 10-18 run and were **not** used:

- RalliSport Challenge (`4D53000F`): registry still points at the
  2026-10-04 `hold-0816` verdict (median 59.94, share 0.9026, 605.9 s).
  Its `status` is already `PLAYABLE` ("in pm/playable-accepted.tsv
  (2026-10-18)"), so section membership is correct; only the numeric
  columns are stale.
- Mortal Kombat: Shaolin Monks (`4D570029`): registry still points at the
  2026-10-06 run that **failed** (`fps_ok 0.4912`, median 45.91,
  `failing_all=fps+hitch`). Its `status` is likewise already `PLAYABLE`
  citing the same 2026-10-18 ledger date.

The ledger (`pm/playable-accepted.tsv`) and the registry's `status` column
agree with each other and with this lane's output (94). Only the
registry's per-run numeric columns (`fps_ok_share`, `fps_window_median`,
`play_s`, etc.) lag a run behind -- they close on the registry's next
rebuild, not something this lane's `Files:` list can fix. Used the brief's
own figures for `compat_notes.tsv` instead, per `compat1017c`'s rule.

## Step 2: generator output

```
python3 docs/testing/compat_page.py --ledger /home/justin/hakux-work/pm/playable-accepted.tsv \
  --registry /home/justin/hakux-work/pm/title-registry.tsv --notes docs/testing/compat_notes.tsv
```

wrote `docs/COMPATIBILITY.md` / `docs/compatibility.csv` with **94
Playable** (up from 92), 20 below_bar, 11 not_playable -- matches the
brief's expectation exactly, both new rows picked up from the ledger with
no `SystemExit`.

- `--check`: up to date.
- `python3 docs/testing/compat_page_selftest.py`: 21 tests, OK -- no
  change needed to `compat_page.py` or its selftest; this promotion needed
  no new generator rule (unlike `compat1018b`'s `BELOW_BAR_OVERRIDES`).

## Step 3: `title_registry.py check --pages`

```
python3 docs/testing/title_registry.py check --root /home/justin/hakux-work --pages
```

exit 3:

- `README.md`: numberless Playable line, as expected -- **nothing to fix**.
  Checked for any other "92" count anywhere in README.md first (none):
  the numberless form has carried no number since the 10-16 switch
  (`compat1018b`'s precedent), so step 3's "92 -> 94" instruction has no
  live target in this file this round.
- `COMPATIBILITY.md` (header) and (table rows): both **match** the table
  (94) -- this lane's fix.
- `Wall`: **matches** (94) -- already current, not touched by this lane
  (not in `Files:`, and already correct).
- `status page`: **92**, stale against the table (94). `status/index.html`
  lives outside this repo (`DEFAULT_ROOT`) and outside this lane's
  `Files:`; same gap `compat1017c` and `compat1018b` both hit and left to
  the next rebuild of that external artifact.
- registry itself: `STALE (sources changed since it was built)` --
  pre-existing, a shared/generated file this lane does not rebuild.

## Step 4: `targets.toml`

Only Mortal Kombat: Shaolin Monks (`4D570029`, line 668) has a block;
RalliSport Challenge (`4D53000F`) has none (confirmed by grep -- only
RalliSport Challenge **2**, a different title_id, `4D530039`, appears).
Shaolin Monks' `notes` field cited the superseded 2026-10-06 run's figures
(603.9 s, median 39.89, 100%, one 115.7 ms hitch) under a "Playable per the
2026-10-18 ledger" header that no longer matched the run it described --
not literally "excluded/held/below the bar" wording, but the same kind of
stale-substance gap `compat1017c` found and fixed in NBA Live 07's block.
Updated to the 2026-10-18 run's own figures (545.0 s, median 59.94, 99.4%,
2 hitches after warm-up worst 301.4 ms), phrased the same way
(`compat1017c`'s "Playable per an owner play session on the Nova, <date>
(...); supersedes the <old date> ... run (...)"). Reparsed with
`tomllib.load` after the edit: still valid, 106 titles. Nothing else in
either block's `iso`/`route` fields needed changing.

## Step 5: other stale references

`grep -rln "RalliSport Challenge\|4D53000F\|Shaolin Monks\|4D570029" docs/
README.md` (all file types), plus a separate `grep -rln "92 Playable|92
games"` for the stale count:

- No stale "92 Playable"/"92 games" count anywhere outside the generator's
  own (now-regenerated) `COMPATIBILITY.md` line.
- `docs/HISTORY.md` (lines 241, 404, 413, 439, 441): dated changelog
  entries reporting what was true on those release dates (e.g. "0.5.2
  (10-17): Halo and Shaolin Monks" citing the pre-fix 27.5-29 fps figure)
  -- not in this lane's `Files:`, same category as `docs/releases/`, left
  untouched.
- `docs/releases/v0.5.2.md`, `v0.5.0.md`, `v0.4.1-j1.md`: dated release
  records, off limits per the brief, not touched.
- `docs/investigations/crimson-skies-performance.md:174`: names
  "RalliSport Challenge 2" (`4D530039`), a different title, not either
  title in scope.
- `docs/testing/flicker.md`: a bug-investigation record of the #804
  flicker itself (10-04 observation, mechanism, reproduction rate) -- a
  historical diagnostic document, not a current Playable/held status
  claim, and not in this lane's `Files:` besides. Left untouched.
- `docs/testing/titles/pathknow/**` (hints, families.md, eval_set.tsv):
  checked all six RalliSport/Shaolin-adjacent files for
  "playable/excluded/held/below the bar" wording -- zero hits; "held"
  there means a held D-pad/trigger input, not an owner hold. Left
  untouched, same outcome `compat1018b` found for the GTA pathfinding
  files.
- `docs/testing/dispatch_gate_selftest.py`: uses RalliSport Challenge
  (`4D53000F`) as fixture data for unrelated dispatch-gate test legs (a
  stand-in title name/id, not a real status claim) -- not in this lane's
  `Files:`, left untouched, same category as `compat1018b`'s
  `selftest_title_locations.py` finding.
- Every other hit (`docs/lanes/*`) is another lane's own folded
  `NOTES.md`/`PR.md`/fixture snapshot -- frozen history, not in this
  lane's `Files:`, not edited.

## Verification

- `python3 docs/testing/compat_page.py --ledger /home/justin/hakux-work/pm/playable-accepted.tsv --registry /home/justin/hakux-work/pm/title-registry.tsv --notes docs/testing/compat_notes.tsv`: 94 playable / 20 below_bar / 11 not_playable.
- `... --check`: up to date.
- `python3 docs/testing/compat_page_selftest.py`: 21 tests, OK.
- `python3 docs/testing/title_registry.py check --root /home/justin/hakux-work --pages`: exit 3 -- README.md and COMPATIBILITY.md (header, table rows) and Wall all match (94); status page (92) and registry staleness are pre-existing gaps outside this lane's `Files:` (see Step 3 above).
- `bash docs/testing/preflight.sh`: passed -- territory ok, coverage ok, board files ok.
- `python3 -c "import tomllib; tomllib.load(open('docs/testing/titles/targets.toml','rb'))"`: parses, 106 titles.

## Selftest

No `selftest.d` fragment reads `compat_notes.tsv`, `targets.toml`,
`COMPATIBILITY.md` or `compatibility.csv`; `compat_page_selftest.py` is the
compat page's own unittest file, not a `selftest.d` fragment, and the fold
only runs named fragments. `Selftest: none -- compat_page_selftest.py is
not a selftest.d fragment`.
