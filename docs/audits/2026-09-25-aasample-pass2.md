# Audit pass 2: PR #332, lane/aasample (#286 class A, CENTER_CORNER_2 sample placement)

Head verified: `b936bb4107` (pass 1's head `a53cd6b6e9` plus the pass-1 audit file).
Base: `origin/master` fetched 2026-09-25.

**Verdict: clean. No HIGH or MEDIUM was raised in pass 1, and none has appeared.**
The four LOWs stand as recorded. None of them is a failure the fold can cause.

## What pass 1 asked pass 2 to confirm

- **The head still changes no binary.** `git diff --stat origin/master...HEAD` is
  9 files: the pass-1 audit, six files under `docs/lanes/aasample/`,
  `nv2a_index.json` and `pgraph.h`. No `vk/draw.c` hunk is present, so
  `draw-c-viewport.patch` has not been applied. `pgraph_anti_aliasing_viewport_offset_x`
  appears once under `hw/`, at its definition (`pgraph.h:609`). An unused
  `static inline` emits no code, and `Prediction: none` still holds.
- **LOW-1 (stale NOTES line numbers).** Not fixed. `NOTES.md:70` still says `:5992`,
  `:73` still says `7058, 7143`, and `:180` still says "unchanged". Accepted as LOW.
  The two lines the patch touches (4496, 5621) are correct, and a reader who
  applies the patch with `git apply` does not depend on the others.
- **LOW-2 (modelled outcome stated as fact).** Not fixed. `pgraph.h:600-603` still
  says "is what makes ... byte-identical". Accepted as LOW. The helper is dead code
  until the section-4 arm lands with the patch, and that change is the right place to
  reword the comment to the measured result.
- **LOW-3 and LOW-4.** These were recorded only (history rewrite; GL out of scope).
  Nothing to verify.

## Mergeability

GitHub reports the PR as CONFLICTING. `git merge-tree --write-tree origin/master HEAD`
shows exactly one conflict, in `docs/testing/nv2a_index.json`. That is the generated
index, which the fold regenerates. It is the same index-only conflict the lane
resolved in `0093ea5017`. It is not a code conflict, and it does not block fold-ready.

## Outcome

`needs-audit-2` → `fold-ready`.
