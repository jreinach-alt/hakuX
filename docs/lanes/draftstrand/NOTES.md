# lane.draftstrand — a draft PR whose lane has exited

PR #153. Harness only; no tracker issue (dispatched directly).

## What was wrong

Ten open lane PRs on 2026-09-19; five were finished, CI-green and stranded in
draft with no lane running (#137, #141, #145, #146, #148). Every actor filters
drafts out, and every one of them is right to: `board.sh:107` skips `isDraft`,
`fleet.py:44` counts only non-draft lane PRs, `fold.sh` refuses to fold a draft
and strips its `fold-ready`, `handback.sh` had no draft handling at all. Draft
means *a lane is still working*, and while the unit is up that is exactly true.

The state is only wrong **once the unit has exited**, and nothing joined those
two facts: `isDraft` comes from GitHub, liveness from systemd, and no job asked
both questions. That join is the whole defect and the whole fix.

The second half matters as much: three of the five had not failed. They ended
**waiting** — CI is ~10 minutes, a device arm ~90, an audit is a different
session — and a lane has no way to sleep. So a lane that pushes and must wait
can only burn turns polling until the turn cap cuts it, or end tidily and
strand. The tidier the lane, the more likely it strands. `roles/lane.md` item 5
told them not to end in draft, and for those three it was not followable.

## What was built

`jobs/handback.sh` gets a **second pickup**, not a second script. The label
table (`HANDBACK_ROWS`) stays what it is; `stranded_drafts()` asks GitHub a
different question and produces the same eight fields, and both feed one loop
body. So the lane-name derivation, the once-per-cause key, the worktree check,
the liveness check, `LANE_MAX`, the attempt counter and the comment are still
written exactly once. There is one `lane.sh resume` call site and the selftest
pins that count at 1 — two causes with two call sites is how they drift.

**Detection** is `open && isDraft && head ~ lane/* && hakux-lane-<name> not
active`. The liveness half is `systemctl is-active`, never a timestamp: a
working lane can be quiet for an hour inside one Gradle build, and a false
positive here kills live work.

**Two causes, because one marker key is not enough.** The marker is
`$label-$pr-$head`, so:

| cause | fires when | why it is separate |
|---|---|---|
| `draft-strand-arm` | the PR carries `verified` or `regressed` | `arms.sh` posting a verdict is information the lane has never seen; it should not wait out a clock |
| `draft-strand-quiet` | nothing has changed on the PR for `DRAFT_STRAND_SECS` (7200) | the fallback when there is no explicit signal |

Sharing one key would mean a verdict landing after a quiet resume could never
reach the lane at that head.

**The quiet clock is GitHub's `updatedAt`, not a file on this host.** A
first-seen stamp written locally restarts every stranded PR's clock whenever
the job is redeployed or the timer restarts — which is exactly when a backlog
of strands exists. 7200s is four fold ticks and outlasts a ~90-minute arm: a
lane resumed at 30 minutes would be handed the same "still queued" it ended on,
and the once-per-head marker would then stop it ever being resumed at that head
again. That false positive is not merely wasteful, it is terminal, which is why
the clock is long rather than eager.

**It resumes the lane; it does not mark the PR ready.** Items 1–4 of the
definition of done — `NOTES.md` written, `Files:` matching the diff, the
prediction committed with its refs — are not checkable by a script. A job that
flipped `isDraft` because CI went green would be declaring finished work that
nobody verified. The selftest pins this by enumerating the `gh pr` verbs the
script invokes (`list`, `comment`) rather than grepping for the phrase — the
brief this job *writes* legitimately tells the lane to run `gh pr ready`, so a
phrase grep matches the prose and proves nothing.

**The resume carries the resolved state.** CI on the head collapsed to
GREEN/RED/NONE/PENDING with the same expression `fold.sh` uses, the arm verdict
label, and how long the PR has been quiet — plus a per-state paragraph (a NONE
gets the merge-conflict-or-retired-marker explanation; a `regressed` gets "read
the `[job.arms]` comment before anything else"). A lane resumed with no new
information repeats what it did before, which is how a PR burns four attempts
having never been wrong about anything.

**A strand resume does not spend an attempt.** `lane.sh resume` counts every
resume; the fourth escalates the model and the fifth is refused outright. That
is right for a lane that ended without finishing and wrong for one that ended
because CI takes ten minutes — re-merges burned two lanes' attempts and
escalated one to Fable for no reason of its own the same night. `lane.sh` is
another lane's file, so the counter is read before the resume and put back
after, for the strand causes only. That is safe from here: by the time
`lane.sh resume` returns 0 the unit is up, and a second
`systemd-run --unit hakux-lane-<name>` cannot start while it is.

**So something else has to be able to end it.** Putting the counter back means
the escalation policy never will. `DRAFT_STRAND_MAX` (3, per lane) is the
replacement: a lane handed the resolved state three times and still in draft is
not waiting on anything this job can see, and gets `blocked:needs-owner` and a
comment saying *why* nothing else was going to stop it. `LANE_MAX`, the
one-resume-per-tick rule and `LANE_MAX_ATTEMPTS` all still apply unchanged — a
lane already out of attempts cannot be strand-resumed at all.

**Stale set.** A draft carrying `needs-rebase`, `needs-audit-1`,
`needs-audit-2`, `needs-remediation`, `fold-ready`, `folded` or
`blocked:needs-owner` is skipped: every one of those already has an actor, and
this cause is only about a PR that has none.

`roles/lane.md` item 5 now says what a waiting lane should actually do (post
`[lane.<name>] waiting:`, name the resolving signal, stop) and names the actor.
`roles/board.md` gains the strand alongside its `needs-rebase` paragraph, and
its "Retries and escalation" section no longer tells the board to resume a lane
whose "PR is not `ready`" — `board.sh` filters drafts out before the board ever
sees one, so that instruction was unactionable from the day it was written.

## The deeper fix — "wake lane X when Y" — and why I did not build a file for it

The brief asks whether a small wake-file is the right shape. **I did not build
one, and I think that is right, for CI.** The wake-file's job is to record
*which lane is waiting on what*, so a producer can fire it. But both producers
already have the answer without being told:

- `fold.sh` reads `statusCheckRollup` on a head every tick anyway; this job now
  reads it in the same `pr list` call that finds the strand. A file saying
  "wake foldregress when #145's CI concludes" would carry no fact that the PR
  itself does not already carry, and would then need its own staleness rules
  for the lane that never gets around to writing it.
- `arms.sh` already publishes its verdict *on the PR*, as the `verified` /
  `regressed` label. That label **is** the wake signal, it is durable, and it
  survives a restart of every job in the harness. `draft-strand-arm` keys on it
  directly.

What the polling shape costs is latency: up to one fold tick (30 min) for an
arm verdict, and up to `DRAFT_STRAND_SECS` (2h) for a wait with no explicit
signal. That is cheap against a PR that previously waited forever, and against
the cost of a registry of waits that can itself go stale — which is the exact
failure `lane.sh`'s own header describes for the fleet registry (`fleet.py`
reported four running lanes, two of which were not running).

**Where a wake-file would genuinely help**, and what I would build if this
proves insufficient: a wait whose resolving signal is *not visible on the PR at
all*. An audit that is a different session, a device that is held, a decision
on another issue. Today those fall through to the 2h quiet clock, which resumes
the lane to tell it nothing new — it costs a session and the lane's only honest
move is to post `[lane.<name>] waiting:` again. If that pattern shows up in the
logs (grep `[job.handback] Resumed` against PRs that then only comment
`waiting:`), the right shape is one line written *by the waiting lane itself*,
e.g. `$WORK/waits/<lane>` holding a shell condition, checked here before the
quiet clock fires. Written by the lane, because the lane is the only actor that
knows what it is waiting for. **Do not build it speculatively**: the registry
that nobody writes is worse than the poll that needs nobody.

## What the next lane should not repeat

- **Do not grep for the phrase when the script's own prose contains it.** The
  first version of "this job never marks a PR ready" was
  `! grep -qE "^[^#]*pr ready"`, which fails against correct code: the brief
  this job writes tells the lane to run `gh pr ready <n>`. Enumerate the verbs
  actually invoked instead.
- **Do not write a negated check as `bash -c '! grep … "$var"'`.** A child
  shell sees only exported variables, so such a check is green against
  anything the moment the variable is fragment-local. The `$got` checks around
  the jq round-trip were written that way first and passed against a query
  that produced nothing.
- **The strand counter is shared state between checks in one fragment.** Three
  resumes earlier in the file silently pushed a later block over
  `DRAFT_STRAND_MAX` and made a correct build look broken. Each block that
  needs a resume clears it, and there is an explicit check that a resume *does*
  increment it — otherwise the cap is unreachable and its checks are vacuous.
- The `--jq` is bypassed by every shim, so a typo in it is invisible to every
  behavioural check. The fragment extracts the real query from
  `stranded_drafts()` and runs it through real `jq` against a fixture that
  includes a non-draft, a `claude/*` head, a failing check, an empty rollup and
  an unconcluded one — the four states that must not read as GREEN.

## The irony, discharged

This lane's own PR is the one that must not strand. Marked ready at the end of
the session, not left for the detector it just built.
