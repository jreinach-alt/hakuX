# Winding down the orchestrator session

Written 2026-09-19 for the local session `Orchestrator Local Session`
(running since 2026-09-07 on `claude/es-de-launcher-disc-error-ojnl14`) so
that Phase 0 of [`ORCHESTRATION-DESIGN.md`](ORCHESTRATION-DESIGN.md) can
start without two actors migrating the same harness at once.

**The channel.** A cloud session cannot message a local one, and a local
session's monitors watch GitHub. So this brief is delivered three ways, and
any one of them is enough: the owner pastes the prompt at the bottom into
the local session; the tracking issue on GitHub carries a link to this file;
and this file is on `origin/claude/hakux-orchestration-design-e663m8`, which
the local session can `git show`. Completion is signalled the same way: one
comment on the tracking issue with a fixed first line.

**The rule for the whole procedure: preserve, do not decide.** Nothing gets
folded, merged, retired, deleted or re-queued. Everything in flight is
pushed somewhere durable and written down. The migration that follows
(fast-forward master, merge the remote lane, move the board) is done once,
by the design session, after this completes.

---

## What the local session does, in order

Each step ends with a line in the hand-off file (§template below). Do not
skip a step because it looks empty; write "none" and move on.

### 0. Announce

Comment on the tracking issue: first line `[lane.orchestrator] wind-down
started`, then the current tip sha of the campaign branch and the local
time. Then stop dispatching: no new lanes, no new briefs, no new territory
rows, no new device requests. Do not dispatch `lane.toolsmith` or
`lane.fold`; both files they own are being rewritten on the design branch.
Leave every hold file exactly as it is.

### 1. Inventory, before touching anything

Capture, verbatim, into the hand-off file:

```
python3 docs/testing/fleet.py 2>&1
bash docs/testing/dispatcher.sh status
ls -la $DISPATCH_DIR/queue $DISPATCH_DIR/running $DISPATCH_DIR/hold
cat $DISPATCH_DIR/hold/*.why 2>/dev/null
git worktree list
git -C /home/justin/hakuX status --short
git -C /home/justin/hakux-work/fold status --short
docs/testing/backlog-gate.sh status
ls $DISPATCH_DIR/fleet/ $DISPATCH_DIR/board-requests/ $DISPATCH_DIR/deliveries/ 2>/dev/null
```

plus the `ListAgents` output and the list of Monitors running (the idle
watchdog and `watch_remote_lane.sh`, if they are).

### 2. Drain the running lanes

For every sub-agent still running, send it one message:

> Wind-down. Finish the step you are in, commit, push your work to
> `origin/lane/<your-lane-name>` (create it if it does not exist), post your
> report on your issue with the first line `[lane.<name>] report`, and stop.
> Do not start anything new. If you are blocked, say on what in the report
> and stop anyway.

Wait up to 60 minutes. For a lane that has not reported by then, record its
worktree path, branch and last commit in the hand-off file and leave its
worktree in place. Never remove a worktree in this procedure.

### 3. Put every unfolded commit on a pushed branch

For each fleet entry in state `reported` (and each `running` lane that
drained), make sure its commits exist on origin under `lane/<name>`:

```
git -C <worktree> push origin HEAD:refs/heads/lane/<name>
```

Record `lane, issue(s), branch, tip sha, files touched` in the hand-off
file. This is the list the fold job will merge, one `--no-ff` merge each,
after master is fast-forwarded.

### 4. Preserve the bound predictions

For every request in `$DISPATCH_DIR/queue` and `$DISPATCH_DIR/running`, read
its `expect` path. If that path is inside a worktree, copy the file to
`$DISPATCH_DIR/predictions/<its sha256>.json` (the binding is the hash, so
the copy is neutral) and record `request id, prediction path, sha256,
a_ref, b_ref` in the hand-off file. Do not edit any request. Do not re-queue
anything. Do not remove holds.

### 5. Apply the pending board requests and push the board

Apply every `$DISPATCH_DIR/board-requests/*.md` that has not been applied,
in one final `board:` commit to `territory.toml` and `nv2a_issues.toml`.
Mark every lane row for a lane that has drained with `state = "retired"` in
`$DISPATCH_DIR/fleet/<lane>.json` (the file, not the TOML). Run
`preflight.sh`. Push the campaign branch. Then verify, and paste the output:

