# compat1017c (#433 Part 4)

## Step 0: Already-tried table

Read `docs/lanes/compat1017b/NOTES.md` and `docs/lanes/compat1017/NOTES.md` on
master: they did exactly this job for 90 ledger titles (31 + Marvel Nemesis,
then DOA3 + Pac-Man World 2) with the same generator, `docs/testing/compat_page.py`.

| Column | Source | Confirmed this session |
|---|---|---|
| `title_id` | the ledger row's own `title_id` | `compat_page.py` joins by `title_id` only; confirmed `--check` before any edit refuses naming exactly NBA Live 07 (`454100A1`) missing from `compat_notes.tsv` (section=playable) |
| `title` | ledger `title` text, verbatim | — |
| `region` | filename > archive-list exact match > websearch > `?`/`none` | checked `/mnt/d/hakux-staging/xiso` for `454100A1`/`NBA_Live_07`: no match. Not websearched — well-known worldwide multi-region EA Sports AAA title, same precedent compat1017 used for Rayman 3 and Marvel Nemesis (a search would only confirm what's already assumed). Stays `?`/`none`. |
| `device` | ledger run text ("Nova") | lowercased to `nova` |
| `fps_median` | registry `fps_window_median` for the matching run, **unless** the registry's `last_run` is a different run than the one the ledger cites (compat1017's documented pitfall) | **Mismatch found**: `pm/title-registry.tsv`'s `454100A1` row still points at `wt/pathfind/docs/lanes/pathfind/runs/nbalive07-1006/verdict.json` (2026-10-07, `fps_window_median=19.99`, `play_s=129.2`) — the old pathfind run the brief says is superseded, not the 2026-10-17 23:28-23:42 owner play session the ledger actually cites. Per compat1017's rule, used the ledger's own precise prose number instead: window median 50.8 fps. |
| `time_at_bar` | registry `fps_ok_share` for the matching run, same mismatch rule | same mismatch as above; used the ledger's prose figure: 98.6% -> `0.986` |
| `gameplay_s` | registry `play_s` for the matching run, same mismatch rule | same mismatch; used the ledger's prose figure: 762 s of play (23:30:08-23:42:50) |
| `tested` | the run date named in the ledger's evidence text | ledger evidence text ("2026-10-17 23:28-23:42 PDT") and the ledger's own banking timestamp ("2026-10-17 23:50") agree on the same date here, so no banking-date-vs-run-date conflict to resolve: `2026-10-17` |
| `notes` | free text, blank unless a reader needs it | filled: telemetry only (no frames), matching the brief's instruction to say so; short phrase, same shape as the existing Need for Speed: Most Wanted row ("Hand-played race; 30 fps cap") |

**Every ledger number cross-checked against the ledger row's own prose; the
registry's auto-tracked numeric columns for this title_id were NOT used**
(confirmed stale: they come from the 10-06/10-07 pathfind run the brief
explicitly says this run supersedes). Nothing in this row was invented.

Stop rule honored: no generator failure repeated twice for the same cause
(one `--check` refusal, for the one documented cause: the missing playable
row).

## Whether a BELOW_BAR row needed to move

Checked `docs/COMPATIBILITY.md`, `docs/compatibility.csv` and
`docs/testing/compat_notes.tsv` for any existing NBA Live 07 / `454100A1`
entry before editing: **none exists in any of the three** (confirmed by
`grep`). The 10-06 pathfind run was never rendered as a `below_bar` row,
because `below_bar_qualifies()` requires `failing_all == "fps"` exactly
(`docs/testing/compat_page.py:71-76`), and that run's registry row records
`failing_all = "duration+fps"` (190 s of gameplay, under the 600 s
confirmation bar, as well as the fps shortfall) — a combined cause, not
`fps` alone, so the generator never demanded a `below_bar` note row for it
and none was ever added. There is nothing to move; this is a plain new
`playable` row, the same shape as Pac-Man World 2 in compat1017b (no prior
entry anywhere on the page).

