# Audit pass 2: PR #578, lane.remote: revert the #557 thermal governor core

Head: 2f46681829 (644e189bb9 plus the pass-1 audit file). Branch: `claude/docs-tooling-agentic-coding-u152m1`. Auditor: job.cloud.

The file name keeps the `-pr578` suffix for the same reason as pass 1: #560's pass-2 audit is already at the unsuffixed path on master.

**Verdict: clean. Fold-ready.** Pass 1 raised no HIGH and no MEDIUM. Neither LOW was fixed, and pass 1 did not require either one to be. Both are accepted below, each with its reason.

## Code since pass 1

`git diff --stat 644e189bb9 2f46681829` shows only the pass-1 audit file. The code pass 1 read is the code on this head.

## Pass-1 checks, re-run on this head

- **No caller left behind.** `git grep -l -e thermal_governor -e HAKUX_THERMAL_ADAPT -- android ui .github` returns nothing.
- **The build from history still works.** `python3 docs/lanes/remote/thermal557_replay.py --selftest` ends `PASS: 0 of 17 groups' checks failed`. That includes R1, where the C core fetched from CORE_REF and the Python model agree on 60 random traces.
- **CI.** The `build` checks were in progress when this file was written. GitHub reports the PR MERGEABLE.

## Findings

**LOW-1 (a stray `thermal_governor.c` beside the harness would win the include): accepted, not fixed.** The scenario can still occur, because `docs/lanes/remote/thermal557_harness.c:26` still uses a quoted include. It cannot occur on this tree, though: `docs/lanes/remote/` holds no `thermal_governor.c`, so today's selftest builds the CORE_REF copy. #557 is stopped, so the harness is a record and nobody is developing against it. The fix stays available if the lane reopens: use `<thermal_governor.c>`, or have `build()` refuse to run when that file exists.

**LOW-2 (the branch name was reused): accepted.** This is process, and nothing on this PR can change it. The path collision is handled by the `-pr578` suffix. The advice to use a suffixed branch for the next PR stands.

## Next

Remove `needs-audit-2` and add `fold-ready`.
