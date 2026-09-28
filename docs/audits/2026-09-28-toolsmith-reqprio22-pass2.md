# Audit pass 2: PR #577, lane/toolsmith-reqprio22

`request.sh --priority blocker|arm|study|sweep` (defect 22, the request.sh half).
Head verified: `3c4ec51ca8`, which is the audited `a3c3fdec9b` plus the pass-1
audit file and nothing else. Auditor: job.cloud, 2026-09-28.

**Verdict: clean.** Pass 1 raised no HIGH and no MEDIUM, so no scenario had to
be closed. The two things pass 1 asked pass 2 to confirm both hold. The PR
goes to `fold-ready`.

## What pass 1 asked pass 2 to confirm

1. **The fragment result still holds on the current head.**
   `git diff a3c3fdec9b 3c4ec51ca8` touches only
   `docs/audits/2026-09-28-toolsmith-reqprio22-pass1.md`. The run below used
   `SELFTEST_ONLY="99-request-priority-flag 99-request-release-prio"` on the host.
   - On the head: **40 passed, 0 failed**.
   - On the head merged with `origin/master` `85347ffbd1`: **40 passed,
     0 failed**. The branch is 40 commits behind, and the merge has no
     conflicts.
   - The order leg read the same in both runs:
     `0-0-x-…-hostops 0-…-rpf-blocker 1-…-rpf-armrel …-rpf-armplain z-sweep-001-Alpha_func`.
2. **The mutant leg is still red on the mutant.** In both runs the mutant queued
   `1-…-rpf-mutblocker`, which sorts third behind `1-…-rpf-armrel`. The shared
   order predicate rejected it ("the order check fails the mutant"). The
   `cmp` guard confirmed that the sed changed the file.

## Did master move under the pass-1 reader sweep?

Between the PR's base `01e62d8d1c` and `origin/master`, the only change to a
harness script under `docs/testing` or `host-tools` is
`selftest.d/51-dispatch-hardening.sh`. The other changed files are prediction
JSON and `nv2a_index.json`. None of the added lines reads a queue id, a tier
prefix, a `.req` glob or a `priority` field. The pass-1 list of readers is
therefore still complete.

## The pass-1 LOWs

These were not required fixes, and none of them has changed:
- **LOW 1:** the blocker tier is self-asserted.
- **LOW 2:** the tier comment in `dispatcher.sh` is stale. It belongs with the
  `yield` half.
- **LOW 3:** `--priority ""` falls back to `study`.

They are carried here so that the defect-22 `yield` half can pick up LOW 2 and
decide on LOW 1.

CI on `3c4ec51ca8`: build ×2 and selftest (0-3), all SUCCESS. GitHub reports the
PR as MERGEABLE.
