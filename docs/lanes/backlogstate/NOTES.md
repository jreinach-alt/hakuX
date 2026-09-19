# lane.backlogstate — a backlog had no "available" state

Issue: none (harness defect, dispatched directly).
Prediction: none: harness script, no pixels claimed.

## Why attempt 1 did not finish (written at the start of attempt 2)

The work was done; the *publication* was not. Attempt 1 ran out of turns at the
old `LANE_TURNS=150` in the middle of its final full `selftest.sh` run — the
truncated `.scratch/selftest2.out` stops mid-section at "arms.sh run: judge the
ERROR path", which is where the process was cut. What it had already done: the
code change, the board migration pushed to `origin/board` as `63e7141f10`, the
draft PR #134 opened with a full body (written through the REST PATCH, because
`gh pr edit --body-file` fails here), and the section-level verification against
`origin/master`'s scripts.

What it had **not** done, all of it after the selftest gate: merge
`origin/master`, move this file off the branch root, push, and
`gh pr ready`. So the lane read as finished and was invisible to the fold job,
which only considers non-draft PRs.

The cause is worth naming precisely, because it is not "ran out of time". The
last four steps are cheap — a merge, a rename, a push, one `gh` call — and they
were left until after a ~10-minute gate run that had already been satisfied at
the section level. **Ordering the expensive confirmation before the cheap
publication is what made a finished lane invisible.** A lane with a green
section-level verification can push and mark ready, then run the full gate: a
ready PR that turns out red is a visible problem, a draft PR that is green is
not a problem anyone can see.

Attempt 2 changed one thing on the substance (below: `CLEARED` is matched only
shouted, so an honest blocker whose prose uses the word is not punished) and
otherwise did those four steps.

## Why attempt 2 did not finish (written at the start of attempt 3)

Attempt 2 published correctly — PR #134 was ready, green and labelled. It was
then handed back `needs-rebase`, twice, on `selftest.sh`: nine harness lanes
were appending checks to one file and the fold job folds one PR per tick, so
the conflict rate on that path was ~100%. Nothing attempt 2 did was wrong and
nothing it could have done would have helped; the fix was structural and
landed as somebody else's lane (#136, `f53f3f66c2`), which split the file into
`selftest.d/NN-<concern>.sh`.

So attempt 3 is not a retry of the work. It is the move onto the new shape,
plus the three things that turned up while doing it — all three from master
having moved under the branch, none from the original change being wrong.

## What attempt 3 changed, and why each was forced

**1. The checks moved to `docs/testing/jobs/selftest.d/93-backlog-state.sh`,
unchanged except where a neighbour forced it.** Both adaptations are marked
`AFTER THE SPLIT` in the fragment.

- *A dispatch directory of its own.* The fragment's fleet fixtures used the
  shared `$DISPATCH_DIR`; `96-fleet-registry.sh` asserts on the exact registry
  contents there and sorts after this one. Appending to a single file hid that
  coupling behind textual order. Separate files make it a real dependency, so
  it has to be broken rather than tolerated.
- *`alpha is running` is now said to systemd.* It used to be the registry
  entry's `"state": "running"` field. `ae3712aae1` (#133) made `fleet.py`
  derive the running set from `systemctl --user list-units hakux-lane-*`,
  because nothing had written that field since the orchestrator role was
  deleted. The fixture follows: same fact, different place asked.

  **This one nearly passed silently and that is the lesson.** The top-level
  shim answers `is-active` and nothing else, which `lane_units()` reads as an
  *empty* fleet — and "an available row held by a RUNNING lane is not
  dispatchable" is true for free against an empty fleet, and against a blind
  one. The check would have stayed green while testing nothing. Two fixture
  sanity checks now assert alpha really is in RUNNING and that fleet was not
  blind, *before* the 0 is read as the skip working.

**2. `96-fleet-registry.sh`'s "an issue no running lane owns FAILs as
dispatchable" was retargeted, not deleted.** It was true of the old code and
this change makes it false on purpose: `#9401` has no tracker row at all, and
the whole point here is that "no blocker" and "somebody looked and nothing
blocks it" are different claims. That fragment is about *provenance* — an
issue no active lane owns must reach `board.sh` as a `^FAIL` naming the issue —
and that still holds, in the section that now describes it correctly. Both
halves are asserted so the old behaviour cannot come back and satisfy it.

