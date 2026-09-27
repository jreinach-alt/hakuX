# Audit pass 2: lane.displayguard (PR #495, #494)

Head verified: `be654ed2a9`. Pass 1 audited `fbe37e204e`.

**Result: clean.** Pass 1 found no HIGH and no MEDIUM, so no remediation was
needed. The four LOWs are unchanged and none of them blocks. Next state:
`fold-ready`.

## What I verified

- **No code changed after pass 1.** `git diff fbe37e204e be654ed2a9` touches
  only `docs/audits/2026-09-27-displayguard-pass1.md`. The refusal ordering,
  the `exit 5` path with the EXIT trap still set, the `fg_watch` lifetime, and
  the anchored `void` regex are the same code pass 1 read.
- **Master has not moved underneath it.** `origin/master` is 14 commits ahead
  of the lane's merge base. None of those commits touch `devices.sh`,
  `soak_title.sh`, `title_verdict.py`, `dispatcher.sh` or `selftest.sh`, and
  `git merge-tree` merges the head into master with no conflict.
- **The selftest is green.** `selftest.d/99-display-covered.sh`, run at the
  head against this repo, reports `pass=18 fail=0`. That includes all three
  mutants (the overlay-type check removed, top activity only, and no watcher),
  and each of them turns its leg red. CI on `fbe37e204e` shows selftest and
  build as success. CI on `be654ed2a9` was still running at the time of
  writing, and the fold job gates on it.

## The pass-1 LOWs, as they stand

| # | Scenario | Can it still occur? | Blocks fold? |
|---|---|---|---|
| L1 | hakuX renders black, so every route frame is under 12,288 B, and the run is reported as `void: display-black` rather than as a render failure | Yes, the code is unchanged. The pass/fail answer is still right (not Playable). Only the triage label is wrong. | No |
| L2 | two adb unknowns in a row (a `UtilAcceptVsock` burst) abort a route soak and void it | Yes. The NOTES chose this on purpose, and the cost is one re-queue. | No |
| L3 | a title that exits mid-route is labelled `not-foreground: <launcher>` before `alive()` can call it exited | Yes, unmeasured. Without a `hakuX-crash` line the result reads void rather than crash. | No |
| L4 | the `fg_wait` remedy's `am start` may restart the guest after `soak start` | Yes, and only on the remedy path. The effect is bounded. | No |

The lane did not act on L1. It is the one worth a follow-up: after the hold,
run `display_clear` a second time and split `render-black` (a title failure)
from `display-black` (void). It can be done after the fold.
