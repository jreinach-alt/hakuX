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
