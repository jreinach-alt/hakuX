# compat1017: catch up the compatibility page to the 88-row Playable ledger

State: ready

Lane: compat1017            Issue: #433 (0.5: 50 Playable)
Base: master @ 427164f2e050e12e6ddaa804646a8ff0c4f7efc7
Files: README.md, docs/COMPATIBILITY.md, docs/compatibility.csv, docs/lanes/compat1017/NOTES.md, docs/testing/compat_notes.tsv, docs/testing/titles/targets.toml
Prediction: none: analysis-only, docs-only lane, no device time
Needs device: no    Needs NDK: no
Selftest: none -- the change is data (a notes string in targets.toml, compat_notes.tsv, the page and CSV); no selftest.d fragment reads them. Covered instead by docs/testing/compat_page_selftest.py (19 tests, OK) and title_registry.py check --pages (Playable 88 on every page)

## What this does

`docs/testing/compat_page.py` refused to run: 31 titles from
`pm/playable-accepted.tsv` (88 rows) were missing from
`docs/testing/compat_notes.tsv`. Added all 31 as `playable` rows, following
the method documented in `docs/lanes/compat1017/NOTES.md`'s Step 0
already-tried table (region priority filename > archive > websearch > `?`;
`fps_median`/`time_at_bar`/`gameplay_s` from the registry's
`fps_window_median`/`fps_ok_share`/`play_s` for the run the ledger actually
cites, checked against the owner-play last_run mismatch pitfall; `tested`
from the ledger's `date_pdt`). 6 of the 31 rows have one or two fields left
blank rather than invented — listed in NOTES.md.

**Marvel Nemesis: Rise of the Imperfects (4541038A)** moves to Playable per
the owner's 2026-10-17 ruling (#851: "Move Marvel Nemesis to Playable in all
references... lots of titles were tested below 0.5.2 and we're not
downgrading them"). Its row renders exactly as the brief specified:
`playable,Marvel Nemesis: Rise of the Imperfects,4541038A,?,none,Nova,30.0,99%,601.9,2026-10-06,`.
`docs/testing/titles/targets.toml`'s `[titles."4541038A"]` notes line no
longer points at the pending `marvel-851` hold; it now says the hold is
released and why.

After the 31 rows, the generator refused a second time for a different
reason: `pm/title-registry.tsv` (shared, outside this worktree) already had
4 BELOW_BAR titles qualifying (`failing_all=fps`) with no notes row —
Burnout 3: Takedown, Stranger's Wrath, NBA Inside Drive 2004, NBA 2K7. These
landed from concurrent lane work (nearbar1017b) after the brief was
written, not from the brief's own list; added by the same method (no ledger
entry for any of the four, so `tested` uses the registry's `last_run_utc`
date directly). None has a clean single-region archive match, so all four
are `?`/`none`.

Regenerated `docs/COMPATIBILITY.md` and `docs/compatibility.csv` via
`compat_page.py`. Fixed the one `README.md` line that used to carry the
Playable count and had silently lost both numbers in an earlier unrelated
restructure (`[N Playable games]` / `N games rated Playable.`) — nothing
else in `README.md` touched, `docs/releases/` untouched.

No title was downgraded for being measured before 0.5.2 (owner 10-17
instruction) — every one of the 31 landed as Playable or BELOW_BAR exactly
as the ledger/registry already called it.

## Checks (all pass)

| Check | Result |
|---|---|
| `compat_page.py` (generate) | runs clean, no missing-title refusal |
| `compat_page.py --check` | up to date |
| `compat_page_selftest.py` | 19 tests, OK |
| `title_registry.py check --pages` | every page (status page, README.md link, README.md bullet, COMPATIBILITY.md header, COMPATIBILITY.md table rows, Wall) reads 88 and matches the registry's table count |

The only remaining line from `check --pages` is `STALE registry is N min
old` — a freshness warning about `pm/title-registry.tsv`'s build age,
unrelated to the page-count check this PR fixes and outside this lane's
writable files.

## preflight.sh: two board-state failures, filed as a board request

`preflight.sh` FAILs `territory` (five of this lane's files are still
double-claimed by the stale, never-started `[lane.compat1016]` and the
folded `[lane.release052c]`/`[lane.storydoc1017]` rows) and `coverage`
(`[issue.851]` says `status = "open"` though it isn't open on GitHub,
stale since before the owner's 2026-10-17 ruling). Both require editing
`territory.toml`/`nv2a_issues.toml`, which this lane may not do. Filed
`dispatch/board-requests/compat1017.md` with the exact asks. Every check
this lane can run directly on its own files passes (table above); these two
are the board's to apply.

[lane.compat1017] waiting: `dispatch/board-requests/compat1017.md` applied
(territory.toml releases for compat_notes.tsv/compatibility.csv from
compat1016 and README.md/COMPATIBILITY.md/compat_page.py from release052c,
plus #851's status corrected in nv2a_issues.toml), then a clean
`preflight.sh` run on this branch.

Release note (none): docs-only change, no emulator code touched.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
