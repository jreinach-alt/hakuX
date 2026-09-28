# lane.cloudlaneguard

`cloud.sh` does not claim a PR while that PR's own lane session is still
running on its head branch.

## The defect

`held_why` asked `unit_busy`, which lists only `hakux-lane-cloud-*-<num>`.
A PR's own lane is a `hakux-lane-<x>` unit in `$WORK/wt/<x>`, and nothing asked
about it. On 2026-09-27, PR #523 (`lane/thermal507-power`) was claimed for
audit1 at 01:24Z and for remediate at 01:34Z while `hakux-lane-thermal507` was
active. Two sessions then committed to that branch minutes apart (`fe5940a6e2`
and `20502ec594`).

## The change

- `lane_on_branch <branch>` lists the running `hakux-lane-*.service` units.
  It uses the same states as `unit_busy`: active, activating, deactivating and
  reloading. It skips `cloud-*` units. For each remaining unit it reads the
  branch checked out at `$WORK/wt/<x>` (`git symbolic-ref`) and prints every
  unit whose branch equals the argument.
  - The brief asked for active and activating only. Deactivating is included
    because a lane's tail can still push while the unit stops. `unit_busy`
    counts it for the same reason.
- `held_why` does this for every kind except `issue`:
  - It reads the head branch by number with
    `gh api repos/$GH_REPO/pulls/<n> --jq .head.ref`.
  - If that call exits non-zero, the PR is held: "its head branch could not be
    read by number". This matches how the label read fails closed.
  - If the REST answer is empty, it uses the head from the list row that
    `first_free` now passes in as `$3`. A PR's head branch never changes. If
    that is empty too, the PR is held.
  - The fallback matters because the existing fragments (71, 72, 98, 99-limits)
    have `gh` stubs that answer every other `api` path with an empty string and
    exit 0. Without the fallback, a strict fail-closed on empty would have
    turned those fragments red.
- In `list` mode the output reads
  `skip <kind> #<n>: its lane hakux-lane-<x> is still running on <branch>`.
- The claim order, the cap and the issue path are unchanged.

## Proof

### The fragment passes

`selftest.d/99-cloud-lane-branch.sh`:

```
== cloud.sh: a PR whose lane is still running on its head is not claimed
  ok   a: with hakux-lane-thermal507 active on lane/thermal507-power, #523 is not claimable
  ok   a: and list names the lane and the branch
  ok   b: with the lane unit inactive, #523 is claimable
  ok   c: with the lane unit active on another branch, #523 is claimable
  ok   d: a cloud-* unit on the branch is not taken for the PR's lane
  ok   e: a head that cannot be read by number holds the PR
  ok   e: and list says why
7 passed, 0 failed
```

### Every leg fails in the world it names

The fragment's `$CL_JOBS` points it at a staged copy of `jobs/`. I ran it
against each version below.

| cloud.sh under test | legs that FAIL |
|---|---|
| origin/master's (the new `held_why` lines reverted) | a, a, e, e (4 of 7) |
| `cloud-*` units not excluded | d |
| no fail-closed on a failed head read | e, e |
| any worktree on the branch holds, unit state ignored | b |
| any running lane holds, branch ignored | c |

Output against origin/master's `cloud.sh`, with the lines reverted:

```
== cloud.sh: a PR whose lane is still running on its head is not claimed
  FAIL a: with hakux-lane-thermal507 active on lane/thermal507-power, #523 is not claimable
  FAIL a: and list names the lane and the branch
  ok   b: with the lane unit inactive, #523 is claimable
  ok   c: with the lane unit active on another branch, #523 is claimable
  ok   d: a cloud-* unit on the branch is not taken for the PR's lane
  FAIL e: a head that cannot be read by number holds the PR
  FAIL e: and list says why
3 passed, 4 failed
```

Legs b, c and d pass on master by construction, because master holds nothing.
They guard against the fix reaching too far, and the mutants in the table show
that each one fails when it does.

### `cloud.sh list` on the real host

Run 2026-09-27 from this branch:

```
cap: LANE_MAX=24 (/home/justin/hakux-work/limits.env, default from lane.sh); 7 lane/audit session(s) active
skip audit2 #523: its lane hakux-lane-thermal507 is still running on lane/thermal507-power
nothing to claim
```

This is the incident PR. Its lane is still running, so the repo's outlet now
refuses it, as the host's interim guard (`audit_outlet.sh` ->
`lane_on_branch.sh`) already did.

### The full suite and preflight

- `selftest.sh`, run locally: `2253 passed, 0 failed`. That includes the other
  `cloud.sh` consumers, 70-73, 98-audit-outlet and 99-limits-env.
- `preflight.sh` passed.

### CI headroom

The first CI `jobs selftest` run on this PR (36367749352, on a0ee77d688) was
**cancelled at the job's `timeout-minutes: 25`**. No check in it failed.

