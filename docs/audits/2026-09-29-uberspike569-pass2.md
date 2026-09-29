[job.cloud] Audit pass 2 of PR #581 (lane.uberspike569, #569 P6 combiner ubershader spike): clean. Pass 1 raised no HIGH or MEDIUM, its three LOWs are accepted or carried to the build PR, and the code head has not moved; the PR moves to fold-ready.

# Audit pass 2: PR #581, lane/uberspike569

- Head verified: `e35ca8dead`. Since the pass-1 head `0b8290ff34`, the only change is the pass-1 file
  `docs/audits/2026-09-29-uberspike569-pass1.md` (`git diff --stat 0b8290ff34 e35ca8dead`). So every
  pass-1 reading of the code still holds as written.
- CI on the head: build, build and check all SUCCESS.

## Pass-1 scenarios

| Pass 1 | Severity | Can it still occur? | Disposition |
|---|---|---|---|
| LOW 1: the `uber_modules` counter is racy under async compile | LOW | Yes, and only under `HAKUX_PSH_UBER=1`. It affects log numbering only, and nothing reads the number. | Accepted for a debug spike. No fix is needed to fold. |
| LOW 2: a text change in psh.c aborts every run with the switch on | LOW | Yes, and only with the switch on. A default build never sets `psh.uber` (it is memset to 0 and gated by `HAKUX_PSH_UBER_DEFAULT 0`), so it cannot reach the `abort()`. | Carried as a condition on `lane/uberspike569-gpl`: a host-side splice check, or a coverage decision made at key time. |
| LOW 3: not bit-exact by construction | LOW | Yes, and only with the switch on. It is stated in the header and in the PR body. | Carried as a condition on any PR that turns it on by default: that PR needs its own exactness leg. |

None of them is a defect in the default-off build. Pass 1's verdict was that they need not be fixed
for this PR to fold, and that still holds.

## Against current master

The branch is 13 commits behind `origin/master`, which has since folded #594 (lane.gpl569, P5
graphics pipeline libraries). `git merge-tree origin/master e35ca8dead` puts one conflict in
`docs/testing/nv2a_index.json` (the regenerated index) and none in code.

In the merged tree, `renderer.h` and `shaders.c` carry the spike's hunks unchanged. #594's GPL path
identifies a fragment library by the binding's `psh.module_info` (`gpl_module_id`), so an uber
module is its own library and cannot alias a specialised one. GPL is also off by default. I found no
semantic interaction.

The index conflict is the usual regenerate-at-fold case, and the fold job resolves it.

## Verdict

Clean. Label: `fold-ready`.
