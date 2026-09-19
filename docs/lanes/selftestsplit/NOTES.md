# lane.selftestsplit — `selftest.sh` split into separately-ownable fragments

## What the problem was

`docs/testing/jobs/selftest.sh` is the gate every change under
`docs/testing/jobs/` must pass, so a lane that fixes something in the harness
also writes the check that proves it. On 2026-09-19 nine harness lanes ran and
**all nine appended a block to that one file**.

The fold job folds one PR per tick, and each fold moves master. From the fold
log that night:

```
07:07:30Z #127 CONFLICT in: docs/testing/jobs/selftest.sh
07:09:30Z #132 CONFLICT in: docs/testing/jobs/fold.sh docs/testing/jobs/selftest.sh
```

Two of the first three folds attempted, both handed back. The conflict rate was
not high, it was structurally ~100%: N harness PRs in flight cost N−1
`lane.sh resume` cycles — an Opus session each, an attempt each against
`LANE_MAX_ATTEMPTS`, a queue place each — to re-land work that was already
finished, tested and green.

## What was done

The checks now live in `docs/testing/jobs/selftest.d/NN-<concern>.sh`, sourced
in sorted order by `selftest.sh`. `selftest.sh` keeps the entry point, the
fixture directories, the shim construction (`gh`, `systemctl`, `systemd-run`,
`adb`), the live prediction and its goldens, and the final tally. The command
CI and every brief run is unchanged: `bash docs/testing/jobs/selftest.sh`.

A lane adding a check now creates or edits one fragment. Two lanes adding
checks touch two paths.

This is a **pure move**: not one check was rewritten.

## The brief's "49" was stale. The number is 65

The brief says the selftest reports `49 passed` and must still report 49. It
reports **65**, and did so before this branch touched anything. Measured on a
throwaway `git worktree add --detach` at `origin/master`, not from the brief:

```
selftest: 65 passed, 0 failed
```