| Workflow | Runs | Duration |
|---|---|---|
| master's `jobs selftest` | three consecutive runs on 2026-09-28 | 22-24 min each |

With master already that close to the cap, a small addition, or a slow runner,
tips a run over. This fragment adds 5 `cloud.sh list` calls, about a second on
this host. The next push is the retry.

The retry on 39494188b9 passed in 24m06s.
- The headroom itself belongs to whoever owns `.github/workflows/`. The fix is
  a higher `timeout-minutes` or a split suite. This lane's brief does not grant
  that file.

## Attempt 2: the board's focus (addendum 2026-09-27 20:07 PDT)

### Why attempt 1 did not finish

Attempt 1 finished the brief as it read when it started, got CI green on
39494188b9, and marked the PR ready. The hostops addendum arrived after that
session had ended, so it never read it. The PR went back to draft, and this
session was resumed to do the addendum.

### The defect

With `BOARD_FOCUS_LABEL=fps-focus` in `limits.env`, `board.sh` offers only
issues that carry the label (board.sh:148-189). `cloud.sh`'s issue pickup had
no such filter. `cloud.sh list` said "would claim issue #527"
(accuracy,needs-triage,cloud), so the cloud outlet was a way around the focus.

### The change

- `FOCUS` is `BOARD_FOCUS_LABEL` with whitespace stripped, as board.sh strips
  it. It comes from `limits.env`, which cloud.sh already sources, or from the
  environment, the same two sources board.sh reads.
- `issue_cloud`'s `--jq` now appends the issue's labels to each row, after a
  unit separator (0x1f). The loop strips them off again before the row reaches
  `first_free`, so the row keeps its old shape.
  - A tab would not work here: tab is IFS whitespace, so `read` would collapse
    the row's existing empty head column.
  - 73-cloud-claim's stub row (`271\t\t...`, with no labels part) still passes
    through unchanged when no focus is set.
- If the focus is set and an issue lacks it, the issue is dropped. `list`
  names all the drops in one line on stderr:
  `skip issue #527: not in the fps-focus focus (BOARD_FOCUS_LABEL=fps-focus)`.
  A claiming run writes the same line through `say`.
- PR audits and remediations are not filtered. The claim order and the cap are
  unchanged.

### Proof

Legs f, g and h in `99-cloud-lane-branch.sh` assert on the words `list` prints:

```
== cloud.sh: an issue outside the board's focus is not offered
  ok   f: with the fps-focus focus, non-focus #527 is not offered
  ok   f: and list names the drop in one line
  ok   f: and the focus issue #530 is offered
  ok   g: with only non-focus #527 open, nothing is claimed
  ok   h: with no focus set, #527 is offered
```

| cloud.sh under test | legs that FAIL |
|---|---|
| attempt 1's (39494188b9 + master merge, no focus filter) | f, f, f, g (4 of 5) |
| the filter applied even when no focus is set | h |

The fragment against attempt 1's `cloud.sh`:

```
  FAIL f: with the fps-focus focus, non-focus #527 is not offered
  FAIL f: and list names the drop in one line
  FAIL f: and the focus issue #530 is offered
  FAIL g: with only non-focus #527 open, nothing is claimed
  ok   h: with no focus set, #527 is offered
```

`cloud.sh list` on the real host, 2026-09-27, after the change:

```
cap: LANE_MAX=24 (/home/justin/hakux-work/limits.env, default from lane.sh); 7 lane/audit session(s) active
skip audit1 #518: its lane hakux-lane-forza414 is still running on lane/forza414b
nothing to claim
```

No focus-drop line appears, and that is expected. #527 now carries
`claimed:cloud,lane:cloud-527`, so it is already claimed by a cloud session.
`issue_cloud`'s jq already excludes it on those labels, so it
never reaches the focus check. The live line also shows the lane guard from
attempt 1 holding a second PR, #518, whose lane `forza414` is still running.

- The full `selftest.sh`, run in this worktree on 0de96ac0ac:
  `2288 passed, 0 failed`. `preflight.sh` passed.
- Staging a subset of fragments in a copy that is not a git tree breaks
  99-limits-env on its own (3 FAIL), with or without this change. Run the full
  suite in the real worktree.

## For the next lane

- A lane unit whose worktree is detached (`symbolic-ref` fails) never matches.
  Today every lane worktree is on `lane/<name>`, so this is not a gap yet. If
  lanes ever run detached, match on `rev-parse HEAD` against the PR's head sha.
- Every `gh` stub in the cloud fragments answers unknown `api` paths with an
  empty string and exit 0. A new REST read in `held_why` has to either tolerate
  an empty answer or update those stubs. The list-row fallback here is the
  first of those options.

### Waiting

- **Waiting on:** CI (`build`, `jobs selftest`) on the head that carries this line.
- **Resolved by:** those checks going green. The PR is then marked ready. The
  selftest job runs close to its 25-minute cap, so a CANCELLED run is the
  timeout and should be rerun, not debugged.
