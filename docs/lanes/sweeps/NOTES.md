# lane.sweeps -- two sweeps the harness does not have

Brief: `briefs/sweeps.md` (owner, 2026-09-19). No tracker issue; harness
capability. Prediction: none, analysis-only -- this moves no pixels.

## What landed

| file | what it is |
|---|---|
| `docs/testing/jobs/pr-sweep.sh` | a script, no model session, every 3h at :13. Five classes of open PR; repairs one. |
| `docs/testing/jobs/issue-sweep.sh` | a script, no model session, 07:41 and 19:41. Four classes of backlog row; repairs none, hands the findings to the board's tick. |
| `docs/testing/jobs/board.sh` | a fifth gate that reads those findings, keyed on their sha256 |
| `docs/testing/jobs/install-host.sh` | the two timers named explicitly in the enable line, and the dirs |
| `docs/testing/systemd/hakux-{pr,issue}-sweep.{service,timer}` | the units |
| `docs/testing/jobs/selftest.d/76-pr-sweep.sh` | 51 checks, a fixture per class and its inverse |
| `docs/testing/jobs/selftest.d/77-issue-sweep.sh` | 49 checks, including the board gate's once-per-set key |

`bash docs/testing/jobs/selftest.sh`: **802 passed, 0 failed.**

## What was measured, and what it changed

### A brief's class can be wrong, and this one was

The brief asked issue-sweep to report "blockers naming a lane that no longer
exists". It was implemented, and then run against the live board on
2026-09-19. It produced **11 of 16 findings, and every one of them was the
`blocked_on` field doing its job**:

