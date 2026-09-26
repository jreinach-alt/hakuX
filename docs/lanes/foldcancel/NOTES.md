# lane.foldcancel: a multi-fold record whose trunk CI was cancelled

## The defect

A tick that folds more than one PR writes `$WORK/fold/multi/<tip>`, and
`attribute_multi()` held later ticks to one fold (`HOLD=one`) until
`trunk_ci <tip>` said GREEN or RED. android.yml and desktop.yml cancel a ref's
older runs when a newer push lands, and `TRUNK_CI_JQ` drops CANCELLED runs, so
a tip whose runs were cancelled read NONE forever and the hold never lifted.

## The change (docs/testing/jobs/fold.sh)

- `TRUNK_CI_JQ` now tells the two silent cases apart. Every run cancelled gives
  `CANCELLED`, and no runs at all gives `NONE`. A mix of cancelled and
  completed runs is still judged on the completed ones, as before.
- `descendant_ci <sha>` fetches `origin/$TIP` into `$REPO` and walks the
  first-parent line from `<sha>` toward the tip, nearest first. It makes one
  check-runs call per commit and reads at most `DESC_MAX` (20) commits:
  - GREEN or RED: that commit answers for `<sha>`.
  - CANCELLED or NONE: keep walking.
  - PENDING (or unreadable): stop. The nearer commit has not answered yet,
    and its answer is more specific than a farther one's.
  - A commit whose first parent is not the previous one: stop. `<sha>` is
    not on the tip's first-parent line.

  It does its own fetch rather than using `cx_tip`. `cx_tip` caches the head
  once per tick, and a revert pushed later in `attribute_multi` would leave
  that cache stale for the conflict pass.
- In `attribute_multi`, a tip that reads CANCELLED or NONE goes to
  `descendant_ci`:
  - GREEN: the record gets `done superseded-green <descendant>`.
  - RED: the existing path runs (base-red check, then revert the batch's last
    fold). The record gets `red-at <descendant>` so the later attribution
    messages name the commit that actually went red.
  - Nothing reported: `HOLD=one`, as before.

  The log line always says which case applied, e.g. `(its own runs: all
  cancelled; 72b77d368a, its nearest descendant to report, answers for it)`.
- **The reverted branch (`trunk_ci "$rv"`) had the same wait, and it can be
  reached.** While a revert waits, nothing folds (`HOLD=all`), but other jobs
  push to master too; audit commits (`audit: pass N of PR ...`) land there.
  Any such push cancels the revert's runs, and before this change that left
  `HOLD=all` in force forever, which is worse than `HOLD=one`. The same
  descendant rule now applies to the revert. Selftest (6r) covers it.

## Why attributing a descendant's RED to the batch is safe

The descendant may also contain later folds. Those are single folds only:
while a record is open and unresolved, `HOLD=one` caps every tick at one fold,
so no second multi-fold record can open until this one closes. The two
records can therefore never both revert in the same tick. The later single
folds can't be what gets reverted either: the revert takes the batch's last
fold (`before..after` in the record) and nothing else.

If a later single fold caused the red, the revert's CI stays RED. The
existing path then re-lands the reverted PR (`done not <pr>`) and names "the
others, or the trunk itself" as the suspects for a person. That is the same
ending the pre-existing path reaches when the trunk itself is at fault. The
cost is one needless revert and re-land, two CI cycles. It never loops,
because the record closes on either answer. The base-red check still applies:
a batch whose base was already RED is not attributed.

A tip that reads PENDING (some run still in progress) is not walked. Its own
runs will either finish, which gives an answer, or be cancelled, which gives
CANCELLED and a walk on the next tick.

## Proof

`docs/testing/jobs/selftest.d/74-fold-multi.sh`:

- **(5)** Tip CANCELLED with no descendant: one fold, and the log says `none of
  its first-parent descendants has reported, 0 read`.
  - **(5c)** Its descendant still PENDING: one fold again (#45 folds, #46
    waits), `1 read`, and the record stays open.
  - **(5g)** The first descendant CANCELLED and the second GREEN: the record
    gets `done superseded-green <second>`, the log names it, and that same
    tick logs `folded #46 #47`.
- **(6)** Tip with no runs (NONE) and a RED descendant (a single fold on
  top): exactly one revert, of #42 (the batch's last fold); #44's file stays.
  The log and #42's comment both name the red descendant.
  - **(6r)** The revert's runs are CANCELLED by an unrelated push. While that
    push is PENDING nothing folds and the log says so. When it goes GREEN the
    record gets `done culprit 42`, and the attribution comment names the red
    descendant, not the silent tip.
- **(4)** jq: every run cancelled gives CANCELLED; `[]` still gives NONE.
- **Mutant:** with `descendant_ci` forced to return 1, the (5g) scenario leaves
  the record open, so (5g) depends on the walk.

### Read-only replay against the real gh (2026-09-26)

The functions are extracted verbatim from fold.sh by `sed` and run with
`GH_REPO=jreinach-alt/hakuX`. Nothing was written except the
`origin/master` ref in this lane's worktree.

```
7039df1d24c8c4fe8f11cffc20fed702a1ab428b own=CANCELLED (all cancelled) -> GREEN at 72b77d368a339b771289104d3f70134c411ad952 after 1 read
993c5fe4b562c49516daaa72a30a3b079b15e34d own=CANCELLED (all cancelled) -> GREEN at dc648227875124651f2e4cfb6985c0053e4f7a47 after 1 read
```

The brief expected `11a7dbe537` or a later commit. The rule it specifies,
the *nearest* descendant with a verdict, gives `72b77d368a` instead: the fold
of #388, 7039df1d24's direct first-parent child. Both of its `build` runs
completed `success` by 12:57:42Z (05:57 PDT). 7039df1d24's two runs were
`cancelled` at 12:50:47Z. So the record could have closed at 05:57 PDT.
Instead it held fold to one per tick until hostops closed it by hand at
11:52 PDT, six hours later. `11a7dbe537` is further down the same
first-parent line and green as well, so it gives the same verdict.

## For the next lane

- There is no path filter on either workflow, so every trunk push gets runs.
  NONE on a trunk commit means the runs were never created, or not yet: the
  commit arrived in the same push as a later one. It does not mean "skipped".
- The walk's 20-commit bound means a record left open across more than 20
  pushes, all cancelled or run-less, stays at `HOLD=one`. The log line says
  `20 read` when that happens.
