# compat1017b (#433 Part 4)

## Step 0: Already-tried table

Read `docs/lanes/compat1017/NOTES.md` (on master, folded by `ad567fae7e`) in full:
it did this exact job for 31 ledger titles plus Marvel Nemesis, and documents the
column-filling method, the owner-play `last_run` mismatch pitfall, a row-ordering
splice bug (fixed, not repeated here since this lane inserts with a small Python
script that explicitly indexes the line after the last `playable` row, not a
blind text split), and the two preflight FAILs (territory, coverage) it filed
to the board instead of hand-editing `territory.toml`/`nv2a_issues.toml`.

| Column | Source | Confirmed this session |
|---|---|---|
| `title_id` | the ledger row's own `title_id` | `compat_page.py` joins `pm/playable-accepted.tsv` to `compat_notes.tsv` by `title_id` only; a ledger title_id with no matching notes row is a hard refusal (confirmed: ran `compat_page.py --check` before any edit, it refused naming exactly the three titles in the brief) |
| `title` | ledger `title` text, verbatim | — |
| `region` | filename > archive-list exact match > websearch > `?`/`none` | checked `/mnt/d/hakux-staging/xiso` (the only local archive filename listing found) for all three title_ids: no match for Dead or Alive 3 (4D53002D) or Mortal Kombat: Deadly Alliance (4D57000C); one match for Pac-Man World 2 (`4E4D0006-Pac_Man_World_2.xiso.iso`) but the filename itself carries no region tag (unlike e.g. `...Europe_En_Fr_De_Es_It...`), so it settles nothing -- treated the same as no match. No websearch done (brief didn't ask for one this time, unlike compat1017's). All three stay `?`/`none`. |
| `device` | ledger run text ("Nova") | lowercased to `nova` to match existing row casing |
| `fps_median` | the registry's `fps_window_median` for the run the ledger cites, when `last_run_utc`'s date matches the run date in the ledger's own evidence text | checked `pm/title-registry.tsv` for all three title_ids before filling anything in: `last_run_utc` matched the ledger-cited run date in all three cases (no mismatch pitfall triggered this time) |
| `time_at_bar` | registry `fps_ok_share` for the matching run | same match check as above |
| `gameplay_s` | registry `play_s` for the matching run; when the registry's `play_s` is blank for that run (Dead or Alive 3's case), the ledger's own precise prose figure, never invented | Dead or Alive 3's registry row has `play_s` empty (checked by direct field-indexed Python read, not a column-count guess) even though `fps_ok_share`/`fps_window_median` are populated for the same run -- used the ledger's own "775 s of gameplay" instead |
| `tested` | the run date named in the ledger's evidence text (the brief states this explicitly as "run 2026-10-12" etc., not the ledger's `date_pdt` banking-date column, which for these rows is the 2026-10-17 ruling date, not the run date) | verified: the registry's `last_run_utc` date portion for all three titles matches the brief's stated run date, so ledger evidence text, brief, and registry all agree |
| `notes` | free text, blank unless a reader needs it | Mortal Kombat: Deadly Alliance's #1058 white-arena defect -- moot, see below: that row was removed before it was ever rendered |

**Every ledger number cross-checked against both the ledger row's own prose and
the live registry (`pm/title-registry.tsv`); no disagreement found for any of the
three titles** (Dead or Alive 3: 100.0%/50.1 median/775 s matches registry
`fps_ok_share=1`/`fps_window_median=50.13`/ledger prose exactly; Pac-Man World 2:
100.0%/59.9 median/595 s matches registry `fps_ok_share=1`/`fps_window_median=59.94`/
`play_s=594.8` exactly). Nothing in this row-filling step was invented.

Stop rule honored: no generator failure repeated twice for the same cause.

## Mid-session change of scope (lane.local, 2026-10-17 ~23:50 PDT)

After the three rows were added and the page regenerated once (91 Playable), a
cross-session message from lane.local arrived: the owner reversed Mortal Kombat:
Deadly Alliance's ruling -- it is **not** Playable (#1058, arena floors/walls draw
flat white). `pm/playable-accepted.tsv` was reverted live (by lane.local, not this
lane) to 90 rows with no 4D57000C row, confirmed by re-reading the file
(`tail`/`grep` both show the row gone). This lane:

