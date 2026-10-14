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

Matches the brief's list (all six selftests, both docs files) plus
`dispatch_gate_selftest.py` and `synth.py`, which the brief didn't name
explicitly but are needed for Part 4's mutant test and the falsifier
fixture respectively. Proceeding on this list.

## Part 1 -- keying

`title_registry.py`'s own resolver (`Catalog.resolve()`) was already
correct: a real build found no UNRESOLVED names and no duplicate-spelling
title_ids. Real build, scratch output (never over `pm/`):

```
python3 docs/testing/title_registry.py build --root /home/justin/hakux-work \
  --out /tmp/titledb1014-scratch/title-registry.tsv --no-forge
```

966 rows; PLAYABLE 72, EXCLUDED 28, PENDING_OWNER 1, CRASH_OR_HANG 15,
BELOW_BAR 68, FAILED_HARNESS 47, VOID 0, UNSCREENED 735 -- matches the
brief's expected numbers exactly. SpongeBob (5451001A) is one row, PLAYABLE.

The defect lived in `status_html.py`'s `titles05()`, which keyed rows by
raw name from `already-on-handhelds.json`, the backfill and verdict.json,
bridging spellings only with an in-session endswith/substring heuristic
that doesn't reach "Nickelodeon SpongeBob SquarePants Battle for Bikini
Bottom USA" from "SpongeBob SquarePants: Battle for Bikini Bottom" (prefix
and suffix words break it).

Fix (committed f1e1ee18f9): `_title_catalog(F)` builds `title_registry.py`'s
`Catalog` once per render, folding in the Playable ledger's own spellings
(so a name the catalog build never saw, but the ledger has under a third
spelling, still resolves). `titles05()`'s `canon(n, tid)` resolves through
the catalog first (by title_id hint, then by name), falling back to the old
in-session matching only when the catalog has no answer. Every `add()` site
now passes through `canon()` before keying a row.

Side fix: `title_registry.py`'s `Paths.targets` now honors `TITLE_TARGETS`
(matching `titlestate.py` and `status_html.py`'s own override convention).
Without it, a fixture-isolated selftest that makes `status_html.py` build a
catalog would leak the real repo's `targets.toml`.

Verification: reran the registry build after the fix -- byte-identical
output except the timestamp. Full relevant selftest set
(`SELFTEST_ONLY="60-status 64-status-html 65-status-objective 67-status-measured 68-status-curve"`
plus 66 standalone): 134 checks, 1 failure (`status shows the arms refusal
in full` in 60-status.sh), confirmed pre-existing by reverting to baseline
and rerunning -- unrelated to this change.

## Still needed before Part 1/2 are "finished" (brief: deliver 1 and 2
finished rather than 3-4 half done)

- The explicit SpongeBob two-spelling falsifier fixture (old logic -> 2
  rows, new logic -> 1 PLAYABLE row), as its own selftest case.
- Registry columns the status page needs (copied-on-handheld, measured,
  below-bar, soak-pending, blocked), so status_html.py stops deriving them
  itself once Part 3 lands.
- `check`'s duplicate-title_id assertion as an explicit, tested error path
  (today there's no live duplicate because rows are built one-per-id by
  construction; the owner's design wants this asserted, not just true by
  accident).

## Not started

Part 3 (hourly_report.sh, Wall sync check, prequeue.py, README.md line 9/14,
COMPATIBILITY.md -- host-only files go under
`docs/lanes/titledb1014/host-tools/` with an INSTALL note), Part 4
(`title_registry.py check --pages` + mutant test), optional SQLite copy.

## Never touched

`docs/lanes/x1port1012`, the Playable ledger rows, the Wall.