**3. `dispatch_state = "done"` was added to the enum, because the board wrote
it before this lane folded.** This is the one substantive change, and it is
evidence rather than pressure.

The first enum was `("available", "blocked")`. Its rule (3) — `available`
requires `status = "open"` — tells a board closing a row that `available` has
stopped holding, and gives it no word to put there instead. Its two options
were to delete the field, losing the record that the row was ever classified,
or to invent a word. On 2026-09-19 it closed #84 and wrote
`dispatch_state = "done"`, which is the right word. Against the two-value enum
that is the "unrecognised value" FAIL — **red for every lane on the repository,
over a row nobody will ever dispatch.** Caught by running `preflight.sh`
against the live board rather than against the fixture.

`done` costs exactly what the others cost. It satisfies nothing on its own:
the coverage gate counts only `available`, `fleet.py` dispatches only
`available`, and `done` on a `status = "open"` row is a FAIL — the exact mirror
of `available` on a closed one. Each value contradicts the `status` it is
written against, so neither can be used to silence anything, which is the
failure mode this whole schema exists to end.

Four targeted mutants, one per new invariant, each tripping only its own
checks — a crowd of reds from the `origin/master` falsification would not have
shown this, since that file knows nothing of `dispatch_state` and fails
everything:

| mutant | trips |
|---|---|
| `STATES` back to two values | "a closed row carrying `done` is accepted"; the open-row rule |
| the `done`-on-open rule removed | the open-row rule alone |
| `done` let into the *covered* set | "`done` cannot cover an open row the way `available` does" |
| `done` let into `fleet.py`'s dispatch branch | "a live row marked `done` is not dispatched" |

The fleet-side check had to be moved onto a **live** row to be worth anything:
the closed `done` row is never reached, because `fleet.py` iterates only live
issues, so "not dispatchable" would have been true of it however `fleet.py`
were written.

`fleet.py` itself was composed rather than chosen at the conflict: master's
`fleet_blind` guard on the dispatch loop keeps this lane's `unclassified` list,
and master's `NOT COMPUTED` qualifier is extended to the new
`NEITHER BLOCKED NOR MARKED AVAILABLE` heading for master's own reason — it is
built by the same running-lane-skipped loop, so a bare `(0)` under FLEET-BLIND
would read as "nothing is unclassified" when nothing was looked at.

**State at the end of attempt 3:** `selftest.sh` 152 passed, 0 failed.
`preflight.sh --allow-tracker` reports `coverage ok`; it still fails on
`territory`, and that is not this lane's — the board dispatched `lane.linecap13`
with a claim on `hw/xbox/nv2a/pgraph/glsl/geom.c` while leaving the same path
in `territory.toml`'s `[free]` list (board branch, lines 140 and 347). This
branch touches no `territory.toml`, and `--allow-tracker` licenses editing the
tracker files, not this gate.

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

A third state: **`dispatch_state = "available" | "blocked" | "done"`** on a
tracker row. "Available" is about the *obstacle*, not the owner — whether a
lane is on it stays territory.toml's business, which is why `fleet.py`'s
running-lane skip still applies on top of it. (`done` was added in attempt 3
after the board wrote it; see "What attempt 3 changed" above. Only `available`
covers a row, and only an open row needs covering.)

- `check_coverage.py`: covered is now owned **or** non-empty `blocked_on` **or**
  `dispatch_state = "available"`. The gap gate is unchanged for an
  *unclassified* row and its message names all three ways out.
