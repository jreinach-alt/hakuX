# titledb1014: title_id as the join key, one table, every reader reads it (#433)

State: draft

Lane: titledb1014            Issue: #433
Base: master @ 76bef8b162
Files: docs/testing/title_registry.py, docs/testing/jobs/status_html.py, docs/testing/jobs/selftest.d/60-status.sh, docs/testing/jobs/selftest.d/64-status-html.sh, docs/testing/jobs/selftest.d/65-status-objective.sh, docs/testing/jobs/selftest.d/66-status-titles.sh, docs/testing/jobs/selftest.d/67-status-measured.sh, docs/testing/jobs/selftest.d/68-status-curve.sh, docs/testing/dispatch_gate_selftest.py, docs/lanes/titles05/fixture/synth.py, README.md, docs/COMPATIBILITY.md, docs/lanes/titledb1014/**
Prediction: none: analysis/tooling change, no device arm
Needs device: no    Needs NDK: no

## Part 1 -- keying

`title_registry.py` already resolved every source to a `title_id` correctly
(its `Catalog.resolve()` handles exact normalized-name matching and the
ISO-stem title-id prefix). A real build (`python3 docs/testing/title_registry.py
build --root /home/justin/hakux-work --out <scratch> --no-forge`) produced:

966 rows; PLAYABLE 72, EXCLUDED 28, PENDING_OWNER 1, CRASH_OR_HANG 15,
BELOW_BAR 68, FAILED_HARNESS 47, VOID 0, UNSCREENED 735.

UNRESOLVED names: none.
Duplicate-spelling titles (one title_id, two names in different sources):
none found in `title_registry.py`'s own build -- its resolver already merges
them into one row. SpongeBob (5451001A) is a single PLAYABLE row there.

The defect was downstream, in `status_html.py`'s own name-joining code,
which never consulted that resolver: `titles05()` keyed
`already-on-handhelds.json`, the backfill and verdict rows by raw name,
bridging spellings only with an in-session substring/endswith heuristic
that does not reach "Nickelodeon SpongeBob SquarePants Battle for Bikini
Bottom USA" from "SpongeBob SquarePants: Battle for Bikini Bottom".

Fix: `status_html.py` now builds `title_registry.py`'s `Catalog` once per
render (`_title_catalog`, also folding in the Playable ledger's own
spellings) and resolves every name through it at a single chokepoint
(`canon()`), before it keys a row. The old in-session matching stays as a
fallback for names the catalog has never seen. `title_registry.py`'s
`Paths.targets` now honors `TITLE_TARGETS`, like its sibling modules, so a
fixture build can't leak the real `targets.toml`.

`title_registry.py`'s `Paths.targets` fix and the `status_html.py` rework
are committed together (f1e1ee18f9) because the second depends on the
first for test isolation; they are not two logically separate changes.

## Part 2 -- status page

Ran the lane's six selftests (60/64/65/66/67/68) against the fixed code:
all pass except one pre-existing, unrelated failure in 60-status.sh
("status shows the arms refusal in full"), confirmed present on unmodified
`master` too (reverted both files, reran, same failure; restored the fix).

A SpongeBob-style two-spelling falsifier and the "N copied/not copied"
line's independence from Playable rows are still being added as an
explicit selftest case (see NOTES.md); this PR will be updated before it
is marked ready.

## Remaining

Parts 3 (other readers: hourly_report.sh, Wall sync check, prequeue.py,
README.md, COMPATIBILITY.md), 4 (`title_registry.py check --pages` +
mutant test) and the rest of Part 2 (explicit falsifier selftest, column
additions to the registry) are in progress -- see
`docs/lanes/titledb1014/NOTES.md` for status and the territory
clarification (the lane's file list lives in the root `territory.toml` on
the `board` ref, not `docs/testing/territory.toml`).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
