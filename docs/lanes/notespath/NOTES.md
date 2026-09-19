# lane.notespath — every lane writes the same file, so only the first can fold

**This file is at `docs/lanes/notespath/NOTES.md` deliberately.** That is the
change: `roles/lane.md` item 3 used to ask for `NOTES.md` in the branch root,
and the first lane to fold landed one on master, after which every fold
conflicted on that exact path.

## What the defect actually is

`master` had no root `NOTES.md`; four running lanes each had one. The first
fold is clean (an add where master has nothing). The second is an add/add
conflict, and `fold.sh` resolves nothing by design, so it labels
`needs-rebase` and stops. It never gets better: once master holds lane A's
notes, every later lane's notes are a conflicting rewrite of the same file.
It is the steady state as soon as two lanes finish, not an edge case.

## What I changed

1. `roles/lane.md` item 3 and `roles/cloud.md`'s cloud-lane path ask for
   `docs/lanes/<lane>/NOTES.md`. Two lanes cannot write the same file, and
   the whole set is readable on master after the folds.
2. `fold.sh` grew exactly one conflict resolution, `resolve_root_notes`: when
   the ONLY unmerged path is root `NOTES.md`, the incoming copy is moved to
   `docs/lanes/<lane>/NOTES.md`, master's root copy is kept untouched, and
   the fold continues. That is for the lanes already running, which will
   never see the new instruction. The refusal in the header comment is about
   *code* and it still stands for every other path.
3. `selftest.sh` grew a block that pins the boundary, not the happy path.

## What I deliberately did not do

- **Not a content merge.** Both sides survive, each at its own path. If the
  destination `docs/lanes/<lane>/NOTES.md` already exists (the lane wrote both
  paths, or folded once before), the job REFUSES and hands the PR back —
  choosing which of two files at the same path wins IS a content decision, and
  this job does not make those.
- **Not a delete.** The lane's record is the whole point of the file; moving
  preserves it, dropping master's root copy would have destroyed the previous
  lane's.
- **Did not touch root `NOTES.md` files already on lane branches.** Those
  lanes are running; a push to their branch is not mine to make. `fold.sh`
  handles them at fold time, which is exactly why half 2 exists.

## How the check is falsifiable

`fold.sh resolve-notes <worktree> <branch>` exposes the resolution on an
in-progress merge, so the self-test drives it on three throwaway repos with no
fake `gh` involved:

| fixture | conflict | expected |
| --- | --- | --- |
| `only` | root `NOTES.md` alone | resolved; lane's text at `docs/lanes/fixture/NOTES.md`; master's text still at the root; nothing unmerged; still a merge commit (`HEAD^2` resolves) |
| `code` | `NOTES.md` **and** `src.c` | refused; conflict left exactly as found; no per-lane file written |
| `taken` | root `NOTES.md`, destination already occupied | refused; the existing file not overwritten |

Run against `origin/master:fold.sh` (the file I am replacing), `resolve-notes`
is not a mode: it falls through to the candidate query, finds nothing, and
**exits 0** — so the `code` and `taken` legs, which require a non-zero refusal,
fail, and every `only` leg fails on the files it asserts. Verified by
`git show origin/master:docs/testing/jobs/fold.sh > fold.sh`, running, and
restoring. Recorded below.

## What the next lane should not repeat

- **`arms.sh list` dominates the self-test's runtime** — minutes, not the
  "seconds" the brief promises, because it walks committed predictions across
  git history in a worktree this size. Nothing to do with your block; do not
  go looking for a hang in your own code when the log stops after
  `== arms.sh list`. Run it to a file in the background and keep working.
- **Two references to root `NOTES.md` live outside this lane's four files**
  and I did not edit them, because they belong to other lanes' territory:
  - `docs/testing/lane.sh` — the `resume` prompt says "read NOTES.md and git
    log first, say in NOTES.md why the previous attempt did not finish".
  - `docs/testing/session-start.sh:67` — "commit NOTES.md before any long
    step".
  Neither opens the file: both are prompt text a model reads, and
  `roles/lane.md` is appended as a system prompt in the same session, so the
  authoritative path is in front of the model either way. Still worth a
  one-line fix by whoever holds those files next. `docs/ORCHESTRATION-DESIGN.md`
  mentions it in three places (:310, :495, :594) and `roles/board.md:92` quotes
  "the lane's `NOTES.md`" — all prose, none of them a path a program opens.
- **No program consumes `NOTES.md`.** `grep -rn "NOTES.md" docs/ .github/` is
  in the brief; the answer is that `fleet.py` and `check_coverage.py` do not
  read it and neither does any workflow. `precompact.sh`, which
  `ORCHESTRATION-DESIGN.md:594` says writes it, does not exist on disk. So the
  rename breaks no consumer — but check again before moving it a second time.
