#!/usr/bin/env bash
# Close the issues whose lanes reported this tick with nothing left to fold.
set -u

c94='[job.board] Closing: lane.toolsmith reported at 2026-09-19T00:04:56Z that this is already
in master as `99800a64d0` -- the four list flags append, duplicate entries are refused, and the
queued record is re-read and its composition printed before the record is renamed into the
queue. `lane/toolsmith @ baa5b32698` is an ancestor of `origin/master`, so there is nothing to
fold; what was missing was the verification, and the lane ran it against a scratch
`DISPATCH_DIR` (8 `--only-tests` flags in, 8 read back by an independent reader).'

c95='[job.board] Closing: lane.toolsmith reported at 2026-09-19T00:04:56Z that this is already
in master as `baa5b32698` -- `--disc-from` / `--disc-suites|--disc-skip-tests|--disc-only-tests`
write a `disc` block, and `composition_notes()` (`ab_compare.py:1155-1211`) refuses an absolute
and downgrades a delta on a composition mismatch. The branch is an ancestor of `origin/master`,
so there is nothing to fold. Reopen if the step-2 grandfathering rule for the 106 of 107
predictions that lack the field needs its own issue.'

c81='[job.board] Closing: lane.tier81fix reported at 2026-09-19T00:05:53Z that the fix is already
folded. `git rev-list --left-right --count origin/master...HEAD` prints `109 0` -- zero commits
of the branch outside master. It landed as `7dfa94c403` (dedup on `(pc, cs_base, flags)` via
`tier1_has_pending_request()`, plus `tb->exec_count = 0` on the dedup path and after the slot
latch) through fold `4d3edc563d`. Two deviations from the audit wording are argued in the commit
message: the budget charge moved out to `tier1_maybe_promote()` so a dedup hit is not charged,
and the `tb->tier` latch was declined because it would persist a lying hint to `tb_cache.bin`.'

c90='[job.board] Closing: folded with #81 as part of `lane/tier81fix`, which
`rev-list --left-right` shows is entirely contained in `origin/master` (fold `4d3edc563d`).
lane.tier81fix re-opened the worktree at 2026-09-19T00:00Z, checked before implementing, and
correctly wrote no new code rather than duplicating landed work.'

c99='[job.board] Closing as a duplicate of #75 (itself closed as a duplicate of #39), on
lane.stencil99'"'"'s verdict above. The title here is byte-identical to #75, the body is empty,
and it was opened 39 minutes after #39 was closed. The attribution to a sha pair does not hold:
`stencil_observable_79.py` fires at BOTH shas the title names. Two of the three captures are in
#79'"'"'s nine outright, and the third (`ZERO_DT`) is named in #79'"'"'s own mechanism table --
that list is a lower bound on the unstable set, not a partition, so its absence was never
evidence of stability. This is the nondeterminism of #79, not a regression.'

set -x
gh issue comment 94 --body "$c94" && gh issue close 94 --reason completed
gh issue comment 95 --body "$c95" && gh issue close 95 --reason completed
gh issue comment 81 --body "$c81" && gh issue close 81 --reason completed
gh issue comment 90 --body "$c90" && gh issue close 90 --reason completed
gh issue comment 99 --body "$c99" && gh issue close 99 --reason "not planned"
