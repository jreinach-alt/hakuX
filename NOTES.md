# lane.backlogstate — a backlog had no "available" state

Issue: none (harness defect, dispatched directly).
Prediction: none: harness script, no pixels claimed.

## What the defect actually is, and one correction to the brief

The brief says `fleet.py` treats any non-empty `blocked_on` as blocked, and
that this is why `DISPATCHABLE NOW, NOT DISPATCHED` read 0 at 06:22Z. **The
first half is not true and the second half has a different cause.**
`fleet.py:218` at master@bdeab36f75 already carried a prose sniff,
`if b and "NOT BLOCKED" in b.upper()`, present since the file was written
(d123e8b34f, 2026-09-13), so those six rows *were* reported dispatchable by
that path whenever their lane was not running.

`DISPATCHABLE NOW` read 0 because **all seven rows were owned by a lane whose
agent was running** — `#84` by lane.fold, `#85` by swizzle87, `#86` by remote,
`#88/#89/#91/#92` by blitsafe — and `fleet.py` skips those first (`if lane and
lane in lanes_with_agent: continue`). That skip is correct behaviour, not the
defect. I reproduced the 0 from the current board and fleet registry; the same
ownership held at 06:22Z (blitsafe and swizzle87 were 6.4h old, fold 8.5h).

**The defect underneath it is real and unchanged.** `check_coverage.py` had
exactly two ways to satisfy its gate — owned by a lane, or non-empty
`blocked_on` — and that gate makes `preflight` red for every lane on the
repository. A backlog's normal condition (open, unblocked, nobody on it yet,
waiting for capacity) could not be expressed at all, so the board wrote it into
the one field that means "do not dispatch this". The evidence is on the board
branch, not just in prose:

- `889f306bcb` "board: cover #107, #109-#112 — blocked_on rows for the
  preflight coverage gate" — the gate naming itself as the reason for the
  field's contents.
- six live-open rows whose `blocked_on` **opens** with "NOT BLOCKED":
  #84, #85, #86, #88, #89, #91.
- `check_coverage.py` counted all six as "with a written blocker" and printed
  `coverage ok`.
- the two deleted rows' "Blocked on local dispatch capacity this tick, not on
  anything technical." — which the `"NOT BLOCKED"` sniff does **not** match, so
  that shape was invisible to the dispatch trigger from both sides.

## What I built

A third state: **`dispatch_state = "available" | "blocked"`** on a tracker row.
"Available" is about the *obstacle*, not the owner — whether a lane is on it
stays territory.toml's business, which is why `fleet.py`'s running-lane skip
still applies on top of it.

- `check_coverage.py`: covered is now owned **or** non-empty `blocked_on` **or**
  `dispatch_state = "available"`. The gap gate is unchanged for an
  *unclassified* row and its message names all three ways out.
