# lane.claimrace -- the audit outlet double-claimed #420 and tore down the live claim

Base: master @ 9f34d60036. Files: `docs/testing/jobs/cloud.sh`,
`docs/testing/jobs/selftest.d/73-cloud-claim.sh`, this file.

## The defect (2026-09-26 15:03-15:04 PDT, host outlet loop)

1. `cloud.sh` claimed audit2 #420 and started `hakux-lane-cloud-audit2-420`.
2. Seconds later the next call listed #420 as unclaimed. `pr_by_label` filtered
   `claimed:cloud` out of `gh pr list --label`, which GitHub serves from the
   search index, and the index lagged the label. The call "claimed" #420 again
   and re-added the row.
3. `systemd-run` refused the unit because it already existed. The "NO SESSION,
   NO CLAIM" rollback then removed the running session's territory row and
   `claimed:cloud`. fleet.py reported "RUNNING with no territory row".

## The change

- **Candidates are re-checked by number before a claim** (`first_free`,
  `held_why`, `unit_busy`). The list functions now return every match, and the
  first one nothing holds is claimed. A candidate is skipped, with the reason
  in the tick log (on stderr in `list` mode), when any of these is true:
  - A unit `hakux-lane-cloud-*-<num>.service` is active, activating,
    deactivating or reloading. The check covers any kind, because an audit and
    a remediation of one PR share one branch, and PRs and issues share one
    number sequence. `deactivating` covers the unit's tail while it is still
    releasing the claim.
  - The labels read by number carry `claimed:cloud` or `blocked:needs-owner`,
    or, for an issue, a `lane:` label.
  - The labels cannot be read. The check fails closed.
  
  A skipped candidate no longer blocks the rest of its queue for that tick.
- **The systemd-run failure path undoes nothing when a unit for that number is
  running.** Its log line calls this a collision and says the claim, the row
  and the snapshot belong to the running session. The EXIT trap still gives the
  attempt back because this tick started nothing. The attempt policy is
  unchanged. When no unit is running, the claim is dropped exactly as before.

### Where this departs from the brief, and why

- **Labels by number come from `gh api repos/.../issues/<n>/labels`, not from
  `gh pr view --json labels`.** Both are read by number and neither is
  search-backed. The REST endpoint answers for PRs and issues alike.
  `label_rm` already trusts it, and the stateful gh shims in selftests 71 and
  72 already answer it. Those shims would have needed changes for `pr view
  --json labels`, and those files are not this lane's.
- **Unit activity comes from `systemctl list-units <glob> --state=...`, not
  from `is-active`.** The glob also matches the exact unit, so the brief's two
  checks are one call. The shared selftest shim answers `active` to every
  `is-active`, so an `is-active` check would have refused every claim in
  fragments 71 and 98. That would have been a test artefact, not a behaviour.

## Proof: the three legs, and the world each one fails in

These run in `selftest.d/73-cloud-claim.sh`, fenced. They use a stateful gh
labels shim (`$CC_LABELS`) whose `issue list` does NOT read the labels, so it
behaves like the lagging search index. They also use a systemctl shim that
matches `list-units` globs against `$CC_ACTIVE`.

| leg | setup | expected | fails in the world where | shown by |
|---|---|---|---|---|
| f (x2) | `hakux-lane-cloud-issue-271` or `-remediate-271` active; list offers #271 | no systemd-run, no label, board sha unchanged, attempt unchanged, "skip issue #271: unit ... is running" | the list is trusted as served | master's cloud.sh: all 10 checks FAIL |
| f2 | no unit; `claimed:cloud` on #271 by number; list still offers it | no claim, board unchanged, "(read by number; the list lagged)" | only the list's labels count | master: 3/3 FAIL |
| g | unit becomes active at systemd-run, which fails (the race past f) | row still on board, `claimed:cloud lane:cloud-271` still on issue, snapshot kept, attempt given back, "collision" logged | every systemd-run failure is rolled back | master: 4 of 6 FAIL (the other two, no session and no attempt, held before too) |
| h | systemd-run fails, nothing active | row removed, labels removed, snapshot removed, attempt unchanged, "dropping the claim" logged | the fix over-reaches and calls any failure a collision | mutant (`if true` for the busy test): 4 of 6 FAIL |

Run against this branch, fragment 73 passes 43 of 43 (legs a-e unchanged,
f-h new). The falsifying runs replaced only `CC_JOBS`, which the fragment
already supports: master's jobs tree gave 26 passed and 17 failed, and the
mutant gave 39 passed and 4 failed. `bash -n` is clean on both files. The full
jobs selftest result is in the PR body.

## For the next lane

- A gap remains, and this change narrows it without closing it. Between
  `first_free` and `systemd-run`, a concurrent tick can still reach two steps:
  the snapshot `rm -rf "$SNAP"` and the `worktree remove --force "$wt"`. Both
  would hit a unit that the other tick started in that window. Only a lock
  around claim-to-start closes that (`flock` on `$WORK/cloud.lock`). The #420
  incident was sequential, not concurrent, so f covers it.
- Do not bring back `head -1` on the list functions. With it, one held
  candidate at the head of a queue hides every candidate behind it.

## Attempt 2 (2026-09-26): why attempt 1 did not finish

Attempt 1 pushed the change and opened PR #446 as a draft, then started the full
jobs selftest as a `run_in_background` task and ended its turn waiting for it.
That task died with the session, so no result was ever posted and the PR stayed
in draft. The suite takes longer than one 10-minute tool call (a foreground run
timed out at 590 s partway through the dispatch-hardening fragments), and it has
no per-fragment entry point. Attempt 2 merged origin/master, ran it in a
detached `systemd-run --user` unit writing `selftest.out`/`selftest.exit` in the
worktree, and polled that log in the same session.

The first full run on the merged tree gave 1886 passed, 2 failed:

- `72-cloud-tail.sh`: "a dispatch that never starts drops the claim as well
  as the row". That check anchors on the ONE line `say "systemd-run failed`,
  and the collision message began with the same words. So `grep -n` returned
  two line numbers and the extent went empty. The collision line now reads
  `say "$unit was not started, and ... is running: this is a collision, not a
  failed start ..."`. Leg g in 73 still matches it. Do not start another
  message in that branch with "systemd-run failed".
- `64-status-html.sh`: "the republished page carries the change". `status.sh`
  never runs `cloud.sh`, and master's CI passes this check. It depends on the
  host's environment, not on this diff. CI is the gate of record for it.
