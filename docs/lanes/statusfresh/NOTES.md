# lane.statusfresh -- the live status is fresh and looks eleven hours stale

Issue: none (harness defect, dispatched directly). PR #150.
Files: `docs/testing/jobs/status.sh`,
`docs/testing/jobs/selftest.d/62-status-freshness.sh`, this file.

## The defect, restated as a rendering fact

GitHub renders a comment's `created_at` next to the author's name and leaves the
comment where it was posted in the timeline. An in-place `PATCH` moves neither.
So #107 read `02:28Z` while holding a body written at `13:32Z`, and the body's
own `_Rewritten ... by status.sh_` line -- correct, and eleven minutes old -- sat
below the fold of what the page shows first, contradicting the timestamp the UI
puts above it. Two states that must be told apart, a jammed fleet and a running
one, rendered identically, and the page's whole purpose is telling them apart.

The REST API was never wrong:

```
id=5738613782  created=2026-09-19T02:28:14Z  updated=2026-09-19T13:32:48Z
```

## Measurements

The brief asks whether a title PATCH is noisy enough to rule out renaming on
every tick. Two facts, both measured here rather than assumed, because the
answer decides the whole design.

**1. Nobody is notified, because nobody is watching.**

```
$ gh api repos/jreinach-alt/hakuX --jq '{visibility,subscribers_count,watchers_count}'
{"subscribers_count":0,"visibility":"public","watchers_count":1}
$ gh api repos/jreinach-alt/hakuX/subscribers --jq '.[].login'      # empty
$ gh api user --jq .login
jreinach-alt
```

`status.sh` authenticates as `jreinach-alt`, which is the account that owns the
repository and reads the page, and GitHub does not notify you of your own
actions. With zero subscribers there is no third party to notify either. So the
notification half of the brief's concern is discharged: **renaming notifies
nobody.** If a collaborator is ever added, this is the fact that expires --
re-run those two calls before widening the title's cadence.

**2. A rename is still permanent litter; an unchanged title is free.**

Measured against this lane's own PR #150 (a PR is an issue, so `PATCH
/issues/<n>` behaves identically, and it was a target I own):

| action | timeline | `updated_at` |
|---|---|---|
| `PATCH` title, new string | `renamed` row appended | bumped |
| `PATCH` body | **nothing** | bumped |
| `PATCH` title, **same** string | **nothing** | not bumped |

So the body is free and silent, and the title costs one permanent timeline row
per *changed* string -- GitHub itself deduplicates a no-op rename, which means
the client-side compare is about saving a row on the page, not about correctness.

## What that measurement chose

- **The body carries the minute.** It renders above every comment, is the first
  thing a phone lands on, and editing it makes no timeline event at all. It is
  deliberately *short* -- clock, counts, deadline, and the warning about the
  comment's rendered timestamp. The roll-up itself stays in the comment: its
  URL is deep-linked from elsewhere, and duplicating a long page above a long
  page is worse on a phone than pointing at it.
- **The title carries the clock quantised to `$FLOOR`** (the status timer's
  30-minute period): `harness: live status -- 13:30Z+, 2 lanes running, 1 arm
  on a device, 0 queued`. Quantising bounds renames to ~48/day on a fleet that
  is otherwise standing still, and it keeps the page honest -- it cannot claim
  freshness finer than the timer that writes it. Reading the stamped time as
  exact therefore errs towards *staler than it is*, which is the safe direction
  for the question this page answers. The `+` says the value is a lower bound.
- The comment is unchanged, and so is everything it reports.

## The bit that cannot be fixed from inside, and what was done instead

A roll-up that is not running writes nothing. It cannot report its own current
silence; there is no arrangement of this script that makes a dead process
announce itself. So the page does the two things it can:

- Every render states its own deadline -- *"Next roll-up due by 14:02 UTC. A
  clock older than that means `status.sh` has stopped."* That hands the reader
  the rule instead of the conclusion, which is the only honest move.
- A lapse that has **already ended** is reported, on both surfaces, when the
  gap exceeds two floors: which window went unobserved, and the warning that an
  absent lane row across it means nothing either way. That is the more useful
  half in practice -- it is the evidence that the fleet jammed.

Closing the remaining hole properly needs a writer that is not the host (a
scheduled Actions run that marks the page stale when the host goes quiet). That
is outside this lane's files and was not attempted.

## Two things found on the way, both fixed here

- `gh issue list --jq '.[0].number'` yields the **string `null`** on an empty
  list, not an empty string. The old `[ -z "$issue" ]` guard therefore missed
  it, and the script proceeded to `PATCH /issues/null/...` -- where every call
  returns 0 and the page goes nowhere. Now anything non-numeric is treated as
  "no issue".
- ...but "no issue" now reaches the create-if-missing path, so it is gated on
  the query having *succeeded*. A network blip must not fork the one page the
  owner reads into two.

## What the next lane should not repeat

- **Do not test freshness with `grep -vq`.** It exits 0 the moment one line
  fails to match, which every one of these files has; it is not a negation. The
  fragment defines `sf_nogrep` (a real `! grep -q`) in the sourcing shell, not
  in a `bash -c`, where an unexported fixture would make the negative green
  against anything.
- **Do not put the exact minute in the title.** It is tempting and it is what
  the brief reaches for first; each tick would then append a `renamed` row to
  the very page being fixed, and status.sh ticks at the end of *every* job, not
  just on its 30-minute timer.
- The selftest's shim answers `issue list` with the bare number, so a check on
  the rename-only-when-changed path has to supply a title of its own. Fragment
  62 swaps in a shim, uses a day-long `STATUS_FLOOR_SECS` so two ticks cannot
  straddle a quantum boundary and turn a real "unchanged" into a flake, and
  restores `selftest.sh`'s shim for whatever is sourced after it.
