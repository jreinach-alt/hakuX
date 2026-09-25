# Audit pass 2: PR #260 (lane/toolsmith) -- arms.sh withdrawn FAILs, idle-tier backpressure, snapshot by rename

Auditor: job.cloud, 2026-09-25. Verifies
`2026-09-25-toolsmith-260-pass1.md` against head `b544236c90` (remediation
commit `b544236c90`, on top of the audited `8655834510`).

**Result: clean. M1 can no longer occur; L1-L3 are carried as LOW -> `fold-ready`.**

## M1. Renaming a file that holds the refuted code withdraws the FAIL -- CLOSED

**The fix.** `names()` in `arms.sh` (the only `git diff` in the withdrawal
code) now runs `git diff --no-renames --name-only`. Both sets go through it:
the arm's code set `names(a, b)` and the branch set `names(base...head)`. No
other diff feeds `withdrawn()`.

**The scenario, re-run.** I rebuilt the pass-1 repro independently (git 2.43.0):
a twenty-line `src/a.c`, a candidate that appends one line, then `git mv
src/a.c src/a2.c` with the refuted content intact.

```
code (a..b):             src/a.c
branch, porcelain:       src/a2.c              <- pass-1 behaviour: no overlap, withdrawn
branch, --no-renames:    src/a.c src/a2.c      <- as arms.sh now runs it: overlap, kept
branch, renames=copies:  src/a.c src/a2.c      <- a host config cannot turn it back on
```

With the old path in the branch set, `code & have` is non-empty, `withdrawn()`
returns `None`, the state stays `regressed`, and the fold gate still holds.
`--no-renames` on the command line overrides `diff.renames` in any config, so
the host's git config cannot reintroduce the scenario.

**The guard.** `94-arms-withdrawn.sh` gains case (f), `lane/moved`: `src/b.c`
reverted and `src/a.c` moved to `src/a2.c` with its content intact. Its FAIL
must stay `regressed []`, and it is in `WANT`. The mutant "rename detection on"
removes `--no-renames` (the anchor matches exactly once) and must turn (f)
red. The fixture was widened to twenty-line files with appended edits, so a
one-line change stays above git's 50% similarity threshold. Without that,
git would not detect (f) as a rename even without the flag, and the mutant
would be green. The commit message says it was green before the widening.
That is the right thing to have checked.

Direction check: the change can only add paths to the branch set, never
remove them, so it can only turn a withdrawal into a keep. A move-and-revert
(file moved AND refuted lines undone) now stays `regressed` when it could
have been withdrawn. That is the conservative direction: a person reads the
FAIL instead of a regression folding silently.

**Selftest.** I ran fragment 94 alone, under the full `selftest.sh`
harness, at `b544236c90`. The result was 19 passed and 0 failed, including
`(f) a refuted file moved with its content intact stays regressed` and
`mutant 'rename detection on: a moved refuted file reads as gone' is red on
(moved)`. CI on the same head is green: `selftest` SUCCESS and both `build`
checks SUCCESS.

## LOW, carried (not remediated, optional per pass 1)

- **L1.** A withdrawal that leaves live PASSes still leaves the PR with
  neither `regressed` nor `verified`. There is no fold effect, because
  `fold.sh` does not require `verified`.
- **L2.** The code set is two-dot `a..b`, so the "code that is gone" line can
  name master's files when `a_ref` is not an ancestor of `b_ref`. That is
  misleading prose, and it never causes a false withdrawal.
- **L3.** `94-arms-idle-tier.sh` still has no zero-normal-request leg. The
  code is correct today, because `arms.sh` has no `set -e`.

None of these can fold a regression, so none blocks.
