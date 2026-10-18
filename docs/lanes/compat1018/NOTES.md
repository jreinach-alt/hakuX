# compat1018 (#433 Part 4)

## Step 0: Already-tried table

Read `docs/lanes/compat1017c/NOTES.md`, `docs/lanes/compat1017b/NOTES.md` and
`docs/lanes/compat1017/NOTES.md` on master: all three did exactly this job
(ledger titles -> `compat_notes.tsv` playable rows -> regenerate
`docs/COMPATIBILITY.md`/`docs/compatibility.csv` with `compat_page.py`) for
the 90, then +3, then +1 titles before these four. Same generator, same
column-filling method.

| Column | Source | Confirmed this session |
|---|---|---|
| `title_id` | the ledger row's own `title_id` | `compat_page.py --check` (run before any edit) refused naming exactly these four as missing from `compat_notes.tsv` (section=playable) |
| `title` | ledger `title` text, verbatim | — |
| `region` | filename > archive-list exact match > websearch > `?`/`none` | checked `/mnt/d/hakux-staging` (every subdirectory, not just `xiso`) for all four title_ids/names: no match for Mortal Kombat: Shaolin Monks or Cel Damage (both stay `?`/`none`, no websearch — see below). Micro Machines (Europe) and Lemony Snicket's A Series of Unfortunate Events (USA) carry their region as part of the ledger's own title text; no local file confirms it independently, but every existing `compat_notes.tsv` row whose title already carries a `(Region)` suffix (X-Men: The Official Game, Conan, Scooby-Doo! Mystery Mayhem, Scooby-Doo! Unmasked, Shadow of Memories — all Europe) is marked `region_source=filename` on exactly that basis. Followed that precedent rather than inventing a new source label: `Europe`/`filename` and `USA`/`filename` respectively. |
| `device` | ledger run text ("Nova") | lowercased to `nova`, matching every row added since 2026-10-12 |
| `fps_median` | registry `fps_window_median` for the matching run, **unless** the registry's `last_run` is a different run than the one the ledger cites (compat1017/b/c's documented pitfall) | Checked `pm/title-registry.tsv` for all four title_ids before filling anything in. Three match (Cel Damage: run `n-45410011-1007`, judged `2026-10-07T15:09:03Z`, registry `fps_window_median=29.9` — matches; Micro Machines (Europe): run `n-4947001C-1014d`, judged `2026-10-14T20:24:06Z`, registry `fps_window_median=59.94` — matches; Lemony Snicket's: run `n-4156001F-1011`, judged `2026-10-12T12:48:36Z`, registry `fps_window_median=59.88` — matches). **Mismatch found for Mortal Kombat: Shaolin Monks**: the registry's `last_run` for `4D570029` still points at `shaolin-1006` (judged `2026-10-06T21:54:16Z`, `fps_window_median=45.91`, `fps_ok_share=0.4912`, `failing_all=fps+hitch`) — a different run than the one the ledger's 2026-10-18 row actually cites, `runs/sweep-4D570029` (10-06, judged `03:21:01Z`). Per the documented rule, used the ledger's own precise prose numbers for this title instead: window median 39.89 fps, not the registry's stale 45.91/0.4912. |
| `time_at_bar` | registry `fps_ok_share` for the matching run, same mismatch rule | same three matches / one mismatch as above; Mortal Kombat: Shaolin Monks uses the ledger's prose `fps_ok 1.0`, not the registry's stale `0.4912` |
| `gameplay_s` | registry `play_s` for the matching run, same mismatch rule | same; Mortal Kombat: Shaolin Monks uses the ledger's prose "603.9 s play", not the registry's stale `604.9` (also stale, from the superseded run) |
| `tested` | the run date named in the ledger's evidence text (compat1017b's rule: not the ledger's `date_pdt` banking/ruling-date column, which for all four of these rows is `2026-10-18`, the offline-reconciliation date, not when any run actually happened) | Mortal Kombat: Shaolin Monks run dated 10-06 in the ledger's own evidence text -> `2026-10-06`; Cel Damage 10-07 -> `2026-10-07`; Micro Machines (Europe) 10-14 -> `2026-10-14`; Lemony Snicket's 10-11 -> `2026-10-11`. All four differ from the `2026-10-18` banking date; none was used for `tested`. |
| `notes` | free text, blank unless a reader needs it | left blank for all four — most `playable` rows have a blank `notes` field (only Need for Speed: Most Wanted and NBA Live 07 carry one, both for an edge case the bare numbers don't explain); none of these four has that shape. The registry/ledger mismatch for Mortal Kombat: Shaolin Monks and the superseded classifier read for Cel Damage (next section) are recorded here, not duplicated into the page's free-text column — the same place compat1017/b/c kept that kind of explanation. |

**Every ledger number cross-checked against the ledger row's own prose and
the live registry; the one disagreement found (Mortal Kombat: Shaolin
Monks) was resolved in the ledger's favor, per precedent, and nothing in
any of the four rows was invented.**

Stop rule honored: no generator failure repeated twice for the same cause
(one `--check` refusal, for the one documented cause: the four missing
playable rows).

## Cel Damage: an older negative classifier read, now superseded

`pm/title-registry.tsv`'s row for `45410011` still carries a `hold_detail`
field from 2026-10-07 lane.local: the same run (`n-45410011-1007`) "PASSED
the harness... but frames 047-070/109 show the car pressed against a canyon
wall... the player never drove. Not Playable." That read is from before any
human frame review of this run; the 2026-10-18 ledger row is exactly that
frame review, done by lane.pathfind, of the full 33 held/contact-sheet
frames (not just the ones the earlier note cited), and it reaches the
opposite conclusion: "vehicular combat across a canyon/desert/town/
train-track course... live driving/combat resuming after each; no
corruption seen." The registry's `status` column already reads `PLAYABLE`
("in pm/playable-accepted.tsv (2026-10-18)"), so the ruling is already
banked outside this lane; the stale `hold_detail` text lives in
`pm/title-registry.tsv`, a generated file outside this lane's `Files:` (not
edited). Checked for any copy of that superseded "never drove" read inside
this lane's writable files (`compat_notes.tsv`, `COMPATIBILITY.md`,
`compatibility.csv`, `targets.toml`): none exists — Cel Damage has never
had a row on the compatibility page before this session (confirmed by
`grep` before editing).

