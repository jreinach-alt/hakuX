# compat1017b: the compatibility page catches up from 88 to 90 Playable

State: ready

Lane: compat1017b             Issue: #433 (0.5: 50 Playable)
Base: master @ ad567fae7e
Files: docs/lanes/compat1017b/**, docs/testing/compat_notes.tsv, docs/compatibility.csv, docs/COMPATIBILITY.md, README.md, docs/testing/title_registry.py, docs/testing/title_registry_selftest.py
Prediction: none: analysis-only, docs-only lane, no device time
Needs device: no    Needs NDK: no
Selftest: none -- data plus a page check no selftest.d fragment runs; title_registry_selftest.py (6 tests, run directly) covers the new README check.

## What this does

`docs/testing/compat_page.py` refused to run: `pm/playable-accepted.tsv`'s three
newest rows (Dead or Alive 3, Mortal Kombat: Deadly Alliance, Pac-Man World 2) were
missing from `docs/testing/compat_notes.tsv`. Added all three, following the method
in `docs/lanes/compat1017b/NOTES.md`'s Step 0 table (region: checked the one local
archive filename listing, no usable match for any of the three; fps/time-at-bar/
gameplay_s from the matching registry run, falling back to the ledger's own precise
prose only where the registry had a blank field; tested date from the run date the
ledger evidence names, not its banking-date column).

**Mid-session scope change** (lane.local, cross-session message, 2026-10-17 ~23:50
PDT): the owner reversed Mortal Kombat: Deadly Alliance's ruling -- not Playable,
#1058's flat-white arena rendering defect keeps it out. `pm/playable-accepted.tsv`
was reverted live to 90 rows with no 4D57000C row. This PR removed the row it had
just added for that title and regenerated: **90 Playable**, not 91. Mortal Kombat:
Deadly Alliance is correctly absent from every section of the page (not `below_bar`
either -- it fails `hitch`, not `fps`, so `below_bar_qualifies()` leaves it off,
matching its real, unconfirmed state).

`docs/testing/titles/targets.toml`: checked all three title_ids for "pending" /
"single-stall" / "awaiting owner" wording to update. None of the three needed a
change -- Dead or Alive 3's and Mortal Kombat: Deadly Alliance's existing `notes`
are about unrelated investigations (a Thor heat-misdiagnosis writeup; a benchmark
route note), and Pac-Man World 2 has no `targets.toml` entry at all. Left the file
untouched; not in this PR's `Files:` line for that reason.

`README.md`: fixed the one line carrying the Playable count (88 -> 90), nothing
else touched. Grepped `docs/` and `README.md` for other stale "88 Playable" counts
and for the three titles being described as failing/unconfirmed elsewhere: none
found in-scope (hits were all technical investigation writeups using these titles
as measurement subjects, not compatibility-status claims, and outside this lane's
`Files:` regardless).

## Checks

| Check | Result |
|---|---|
| `compat_page.py` (generate) | runs clean, 90 playable / 19 below_bar / 11 not_playable |
| `compat_page.py --check` | up to date |
| `compat_page_selftest.py` | 19 tests, OK |
| `title_registry.py check --pages` | FAILs on `pm/title-registry.tsv` staleness (built before the ledger's latest bank; a scratch `/tmp` rebuild confirms it would read 90 once rebuilt) -- not a defect in this PR's files, filed to the board |
| `preflight.sh` | territory FAILs: this lane's seven files are double-claimed by the folded, unreleased `[lane.compat1017]`; filed to the board |

## Board requests

`dispatch/board-requests/compat1017b.md`: release this lane's files from the folded
`[lane.compat1017]` territory row; note on the registry staleness above.

Release note (none): docs-only compatibility-page update; nothing a player sees change in the emulator itself.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

## README line restored (found after the first push)

compat1017 rewrote README line 15 into "**[88 Playable games](...)** so far ... 88 games rated Playable." host-tools/home_page.py matches the numberless line ("**Games rated Playable so far:** [the list, with progress charts](.../blob/home/STATUS.md).") and writes the count from STATUS.md into home; against the numbered line every home update since 23:00 PDT failed, so the public README and STATUS.md stayed at 88. This PR puts the numberless line back (the count is home's, owner 10-16) and makes `title_registry.py check --pages` require that exact line instead of reading a number out of the README (the old check was the reason the number was added). The Playable count itself is on home's STATUS.md and the compatibility page.
