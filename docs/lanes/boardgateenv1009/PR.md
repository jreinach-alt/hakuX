# boardgateenv1009 -- the board push gate stages master's docs/testing into the pushing tree's index (#433, 0.5)

State: ready

Lane: boardgateenv1009          Issue: none (harness fix, #433 umbrella)
Base: master @ 39379dafdd
Files: docs/lanes/boardgateenv1009/NOTES.md, docs/lanes/boardgateenv1009/OUTBOX.md, docs/lanes/boardgateenv1009/PR.md, docs/testing/jobs/board-push-gate.sh, docs/testing/jobs/selftest.d/97-board-push-gate.sh
Prediction: none: shell/selftest change, no pgraph golden or device arm
Needs device: no    Needs NDK: no
Release note: none. This PR changes no emulator code (board push gate + its selftest only).

**The defect, confirmed by hand.** Git exports `GIT_DIR` (and the rest of its "local" env vars) to every
pre-push hook, set to the PUSHING worktree's own git dir. `board-push-gate.sh` never cleared it, so its scratch
checkout (`git -C "$S" checkout -q "$base_sha" -- docs/testing`) used the PUSHING tree's git dir and index with
the scratch directory as `-C`'s work tree: the file content landed on the scratch tree's disk (so the checkers
still saw what they needed and the gate still said PASS), while the same files were staged in the pushing/board
tree's OWN index -- a place that does not have them on disk, i.e. `git status` there shows them `AD`. Reproduced
in a scratch `mktemp -d` worktree pair outside the repo (deleted after) before writing the fix; full repro steps
in NOTES.md. This is the shape of the observed board commit ffda08b215 (10-09): 127 files changed for an
intended 9-line edit, with no corresponding working-tree edit by the session.

**The fix.** `board-push-gate.sh` now unsets every name `git rev-parse --local-env-vars` reports (git's own
list of repository-local env vars), before its first `git` call. That command needs no valid repository itself
(checked: it prints the same static list with a bogus `GIT_DIR` set), so it is safe to run unconditionally.
Every git call in the gate already names its tree with `-C`, so this is pure subtraction.

**The selftest.** Added three checks right after the existing "after the repair the same push goes through"
case in `97-board-push-gate.sh` -- that case already drives a real `git push` through the installed hook to a
PASS, which already runs the gate exactly the way the defect needs (a real pre-push hook, git's own `GIT_DIR`
export, no synthesis). The new checks look at what that push left behind in `$BP/bt` (the pushing/board tree):
nothing staged under `docs/testing`, no `docs/testing` on disk (the board tree never has any), and `git status`
otherwise clean.

`SELFTEST_ONLY=97-board-push-gate.sh docs/testing/jobs/selftest.sh`, with the fix (tail):
```
  ok   after the repair the same push goes through (exit 0, gate PASS)
  ok   ...and the remote's `board` is the repaired commit
  ok   ...and the push did NOT stage origin/master's docs/testing into $BP/bt's own index
  ok   ...nor leave it on $BP/bt's disk (the board tree still has no docs/testing at all)
  ok   ...and $BP/bt is otherwise clean: only the two board files, nothing extra staged
  ok   a hook whose gate script is missing FAILS CLOSED on `board` only
selftest: 97-board-push-gate.sh took 2s

selftest: 28 passed, 0 failed, PARTIAL: 1 of 129 fragments (fake host in /tmp/hakux-selftest.IrkiS3)
```

Mutant (the `for _v in $(git rev-parse --local-env-vars...); do unset "$_v"; done` line removed, comment left
in place), same run:
```
  ok   after the repair the same push goes through (exit 0, gate PASS)
  ok   ...and the remote's `board` is the repaired commit
  FAIL ...and the push did NOT stage origin/master's docs/testing into $BP/bt's own index
  ok   ...nor leave it on $BP/bt's disk (the board tree still has no docs/testing at all)
  FAIL ...and $BP/bt is otherwise clean: only the two board files, nothing extra staged
  ok   a hook whose gate script is missing FAILS CLOSED on `board` only
selftest: 97-board-push-gate.sh took 1s

selftest: 26 passed, 2 failed, PARTIAL: 1 of 129 fragments (fake host in /tmp/hakux-selftest.J66br9)
```
The two new checks are the only ones the mutant turns red; all 25 pre-existing checks in the fragment, and the
existing "lets a push to another ref through" / "FAILS CLOSED" cases, stay green either way -- this bug was
invisible to a PASS/FAIL verdict alone. Fix restored and reran green before this push. Also ran the full
`docs/testing/jobs/selftest.sh` (no filter) with the fix in place as a broader regression check; no other
fragment's output changed.

**Scope.** `jobs/board.sh` (the hook installer) is not in this lane's territory and is untouched. One item
named in OUTBOX.md for whoever owns it: a belt-and-suspenders clear inside the generated hook itself, which is
not required today (every caller of the gate now clears its own environment) but would be a second layer if a
future gate script forgets to.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
