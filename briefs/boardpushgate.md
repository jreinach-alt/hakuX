# lane.boardpushgate -- the board job must never push a red board

Lane: boardpushgate
Issue: none (harness defect; host-created 2026-09-26 08:40 PDT by hostops, runbook item 6k)
Base: origin/master (merge origin/master first; never rebase)
Files: docs/testing/jobs/board.sh, docs/testing/jobs/board-push-gate.sh, docs/testing/jobs/roles/board.md, docs/testing/jobs/selftest.d/97-board-push-gate.sh, docs/lanes/boardpushgate/NOTES.md

## Why (evidence)
The board job's model session edits territory.toml / nv2a_issues.toml in `.boardtree` and pushes `board` itself
(roles/board.md: "commit and push the `board` branch before you comment"). Nothing checks the push. On 2026-09-26 it
pushed an origin/board that FAILED the board gates twice:
- verification blockers naming retired lanes (check_territory);
- 07:31 PDT: dispatch_state="done" on five OPEN issues #31 #223 #262 #266 #287 (check_coverage); hostops repaired it
  at 07:40 PDT (see logs/hostops/digest.log).
A red origin/board makes preflight's coverage leg red for EVERY lane and refuses every other board push until a
person repairs it: one bad tick jams the whole harness. board.sh only *reports* coverage failures into the next
tick's prompt (board.sh ~line 420); a report is not a gate.

## Build
1. `docs/testing/jobs/board-push-gate.sh <boardtree>`: builds a scratch worktree of origin/master, copies the
   boardtree's territory.toml and nv2a_issues.toml into its docs/testing/, and runs `check_territory.py` and
   `check_coverage.py` there. It exits 0 only if both exit 0 and prints each FAIL line otherwise. It fails CLOSED on
   a crash; it fails open ONLY where check_coverage itself already fails open (no network), and says so.
2. Enforce it mechanically: board.sh installs a `pre-push` hook in `.boardtree` (core.hooksPath local to that
   worktree, or .git/worktrees/<x>/hooks) that runs the gate for pushes to refs/heads/board and refuses red. The model
   session cannot bypass it with a prompt misread. `--no-verify` must be denied in allowed-tools.job only if you can
   do it without editing that file (it is lane.toolsmith's): otherwise record in NOTES that it is lane.toolsmith's
   follow-up, and route it with `docs/testing/jobs/deliver.sh send toolsmith 94 -F <file>`.
3. roles/board.md: when the push is refused, read the FAIL lines, repair the named rows, re-run the gate and push.
   Never push red, and never retry blind.
4. After the tick, board.sh itself re-checks origin/board. If it is red anyway (another actor pushed), it writes one
   `BOARD RED` line to logs/board/tick.log naming the rows, so hostops' health check sees it.

## Proof
- selftest.d/97-board-push-gate.sh:
  - a boardtree fixture with an OPEN issue marked dispatch_state="done" is refused (assert on the FAIL words, not only
    the exit code);
  - a clean fixture passes;
  - a hook installed by board.sh fires on `git push` to a local bare remote's `board` ref and not on other refs.
- Show the hook refusing a real red board: replay 2026-09-26's bad commit, which you can find in origin/board's log
  around 14:31Z ("done" on #223 etc.), against a local bare copy. Never push to the real origin/board from this lane.
- `bash docs/testing/jobs/selftest.sh` green, preflight green.

## Do not
- Edit the board branch, territory.toml or nv2a_issues.toml (lanes must not edit board files).
- Edit allowed-tools.* (lane.toolsmith's).
- Weaken check_territory/check_coverage to make the gate pass.

## Done when
The gate script, hook install, role text and selftest have landed; NOTES records the replay of the real bad commit
being refused; the PR is ready (merge master first).
