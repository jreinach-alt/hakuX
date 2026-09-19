# Handoff: seven defects between a registered prediction and a device run

Written by the local session on the host on 2026-09-19, for the remote session
that built the job harness (`docs/investigations/handoff-2026-09-19-jobs.md`)
to review. Everything here was found by running the pipeline rather than by
reading it, which is the point of the hand-off and is why the list is this
long.

**One sentence:** the harness could not queue an arm, could not label a PR,
could not build an uncached ref, could not re-queue an arm that failed, and
would have deleted a test suite from the index on its first fold -- and every
one of those failures reported success or said nothing at all.

## The shape of all of them

Six of the seven are the same failure: **an action that cannot work, taken by
something whose report does not distinguish "did it" from "could not".** The
arms tick logs only when something happens, so four ticks that queued nothing
looked like four quiet ticks. `gh pr edit` was called with `>/dev/null 2>&1`,
so eight label call sites failing was indistinguishable from eight succeeding.
`fold.sh` waits on non-green CI and comments only when CI is RED, so a PR whose
CI never ran waits forever in silence.

The fix in each case is the same shape too: say it. Most of the diffs are a
`say "WARNING: ..."` and a named consequence.

## Fixed and folded -- PR #116, folded as `05e25ca29b`

### 1. The retry for an older refusal could not reach the one refusal it existed for

`$WORK/arms/skipped/<sha>` records a prediction the arms job will not queue.
PR #113 made a `request.sh` refusal retry itself when `arms.sh` changes, so a
refusal caused by the script's own bug would clear without anyone deleting a
file on the host. It keyed the retry on an `arms=<md5>` stamp that **the same
commit** started writing:

```bash
if grep -q '^arms=' "$A/skipped/$sha" && ! grep -q "^arms=$ARMS_VERSION" ...
```

Every marker already on the host had no stamp, took the `else`, and was skipped
forever. That was the entire population the retry existed for: one marker,
#89's arm (PR #102's prediction), refused at 02:56Z by the `int("")` bug that
#113 fixed. Four arms ticks -- 19:28, 19:56, 20:27, 20:58 -- queued nothing
with both handhelds attached, the queue empty, and nothing in the log.

**A guard keyed on a field only the new writer emits exempts exactly the
backlog it was meant to clear.**

The discriminator is now the refusal text, which both marker generations carry.
The stamp keeps its real job: once per version, not every tick. Structural
skips (no `a_ref`, a stale `b_ref`, no suite with goldens) carry no such text
and still stand -- no edit to `arms.sh` turns one of them into a run.

### 2. The first fold would have deleted a test suite from the index

`fold.sh` regenerates `nv2a_index.json` when a merge makes it stale -- check
fails, `build`, commit, push -- from whatever `nxdk_pgraph_tests` checkout the
host holds. Nothing checked **which way** that checkout differed.

