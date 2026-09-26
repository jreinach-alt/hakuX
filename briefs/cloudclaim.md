# cloudclaim -- cloud.sh: a claim that never started must not spend an attempt; clear a stale folded branch

Lane: cloudclaim
Issue: #94 (harness defects)
Base: origin/master at a5b5b628f2 or later.
Files: docs/testing/jobs/cloud.sh, docs/testing/jobs/selftest.d/73-cloud-claim.sh, docs/lanes/cloudclaim/**
Needs device: no. Needs NDK: no.

## Why (evidence)
2026-09-26 07:44 PDT the host ran the audit outlet (`cloud.sh`) three times for issue #271. Each run printed
`fatal: a branch named 'lane/cloud-271' already exists` / `cannot create .../wt/cloud-issue-271 for issue #271 on a new
lane/cloud-271; not claiming` and exited 5 -- and each run raised `$WORK/attempts/cloud-issue-271` by one (1 -> 4),
so the next `cloud.sh list` said `would REFUSE issue #271: 4 attempts`. The issue had had ONE real session.
Two defects in docs/testing/jobs/cloud.sh:
1. The counter is written at `echo "$n" > "$att"` (~:428) BEFORE the worktree is created, and the three
   `exit 5` paths under "claim and start" (~:494, :497, :523) do not restore it (the path at ~:480 does:
   `echo "$(( n - 1 ))" > "$att"`). A claim that never started a session is not an attempt.
2. The new-branch path (`worktree add -b lane/cloud-<n>`) fails whenever a local `lane/cloud-<n>` survives from a
   previous, already-folded session (here a9f64b930c, an ancestor of origin/master). The host runbook deletes it by hand
   (`git merge-base --is-ancestor lane/<x> origin/master` then `git branch -D`); the outlet should do that itself, and only
   in that case (a branch that is NOT an ancestor of the tip may hold unpushed work: keep refusing, and say why).

## Build
- Restore the counter on every exit between the write and the session start (a trap or explicit rollbacks; match the
  file's style).
- Before `worktree add -b`, if the local branch exists, is not checked out in a worktree, has no remote, and is an
  ancestor of origin/$TIP, delete it and log one line; otherwise refuse as today.

## Proof
docs/testing/jobs/selftest.d/73-cloud-claim.sh (fenced HAKUX_WORK/REPO_DIR, a scratch repo): (a) a forced worktree failure
leaves the attempts file unchanged; (b) a stale local lane/cloud-N that is an ancestor is deleted and the claim proceeds
(stub the session start); (c) a stale branch with a commit NOT on the tip is kept and the claim refused. Each leg must fail
on origin/master's cloud.sh (run it once against the old file and paste the failures in NOTES).
Run `bash docs/testing/jobs/selftest.sh` (the whole suite) green.

## Done when
A READY PR with the selftest's before/after output in docs/lanes/cloudclaim/NOTES.md.

## Do not
Edit board files. Run cloud.sh against the live $WORK. Trigger CI as a self-check. Wait on a background task at the end of a turn.
