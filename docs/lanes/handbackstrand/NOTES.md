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

RESULTS_PLACEHOLDER

## For the next lane

- `$WORK/wt/` is where lane worktrees live and `handback.sh` treats a dir
  there as a lane. A scratch file written with a `../` path from a lane
  worktree lands in `wt/`; keep scratch in `$WORK/<something>-scratch`.
- The `dispatch/queue/withdrawn` entry is a directory; only `*.req` is read.