- **#91**: `PR #102 (lane.blitsafe, folded into master 3d072c6ea6) did NOT
  deliver a fix here`
- **#13**: `TRACKER NOTE 2026-09-14 at lane.lows' request, from remediating
  audit LOW L10 ...`
- **#68**: `ANSWERED 2026-09-14 BY THE THREE-ARM RE-RUN ...`

A blocker NAMES the lane that established it, and that lane having finished
is the ordinary case. Narrowing the shape to "waiting on lane.X" rather than
dropping it was considered and rejected: **there is not one positive example
on the live board to calibrate a phrase list against**, so it would be a
classifier whose only tested case is the negative one. The shape is gone, the
reason is in `issue-sweep.sh`'s class-3 comment, and the selftest now carries
#91's own wording as a fixture that must NOT be reported.

A gate that is wrong eleven times out of sixteen on its first real run teaches
its reader to skip the section. That costs more than the shape is worth.

**The next lane should not re-add it** without a positive example in hand.

### The remaining classes were checked against live data, both ways

A fixture being green is not evidence the gate works on the board. Both sweeps
were run in `list` mode against the live repository, and every class was
cross-checked independently (`git show origin/board:nv2a_issues.toml` against
`gh issue list`):

| class | live count | independent check |
|---|---|---|
| orphan `claimed:cloud` | 1 (**#141**, kind `remediate`, 2572s with no unit) | `systemctl --user list-units 'hakux-lane-*'` has no `-141` unit |
| draft strand | 2 (#175, #171) | both already named by `handback.sh list`, so the sweep is silent |
| ready, no state label | 1 (#172) | board reported healthy, quiet 936s, so no comment |
| stale red | 0 | no `fold-ready` PR has an all-pre-trunk failing rollup |
| `regressed` | 2 (#148, #141) | `arms.sh state` recomputes `regressed` for both; the label stands |
| no tracker row | 0 | cross-check agrees: every one of 23 open issues has a row |
| untriaged | 0 | cross-check agrees |
| closable (`fixed-verified`/`unmodellable`) | 0 | cross-check agrees |
| `available` unpicked | 0 | cross-check agrees |
| ghost owner | 11 | see below |

The four zeroes are the ones worth stating: they are the sweep agreeing with
an independent read of the same two files, not the sweep being blind. The
fixture proves each of them trips when the state is present.

**#141 is orphaned right now** and this lane did not repair it. `cloud.sh
finish` calls `territory_row rm`, which **pushes to `origin/board`**, and
`roles/lane.md:79` forbids a lane writing those files by any route. Reported,
not touched. It is the first thing the installed timer will fix.

The 11 ghost-owner findings are all real: `lane.remote` (PR #162, folded),
`lane.indexcheck`, `lane.hilodot10` (#168 closed while this lane was running),
`lane.wbufclip`, `lane.blendrace50`, `lane.diagsoak77`, three
`lane.cloud-*-115` rows, and the `lane:cloud-110` / `lane:cloud-109` labels.

**A gap in `cloud.sh` this surfaced, which is NOT fixed here** (PR #171
lane.turncap holds that file): the issue path adds `lane:cloud-<n>` at claim
and `cloud.sh finish` clears only `claimed:cloud`. So an issue claimed by a
cloud lane that never opened a PR keeps a `lane:` label forever, and
`board_filter`'s `SKIP_PREFIX` makes it invisible to dispatch permanently --
the same shape as the orphaned `claimed:cloud`, with no `finish` to run. That
is why pr-sweep repairs only the PR variant of the orphaned claim and reports
the issue variant: a half-repair that looks complete is worse than a report.

### A selftest fixture truncated four real job scripts

`cat > "$PS/jobs/cloud.sh"` **follows the symlink** and writes through it. The
first run of `76-pr-sweep.sh` replaced the real `cloud.sh`, `fold.sh`,
`handback.sh` and `arms.sh` with three-line stubs in the worktree. It was
visible only because 189 unrelated checks went red in the same run; with one
fewer stub it would have been a silent corruption committed alongside the
feature.

`ps_stub()` is now the only writer into the scratch tree and it `rm -f`s
first, and five checks assert that each stub is a regular file and that the
real scripts still contain their own header sentences. A falsification fixture
must swap **inside** the symlink tree, never at the path the tree points to.

### A fixture that drifts with wall-clock time passes its negatives for free

The stale-red checks first placed each CI entry `TRUNK_AGO + 600` seconds in
the past -- which is 600s before the trunk head only at the instant
`TRUNK_AGO` was computed. A dozen `ps` runs, each with a real `git fetch`,
sit between that instant and the class-4 block, so the fixture drifted past
the trunk head, the class went silent, and **all four "this must NOT be
reported" checks passed for free**. Offsets are now taken from the trunk head
itself, and every negative carries a plainly-stale #214 in the same fixture as
a control, so a classifier that has gone blind fails instead of passing.

## Decisions, and what would change them

**issue-sweep starts no model session; it feeds the board's.** The brief
allowed either that or an argued alternative. The board tick is the harness's
only actor for judgement AND the only actor permitted to write
`nv2a_issues.toml`; a second timed session would be a second writer of one
file, which `cloud.sh`'s header is a long apology for. The handoff is
`$WORK/board/issue-sweep.findings`, and the key is a **content hash, not a
timestamp** -- the sweep rewrites the same findings while they hold, twice a
day, against a board that ticks every 20 minutes, so "does the file exist?"
would wake a model tick every 20 minutes for as long as one row stayed
untriaged. It is marked seen only when the tick returned 0.

**Class 4 (stale red) is reported and never relabelled.** `lane.stalecheck`
(PR #169) owns it in `fold.sh` and had not folded when this was written. What
the sweep adds is the case where that owner is **absent from the trunk it ran
from** -- checked with `grep stale_red fold.sh`, both directions in the
fixture -- or present and silent past six hours.

**Class 2 defers to `handback.sh list`** and reports only what it is silent
about. The match is anchored at line start: a bare `#<n>` also matches those
digits quoted inside a sentence about a different PR, which would silence a
real finding.

**The fold job is not looped.** One fold per tick is deliberate
(`fold.sh:486`, reason at `fold.sh:25`). Nothing here touches it.

**Never `regression-accepted:`.** Owner only. Class 5 asks `arms.sh state` and
reports; it writes no label in either direction.

## The stopgap

Two `CronCreate` jobs in the owner's interactive session cover tonight (a PR
sweep `13 */3 * * *`, an issue sweep `41 7,19 * * *`). They live only in that
session and expire after 7 days. Once `install-host.sh` has run, **delete them
with `CronDelete`** -- the timers land on the same minutes deliberately, so
leaving both would double every sweep.

## What the next lane should not repeat

1. Do not re-add the `blocked_on`-names-a-dead-lane shape without a positive
   example from the live board. It was measured and it is noise.
2. Do not write into a scratch tree of symlinks without unlinking first.
3. Do not build a time-relative CI fixture from `now`; build it from the
   quantity the code compares against.
4. Do not make pr-sweep repair the `claimed:cloud` on an *issue*. `cloud.sh
   finish` does not remove the `lane:cloud-<n>` label, so the repair would
   look complete and leave the issue just as invisible. Fix `cloud.sh` first.
5. A negative check with no positive control in the same fixture is not a
   check. Five of them passed here while the thing they guarded was broken.