- `dispatch_state` costs something, because a value invented to satisfy a gate
  gets used to silence it. Four new failures: an unrecognised value;
  `available` with a non-empty `blocked_on`; `available` with `status != open`
  (the guard on the opposite failure — "finished work reading as available is
  how an issue gets re-dispatched", this script's own sentence about #56/#57/#61);
  `blocked` with nothing in `blocked_on`. Attempt 3 added the fifth and its
  mirror: `done` on a row whose `status` is still `open`.
- a `blocked_on` whose **opening claim** asserts non-blockage is now a FAIL,
  scoped to live-open issues.
- `fleet.py`: `DISPATCHABLE NOW` is exactly the `available` rows not held by a
  running lane. The prose sniff is deleted. A new section, `NEITHER BLOCKED NOR
  MARKED AVAILABLE`, shows rows that say nothing, because calling them
  dispatchable asserts more than an empty row supports.
- `docs/testing/jobs/selftest.d/93-backlog-state.sh`: a whole fake board
  (`$T/board` with copies of the three modules plus two toml files;
  `HAKUX_BOARD_REF=` makes board_files fall back to it) and 27 checks over
  twelve variants of one row. **The fixture is a whole fake board, not a unit
  test of a regex**, because the defect is a disagreement *between* two
  consumers of one schema: coverage counted those rows as blocked while fleet
  undid it with a substring search. Both read the board through
  `board_files.py`, so a directory of copies *is* a board and the real scripts
  run against it unmodified.
- `docs/testing/jobs/selftest.d/96-fleet-registry.sh`: one check retargeted,
  not deleted — see "What attempt 3 changed" above.

## Two things I got wrong on the first pass, both caught by measuring

**The AVAILABLE count read 0 on a board with seven available rows.** I kept the
old summary-line shape — owned, then available-and-*not*-owned, then
blocked-and-not-owned, three buckets summing to the total — and every migrated
row is *also* held by a lane, so the new state's count was zero exactly when the
state was in use. The counts now overlap and the line says so; the sum property
carried no information anyway, since the gate above fails on an unclassified row.
Pinned by the `ownedavail` selftest variant.

**Moving the empty-row case to a note would have dropped a FAIL.** The old
`fleet.py` called a row with no blocker "dispatchable" — wrong description,
non-zero exit. Describing it accurately as unclassified and printing it as a
note would have been right and *silent*. #34 and #62 are in exactly that state
on the live board (owned by lane.remote, no blocker, nothing else), so the hole
opens the moment that lane stops running. It is now a separate section with
accurate words and the same exit code.

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

**Case carries meaning for exactly one of the claims, and I got this wrong on
the first pass.** "not blocked", "not a blocker" and "unblocked" have no
innocent reading as a blocker's *opening* claim, in any case. "cleared" does:
`Blocked until the audit has cleared the held fold` is a perfectly good
blocker, and matching it case-insensitively in the opening would have made the
new gate fail an honest row — the same pressure that produced this defect,
pointed the other way. So `CLEARED` and `NO LONGER BLOCKED` are matched only
SHOUTED, which is how the board writes its own status markers and how #89 wrote
this one. Both sides are pinned by selftest variants (`honest`, `shouted`); the
first would have been a FAIL under the first pass's regex.

## Verified against the code being replaced, not reasoned about

`SELFTEST_BOARD_SRC` points the fragment at a directory of scripts, so it can
be run against the code being replaced rather than reasoned about. Re-measured
at the end of attempt 3, after the move into `selftest.d/`:

| scripts | result |
|---|---|
| this branch | 27 passed, 0 failed |
| `origin/master:docs/testing/{check_coverage,fleet,board_files}.py` | **5 passed, 22 failed** |

The 22 fail for four distinct reasons — the summary line's shape, the fleet
section names, the position-anchored detector, and the four `dispatch_state`
validations — which matters, because N reds that are all one reason is one
red wearing a crowd's clothes.

The five that pass against the old code all pass for stated reasons, and each
is a check that *should* be true either way:

| passes against the old code | why that is correct |
|---|---|
| the three modules were copied | the fixture's own sanity check |
| the fixture's lane really is RUNNING | a property of the fixture, not the fix |
| ...and fleet was not blind | same |
| an UNCLASSIFIED row still fails | the guard that behaviour was **preserved** — the gate is not weakened |
| `done` cannot cover an open row | old code has no `done`, so it covers nothing; the mutant that makes this fail is `donecovers` |

That last row is why the falsification against `origin/master` is not enough
on its own and the four targeted mutants exist. A file that knows nothing of
`dispatch_state` fails everything, so a vacuous check hides in the crowd.

Every assertion is on the **output words**, never on the exit code: the old
`check_coverage.py` exits 1 on most of these variants too, for the wrong reason
(the available row reads as an uncovered gap). rc is far too coarse to tell the
fix from the defect here.

Reproduce with the uncommitted drivers in `.scratch/`: `run-selftest.sh` (the
whole gate, fake host inside the worktree), `falsify.sh` (the same fragment
against `origin/master`'s three board modules — it refuses to run if those
already know `dispatch_state`, i.e. if this PR has folded), and `mutants.sh`
(the four targeted mutants). All three swap into a copy tree and never touch
the real paths.

## What actually moves, as a differential

All seven rows are held by a running lane today, so `DISPATCHABLE NOW` is 0
before *and* after. That 0 proves nothing. With blitsafe's fleet row set to
`retired` against the real board:

```
OLD scripts, OLD tracker:  DISPATCHABLE (4)  #88 #89 #91 #92  "blocker says NOT BLOCKED"
                           coverage ok (29 open: 12 owned by a lane, 17 with a written blocker)

NEW scripts, MIGRATED:     DISPATCHABLE (4)  #88 #89 #91 #92  "dispatch_state=available"
                           coverage ok (29 open: 7 AVAILABLE, 20 blocked, 12 owned by a lane)
```

`fleet.py`'s count is unchanged and I am not going to dress that up: the old
sniff did catch those four, one of them (#92) by a false positive that happened
to land on the right answer. What moves is (a) the checker's summary line no
longer calling seven unblocked rows blocked, and (b) the board being able to
write "waiting for capacity" without lying, which is the shape that was
invisible to *both* consumers.

**Correcting my own wording here**, checked at `idle-watchdog.sh:223` rather
than remembered: the watchdog takes `check_coverage.py 2>&1 | head -6`, matches
`FAIL*` against the whole block and reads the detail with `sed -n 2p`. It is not
`sed -n 1p`, and the summary is not line 1 of stdout either — `board read from:`
is. The substance is unaffected, because `head -6` carries the summary and the
FAIL detail either way, and the reason this channel matters is the watchdog's
own design note at line 78: the loop re-invokes its children fresh every poll,
so what the CHILD says reaches a running watchdog and what the LOOP says does
not.

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

## The territory flag on this PR, and the coordination it asked for

At wave 101 the board wrote a `[lane.backlogstate]` row that **excludes**
`fleet.py` and `check_coverage.py`, on the grounds that both are
`lane.toolsmith`'s STANDING claim, that a standing claim does not go stale
while its agent is not running, and that a finished PR is not the same as a
lane asking. All three are correct as stated, and the row is right that this
lane never asked.

What it is missing is that this lane never *chose* those files either: the
brief dispatched it directly at them — "Your files: `docs/testing/check_coverage.py`,
`docs/testing/fleet.py`, `docs/testing/jobs/selftest.sh`, and
`nv2a_issues.toml` on the `board` branch only." The gap is between the
dispatch and `territory.toml`, not between this lane and the file. That is
this lane's own defect one level up — a claim nothing can see — and it is why
the row calls it an "invisible-lane defect".

The row asks for one concrete thing before folding: read this diff against the
two live warnings in toolsmith's note. Done, and both come back clean:

- **`classify_residuals.py`'s `_ZB` trap** — about `classify_residuals.py`.
  This diff does not touch that file and nothing in it classifies residuals.
- **The `dispatcher.sh` snapshot-vs-source split** — the real question, and
  worth asking: if a consumer runs a `cp -f` snapshot taken outside the repo,
  an edit to the tracked source is inert. Checked at
  `dispatcher.sh:90`, `snapshot_scripts()` copies exactly
  `dispatcher.sh devices.sh soak_title.sh run_disc.sh score_sweep.py
  affinity.py captures.py make_test_iso.py extract_results.py`. **Neither
  `check_coverage.py` nor `fleet.py` is in that list**, and every consumer
  found by grep (`board.sh:181`, `preflight.sh`, `idle-watchdog.sh:223`,
  `status.sh`, `handback.sh`, `session-start.sh`, `backlog-gate.sh`) invokes
  them from the tree. So this change reaches its consumers on the fold, with
  no restart and no re-snapshot.

`lane.toolsmith` was not running at this wave (`fleet.py` reported `fold` and
`remote`), so there is nobody to coordinate *with* in-band; this section and
the PR comment are the record.

## For the next lane

- **Do not re-add a prose sniff to `fleet.py`.** The table above is why. If a
  new shape of dishonest `blocked_on` turns up, extend the *position*-anchored
  check in `check_coverage.py`, which fails loudly, rather than a consumer that
  silently reinterprets.
- **Do not take `idle-watchdog.sh` as a drive-by.** Its line 226 is wrong
  because of this change (below), and fixing it is one line — but it is
  `lane.toolsmith`'s, and this PR is already flagged for editing two of that
  lane's files without asking. Adding a third while the flag is open would be
  the same mistake with the excuse worn thin. Ask for it, or leave it.
- **`docs/testing/idle-watchdog.sh:226`** (note the path — it is *not* under
  `jobs/`, which cost me a minute) **still says "Give it a lane in
  territory.toml or write blocked_on on its tracker entry."** That advice is now
  incomplete — it omits the third state. I did not touch it: it is not in this
  lane's files, and a running `while` loop holds the version it started with, so
  editing it would change nothing tonight anyway. Worth a line when someone next
  restarts the watchdog. Re-verified at line 226 after merging
  `origin/master@bc7ccef95d`.
- The closed rows that also open with "NOT BLOCKED" (#82, #87, #90, #94, #95
  and #52 mid-text) are **deliberately left alone**. The new check is scoped to
  live-open issues; a closed row's `blocked_on` is history and rewriting it
  destroys the record for no gain.
- **`gh pr edit --body-file` fails here too, not just `--add-label`.** Updating
  this PR's body with it printed the Projects-classic GraphQL refusal and
  changed nothing; `gh api -X PATCH repos/O/R/pulls/<n> -F body=@file` worked.
  Nothing in `docs/testing/jobs/` writes a PR body today, so no live defect —
  but `docs/ORCHESTRATION-DESIGN.md:218` plans the grant mechanism as "a comment
  `/grant path` from the board job that **edits the PR body**", and `gh-label.sh`
  already knows the general cause ("`gh pr edit` asks for project cards on every
  edit"). Whoever builds `/grant` should go through REST from the start.
  `selftest.sh:282`'s check is scoped to `--add|remove-label` and would not
  catch a `--body` regression.
- **`docs/ORCHESTRATION-DESIGN.md:222` lists the tracker's rich fields**
  (`blocked_on`, `blocker_falsifier`, `blocker_tested`, `fixed_by`) and now
  omits `dispatch_state`. One line, and I did not take it: PR #122 is
  `claude/hakux-orchestration-design-e663m8` with no `Files:` line, so that
  document is very likely being rewritten right now and a one-word edit there
  is a collision nothing can see. The in-band channel does work without it —
  the coverage FAIL messages name the field, and the summary line now prints
  `N AVAILABLE`. That is the channel that reaches a *running*
  `idle-watchdog.sh`, because the loop re-invokes the script fresh each poll
  while holding its own text from startup.
- **`selftest.sh:282`'s line number is dead** and so is every other one I wrote
  against that file: #136 split it into `selftest.d/*.sh`. The label check is
  now `selftest.d/80-labels.sh`. Cite fragments, not offsets into the file that
  no longer holds the checks.
- **#34 and #62 are unclassified on the live board** — owned by lane.remote, no
  blocker, no `dispatch_state`. They pass coverage on ownership alone today and
  will fail `fleet.py` the moment remote stops running. They are not in this
  lane's migration set (remote is mid-queue on them), but somebody should write
  a state on them.
- Ordering hazard I checked rather than assumed: between pushing the board
  migration and this PR folding, `master` carries the old `check_coverage.py`
  against a migrated board. All seven migrated rows are owned by a lane in
  `territory.toml`, so the old gate still passes on ownership — verified by
  running `origin/master`'s `check_coverage.py` against the migrated tracker
  (`coverage ok (29 open: 12 owned by a lane, 17 with a written blocker)`).
  If a lane retires in that window before the fold, the old gate would fail on
  a row that *is* classified. Fold this before retiring blitsafe, swizzle87,
  remote or fold.
- The migration is `63e7141f10` on `board`; the tip it was written against was
  `0458dc53a0`. If board has moved since, `.scratch/push-board.sh` re-derives
  from the fresh tip rather than forcing.
