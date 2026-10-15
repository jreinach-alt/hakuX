# lane.titledb1014 notes (#433)

## Territory clarification

The lane's file list is in the **root-level `territory.toml` on the `board`
ref** (`git show board:territory.toml`), not `docs/testing/territory.toml`
(a different, unrelated file by the same name -- the worktree's own copy of
that one never mentions this lane). `[lane.titledb1014]` there lists:

```
docs/lanes/titledb1014/**, docs/testing/title_registry.py,
docs/testing/dispatch_gate_selftest.py, docs/testing/jobs/status_html.py,
docs/testing/jobs/selftest.d/{60-status,64-status-html,65-status-objective,
66-status-titles,67-status-measured,68-status-curve}.sh,
docs/lanes/titles05/fixture/synth.py, README.md, docs/COMPATIBILITY.md
```

Everything touched (listed in PR.md's `Files:`) is a subset of this.
`dispatch_gate_selftest.py` and `synth.py` were in territory but never
needed changes -- `read_registry()`'s two external-caller-safe additions
(below) were verified against the existing `dispatch_gate_selftest.py` as
a regression check, not edited.

## Part 1 -- keying (done)

`title_registry.py`'s own resolver (`Catalog.resolve()`) was already
correct: a real build finds no UNRESOLVED names and no duplicate-spelling
title_ids.

```
python3 docs/testing/title_registry.py build --root /home/justin/hakux-work \
  --out <scratch> --no-forge
```

Current real counts: 966 rows; PLAYABLE 72, EXCLUDED 28, PENDING_OWNER 1,
CRASH_OR_HANG 15, BELOW_BAR 68, FAILED_HARNESS 48, VOID 0, UNSCREENED 734
(one title moved UNSCREENED -> FAILED_HARNESS between checks during this
lane's life; unrelated to this change). SpongeBob (5451001A) is one row,
PLAYABLE. **UNRESOLVED list: empty. Duplicate-spelling list: none beyond
the diagnosed SpongeBob case** (and that one folds to a single row in
`title_registry.py`'s own build -- the defect was downstream in
`status_html.py`, see below).

The defect lived in `status_html.py`'s `titles05()`, which keyed rows by
raw name from `already-on-handhelds.json`, the backfill and verdict.json,
bridging spellings only with an in-session endswith/substring heuristic
that doesn't reach "Nickelodeon SpongeBob SquarePants Battle for Bikini
Bottom USA" from "SpongeBob SquarePants: Battle for Bikini Bottom" (prefix
and suffix words break it).

Fix (f1e1ee18f9, then e293ab677e): `_title_catalog(F)` builds
`title_registry.py`'s `Catalog` once per render, folding in the Playable
ledger's own spellings. `titles05()`'s `canon(n, tid)` resolves through the
catalog first -- by title_id hint, then by the catalog's own stable name,
*not* `by_tid`'s raw entry (e293ab677e: `by_tid` can still carry the
unresolved ISO-stem spelling for a title the ledger reached first) --
falling back to the old in-session matching only when the catalog has no
answer. Every `add()` site passes through `canon()` before keying a row.

Side fix: `title_registry.py`'s `Paths.targets` now honors `TITLE_TARGETS`
(matching `titlestate.py` and `status_html.py`'s own override convention),
so a fixture-isolated selftest that makes `status_html.py` build a catalog
can't leak the real repo's `targets.toml`.

The SpongeBob falsifier (26f2c5abb0,
`docs/lanes/titledb1014/fixture/spongebob_falsifier.py`, wired into
selftest 66): builds one minimal tree with the two spellings, renders
`titles05()` against the pre-#433 `status_html.py` (ref `f1e1ee18f9~1`,
must SPLIT into a copied row and a Playable row -- reproducing the owner's
report) and against the current one (must FOLD to one Playable row). A
green run on the "old" half and a red run on the "new" half is the
falsifier: if either side ever stopped doing what it's supposed to, this
prints FAIL.

`check`'s duplicate-title_id and UNRESOLVED assertions (a02c2b5f31):
`build()` cannot structurally emit a duplicate row (one row per id, from a
dict keyed by id), so these facts have to survive from `build()` into the
written file for `check` (which only reads, never rebuilds) to see them.
`write()` now persists `unresolved` as `# UNRESOLVED\t<where>\t<name>\t<why>`
comment lines; `read_registry()` now also scans the raw line stream for a
repeated `title_id` (keeping the old silent-last-wins dict behaviour, but
now reporting the fact too). Both ride in the header dict as `_unresolved`/
`_duplicate_tids` rather than widening `read_registry()`'s 2-tuple return,
which `dispatch_audit.py`, `dispatch_gate.py` and
`dispatch_gate_selftest.py` all unpack as exactly 2 values. Verified against
a synthetic registry with one duplicate id and one UNRESOLVED line (both
correctly flagged, exit 3) and against `dispatch_gate_selftest.py`'s full
suite (59 legs, 59 green -- the 3 external callers are unaffected).

