# lane.boardpushgate

The board job must never push a red board. Brief: host-created 2026-09-26
(hostops runbook item 6k); no issue.

## Why attempt 1 did not finish

Attempt 1 (session ended 2026-09-26T15:21Z) opened draft PR #408, pushed a
NOTES stub, and ended. Nothing else was on the branch: no gate, no hook, no
selftest, and nothing running in the background. It did not end waiting on
anything. It ended before starting the work. Attempt 2 did all of it from a
merge of origin/master (198887ce58).

## What landed

- `docs/testing/jobs/board-push-gate.sh [--rev <commit>] <boardtree>`. Adds a
  `--no-checkout` scratch worktree of origin/master and checks out only
  `docs/testing`, since check_territory walks git history and needs a repo
  around it but not 15k files. It copies the two board files in (from the
  working tree, or with `--rev` from the pushed commit) and runs
  check_territory.py and check_coverage.py there with `HAKUX_BOARD_REF=`
  and `HAKUX_TIP=<base>`. Exit 0 only if both exit 0. On a failure it prints
  each FAIL line and the rows under it, up to the first blank line, and drops
  the explanatory paragraph. It fails closed on a missing file, an
  unresolvable base, a failed worktree add, or a checker that exits non-zero
  without a FAIL line (crash or timeout). It fails open only where
  check_coverage does (`coverage NOT CHECKED`), and then prints a NOTE saying
  so, never `ok`. The scratch worktree is removed and pruned on exit.
- `board.sh`:
  - `install_board_hook <tree> <gate>` and a `board.sh install-hook` mode.
  - Every tick it creates `$WT/.boardtree` if missing and arms it and `$WT`.
  - It re-checks `origin/board` after every tick, on the quiet path too, and
    logs one `BOARD RED: origin/board <sha> fails the board gates: <rows>`
    line to logs/board/tick.log.
- The hook is per worktree. `extensions.worktreeConfig=true` plus
  `git config --worktree core.hooksPath <gitdir>/board-hooks`. On git 2.43
  hooks resolve through the common dir, so `.git/worktrees/<x>/hooks` alone
  is never read. It gates only a push whose remote ref is `refs/heads/board`,
  judges the pushed sha (not the working tree), refuses a delete of `board`,
  and refuses if its gate script is missing.
- `roles/board.md`: a new section, "The push gate refuses a red board":
  read the FAIL lines, repair those rows, re-run the gate, push on PASS.
  Never `--no-verify`, never retry unchanged.

## Replay of the real red boards (2026-09-26, read-only, nothing pushed)

`board-push-gate.sh --rev <sha> .` in this worktree, gh live:

| board commit | when (PDT) | gate | named |
|---|---|---|---|
| ec8ce1a6dc | 07:25 | REFUSED | 4 blockers naming retired lanes: #272 #275 (zrtz272), #281 (nanfix281), #382 (surfwatch382) |
| 3d5b685410 | 07:33 | REFUSED | `done` on open #223 #262 #266 |
| 60c5bd4d80 | 07:34 | REFUSED | `done` on open #31 #223 #262 #266 #287 (the brief's five) |
| 8313751cb0 | 07:37 (hostops repair) | REFUSED | #404 open with no lane or blocker. #404 was filed after this commit, so this is today's GitHub against a 07:37 board, not a defect of that commit |
| 750c08c908 (origin/board now) | 08:21 | PASS | both checkers ok |

The hook half of the replay (refusal on a real `git push` to a bare remote's
`board` ref) is in the selftest, against a fixture board that has the same
defect as 60c5bd4d80 (`dispatch_state = "done"` on an open row).

## Selftest: selftest.d/97-board-push-gate.sh

It builds its own repo, orphan board, two bare remotes and a REST gh shim.
Every check asserts on output words as well as exit codes:

- clean board: PASS
- open issue with `done`: REFUSED, check_coverage's FAIL line, `#2` named
- offline: FAILED OPEN note, no `ok`
- unparsable toml: crash, fail closed
- bad base: fail closed, no leftover worktree
- install-hook: sets hooksPath in config.worktree only, not the shared config
- push to another ref: passes, gate not run
- red push to `board`: refused, and the gate judged the commit while the
  working tree was clean
- deleting `board`: refused
- another worktree of the same repo: not gated
- repaired push: passes, and the remote ref equals it
- missing gate script: `board` refused, other refs pass

## Not done here: --no-verify is lane.toolsmith's

`allowed-tools.job` grants `Bash(git:*)`, so `git push --no-verify` and
`git -c core.hooksPath=/dev/null push` both bypass the hook. Denying them is
lane.toolsmith's file. This was routed with
`deliver.sh send toolsmith 94 -F ...`. Until then, the post-tick
`BOARD RED` line is what catches a bypass.

## For the next lane

- Do not put the hook in the common `hooks/` dir or set `core.hooksPath` in
  the shared config. Every checkout of the owner's repo would inherit it.
- check_coverage compares against live GitHub, so replaying an old board
  commit can go red on issues filed after it (the #404 row above). Read the
  rows, not only the verdict. It also returns at its FIRST failing class, so
  one replay can name different rows at different times. The same 60c5bd4d80
  replayed at ~17:40Z named #184 and #315 (closed on GitHub since then, still
  `open` in that commit) and never reached the `done` rows. Its refusal was
  still right. origin/board 8f33080740 (10:25 PDT) passed at that time.
