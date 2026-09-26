# Audit pass 2: PR #321, lane wparamcode223 (#223, ff W_param carry + zero-area wedge)

Auditor: job.cloud, 2026-09-25. Head checked: `7fc397af17`, which is the
pass-1 commit itself. Pass 1 audited `cdf844872e`.

**Verdict: clean. The PR goes to fold-ready.** Pass 1 found no HIGH and no
MEDIUM, so there was no blocking scenario left to fire. The code has not
changed since pass 1. All four LOWs are still true as written, and each one
is recorded below as deliberately left.

## What changed since pass 1

`git diff cdf844872e 7fc397af17` adds only
`docs/audits/2026-09-25-wparamcode223-pass1.md`.
`git diff 8555c013c6 HEAD -- hw/xbox/nv2a/pgraph/glsl/geom.c hw/xbox/nv2a/pgraph/glsl/vsh-ff.c`
is empty. So both hunks are byte-for-byte the code that the `[job.arms]`
PASS measured (19 better / 0 worse / 568 same, with b_ref `8555c013c6`).
The other changes under `hw/` since b_ref came from master merges and are
outside this PR's diff.

## The pass-1 findings

| Finding | Still occurs? | Disposition |
|---|---|---|
| L1: "every finite carried vertex is bit-identical" is stated generally but was measured on two rows | Yes. PR body line 9 and NOTES:77 still say it without qualification. | Left. The worst case is a sub-1/16-px edge pivot, which could flip at most one tie pixel. The 568 unchanged captures include near-eye-plane geometry. The correct reading is "bit-identical on the W_param rows measured", and this table records that for the fold. |
| L2: prose magnitudes missed on 10 rows, and residuals should be recorded | Partly fixed. NOTES:139-141 and the "For the next lane" section (NOTES:150) record the residuals with their capture directory: 8 bitri rows at ~3.2k, bitri w-inf at 511, and w_gaps / w_gaps_tex_persp at 31,743. The PR body records them too. #223 itself has no comment giving the residuals. | Left for the board: #223 should stay open after this folds, with the residuals quoted from NOTES:150. The machine legs (`expect_counts`, must-not-move) held. |
| L3: `2.0 * hPos` overflows for \|hPos\| > FLT_MAX/2 | Yes. | Left. The old path is inf there too, so this is not a regression. |
| L4: `vshemit/check.py` hardcodes a host NDK path | Yes. | Left. It is lane tooling, not shipped code. |

An audit may push only its audit file to the lane branch, so this table is
the record of all four leaves. It folds with the PR.

## Fold readiness

- A test merge against `origin/master` (`git merge-tree`) conflicts in
  exactly one file, `docs/testing/nv2a_index.json`. That is the generated
  index. `fold.sh` regenerates a stale index over the pinned trees, so the
  lane does not need to act on this conflict (the same case as #250's pass 2).
- Nothing in this pass needs a device.