## Part 2 -- status page (done, with one scope decision -- see below)

Ran the lane's six selftests (60/64/65/66/67/68) against the fixed code
repeatedly through every commit in this lane: 136 checks, 1 pre-existing,
unrelated failure in 60-status.sh ("status shows the arms refusal in
full"), confirmed present on unmodified `master` too.

**Scope decision, needs owner/lane.local sign-off if it should go
further:** only selftest 66 got *new* assertions (the SpongeBob falsifier
and, this lane's last commit, the `check --pages` falsifier). 60/64/65/67/68
were run to confirm no regression but were not given new assertions of
their own. The brief's Part 2 also describes a fuller rewrite --
`titles05()` reading its title list and its "N copied/not copied/blocked/
soak pending/below 30/inputs ready" line purely from the generated TSV,
with *no* name-keyed source left in the function at all. That rewrite was
judged too large and too risky to attempt in this lane relative to the
actual defect (two spellings of one title_id landing on two rows), which
the `canon()`/`Catalog` chokepoint already fixes and the falsifier already
proves fixed: every `add()` site now keys through title_id before a name
is ever used for display. The remaining name-keyed reads in `titles05()`
(for titles the catalog has not learned any spelling for at all) are a
fallback path, not the join the owner reported broken. Reopening this
would be a `lane.titledb1014` follow-up, not a blocker on this PR.

## Part 3 -- other readers (done, 4e1dd28f68)

- `README.md` lines 9 and 14: 57 -> 72.
- `docs/COMPATIBILITY.md`: header count 57 -> 72, and the 15-row data gap
  that caused the stale count closed with real rows (fps from the registry,
  date/device from the ledger) -- verified by exact set-equality between
  the registry's PLAYABLE set and the table's rows (72 = 72, zero
  differences either direction).
- `host-tools/hourly_report.sh` and `pm/prequeue.py` are not in this repo.
  Edited copies are under `docs/lanes/titledb1014/host-tools/` with
  `INSTALL.md`, for lane.local to diff and install (statuspage1013's
  precedent). `hourly_report.sh`'s PLAYABLE block now counts
  `status == PLAYABLE` rows in the table instead of re-deriving the count
  from the ledger itself, and reports a `LEDGER/TABLE MISMATCH` if they
  ever disagree. `prequeue.py`'s ledger section no longer adds its own
  "already in the Playable ledger" block reason (the registry loop right
  above it already blocks on the same table's `status == PLAYABLE`); the
  evidence-text print stays, since the table has no per-row acceptance
  date or evidence text to replace it with. `prequeue.py`'s multi-run
  verdict-history view (the "last 4 distinct verdicts") is unchanged on
  purpose: the table's single `latest_verdict`/`fps_ok_share` columns carry
  only the most recent verdict, not the history this view shows -- would
  need a registry schema change, out of scope here.
- The Wall sync check: `pm/.wall-synced` was already in sync with the table
  at 72 before this lane touched anything; `check --pages` (Part 4) now
  asserts this on every run instead of it being a coincidence.

## Part 4 -- the consistency check (done, cab2bd0f78)

`title_registry.py check --pages` reads six sources -- the rendered status
page, README's link and bullet, COMPATIBILITY's header and table-row count,
and the Wall's `.wall-synced` -- each by its own regex/row-count (never by
name: a numbers cross-check, not another join) and fails naming any page
whose Playable count disagrees with the table's. New `Paths` fields
(`status_page`, `repo_readme`, `repo_compat`, `wall_synced`), each
override-able via `TITLE_STATUS_PAGE`/`TITLE_REPO_README`/
`TITLE_REPO_COMPAT`/`TITLE_WALL_SYNCED`, following the existing
`TITLE_TARGETS` convention, so the falsifier never has to touch the real
repo or host status dir.

`pages_check_falsifier.py` (wired into selftest 66): builds a fixture
registry (through the real `write()`/`Paths`/`sources_digest()`, so its own
digest matches what `check` recomputes -- a hand-rolled digest would make
`check` report STALE regardless of `--pages`) and six agreeing fixture
pages; confirms `check --pages` passes naming every page, then mutates one
page's own number (the README bullet) and confirms the check fails naming
only that one page, with the other five still reported as matching.

Verified against real, live production data (all six real files) with zero
discrepancies, exit 0.

## Not started / deferred

- The optional SQLite copy (`pm/title-registry.db`) mentioned in the brief
  as "if it makes the readers simpler" -- none of this lane's readers
  needed it; the TSV was sufficient for all of Part 3 and Part 4.
- New registry columns for status_html's remaining name-keyed fallback
  paths (see the Part 2 scope decision above).

## Never touched

`docs/lanes/x1port1012`, the Playable ledger rows, the Wall.