- removed the Mortal Kombat: Deadly Alliance row it had just added to
  `compat_notes.tsv` (the file changed out from under this session once, by lane.local
  live-editing `pm/playable-accepted.tsv`, not `compat_notes.tsv` itself -- no
  collision on this lane's own files),
- regenerated the page: **90 Playable**, not 91,
- confirmed Mortal Kombat: Deadly Alliance is simply absent from every COMPATIBILITY.md
  section (not `below_bar` either -- `below_bar_qualifies()` requires
  `failing_all == "fps"` exactly, and this title's registry row fails `hitch`, not
  `fps`, so it is correctly left off per the page's own "inconclusive runs are left
  off, not guessed at" rule, matching its real state: a single-stall BELOW_BAR title
  with a known rendering defect, never confirmed Playable),
- fixed README's count to 90 instead of 91 (below),
- checked `docs/testing/titles/targets.toml`'s existing Mortal Kombat: Deadly Alliance
  and Dead or Alive 3 sections (see below) -- neither needed a change, so the
  "stall ruled loading but #1058 keeps it from Playable" wording lane.local asked
  for, conditional on existing pending/single-stall text, was never applicable.

## Step 4: `targets.toml` -- nothing to change

Checked all three title_ids against `docs/testing/titles/targets.toml`:

- **Dead or Alive 3** (`4D53002D`, line 67): has a `notes` field, but it is entirely
  about a 2026-09-30 Thor mis-diagnosis investigation (Daijishou regaining display
  focus mid-run, misread as a heat stop) and an `#431` fps-target citation. No
  "pending" / "single-stall" / "awaiting owner" wording anywhere in it. Left
  untouched.
- **Mortal Kombat: Deadly Alliance** (`4D57000C`, line 644): `notes` is a single
  sentence about the `gen-mk-deadly-alliance` classifier-path benchmark route, "not
  yet device-proven." No wording about the stall ruling, Playable status, or #1058
  either. Left untouched -- correct either way, since the title stays non-Playable.
- **Pac-Man World 2** (`4E4D0006`): **no entry at all** in `targets.toml` (checked by
  title_id and by name, including an `(En,...)` variant spelling; no match).

Brief's instruction was to change *that* sentence only, where it exists; it doesn't
exist for any of the three, so no edits were made to this file. Listed here rather
than silently skipped.

## Step 5: other stale references

`grep -rln` for the three titles' names across `docs/` and `README.md` turns up
`docs/investigations/*.md` (audio/vblank/pgraph-skew profiling writeups),
`docs/HISTORY.md` (a startup-time-reduction table), `docs/testing/nv2a_issues.toml`,
various `docs/testing/titles/pathknow/` hint files, and route/prediction files under
`docs/testing/`. None of these claim a Playable/failing/unconfirmed status for any
of the three titles -- they are technical measurement writeups (frame timing, audio
RMS, texture-cache exhaustion) that happen to use these titles as test subjects, with
zero compatibility-status language to correct. None of them are in this lane's
`Files:` list either (`nv2a_issues.toml` is explicitly off-limits; the others were
never granted), so even a stale status claim there would be a board matter, not an
edit here -- moot, since none exists.

The only stale "88 Playable" count found anywhere in-scope was `README.md`'s single
summary line (`**[88 Playable games]...88 games rated Playable.**`); fixed to 90.
No other README line or in-scope doc carried the old count.

## Verification

- `python3 docs/testing/compat_page.py --ledger pm/playable-accepted.tsv --registry
  pm/title-registry.tsv --notes docs/testing/compat_notes.tsv`: runs clean, 90
  playable / 19 below_bar / 11 not_playable.
- `... --check`: up to date.
- `python3 docs/testing/compat_page_selftest.py`: 19 tests, OK.
- `python3 docs/testing/title_registry.py check --pages`: **FAILs**, but not on
  anything this lane's files control -- `pm/title-registry.tsv` (generated, shared,
  outside this lane's `Files:`) was last built *before* `pm/playable-accepted.tsv`
  banked Dead or Alive 3 / Pac-Man World 2, so its own `PLAYABLE` row count is still
  88. A scratch rebuild to `/tmp` (never written to the live registry) with
  `title_registry.py build --no-forge` against current sources gives `PLAYABLE 90`,
  confirming this is a staleness gap that closes on the next real rebuild, not a
  defect in this PR's files. Filed to the board (below) so it isn't mistaken for
  one. The Wall still reads 91 (synced before lane.local's revert) -- also not this
  lane's file.
- `bash docs/testing/preflight.sh`: FAILs `territory` (all seven of this lane's
  files double-claimed by the folded `[lane.compat1017]`, which never released its
  rows). `coverage` is OK. Filed to the board (below), per the lane contract
  (never hand-edit `territory.toml`).

## Board requests filed

`dispatch/board-requests/compat1017b.md`: asks to release this lane's seven files
from the folded `[lane.compat1017]`'s `territory.toml` row, and notes the
`title_registry.py check --pages` staleness so it isn't misread as a defect.

## Selftest

No selftest.d fragment reads `compat_notes.tsv`, `targets.toml`, `COMPATIBILITY.md`
or `README.md`'s Playable count; `compat_page_selftest.py` is not a selftest.d
fragment and the fold only runs named fragments. `Selftest: none` in `PR.md`.
