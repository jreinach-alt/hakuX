# compat1017 (#433 Part 4)

## Step 0: Already-tried table

Read `docs/lanes/compatpage1012` (NOTES.md + PR.md, on master) and
`docs/lanes/compatrefresh1013/PR.md` (that lane left no NOTES.md — confirmed
by `git log` on the path, nothing found) plus `git log -p -- docs/testing/compat_notes.tsv
docs/testing/compat_page.py` for how an existing `playable` row in
`compat_notes.tsv` was filled.

| Column | Source | How an existing row got it |
|---|---|---|
| `title_id` | ledger `title_id` (or `pm/title-registry.tsv` alias resolution) | `compat_page.py` joins by `title_id`, never by title text (compatpage1012's hard lesson) |
| `title` | ledger `title` text, verbatim | — |
| `region` | priority: 1) the tested disc image's own filename/request metadata ("filename"), 2) an exact single match in the archive filename list ("archive"), 3) a websearch that positively settles one region with zero counter-evidence ("websearch"), else `?` | compatrefresh1013's new rows used "filename" when the actual tested image's name carried a region; compatpage1012 established the archive-list fallback |
| `region_source` | one of `filename`, `archive`, `websearch`, `none` | same priority as above; `none` pairs with `region=?` |
| `device` | the ledger's run text ("Nova"/"nova") | `device_name()` capitalizes either case for display, so raw case in the TSV doesn't matter |
| `fps_median` | registry `fps_window_median` for the run the ledger cites | verified against existing rows; blank (via `fps1()`, which renders `""` for `None`) when the registry's `last_run` doesn't match the ledger's cited run |
| `time_at_bar` | registry `fps_ok_share` (NOT `play_share`) | verified against Azurik: Rise of Perathia's existing row |
| `gameplay_s` | registry `play_s` (the **play** window, not the full scored window which can include menus/cutscenes) | verified against Marvel Nemesis's own ledger evidence text, which distinguishes "601.9 s of play" from "scored 1073.9 s" |
| `tested` | for ledger-sourced (playable) rows: the ledger's own `date_pdt` (date portion) — verified against Alien Hominid. For registry-only (below_bar) rows with no ledger entry: the registry's `last_run_utc` date portion (verified against the existing Turok Evolution row, UTC date used as-is, no PDT shift) | — |
| `notes` | free text, left blank unless there's something a reader needs (e.g. `RED_OVERRIDES`-style exceptions) | — |

**Pitfall carried forward from this session**: for "owner-play" (hand-marked
analysis-copy) acceptances, the registry's auto-tracked `last_run`/numeric
columns often reflect a *different* run than the one the ledger actually
cites. Checked, for every new row below, whether the registry's `last_run`
path matches the ledger's cited run id; when it didn't, used the ledger's own
precise prose figures instead (never "about X" estimates), and left a field
blank rather than guess. **Never invent a number; a missing one is left blank
and listed** — see below for which rows have a blank field.

Stop rule honored: no generator failure repeated twice for the same cause
(the BELOW_BAR expansion below was a second *distinct* cause, not a repeat).

## The 31 ledger titles named in the brief

Added as `playable` rows to `compat_notes.tsv`, all device `nova`, in ledger
evidence order (2026-10-13 through 2026-10-16), ending with Marvel Nemesis:
Rise of the Imperfects exactly as the brief specified
(`playable,Marvel Nemesis: Rise of the Imperfects,4541038A,?,none,Nova,30.0,99%,601.9,2026-10-06,`
once rendered — raw stored values are `29.97`/`0.9888`).

Region sourced from the archive filename list (`region_source=archive`) for
22 of 31. For the other 9 — ATV Quad Power Racing 2, Burnout Revenge, Shrek
2, Harry Potter and the Philosopher's Stone, TimeSplitters 2, Genma
Onimusha, Family Guy Video Game, Rayman 3 Hoodlum Havoc, Marvel Nemesis —
region stays `?`/`none`: either no archive match, a websearch that turned up
more than one region with no way to prefer one, or (Rayman 3, Marvel Nemesis)
not searched at all per precedent (well-known worldwide multi-region AAA
titles the brief itself didn't ask to be searched; a search would only
confirm what's already assumed, per compatpage1012's rule for exactly this
shape of title).

Blank (never-invented) fields, left blank and listed here per the brief's
rule:
- ATV Quad Power Racing 2 (4143000A): `fps_median`, `gameplay_s` blank — registry's `last_run` doesn't match the ledger's cited owner-play run; the ledger prose doesn't state either figure precisely.
- Burnout Revenge (45410076): `fps_median` blank — same mismatch; ledger states `time_at_bar`/`gameplay_s` precisely so those are filled.
- Avatar: The Last Airbender (54510105): `gameplay_s` blank.
- Genma Onimusha (43430001): `fps_median`, `gameplay_s` blank.
- Manhunt (54540019): `time_at_bar` blank.
- Family Guy Video Game (545400B0): `gameplay_s` blank.

## A second, unlisted cause: 4 BELOW_BAR titles the generator also demanded

