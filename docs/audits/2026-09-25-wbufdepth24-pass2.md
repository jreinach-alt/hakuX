# Audit pass 2 -- PR #268, lane/wbufdepth24 (#266)

Head audited: `396fc65576` (pass 1 plus nothing else). Master: `origin/master`
as fetched 2026-09-25.

**Result: clean. Next state: `fold-ready`.** Pass 1 found no HIGH and no
MEDIUM, so no scenario needs to be shown as no longer possible. This pass
checks that pass 1's conclusion still holds against current master, and it
checks the one item pass 1 left open (L4).

## The change against current master

- `git log HEAD..origin/master -- hw/xbox/nv2a/pgraph/glsl/psh.c` is empty.
  The D24 hunk sits on the same text as on the tree the arm measured, so the
  arm verdict (18 better, 0 worse, 512 same over 530) still describes this
  code.
- The `psh.c` diff is still the single `min(zfloor, 16777215.0)` in
  `DEPTH_FORMAT_D24`, with the comment. No other switch case changed.

## L4 -- the conflict

`git merge-tree --write-tree origin/master HEAD` shows one conflicting path:
`docs/testing/nv2a_index.json`. `psh.c`, the prediction, NOTES and
`classify.py` all merge cleanly.

This is exactly the case that `fold.sh` (master) resolves mechanically. When
the index is the whole conflict, fold stages master's copy and rebuilds the
index over the merged tree, using the pinned trees. That path hands the PR back only
if the two sides name different `provenance.tests_commit`. They name the same
one:

| side | tests_commit | suites |
|---|---|---:|
| origin/master | `6743b6ab16` | 104 |
| lane head | `6743b6ab16` | 104 |
| merge base `e2f617ed99` | `6743b6ab16` | 104 |

So L4 does not need a lane merge. Fold resolves it. Pass 1 asked for a merge with a
rebuilt index before the fold. Fold does that itself, so asking the lane to do it
would repeat the fold's work.

## L1-L3

These remain as pass 1 left them. They are LOW, and none of them has a failure
scenario on this PR: the arm's rows moved as the prose said, the untouched
switch cases emit unchanged text, and session 2 of NOTES supersedes session
1's row count. They are not blocking.