- `dispatch_state` costs something, because a value invented to satisfy a gate
  gets used to silence it. Four new failures: an unrecognised value;
  `available` with a non-empty `blocked_on`; `available` with `status != open`
  (the guard on the opposite failure — "finished work reading as available is
  how an issue gets re-dispatched", this script's own sentence about #56/#57/#61);
  `blocked` with nothing in `blocked_on`.
- a `blocked_on` whose **opening claim** asserts non-blockage is now a FAIL,
  scoped to live-open issues.
- `fleet.py`: `DISPATCHABLE NOW` is exactly the `available` rows not held by a
  running lane. The prose sniff is deleted. A new non-fatal section, `NEITHER
  BLOCKED NOR MARKED AVAILABLE`, shows rows that say nothing — coverage owns
  failing on those, and calling them dispatchable would assert more than an
  empty row supports.
- `docs/testing/jobs/selftest.sh`: a whole fake board (`$T/board` with copies of
  the three modules plus two toml files; `HAKUX_BOARD_REF=` makes board_files
  fall back to it) and 13 checks over seven variants of one row.

## Why the detector is anchored at the start of the field

Do **not** re-do this as a free-text search for `NOT BLOCKED|CLEARED`. Measured
over all 81 rows: that matches 14, and three of the matches are false in
different ways.

| row | matches on | what it actually says |
|---|---|---|
| #91 | "…ARE EXPLICITLY NOT BLOCKED BY THIS" | about **#84**, not itself |
| #92 | "I had written NOT BLOCKED and then left it unallocated" | the board recording a wording it had **already corrected** |
| #44 | "test-and-cleared" | a code fact about DIRTY_MEMORY_NV2A_TEX |
| #91 | "audit pass 2 cleared them" | about two commits |

`fleet.py`'s old sniff produced exactly that #92 false positive: a row the
board had deliberately written as an assignment was reported dispatchable on
the strength of a sentence describing a wording it no longer used. What all six
real cases have in common is a *position*, not a phrase — the field's own
leading claim. So the check looks at the first 90 characters. Two idioms that
cannot occur innocently ("not on anything technical", "dispatch capacity") are
matched anywhere.

## Verified against the code being replaced, not reasoned about

`SELFTEST_BOARD_SRC` points the new section at a directory of scripts. Run
against `origin/master:docs/testing/{check_coverage,fleet,board_files}.py`,
**4 of the 13 checks fail** and every one of those four is the defect:

```
  FAIL an explicitly AVAILABLE row is covered -- the third state
  FAIL fleet calls exactly the available row dispatchable
  FAIL a mid-text 'NOT BLOCKED' about another row is NOT dispatchable
  FAIL fleet does not call an unclassified row dispatchable
  FAIL a blocked_on that OPENS with NOT BLOCKED fails        (see below)
```

Every assertion is on the **output words**, never on the exit code: the old
`check_coverage.py` exits 1 on most of these variants too, for the wrong reason
(the available row reads as an uncovered gap). rc is far too coarse to tell the
fix from the defect here.

## The migration (7 rows, on the `board` branch only)

#84, #85, #86, #88, #89, #91 (required by the new gate) and #92 (not required —
its opening is an assignment record, not an assertion of non-blockage — but its
field was never a blocker either, so it moved with them). Each row: `blocked_on`
emptied, `dispatch_state = "available"` added, and the old text appended to
`status_note` **verbatim** behind a dated `MIGRATED 2026-09-19` marker saying
what field it came from and why.

Done by a script that parses before, parses after, and refuses to write unless

- the file still parses with `tomllib`,
- the row count is still exactly 81,
- **every row but the seven is byte-identical in its parsed form**, and
- each of the seven differs in exactly `blocked_on`, `status_note`,
  `dispatch_state`, with `status_note == old_note + MARK + old_blocked_on`.

Three board-file breakages in one session came from text slicing; this is the
in-memory parse the project's own rule asks for.

`blocker_falsifier` and `blocker_tested` are **kept** on the migrated rows. They
describe a blocker that no longer holds, which the marker says out loud. Deleting
them would destroy the record of when the claim was last tested, and no consumer
reads them for a row with an empty `blocked_on` (`fleet.py`'s UNTESTED section
only considers rows with a non-empty blocker).

## For the next lane

- **Do not re-add a prose sniff to `fleet.py`.** The table above is why. If a
  new shape of dishonest `blocked_on` turns up, extend the *position*-anchored
  check in `check_coverage.py`, which fails loudly, rather than a consumer that
  silently reinterprets.
- **`idle-watchdog.sh:226` still says "Give it a lane in territory.toml or
  write blocked_on on its tracker entry."** That advice is now incomplete — it
  omits the third state. I did not touch it: it is not in this lane's files,
  and a running `while` loop holds the version it started with, so editing it
  would change nothing tonight anyway. Worth a line when someone next restarts
  the watchdog.
- The closed rows that also open with "NOT BLOCKED" (#82, #87, #90, #94, #95
  and #52 mid-text) are **deliberately left alone**. The new check is scoped to
  live-open issues; a closed row's `blocked_on` is history and rewriting it
  destroys the record for no gain.
- Ordering hazard I checked rather than assumed: between pushing the board
  migration and this PR folding, `master` carries the old `check_coverage.py`
  against a migrated board. All seven migrated rows are owned by a lane in
  `territory.toml`, so the old gate still passes on ownership — verified by
  running `origin/master`'s `check_coverage.py` against the migrated tracker.
  If a lane retires in that window before the fold, the old gate would fail on
  a row that *is* classified. Fold this before retiring blitsafe, swizzle87,
  remote or fold.