```
git -C /home/justin/hakuX status --short            # must be empty
git -C /home/justin/hakuX log --oneline origin/claude/es-de-launcher-disc-error-ojnl14..HEAD   # must be empty
git -C /home/justin/hakux-work/fold status --short  # must be empty
```

### 6. Write the hand-off file

`docs/investigations/handoff-2026-09-19.md`, from the template below, with
every section filled. Commit it as
`docs: hand-off for the orchestration migration [skip ci]` and push. This
file is the only thing the next actor reads; assume nothing in the
transcript survives.

### 7. Release everything the session holds

```
docs/testing/backlog-gate.sh release
docs/testing/hold_device.sh release     # only if this session started a hold_device
docs/testing/goal.sh clear
```

Stop the idle watchdog and `watch_remote_lane.sh` Monitors. Confirm
`stop-emulator.sh` will run at turn end (it is a Stop hook; nothing to do
unless a lease is being renewed by something this session started).

### 8. Signal, and end

Comment on the tracking issue with the first line
`[lane.orchestrator] wind-down complete`, then the campaign tip sha, the
hand-off file path, and the count of lane branches pushed. End the turn.
**Do not start another turn on this session.** If the Stop hook blocks the
stop, it is the old backlog gate; the release in step 7 makes it inert, and
its release valve allows the stop after six blocks regardless.

## What the local session must not do

- Do not fast-forward or push `master`.
- Do not merge, cherry-pick or fold anything, including PR #45's branch.
- Do not edit `dispatcher.sh`, `preflight.sh`, `settings.json`,
  `check_territory.py`, `check_coverage.py`, `fleet.py`, the hooks or the
  timer units. All of them are being changed on the design branch.
- Do not create Routines, crons or new Monitors.
- Do not remove worktrees, hold files, queued requests or fleet files.
- Do not answer the remote lane's open question on PR #45 (the two shas it
  asked for). The design session answers it by merging the branch.

## What happens next, and who does it

| step | actor | when |
|---|---|---|
| Fast-forward `master` to the campaign tip | design session, on the owner's go | after "wind-down complete" |
| Merge `claude/docs-tooling-agentic-coding-u152m1` into master with `--no-ff`; comment on PR #45 | design session | same |
| Merge each `lane/<name>` from the hand-off list with `--no-ff` | design session | same |
| Create the orphan `board` branch from the final TOMLs | design session | same |
| Land the Phase 0 code (dispatcher private builds, `lane.sh`, hooks, units, preflight) as a PR to master | design session, already in progress | CI green, owner merges |
| Install units and settings on the host, restart the dispatcher | owner, `docs/testing/jobs/install-host.sh` | once |

---

## Hand-off file template

```markdown
# Hand-off, 2026-09-19: orchestrator session wound down

Written by the local orchestrator session at <time>. Campaign tip <sha>.

## 1. Inventory at wind-down
<verbatim outputs from step 1>

## 2. Lanes drained
| lane | issues | agent state | branch | tip | files | report comment |
|---|---|---|---|---|---|---|

## 3. Lanes that did not respond
| lane | worktree | branch | last commit | what it was doing |

## 4. Unfolded work, by branch (the fold list)
| branch | issues | commits | audit state (pass1/pass2/none) | notes |

## 5. Bound predictions
| request id | state (queued/running) | prediction sha256 | a_ref | b_ref | copied to |

## 6. Board requests applied in the final board commit
<list, or "none">

## 7. Holds and the device state
<hold files, .why contents, last known device state>

## 8. Open questions the next actor must answer
<numbered; include the remote lane's PR #45 request and any grant a lane asked for>

## 9. Released
backlog gate: <output>   hold_device: <output>   goal: <output>   monitors stopped: <list>
```

---

## The prompt to paste into the local session

```
Wind-down. Phase 0 of the orchestration redesign starts now and this session is
being retired. Fetch and read the procedure, then follow it exactly, in order,
preserving everything and deciding nothing:

    git fetch origin claude/hakux-orchestration-design-e663m8
    git show origin/claude/hakux-orchestration-design-e663m8:docs/ORCHESTRATION-WIND-DOWN.md

The tracking issue is the one titled "harness: Phase 0 -- wind down the
orchestrator session and migrate to jobs" (find it with gh issue list). Announce
there first, signal completion there last, and then end the turn and do not
start another. Do not fold, merge, fast-forward master, edit the dispatcher or
preflight or hooks, or touch PR #45. Everything else you hold goes onto a pushed
lane/<name> branch and into docs/investigations/handoff-2026-09-19.md.
```
