# lane.handbackstrand -- NOTES

2026-09-25. PR #258. Brief: `draft-strand-arm` resumes once per new VERDICT,
not once per new head; no strand resume while the lane's own arm is in flight.

## What changed (`docs/testing/jobs/handback.sh`)

1. **The arm marker is keyed on the verdicts.** `verdicts_of <branch>` reads
   `$WORK/arms/pairs/*.json` (a pair is the branch's when `source` before the
   colon equals it, exactly -- not a prefix) and `$WORK/arms/judged/<sha>`,
   classifying FAIL-then-PASS exactly as `arms.sh`'s `label_decide` does, and
   hashes the sorted `(sha, verdict)` pairs. The marker is
   `done/draft-strand-arm-<pr>-v<hash16>`. UNJUDGED / ERROR lines are not
   verdicts there and are not new information here.
   - With no judged verdict on disk for the branch (label set by hand, or
     an arms dir this host cannot read) it falls back to the head key it
     always had. That keeps `99-handback-draft.sh`'s D4 block (a label with
     no arms data) meaning what it meant.
   - Why not call `arms.sh state`: it rewrites `$WORK/arms/log/label-index.tsv`
     with `>`, and an arms tick mid-judge reading that index would see it
     truncated. Same read, not the same process.
2. **In-flight hold, both strand causes.** `inflight_of <branch> <name>`
   looks in `$DISPATCH_DIR/running` then `queue` for a `.req` whose
   `expect_sha` is one of the branch's registered prediction shas (how
   `arms.sh` queues), whose `purpose` says ` from <branch>:`, or whose
   `requester` is `<name>-base|fix` / `arms-<name>-base|fix` (`ab_run.sh
   --who <name>`). If one exists: no resume, no cause marker, and one
   `tick.log` line per request id (`done/inflight-<pr>-<id>`). Applied to the
   quiet cause too: a lane quiet 2 h whose arm is still queued is waiting, not
   stranded. The brief asked "do not strand-resume a lane whose own arm is in
   flight", which reads as both causes.
3. Cap, attempt bookkeeping, quiet key, label rows: unchanged. The brief text
   and the resume comment now say the arm key is per verdict.

## Proof

`selftest.d/99-handback-strand.sh`, copying `99-handback-draft.sh`'s shims into
its own dir. Three branches with verdicts, ours in the middle
(`lane/selftesthr`, `lane/selftesths`, `lane/selftesths-x` -- the last shares our
name as a prefix). Resumes are COUNTED from the systemd-run log.

Mutant and falsification runs happened in a scratch worktree at `origin/master`
(`$WORK/handbackstrand-scratch`). Its `selftest.d/` was pruned to
`99-handback-draft.sh` + `99-handback-strand.sh`, with the fragment copied in.
Nothing was swapped in the lane tree, and the scratch tree was never staged.

| handback.sh under test | result | reds |
|---|---|---|
| **old, origin/master** (falsification) | 85 ok / 13 FAIL | (a) keyed-on-verdicts x2, **(b) new head resumes x4**, (c) x2, (d) list/log/count/--who/release x6 |
| mutant 1: arm marker back on the head | 85 ok / 13 FAIL | the same 13; **(b) resumes on a new head** |
| mutant 2: in-flight check dropped | 91 ok / 7 FAIL | (d) only: queued arm resumes, PR told, list, log, count, --who, release |
| this branch | 98 ok / 0 FAIL | none |

On the old code, (d)'s first two rows ("queued arm is not resumed", "nor told")
pass only because the old head marker from (a) already exists at that head.
Mutant 2 makes them red, so they do check the hold.

Full `bash docs/testing/jobs/selftest.sh` on this branch after merging master: see the PR body.

## Why attempt 1 did not finish

The code and fragment were committed locally (`cdce86db63`) but never pushed.
NOTES stayed untracked with a placeholder where these results go. The session
ended before the mutant and falsification runs, which was not a wait on
anything. The remote head stayed at the claim commit, so CI's GREEN on
`1e138124da` said nothing about this work. Attempt 2 committed NOTES, merged
`origin/master` cleanly (35 commits), pushed, and ran the proof above.

## For the next lane

- `$WORK/wt/` is where lane worktrees live and `handback.sh` treats a dir
  there as a lane. A scratch file written with a `../` path from a lane
  worktree lands in `wt/`; keep scratch in `$WORK/<something>-scratch`.
- The `dispatch/queue/withdrawn` entry is a directory; only `*.req` is read.