After adding the 31 rows, `compat_page.py` refused a second time, for a
different reason: `pm/title-registry.tsv` (a live file shared across lanes,
outside this worktree) already carries four BELOW_BAR, `failing_all=fps`
titles with no `compat_notes.tsv` row at all — Burnout 3: Takedown
(4541005B), Stranger's Wrath (4541006D), NBA Inside Drive 2004 (4D53000B),
NBA 2K7 (545400AE). None of these are in the brief's 31; they landed in the
shared registry from concurrent lane work (nearbar1017b's "three more
near-cap titles", folded just ahead of this lane's merge of
`origin/master`) between when the brief was written and this session.
`below_bar_qualifies()` is a hard requirement of the generator, not optional,
so these had to be added too, by the same method as the table above (no
ledger entry for any of the four, so `tested` uses the registry's
`last_run_utc` date directly): `fps_median`=`fps_window_median`,
`time_at_bar`=`fps_ok_share`, `gameplay_s`=`play_s`, device `nova`. Region:
no single clean archive match for any of the four (NBA Inside Drive 2004 has
two archive entries with different region labels — "(USA)" and "(USA,
Asia)" — an ambiguous match, treated the same as "none"), so all four are
`?`/`none`.

## Row ordering fix

The splice script that inserted the 31 new playable rows landed them one
line off — a stray `below_bar` row (Turok Evolution) ended up sandwiched
*before* the new block instead of after it, because the file mixes CRLF and
a few bare-LF line terminators and the splice script split strictly on
`\r\n`. `compat_page.py`'s own `read_tsv()` opens with `newline=""` and
`readlines()`, which is tolerant of mixed endings, so the misplacement never
broke the generator (it buckets by the `section` column value, not file
position) — but it was fixed anyway for readability, by moving the one
stray row with a text-mode (`newline=""`) script instead of a raw byte
split, which handles the mixed endings correctly.

## Other changes

- `README.md`: the one line that used to carry a Playable count
  (`[N Playable games](...)` / `N games rated Playable.`) had been reworded
  during an unrelated restructure and silently dropped both numbers. Changed
  only that line to carry both again: `**[88 Playable games](...)** so far,
  with progress charts — 88 games rated Playable.` Nothing else in the file
  touched; `docs/releases/` untouched.
- `docs/testing/titles/targets.toml`, `[titles."4541038A"]`: changed only
  the sentence that referenced the pending `marvel-851` hold, to record that
  it's released and why (owner ruling 2026-10-17: a stall with the guest and
  renderer both idle is loading, not a hitch) and that Marvel Nemesis is
  Playable per the ledger. Left the rest of the `notes` field (the #431/
  benchmark-route explanation) untouched.
- `docs/COMPATIBILITY.md` and `docs/compatibility.csv`: regenerated via
  `compat_page.py` from the updated `compat_notes.tsv`. 88 playable / 19
  below_bar / 11 not_playable.

## Verification

- `python3 docs/testing/compat_page.py --check ...`: up to date.
- `python3 docs/testing/compat_page_selftest.py`: 19 tests, OK.
- `python3 docs/testing/title_registry.py check --pages`: every page
  (status page, README.md link, README.md bullet, COMPATIBILITY.md header,
  COMPATIBILITY.md table rows, Wall) reads 88 and matches the registry's
  table count. The only remaining line from that command is `STALE registry
  is N min old` — a freshness warning about `pm/title-registry.tsv`'s build
  age, unrelated to the page-count check and outside this lane's writable
  files (the registry itself isn't something a docs lane rebuilds).
- No duplicate `title_id` values in `compat_notes.tsv` after all edits
  (checked via `cut -f2 | sort | uniq -d`); row counts reconcile exactly:
  84 original lines + 31 new playable + 4 new below_bar - 1 (moved, not
  added) = 119... actually 84 + 31 + 4 = 119 total lines, 88 playable + 19
  below_bar + 11 not_playable + 1 header = 119. Confirmed by direct
  `grep -c` per section.

## Selftest

`docs/testing/compat_page_selftest.py` is the compat page's own selftest;
all 19 fragments in it exercise `compat_page.py` end to end (row building,
rendering, `--check`) and all pass against the updated `compat_notes.tsv`.
No other selftest file is specific to the compat page.

## preflight.sh: territory + coverage FAIL, both board-state, both filed

`docs/testing/preflight.sh` FAILs two gates neither of which this lane can
fix directly (both require editing `territory.toml` or `nv2a_issues.toml`,
which a lane may not touch per the lane contract):

- **territory**: `docs/testing/compat_notes.tsv` and `docs/compatibility.csv`
  are still claimed by `[lane.compat1016]` (standing=false, never started —
  this lane's own territory note already says compat1017 replaces it, but
  the files were never released); `README.md`, `docs/COMPATIBILITY.md` and
  `docs/testing/compat_page.py` are still claimed by the folded
  `[lane.release052c]` (its own handoff note already says these go to
  compat1017/titlekey1016, but the release was never recorded); `README.md`
  is also listed by the folded `[lane.storydoc1017]`, whose own row says
  that overlap is expected and disjoint.
- **coverage**: `[issue.851]` in `nv2a_issues.toml` still has
  `status = "open"` though the issue isn't open on GitHub — stale since
  before the owner's 2026-10-17 ruling that resolved it (Marvel Nemesis to
  Playable).

Filed `dispatch/board-requests/compat1017.md` asking the board to release
the five files from the stale/folded rows and correct `#851`'s status.
Every check this lane can run directly (`compat_page.py`, `--check`,
`compat_page_selftest.py`, `title_registry.py check --pages`) passes; these
two preflight failures are the board's to apply, not a defect in this
lane's own files.
