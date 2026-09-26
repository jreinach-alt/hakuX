# Audit pass 2: PR #347, lane.pshqueue

Head verified: `47bc3dfc9c` (lane/pshqueue, the pass-1 commit on top of
`e00d25530b`). No code has changed since pass 1, so pass 2 checks each pass-1
finding against the same diff.

**Verdict: clean, fold-ready.** Pass 1 found no HIGH and no MEDIUM. Of the
five LOWs, L5 is fixed, L1 to L3 are limits the lane had already recorded, and
L4 is accepted as it stands. CI on this head: `check` and both `build` jobs
pass, and the PR is mergeable.

## Scope re-check

`git diff origin/master...HEAD -- hw/` contains the #279 hunk (`psh.c`,
DOT_ZW `zvalue`/`zfloor` inside `depth_needed`), the #285 swap (`psh.c` code
and uniform staging, plus `psh.h` `DECL`), and nothing else. There are no
BRDF or `sampler3D` lines, so the #315 revert holds. Only
`pshqueue-279-dotzw.json` and `pshqueue-285-g8b8.json` are under
`docs/testing/predictions/`.

## Findings

| Finding | Pass-2 state | Evidence |
|---|---|---|
| L1: DOT_ZW has no guard for a divisor of 0 or NaN | Still possible; accepted as recorded | The hunk is unchanged. No test has w = 0, so a guard would pick a value without evidence (cloud-279 NOTES). The scenario remains, on a 0/0 texel only. It should be taken up as a #279 follow-up, not by this PR. |
| L2: the DOT_ZW depth skips depth clipping and the clip-min/max clamp | Still possible; accepted as recorded | Unchanged, and also a stated limit in the cloud-279 NOTES. The only test uses clip range 0..2^24. |
| L3: #285 swaps the value but not the write mask or the blend constant | Still possible; accepted, not a regression | Before the hunk the same mask and constant cases were already wrong. No capture exercises them. |
| L4: `register.sh` still registers `pshqueue-315-brdf.json` | Still present; accepted | `docs/lanes/pshqueue/register.sh:36-46`. The file is under the lane's notes directory, and nothing runs it. Only a manual re-run followed by a commit would reinstate the prediction. An auditor may push only the audit file, so this is left for whoever next touches the lane. |
| L5: the PR title names #315 | **Fixed** | Retitled by REST PATCH and read back: "lane.pshqueue: #279 DOT_ZW, #285 G8B8 psh.c hunks, one arm each". The fold commit takes this title. |

None of the five is incorrect behaviour on a path the diff introduces that was
correct before. L1 and L2 are new behaviour on the DOT_ZW path only, which
previously wrote no depth override at all, so the whole quad was wrong.