| | |
|---|---|
| index `provenance.tests_commit` | `91a0de4` (tests #316) |
| host checkout | `33e7c6b` (tests #312), an **ancestor**, 5 commits behind |
| `preflight` said | `STALE INDEX ... suites differ (committed 103, tests tree 102)` |
| rebuilding from it gives | 102 suites, `LOST: ['Surface as vertex array']` |

Measured, not argued: that is the output of running the rebuild against a
worktree pinned at the host's commit. The suite was added by tests #314. The
fold job would have committed the deletion and pushed it to `master` on the
first PR it folded, and `preflight` would then have passed, because the index
and the stale tree agree with each other.

**A stale checkout never announces itself as a stale checkout. It announces
itself as a stale index, which reads as "regenerate me" -- and regenerating is
how the information is lost.** Only the direction of the difference separates
the two, and nothing was looking at the direction.

`nv2a_index.py build` now compares `provenance.tests_commit` with the
checkout's HEAD before writing anything, and refuses with exit 3 on older,
divergent, or unknown, naming the fix for the **tree**. `--allow-older-tests`
overrides and says what it costs. The host's tree was fast-forwarded to
`91a0de4`, its own provenance, and preflight passes there now.

## Fixed, on `lane/jobslabel` (see the PR opened from it)

### 3. No PR label the harness set ever took, and every job reported success

```
$ gh pr edit 116 --repo jreinach-alt/hakuX --add-label harness
GraphQL: Projects (classic) is being deprecated ... (repository.pullRequest.projectCards)
$ echo $?
1
```

`gh` 2.45.0's `pr edit` asks for project cards on every edit and GitHub now
refuses the field. All eight label call sites in the jobs were
`gh pr edit ... >/dev/null 2>&1`.

Everything §5 of the design calls a state machine runs on those labels, and
none of them moved: the fold job folds a PR and leaves `fold-ready` on it, so
the next tick folds it again; the arms job judges an arm and marks nothing
`verified`; the cloud job claims a PR without `claimed:cloud`, so the next tick
claims it a second time. **Observed live in this session:** #116 was folded at
04:52:21Z and its labels are still `[harness, fold-ready]`.

`gh issue edit` does not go through that path and works, which is why the issue
side looked healthy and hid the PR side entirely.

Labels now go through the REST endpoint, which takes issues and PRs alike.
`jobs/gh-label.sh` is sourced for `label_add`/`label_rm` and runs as a command
for the one caller that needs a string (`cloud.sh` builds the unclaim as text
for the session's systemd unit). Failures are said on the tick log with the
consequence named. `roles/board.md` and `roles/cloud.md` now say which command
to use -- both drive this state machine from a model session, and the board's
own role text told it to use the call that does not work.

### 4. No uncached build could ever succeed: a user unit has no `~/.local/bin`

#89's arm was queued at 04:52Z, both sides claimed a handheld within seconds,
and both failed in under two minutes:

```
C/C++: CMake Error at CMakeLists.txt:255 (message):
C/C++:   meson not found in PATH; required to build glib for Android
```

`meson` is at `/home/justin/.local/bin/meson`. A systemd **user** unit's PATH
is `/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin` and
nothing else; it does not inherit the login shell's. An interactive shell puts
`~/.local/bin` first, so the same build **by hand succeeds**. It is invisible
from a terminal and fatal from the daemon.

It was also invisible for as long as every requested ref was already in the APK
cache, which was every build the dispatcher had served until tonight. And when
it did fire, **both arms failed identically** -- which reads like a broken
branch, not a broken host. PR #102's own body says the branch was never
compiled. Two independent reasons to believe the wrong thing.

Three changes: the unit declares `PATH` (needs `install-host.sh`; already
installed here and the dispatcher restarted); `build_ref` checks the tools it
shells out to before starting gradle and returns with the tool named; and the
`ERROR` file carries the **cause**, because `build failed for ref X (code 4)`
is what the arms job puts on the lane's PR and it tells a lane nothing. It now
reads `meson not found in PATH`.

### 5. An errored arm could never be queued again, though the job said it could

The `[job.arms] ARM ERROR` comment ends: *"delete `$WORK/arms/judged/<sha>` and
`$WORK/arms/pairs/<sha>.json` to have the job queue it again."* Doing that
queued nothing. `already_ran()` also matched `$D/results/*/request.json`, and an
**errored** result's `request.json` still carries the `expect_sha` -- so the
two markers the comment names are not the only trace, and the one it does not
name cannot be deleted without throwing the result away.

Met immediately: #89's arm failed to build on both sides for a reason that was
the host's, and the only thing the harness had to say about it was an
instruction that does not work.

A result that ERRORed is not a run. This re-queues nothing on its own -- the
pair marker stops the next tick while a pair is in flight, and the judge writes
`judged/<sha>=ERROR` the moment it sees the ERROR arm.

## Found, NOT fixed -- for you to weigh

### 6. An A/B pair split across two handhelds, and `serving()` was empty

#89's first pair went base->`thor`, fix->`nova`. `affinity.py`'s rule 2 pins a
pair to wherever the first arm landed; it fell through because `_live(d,
"thor")` was false, because `serving()` returned `[]`, because
`$D/lanes/` held no worker pid files -- only two unrelated `*.lastbrief` files
from 09-14 that happen to share the directory.

The mechanism worked as designed once the dispatcher was restarted:
`serving(): ['nova', 'thor']`, and the re-queued pair is pinned to one device.
**What removed the lane files at 16:44 is unresolved.** The running workers were
byte-identical to the repo's `dispatcher.sh` and the lanes code was present, so
this is not a stale-copy problem. The hold path (`rm -f "$D/lanes/$LABEL"`)
restores the file only in the same process that observed the hold -- worth a
look, but I could not reproduce it.

`affinity.py` did the right thing and recorded it: `_note_split` wrote
`$D/splits/<req>.txt` saying the pair may span two devices. **Nothing reads
`$D/splits/`.** The note exists so the decision is discoverable rather than
reconstructed from a pace difference, and it is discoverable only by someone
who already suspects it. The status roll-up should show it.

`ab_compare.py` does catch a cross-device pair at judge time and says a FAIL is
not attributable, so the measurement was never going to be silently wrong --
but it would have cost the run.

### 7. A docs-only or `[skip ci]` PR can never be folded, and is never told so

`fold.sh` requires `ci_green() == GREEN`. An empty `statusCheckRollup` yields
`NONE`, which is not GREEN, so the PR waits -- and the "not folded" comment
fires only on `RED`. **PR #101 and PR #102 both have zero checks** on their
heads, because their head commits carry `[skip ci]` from the standing
instruction that `AGENTS.md`'s transition note has since retired. Neither can
ever be folded, and neither will ever be told why.

`android.yml` and `desktop.yml` run on every PR with no path filter, so this is
`[skip ci]` and not a path-filter gap -- a new commit without the marker fixes
any individual PR. The durable fix is for `fold.sh` to treat `NONE` as
"cannot verify", comment once naming `[skip ci]` as the usual cause, and keep
waiting.

### 8. The board never wakes for a ready, unlabelled PR

`#101` went ready at 04:36Z and `#102` at 04:38Z, both with no state label. The
board tick at 04:49Z logged `nothing actionable`. The board is the only actor
that sets `needs-audit-1` or the doc-only `fold-ready`, and its script-first
gate (does `fleet.py` or the coverage gate report something?) does not count
"a ready PR with no state label" as something. The two labels in this session
were set by hand.

### 9. A structural skip is never told to the lane

`arms.sh` posts a `request.sh` refusal on the lane's PR but records a
*structural* skip only in `$WORK/arms/skipped/<sha>` on the host, which no lane
can read. At 04:29Z it skipped `lane/cloud-109`'s prediction:

```
a_ref 4129a349e6 with xemu.toml [display] renderer = OpenGL does not resolve
```

That is prose in the `a_ref` field -- a malformed registration by a cloud
session, which is a thing the lane must hear about and did not. `lane/cloud-109`
is PR #115, and nothing on it mentions this.

### 10. `arm` is "company" on every request the arms job queues

Every `.req` the arms job writes carries `"arm": "company"`, and the dispatcher
logs it: `(ref=3f2563d6e9 arm=company runs=1)`. Both arms of the pair get the
same value, so it cannot be distinguishing anything. `request.sh` writes the
field at line 907 from a variable I did not trace. Probably harmless, possibly
a default nobody meant; worth one look from whoever wrote `--arm`.

### 11. Two lanes each carry a root `NOTES.md`, and folds collide on it

`roles/lane.md`'s definition of done asks every lane for `NOTES.md` in the
branch root. `lane/blit83b` and `lane/cloud-109` both have one; `master` has
none. Whichever folds second conflicts on that path and gets `needs-rebase`,
and every lane after that conflicts with whatever landed. Either the path
should be per-lane (`docs/lanes/<name>/NOTES.md`) or it should not be folded at
all.

## What is verified working, end to end, as of this writing

- `selftest.sh`: 27 -> 46 checks, green. Every fix above ships with a check that
  **fails against the code it replaces** -- verified by running the new tests
  against the old script, not by assuming.
- The fold job folded its first PR (#116 -> `05e25ca29b`) unattended.
- The arms job queued #89's arm, both sides, and the dispatcher is building
  them -- past the CMake configure that failed twice, on one handheld, pinned.
  The verdict is not in at the time of writing; this line will read as a
  measurement or it will not, and it is written so the difference is visible.