`selftest.sh` is byte-identical at `1f7572a34c` (this lane's base) and at
`bc7ccef95d` (master after #135 folded mid-session), so 65 is the count at
both — the difference is not something that landed while I worked, the brief's
figure was simply already old when it was written. **The invariant the brief
wanted still holds, against the number that is actually true.** Anyone
re-checking this after the other `selftest.sh` PRs land should re-take the
baseline from their merge rather than quoting 65 either.

## Fragments, and what depends on what

Order is fixed by the numeric prefix, and it is load-bearing for 10..60.

| Fragment | Checks | Depends on |
| --- | --- | --- |
| `10-arms-list.sh` | 2 | `selftest.sh`'s `$EXP`, the goldens tree, `arms/since`. First of the arms chain; nothing is queued when it runs. |
| `20-arms-queue.sh` | 6 | **10** (an empty queue). Leaves the pair and the two `.req` files. |
| `30-arms-error.sh` | 2 | **20** (the pair it errors). |
| `40-arms-refusal.sh` | 10 | **20/30** — runs `arms.sh` over the standing queue. Registers `$EXP2`, `$EXP3` from `selftest.sh`'s `$A`/`$B`. |
| `50-arms-requeue.sh` | 2 | **20/30**, whose markers it clears; it then drives the whole queue itself. Last of the arms chain. |
| `60-status.sh` | 11 | **10..50** — the refusal `status.sh` renders is 40's. |
| `65-fold-cloud-list.sh` | 2 | nothing |
| `70-cloud-audit.sh` | 3 | nothing (reads `cloud.sh`'s own text) |
| `75-nv2a-index.sh` | 5 | nothing (own throwaway repos under `$T/gate`) |
| `80-labels.sh` | 6 | nothing, but it **truncates `$SELFTEST_GH_LOG`** as it goes, so no later fragment may depend on what that log held before it. |
| `90-fold-notes.sh` | 16 | nothing (own git fixtures under `$T/foldnotes`) |

65..90 are order-independent of each other and of 10..60. The numbering leaves
`00-09`, `85-89` and `91-99` free, plus the gaps, so an insertion rarely needs
to renumber anything.

`NN` is **exactly two digits**, and `selftest.sh` refuses a name that is not
`NN-<concern>.sh`. Not pedantry: a glob sorts lexically, so `100-x.sh` would
run *before* `20-x.sh`, and a fragment named `check-x.sh` would simply never be
sourced. A gate that silently stops running is the failure mode this lane
exists to remove, so both cases are a hard `exit 2`, as is an empty
`selftest.d` (a clean run having checked nothing). The `*.md|*~` arm lets a
README and an editor backup sit in the directory.

The glob output is re-sorted through `LC_ALL=C sort`: the runner's collation is
not this box's, and the order is load-bearing.

## Proofs

**1. Pure move — byte-identical, same order.** `.selftest-runs/puremove.py`
(scratch, not committed) reads `origin/master:docs/testing/jobs/selftest.sh`
— the committed original, not the working tree — takes lines 101–354 (the
check region), strips each fragment's header comment, concatenates the
fragments in sorted order and compares non-blank lines:

```
PURE MOVE: 238 non-blank lines, identical
```

That the *concatenation in sorted order* matches is the part that matters: it
proves the numeric prefixes reproduce the original relative order exactly, so
the arms chain's fixture sequence is preserved. The splitting script refuses to
write at all if any non-blank line of the region lands in no fragment, or if
two line ranges overlap.

**2. Same count, same checks, same order, not slower.** Both runs on the same
content (`bc7ccef95d`), back to back, same box:

| | passed | failed | exit | wall clock |
| --- | --- | --- | --- | --- |
| `origin/master` unsplit, detached worktree | 65 | 0 | 0 | 278s |
| this branch, split | 65 | 0 | 0 | 278s |

and the totals are not the whole comparison — the two logs, reduced to their
`==` section headings and `ok`/`FAIL` lines and normalised for the timestamped
`.req` filenames, diff clean:

```
IDENTICAL: 65 checks passed, same order, same sections
```

Timing: the box is shared with other lane sessions, so 278s is contended, not
a clean figure; an earlier contended pair read 375s (unsplit) and 360s
(split). The structural argument is the stronger one — the cost is the eight
`arms.sh` invocations, which are untouched, and the split adds eleven `source`
calls. The CI job's timeout is 15 minutes.

**3. A failing fragment fails the run.** The tally is shared state across
sourced files, and that is exactly the property a split like this can silently
lose. Tested for real: wrote `selftest.d/99-deliberate-failure.sh` with one
`bad`, one failing `check` and one passing `check`, ran the entry point, then
deleted it.

```
exit=1   (must be non-zero)
== deliberate failure
  FAIL a deliberately failing fragment
  FAIL a deliberately failing check in a fragment
selftest: 66 passed, 2 failed
```

66 = the 65 plus the fragment's one passing check, so the *passing* side of the
tally is shared too, not just the failing side. `set -u` is on throughout and
the fragments inherit it.

**4. The name guards trip.** Each of these was created in `selftest.d/`, run,
and deleted:

| fixture | result |
| --- | --- |
| `check-foo.sh` | `exit 2`, "is not selftest.d/NN-\<concern\>.sh and would never be sourced" |
| `100-late.sh` | `exit 2`, same message (it would have sorted before `20-`) |
| an empty `selftest.d` | `exit 2`, "no fragments … nothing would be checked" |

All three exit before a single check runs, so none can be mistaken for a pass.

**5. CI still fires.** `.github/workflows/jobs-selftest.yml` gained
`docs/testing/jobs/selftest.d/**` to both `paths:` lists. Worth being precise:
the existing `docs/testing/jobs/**` **already** matched the new directory —
GitHub's `**` crosses directory separators — so this is belt-and-braces rather
than a fix, and a comment on the `push:` list says so. It is there for whoever
next narrows `jobs/**`.

## What the next lane should not repeat

- **Do not edit `selftest.sh` to add a check.** Add
  `selftest.d/NN-<concern>.sh`. An append to `selftest.sh` re-creates exactly
  the collision this lane removed.
- **Do not edit a script while a long run of it is in flight.** I did this and
  corrupted a baseline: bash reads a script lazily by byte offset, so an edit
  that shifts bytes ahead of the interpreter's position makes it resume
  mid-token. It surfaced as `selftest.sh: line 125: pass: command not found`,
  which reads exactly like a defect in the change and is not. Finish every
  edit, *then* measure. (Corollary that cost a second run: `TaskStop` on the
  wrapper did not reap the `selftest.sh` child, which kept writing to the log
  path through its inherited fd. Two runs interleaved into one file and it
  ended `72 passed, 1 failed` — a number belonging to neither. **Give every
  run its own log filename**, and check the `fake host in /tmp/...` tempdir on
  the tally line is the one you expect before believing it.)
- **Take the baseline before the first edit, and date it.** "49" came from the
  brief and was wrong by 16. The measurement that settles it is a throwaway
  `git worktree add --detach origin/master` — a pristine tree that cannot be
  disturbed by your own edits, with its own `$T`.
- `git add -A` in this worktree stages the detached baseline worktree as an
  embedded git repository. Stage explicit paths.

## Sequencing

This PR moves the lines every other open `selftest.sh` PR is appending to, so
it conflicts with all of them by construction. **It must be folded last.** At
the time of writing that is #122, #126, #127, #130, #132 and #134. The one
merge from master needed so far (`bc7ccef95d`, #135) touched only `arms.sh` and
merged clean; any block that lands in `selftest.sh` before this folds has to be
carried into the right fragment by hand, and the merge commits on this branch
record which went where.
