# Audit pass 2: PR #235, lane shadeflat224 (#224 family A)

Auditor: job.cloud, 2026-09-25. Head: `a73e07e11d`. Pass 1:
`docs/audits/2026-09-25-shadeflat224-pass1.md` (head `8becbfaeb0`).

**Verdict: clean for code. `fold-ready`.** Pass 1 found no HIGH or MEDIUM,
so no remediation was due. `8becbfaeb0..a73e07e11d` touches only the pass-1
audit file, so the code pass 1 read is the code on the head, and every
"holds" in pass 1 still holds. The one open item is the replicate arm's
W_param verdict. That item is the fold gate's to enforce, and it does (below).

## Pass-1 findings, re-checked

| finding | can the scenario occur on `a73e07e11d`? |
|---|---|
| L1: GL half unexercised by any arm | Yes, unchanged. It is a coverage gap, not a defect. No GL arm exists or is registered. It is a LOW and stays a LOW. |
| L2: `get_draw_mode()` maps ADJ→ADJ whatever the shade/polygon mode | No failure path today. Replay still restores CONTROL_3 and SETUPRASTER from the queue entry, because `hw/` did not change since pass 1. It is a trap for a future replay path, and it stays a LOW. |
| L3: degenerate flat QUADS on the raw-vertex fallback draw nothing | Unchanged. The behaviour moves toward silicon's, so it is recorded and is not a defect. |
| L4: `nv2a_index.json` provenance names the live tree | Unchanged. The index content is correct and the provenance path is mutable. LOW. |

None of the four was a HIGH or MEDIUM. None needed a fix to pass.

## The open item: W_param must_not_move legs

Pass 1 asked pass 2 to read the verdict of
`shadeflat224-flatdiag-replicate.json`. **That verdict has not landed.** As of
this audit there is no second `[job.arms]` comment on the PR. `arms.sh state
lane/shadeflat224` still returns `STATE=regressed` from the single FAIL on pair
`42c014b32fab`. So this pass cannot say the W_param legs are readable and
unmoved. It does not say so.

It does not need to say so to hand off, and here is why. `fold.sh:675` reads
the `regressed` label and refuses to fold (fold-ready is kept) unless a
`regression-accepted:#N` label is present. The arms job computes `regressed`
from the verdicts on disk. It clears only when a later verdict supersedes the
FAIL. So `fold-ready` here means "the code audit is done", and the fold
still waits on the replicate. The first arm is consistent with an unreadable
B-side pull rather than a regression. Its W_param "movers" are all `[status ok
-> unreadable]`, and B's `run1.log` reports 54 of 110 coverage. It is no
evidence that the patch reaches W_param.

When the replicate lands, whoever reads it checks every mover's `[status]`
tag and B's `run1.log` coverage line before trusting a pass. A void leg is not
a pass.
