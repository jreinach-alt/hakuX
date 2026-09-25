# Audit pass 2: PR #263 (lane shadetie224b), #224 family B

Auditor: `[job.cloud]`, 2026-09-25. Head audited: `0d4b527760`. Pass 1
(`2026-09-25-shadetie224b-pass1.md`) read `9afbc48b20` and found no HIGH, no
MEDIUM and four LOWs. It asked pass 2 to confirm that none of the LOWs has
become a MEDIUM: either the head's `vsh-ff.c` helpers are unchanged from
`9afbc48b20`, or any change has been re-run through `exact.py`.

**Result: clean.** Next state: `fold-ready`.

## What was verified

1. **The code is unchanged since pass 1.** `git diff --stat 9afbc48b20 0d4b527760`
   touches only `docs/audits/2026-09-25-shadetie224b-pass1.md`. So
   `hw/xbox/nv2a/pgraph/glsl/vsh-ff.c` is byte-identical to the tree pass 1 read.
2. **Master has not moved under the code pass 1 relied on.** Between the merge
   base `2b04d4d422` and `origin/master`, no commit touches `vsh-ff.c` or
   `vsh.c`. Pass 1's safety arguments therefore still hold on the fold result:
   - `vsh.c` still clamps with `clamp(NaNToOne(oD0/oB0))` before
     interpolation, so inf and NaN never become varyings.
   - `vsh.c` still writes `vtxD1` from `oD1` only under `specular_enable`.
   GitHub reports the PR as MERGEABLE/CLEAN, and CI is green on this head:
   build, build and check all pass.
3. **`exact.py` passes on the head anyway.** I rebuilt the emitter from the
   head's `vsh-ff.c` (`vshemit/build.sh`) and ran `exact.py`:
   `cases 60000 mismatch 0 edge-skipped 676`. The GLSL helpers agree with the
   envytools port on every case not skipped as an edge case.

## The pass-1 scenarios

| Finding | Scenario | Status at head |
|---|---|---|
| LOW-1 | The local-light / local-eye composition (`s < 0` zeroing, extra `ltsA` truncation) has no offline model | Unchanged: `vsh-ff.c:518` and `:522` are as read. There is still no golden reaching the case, so it stays LOW. It is not a defect the PR can fix without a silicon reference. |
| LOW-2 | `ltR(NaN)` gives NaN, which `NaNToOne` turns into 1, where the port gives 0 | Unchanged. It is still unreachable from D3D specular tables. |
| LOW-3 | `< 0.0` against the port's sign bit differs on -0.0 | Unchanged. It is still unreachable with colour-range operands. |
| LOW-4 | Shader cost is unmeasured | Unchanged. Nothing in the gate measures it. Game-side frame time is the place to watch after the fold. |

None of the four moved: the code they describe is identical and so is the
code they depend on. None of them was a scenario that remediation had to
close.

The one failing arm leg (`Specular_back/SpecParams_FF_Pow0_1`, 1259 -> 1280)
is covered by the `regression-accepted:224` label already on the PR. Pass 1
recorded leads for it. They are not findings, and this pass does not reopen
the leg.
