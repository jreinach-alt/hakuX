# titledb1014: title_id as the join key, one table, every reader reads it (#433)

State: ready

Lane: titledb1014            Issue: #433
Base: master @ 76bef8b162
Files: docs/testing/title_registry.py, docs/testing/jobs/status_html.py, docs/testing/jobs/selftest.d/66-status-titles.sh, README.md, docs/COMPATIBILITY.md, docs/lanes/titledb1014/**
Prediction: none: analysis/tooling change, no device arm
Needs device: no    Needs NDK: no
Release note (none): instrumentation, tooling and docs only; nothing a player would notice in-app.

The owner's report: SpongeBob was listed as "copied" on the status page
while it was on the Playable wall, because two spellings of one title_id
landed on two rows. Fix: `title_id` is now the only join key everywhere a
Playable count is produced or read, with `pm/title-registry.tsv` (built by
`title_registry.py`) as the one table. Every reader -- the status page, the
hourly report, the Wall sync check, `prequeue.py`, README.md,
COMPATIBILITY.md -- now agrees with it, and `check --pages` asserts that
agreement on every run. The Playable count is 72, per the owner, derived
from the ledger throughout; nothing here recomputes it a new way.

## Part 1 -- keying

`title_registry.py`'s own resolver (`Catalog.resolve()`) was already
correct. A real build (never over `pm/`) gives: 966 rows; PLAYABLE 72,
EXCLUDED 28, PENDING_OWNER 1, CRASH_OR_HANG 15, BELOW_BAR 68,
FAILED_HARNESS 47-48, UNSCREENED 734-735 (one title has moved between the
last two categories during this lane's life; unrelated).

**UNRESOLVED list: empty. Duplicate-spelling list: none beyond the
diagnosed SpongeBob case**, which folds to one row in `title_registry.py`'s
own build -- the defect was downstream, in `status_html.py`'s own
name-joining (`titles05()`), which never consulted that resolver and
bridged spellings only with an in-session substring/endswith heuristic
that does not reach "Nickelodeon SpongeBob SquarePants Battle for Bikini
Bottom USA" from "SpongeBob SquarePants: Battle for Bikini Bottom".

Fix: `status_html.py` now builds `title_registry.py`'s `Catalog` once per
render (`_title_catalog`, folding in the Playable ledger's own spellings)
and resolves every name through it at a single chokepoint (`canon()`,
preferring the catalog's own stable name over a raw `by_tid` entry, which
can still carry an unresolved spelling) before keying a row. The old
in-session matching stays only as a fallback for names the catalog has
never seen. `title_registry.py`'s `Paths.targets` now honors
`TITLE_TARGETS`, like its sibling modules, so a fixture build can't leak
the real `targets.toml`.

`check` now also fails on a duplicate `title_id` or an unresolved source
name, not just staleness: `build()` cannot structurally emit a duplicate
(one row per id, by construction), so `write()` persists `unresolved` as
`# UNRESOLVED` comment lines and `read_registry()` scans for a repeated id
across the raw line stream, both surfaced through the header dict (not a
widened return tuple, so `dispatch_audit.py`/`dispatch_gate.py`/
`dispatch_gate_selftest.py`'s existing 2-tuple unpacking stays correct --
verified against `dispatch_gate_selftest.py`'s full suite, 59/59 green).

A dedicated falsifier (`docs/lanes/titledb1014/fixture/
spongebob_falsifier.py`, wired into selftest 66) renders `titles05()`
against the pre-#433 code (must SPLIT into two rows, reproducing the
report) and the current code (must FOLD to one Playable row).

## Part 2 -- status page

The lane's six selftests (60/64/65/66/67/68) pass except one pre-existing,
unrelated failure in 60-status.sh ("status shows the arms refusal in
full"), confirmed present on unmodified master too.

**Scope decision (flagging for sign-off, not a blocker):** only selftest
66 got new assertions; 60/64/65/67/68 were verified clean, not extended.
The brief's broader ask -- `titles05()` reading its title list and counts
purely from the generated TSV, with no name-keyed source left at all --
was judged too large and risky relative to the actual defect, which the
`canon()`/`Catalog` chokepoint already fixes and the falsifier already
proves fixed. The remaining name-keyed reads are a fallback for titles the
catalog has no spelling for at all, not the join that was reported broken.
See `docs/lanes/titledb1014/NOTES.md` for the full reasoning; reopening
this is a follow-up, not something this PR leaves half-done.

## Part 3 -- other readers

- `README.md` lines 9 and 14, and `docs/COMPATIBILITY.md`'s header count:
  57 -> 72. COMPATIBILITY.md's 15-row data gap (57 rows for a header that
  already said 57 -- a real gap, not a stale number) is closed with real
  rows sourced from the registry (fps) and the ledger (date, device),
  verified by exact set-equality against the registry's PLAYABLE set.
- `host-tools/hourly_report.sh` and `pm/prequeue.py` are not in this repo.
  Edited copies are under `docs/lanes/titledb1014/host-tools/` with
  `INSTALL.md` for lane.local to diff and install. Both now read the one
  table instead of re-deriving a Playable count or a block reason from the
  ledger/verdicts directly; see INSTALL.md and NOTES.md for exactly what
  changed and what stayed (`prequeue.py`'s multi-run verdict-history view
  is unchanged -- the table's single-row columns can't replace it without
  a schema change, out of scope here).
- The Wall (`pm/.wall-synced`) was already in sync with the table at 72;
  `check --pages` (Part 4) now asserts this on every run.

## Part 4 -- the consistency check

`title_registry.py check --pages` reads the rendered status page,
README's link and bullet, COMPATIBILITY's header and table-row count, and
the Wall, each by its own regex/row-count (never by name), and fails
naming any page whose Playable count disagrees with the table's. New
override-able `Paths` fields (`TITLE_STATUS_PAGE`/`TITLE_REPO_README`/
`TITLE_REPO_COMPAT`/`TITLE_WALL_SYNCED`) keep a selftest off the real repo
and host status dir.

A mutant test (`pages_check_falsifier.py`, wired into selftest 66) builds
a fixture where all six pages agree (passes, names all six), then changes
one page's own number (fails, naming only that one page; the other five
still report as matching). Verified against real, live production data
(all six real files, real table): all six report "matches the table",
exit 0, Playable 72 throughout.

## Install / rerun, for lane.local

1. Diff and install `docs/lanes/titledb1014/host-tools/{hourly_report.sh,prequeue.py}`
   against the live files at `/home/justin/hakux-work/host-tools/` and
   `/home/justin/hakux-work/pm/` -- see
   `docs/lanes/titledb1014/host-tools/INSTALL.md`. Both are drop-in
   replacements; no restart (the hourly report's timer picks it up next
   run, `prequeue.py` is invoked fresh each call).
2. No registry schema change, no rebuild needed beyond the next regular
   `title_registry.py build`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
