# lane.cloudclaim -- cloud.sh: an unstarted claim spends no attempt; a folded lane/cloud-N is cleared

Issue #94 (harness defects). Files: `docs/testing/jobs/cloud.sh`,
`docs/testing/jobs/selftest.d/73-cloud-claim.sh`, this file.

## The incident

2026-09-26 07:44 PDT, issue #271: three ticks of the audit outlet each died on
`worktree add -b lane/cloud-271` ("a branch named 'lane/cloud-271' already
exists", a folded session's leftover at a9f64b930c, an ancestor of
origin/master) and exited 5. Each raised `$WORK/attempts/cloud-issue-271`
(1 -> 4), so `cloud.sh list` refused an issue that had had one session.

## What changed in cloud.sh

1. **The attempt is given back by an EXIT trap**, installed at the write of
   the counter and cleared only once `systemd-run` has started the unit. It
   restores the file as it was (an absent file stays absent), rather than
   writing `n - 1`. Between the write and the session there were five exits
   (worktree busy `exit 0`, fetch `exit 4`, three `exit 5`, snapshot `exit 6`)
   and only the snapshot path and the systemd-run failure path gave the count
   back. Those two explicit rollbacks are gone; the trap covers them.
2. **A stale local `lane/cloud-<n>` is deleted before `worktree add -b`**
   only when it is (i) checked out in no worktree, (ii) absent on origin
   (`git ls-remote --exit-code` returns 2; any other failure refuses), and
   (iii) an ancestor of `origin/$TIP`. One line is logged with its short sha.
   Otherwise the claim is refused with the reason: checked out, origin has it,
   origin could not be asked, or "holds N commit(s) not on origin/$TIP, which
   may be unpushed work". The refusal spends no attempt (the trap).

The remote-branch check uses `ls-remote`, not the local tracking ref: the
code path is already the "no `refs/remotes/origin/$branch`" branch, and
`fetch origin master board` never creates that ref, so its absence says
nothing about origin.

## Proof: selftest.d/73-cloud-claim.sh

Fenced: own `$HAKUX_WORK`, own scratch repo and bare origin (master with two
commits, the orphan `board` branch), own gh/systemctl/systemd-run shims, and a
`git` shim that fails `worktree add` only when `CC_FAIL_WT` is set. A
`systemd-run` line in the log is "the session started". `$CC_JOBS` selects the
jobs tree, so the same legs ran against origin/master's file staged under
`.scratch/old` (a `git archive` of `docs/testing/jobs` + `lane.sh`).

Legs: (a) forced worktree failure, attempts unchanged (1 stays 1 over three
ticks; absent stays absent); (b) stale ancestor branch deleted, session
starts, branch recreated at origin/master, deletion logged, attempt counted;
(c) branch with a commit not on the tip kept, refused with the reason, no
attempt; (d) ancestor that origin still has, kept; (e) ancestor checked out
in another worktree, kept.

### Before: origin/master (02374a6847) cloud.sh

```
== cloud.sh: an unstarted claim spends no attempt; a folded lane/cloud-N is cleared
  ok   a: the claim fails at worktree add, so no session starts
  FAIL a: and the attempts file is unchanged (1, the one real session)
  FAIL a: three such ticks, as on #271, still leave it at 1 -- not 4
  FAIL a: with no attempts file before, there is none after
  FAIL b: the stale lane/cloud-271 (an ancestor of origin/master) is deleted and the session starts
  FAIL b: it is recreated at origin/master, not left at the folded sha
  FAIL b: the deletion is logged, with the sha
  ok   b: and the attempt it spent is counted (1 -> 2), because a session ran
  ok   c: a lane/cloud-271 holding a commit not on origin/master is kept
  ok   c: the claim is refused, so no session starts
  FAIL c: and the refusal says why
  FAIL c: the refused claim spends no attempt
  ok   d: an ancestor that is still on origin is not deleted
  FAIL d: and the refusal says origin has it
  FAIL d: no attempt spent
  ok   e: an ancestor checked out in another worktree is not deleted
  FAIL e: and the refusal says it is checked out
  FAIL e: no attempt spent
pass=6 fail=12
```

Every leg fails at least one check. The six that pass on the old file are
the safety properties it already had (it never deleted a branch, never
started a session on a failed claim). "b: attempt counted 1 -> 2" passes on
the old file for the wrong reason: it spent the attempt with no session.

### After: this branch

```
== cloud.sh: an unstarted claim spends no attempt; a folded lane/cloud-N is cleared
  ok   a: the claim fails at worktree add, so no session starts
  ok   a: and the attempts file is unchanged (1, the one real session)
  ok   a: three such ticks, as on #271, still leave it at 1 -- not 4
  ok   a: with no attempts file before, there is none after
  ok   b: the stale lane/cloud-271 (an ancestor of origin/master) is deleted and the session starts
  ok   b: it is recreated at origin/master, not left at the folded sha
  ok   b: the deletion is logged, with the sha
  ok   b: and the attempt it spent is counted (1 -> 2), because a session ran
  ok   c: a lane/cloud-271 holding a commit not on origin/master is kept
  ok   c: the claim is refused, so no session starts
  ok   c: and the refusal says why
  ok   c: the refused claim spends no attempt
  ok   d: an ancestor that is still on origin is not deleted
  ok   d: and the refusal says origin has it
  ok   d: no attempt spent
  ok   e: an ancestor checked out in another worktree is not deleted
  ok   e: and the refusal says it is checked out
  ok   e: no attempt spent
pass=18 fail=0
```

## For the next lane

- The full `selftest.sh` takes over 10 minutes here; run it detached and poll
  its output file, not as one foreground call.
- The Bash tool here rejects `$?` and quoted braces in a command; put probes
  in a file.
- Not done, out of this brief: the PR path (`worktree add --detach`) cannot
  hit the branch collision, but the host's runbook deletion of stale
  `lane/<x>` for local lanes is still manual.