## Step 4: `targets.toml`

Checked all four title_ids against `docs/testing/titles/targets.toml`:

- **Mortal Kombat: Shaolin Monks** (`4D570029`, line 668-672): `notes`
  ended "Not yet device-proven." Stale now that the title is Playable.
  Updated to record what's now true: Playable per the 2026-10-18 ledger
  (pathfind held run `sweep-4D570029`, 10-06, frame-reviewed; 603.9 s of
  play, window median 39.89 fps, 100% at or above the 30 fps bar, one
  115.7 ms hitch after warm-up). Left the rest of the `notes` field (the
  route/benchmark description) untouched.
- **Cel Damage** (`45410011`): no entry at all in `targets.toml` (checked
  by title_id and by name). Nothing to change.
- **Micro Machines (Europe)** (`4947001C`): no entry at all. Nothing to
  change.
- **Lemony Snicket's A Series of Unfortunate Events (USA)** (`4156001F`):
  no entry at all. Nothing to change.

Same shape as compat1017b's Pac-Man World 2 and compat1017c's NBA Live 07
before its own edit: the brief's step-4 instruction only applies where an
entry exists, and here only one of the four has one.

## Row insertion

Inserted after the last existing `playable` row (NBA Live 07, line 92) and
before the `below_bar` section starts (Turok Evolution, line 93), matching
the file's CRLF line endings, using a small Python script that opens with
`newline=""` and indexes the exact line (the method compat1017b and
compat1017c used, avoiding compat1017's row-ordering splice bug on mixed
line endings). Order follows the ledger's own row order (2026-10-18 block,
top to bottom):

```
playable	4D570029	Mortal Kombat: Shaolin Monks	?	none	nova	39.89	1.0	603.9	2026-10-06	
playable	45410011	Cel Damage	?	none	nova	29.9	0.9815	1082.1	2026-10-07	
playable	4947001C	Micro Machines (Europe)	Europe	filename	nova	59.94	1.0	672.9	2026-10-14	
playable	4156001F	Lemony Snicket's A Series of Unfortunate Events (USA)	USA	filename	nova	59.88	1.0	606.8	2026-10-11	
```

## Verification

