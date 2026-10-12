# boardgateenv1009 -- the board push gate stages master's docs/testing into the pushing tree's index (#433, 0.5)

## The mechanism, confirmed by hand before touching the fix

Reproduced the defect outside the repository (a scratch `mktemp -d` under the worktree, deleted after): a worktree
`PUSHWT2` on an orphan `boardbranch` (no `docs/testing` at all -- the real board tree's shape), and a second
worktree `S2` of `master` (which has `docs/testing`). Running

```
GIT_DIR=<PUSHWT2's absolute git dir> git -C S2 checkout -q master -- docs/testing
```

(no `GIT_WORK_TREE`) wrote the file content into `S2`'s working tree (because `-C` sets the cwd, and git falls
back to cwd as the worktree when `GIT_WORK_TREE` is unset and `GIT_DIR` doesn't look like a bare `.git`), **but
staged it in `PUSHWT2`'s own index** (because `GIT_DIR` picks the repository/index, and `-C` does not override
that). `git -C PUSHWT2 status --porcelain` afterward: `AD docs/testing/f.txt` -- Added in the index, Deleted in
the worktree, i.e. staged in a place that does not have the file on disk. That is exactly the shape of the
observed board commit (127 files changed, no corresponding working-tree edit by the session). Clearing `GIT_DIR`
(and the rest of `git rev-parse --local-env-vars`) before the call removes the pollution entirely; verified both
directions by hand.

A first repro attempt (two worktrees of the SAME branch, so `docs/testing/f.txt`'s content was already identical
to what is checked out) showed no diff at all -- not because the bug was absent, but because checking out content
that already matches `HEAD` never shows as staged. Needed a worktree whose branch genuinely lacks the path, which
is also the real board tree's shape, to see the pollution.

## The fix (`board-push-gate.sh`)

One line, placed before `set -u` and the first `git` call: iterate `git rev-parse --local-env-vars` (git's own
list of repository-local env vars: `GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_OBJECT_DIRECTORY
GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_IMPLICIT_WORK_TREE GIT_GRAFT_FILE GIT_NO_REPLACE_OBJECTS
GIT_REPLACE_REF_BASE GIT_SHALLOW_FILE GIT_CONFIG GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT` on this git) and `unset`
every name it prints, rather than the brief's hand-picked subset: a newer git exporting one more repository-local
var is still covered, and `git rev-parse --local-env-vars` itself needs no valid repository (confirmed: it prints
the same static list even with `GIT_DIR=/nonexistent/.git` set), so it is safe to run before anything else.

Every git call in the gate already names its tree with `-C`, so this is pure subtraction -- nothing the gate
relies on reads these vars on purpose.

## The selftest case (`selftest.d/97-board-push-gate.sh`)

Added after "after the repair the same push goes through" (the existing real `git push` through the installed
hook that reaches a PASS). That push *already* runs the gate exactly the way the defect requires -- as a real
pre-push hook, with git's own `GIT_DIR` export, no synthesis needed -- the existing fragment just never looked at
`$BP/bt`'s own index afterward. Added three checks on `$BP/bt` (the pushing/board tree) right there:
- `git diff --cached --name-only -- docs/testing` is empty (nothing staged),
- `docs/testing` does not exist on `$BP/bt`'s disk (board tree has none, by design),
- `git status --porcelain` is empty (nothing else leaked either).

Mutant: removed the `for _v in ...; do unset ...; done` line (keeping the explanatory comment, which still names
`local-env-vars`) and reran `SELFTEST_ONLY=97-board-push-gate.sh`. Result: 26 passed, 2 failed -- the "did NOT
stage" and "otherwise clean" checks went red (`AD docs/testing/*.toml`-shaped staging under `$BP/bt`'s index);
the "nor leave it on disk" check stayed green, consistent with the brief's own observation that the board tree's
files on disk do not change -- only its index does. All 25 pre-existing checks in the fragment stayed green
under the mutant, so the new case is the only one that depends on the fix. Restored the fix; reran; 28/28 green.
Pasted both tails in PR.md.

Ran the fragment alone and the full `selftest.sh` (`SELFTEST_ONLY` first, then no filter) with the fix in place;
both clean. No other fragment's output changed.

## Scope held

Did not touch `jobs/board.sh` (the hook installer). The hook it writes already exports nothing extra on its own
-- the exposure is git's own pre-push behavior, external to `board.sh`'s control, so there is nothing for
`board.sh` to clear; flagged in OUTBOX.md anyway per the brief's instruction, in case a belt-and-suspenders
clear in the hook script itself is wanted later.

Never ran this gate against a real board tree or `~/hakux-work/board-wt`; every repository and worktree used
here lives under `selftest.sh`'s own `$T` (itself a `mktemp -d`), consistent with the existing fragment's style
and the lane's offline/no-side-effects rules.