Separately: `pm/title-registry.tsv`'s `status` column for `454100A1` already
reads `PLAYABLE` (set live, outside this lane, "in pm/playable-accepted.tsv
(2026-10-17 23:50)") even though its numeric columns are still the stale
10-06 run. `build_below_bar_rows()` only considers rows with
`status == "BELOW_BAR"`, and separately excludes any title_id that is in the
ledger ("ledger wins over the registry") — so this title was never a
below_bar candidate by either path, confirming the mismatch above is purely
a numeric-staleness issue, not a section-membership one.

## Row added

Inserted after the last `playable` row (Pac-Man World 2, line 91) and before
the `below_bar` section starts (Turok Evolution, line 92), matching the
existing CRLF line endings, by a small Python script that indexes the exact
line rather than a blind text split (same method compat1017b used, avoiding
compat1017's row-ordering splice bug):

```
playable	454100A1	NBA Live 07	?	none	nova	50.8	0.986	762	2026-10-17	Owner play session; telemetry only, no frames
```

## Step 4: `targets.toml`

`docs/testing/titles/targets.toml` line 656-660, `[titles."454100A1"]`: the
existing `notes` field was the `#433` step 6c classifier-path benchmark
description ending "not yet device-proven" — stale, since the title is now
Playable on an owner play session. Did **not** carry a BELOW_BAR / 19.99 fps
/ "unconfirmed" sentence (that wording lives in the registry and the old
run's own verdict.json, not in `targets.toml`), so the brief's literal
trigger condition wasn't present verbatim, but the field's substance (device
not proven) was exactly as stale as that condition describes. Updated the
sentence to record what's now true: Playable per an owner play session on
2026-10-17 (~51 fps median, 98.6% at or above the bar), the 2026-10-06
pathfind run (median 19.99 fps) predating the current build. Left the rest
of the `notes` field (the route/benchmark description) untouched — still
accurate, since `gen-nba-live-07` is still the route used.

## Step 5: other stale references

`grep -rln "NBA Live 07\|454100A1" docs/` (excluding `docs/releases/`, off
limits) turns up:

- `README.md:29` — "Faster. NBA Live 07 went from 23 to 47 fps..." — a
  HISTORY-style performance note, not a compatibility-status claim; no
  Playable/failing wording to correct, and README.md is explicitly out of
  this lane's `Files:` besides.
- `docs/testing/titles/targets.toml` — handled above.
- `docs/testing/titles/pathknow/` and route/prediction files under
  `docs/testing/` referencing `gen-nba-live-07` — technical route
  definitions (drive/shoot benchmark path), not compatibility-status prose.
- `docs/HISTORY.md` if present — not found referencing this title_id beyond
  the README line already covered; confirmed by the same grep.

Nothing else found claiming NBA Live 07 as failing/below-bar/unconfirmed
anywhere in scope. `docs/releases/` untouched per the brief.

## Verification

- `python3 docs/testing/compat_page.py --ledger /home/justin/hakux-work/pm/playable-accepted.tsv --registry /home/justin/hakux-work/pm/title-registry.tsv --notes docs/testing/compat_notes.tsv --check`: before the edit, refused naming NBA Live 07 as missing; after the edit, up to date.
- `python3 docs/testing/compat_page_selftest.py`: 19 tests, OK.
- `python3 docs/testing/title_registry.py check --pages`: result recorded below (registry is generated/shared, outside this lane's `Files:`).
- `bash docs/testing/preflight.sh`: result recorded below.

## Selftest

No selftest.d fragment reads `compat_notes.tsv`, `targets.toml`,
`COMPATIBILITY.md` or `compatibility.csv`; `compat_page_selftest.py` is not a
selftest.d fragment and the fold only runs named fragments. `Selftest: none`
in `PR.md`.