- `python3 docs/testing/compat_page.py --ledger /home/justin/hakux-work/pm/playable-accepted.tsv --registry /home/justin/hakux-work/pm/title-registry.tsv --notes docs/testing/compat_notes.tsv --check`: before the edit, refused naming all four titles as missing; after the row insert, refused a **second, distinct** cause (see below); after resolving that, up to date.
- `python3 docs/testing/compat_page.py ...` (no `--check`, writes the files): 95 playable / 18 below_bar / 11 not_playable.
- `python3 docs/testing/compat_page_selftest.py`: 19 tests, OK.
- `python3 docs/testing/title_registry.py check --pages`: exit 3 (not an error on this lane's files) -- `README.md`: numberless Playable line, OK. `COMPATIBILITY.md` header and table rows: 95, matches. `Wall`: 95, matches. `status page`: 95, matches (an earlier run before this edit finished showed 91 there; it caught up on its own, outside this lane, by the time the edit was done). The only remaining line is `STALE registry sources changed since it was built` -- `pm/title-registry.tsv`'s own `sources_digest` predates this session's edits to `compat_notes.tsv`, the same digest-staleness shape compat1017b/c both hit; not a defect in this lane's files, closes on the next rebuild.
- `bash docs/testing/preflight.sh`: **territory FAILS** -- `territory.toml` double-claims `docs/testing/compat_notes.tsv`/`docs/compatibility.csv`/`docs/COMPATIBILITY.md` against the folded, `standing=false` `[lane.compat1017c]` (fold commit `440d148b7a`, confirmed an ancestor of `origin/master`), and `docs/testing/titles/targets.toml` against the folded, `standing=false` `[lane.topspinroute1018]` (fold commit `6bd7ed71f3`, also confirmed an ancestor). Neither lane ever released these rows. Filed `dispatch/board-requests/compat1018.md` asking the board to release all four, per the lane contract (never hand-edit `territory.toml`). Every other step -- `psh_differ`, `aci_vmstate`, `nv2a index`, `coverage`, `board files` -- passes.

## A second, distinct generator failure: a BELOW_BAR title landed from concurrent work, and two others stopped qualifying

After inserting the four playable rows, `compat_page.py` refused again, for a
different, unlisted cause (not a repeat of the first -- the stop rule
doesn't apply): `pm/title-registry.tsv` already carries a fifth title,
Buffy the Vampire Slayer (`45410012`), with `status=BELOW_BAR` and
`failing_all=fps` (the sole qualifying shape `below_bar_qualifies()`
checks), and no `compat_notes.tsv` row -- the same "second, unlisted cause"
shape compat1017 documented for its four below_bar titles. Added it the
same way: no ledger entry, so `tested` uses the registry's `last_run_utc`
date (`2026-10-18`) directly; `fps_median`/`time_at_bar`/`gameplay_s` from
the registry's `fps_window_median`/`fps_ok_share`/`play_s` (`play_s` is
blank in the registry for this run, so `gameplay_s` is left blank too, same
as the existing ATV Quad Power Racing 2/Genma Onimusha/Family Guy rows);
region `?`/`none` (no local archive/filename match found for `45410012` or
"Buffy"; a well-known licensed AAA title, no websearch, same precedent
compat1017/b/c used for Rayman 3/Marvel Nemesis/NBA Live 07); device `nova`.

Regenerating again surfaced a **third**, also-distinct cause: `compat_notes.tsv`
already listed two below_bar titles -- Amped 2 (`4D530041`) and Forza
Motorsport (`4D53006E`) -- that no longer qualify against the live registry.
Checked both: Amped 2's current registry row has `failing_all=duration+hitch`
(not `fps` alone; was previously a pure-fps row, confirmed by the brief's own
documented history for this title in its `hold_detail` field), Forza
Motorsport's is `failing_all=duration+fps`. `below_bar_qualifies()` requires
`failing_all == "fps"` exactly, so neither qualifies any more -- a fresh
verdict landed in the shared registry (the same 2026-10-18 `z-1792324...`
dispatch batch as Buffy's and Mortal Kombat: Shaolin Monks' rows, outside
this lane, between when the brief was written and this session) that moved
both from a clean fps-only failure to a combined cause. Removed both rows
from `compat_notes.tsv`'s below_bar section: `build_below_bar_rows()` raises
exactly this as a hard refusal (`compat_notes.tsv lists below_bar titles
that no longer qualify against the registry`), it is not optional, and the
same "a combined cause means gameplay was not cleanly confirmed, so it is
correctly left off the page" rule compat1017c applied to Mortal Kombat:
Deadly Alliance applies here -- neither title is CRASH_OR_HANG either, so
both are simply absent from every section now, matching their real,
unresolved state. Confirmed by `grep` that no stale copy of either row was
left anywhere in `compat_notes.tsv`, `COMPATIBILITY.md` or `compatibility.csv`.

This is still only two *distinct* causes beyond the brief's four titles (the
missing-below_bar-row cause, and the no-longer-qualifies cause), not the
same cause recurring -- the stop rule was not tripped.

## Selftest

No selftest.d fragment reads `compat_notes.tsv`, `targets.toml`,
`COMPATIBILITY.md` or `compatibility.csv`; `compat_page_selftest.py` is not
a selftest.d fragment and the fold only runs named fragments — same
precedent compat1017/b/c all record. `Selftest: none` in `PR.md`.
