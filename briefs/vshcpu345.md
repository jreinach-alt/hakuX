# vshcpu345 -- #345 half 2: silicon arithmetic in the nv2a_vsh_cpu constant-writeback evaluator

Lane: vshcpu345
Issue: #345 (half 2; half 1 folded as PR #383)
Base: origin/master at a5b5b628f2 or later.
Files: subprojects/nv2a_vsh_cpu.wrap, subprojects/packagefiles/nv2a_vsh_cpu/**,
       android/app/src/main/cpp/CMakeLists.txt, docs/testing/predictions/vshcpu345-*.json,
       docs/lanes/vshcpu345/**
       (pgraph.c is not yours: if the fix needs a call-site change there, ask on your PR. android/ in the diff means the PR needs audit.)
Needs device: yes (Thor or Nova) to run nxdk_vsh_tests' CPU Shader Tests; scored with docs/testing/vsh_score.py.

## Why (evidence)
lane.xbox's silicon run (PR #344, docs/lanes/xbox/) of nxdk_vsh_tests `CPU Shader Tests` shows the
nv2a_vsh_cpu library (third-party, subprojects/nv2a_vsh_cpu.wrap pinned at 1115255708, and fetched again by
android/app/src/main/cpp/CMakeLists.txt at the same rev), used by pgraph_vsh_writeback_constants
(pgraph.c ~:4066/:4409/:5007), diverges from silicon: no zero-forcing of 0*inf / 0*NaN products in MUL/MAD/DP3/DP4/DPH,
RCC(+inf) returns the wrong sign, and the clamp uses a decimal 2^-64. docs/lanes/dpforce345/NOTES.md "Half 2 (not built)"
says a post-correction in pgraph.c cannot work (intermediate products are gone by writeback), so the fix is IN the
library: a meson wrap patch (`diff_files` under subprojects/packagefiles/nv2a_vsh_cpu/) plus the matching CMake
patch step for the FetchContent path, kept byte-identical. The library is in no board row, which is why nobody did it.

## Build
1. Write the patch against nv2a_vsh_cpu @1115255708 (silicon rules: glsl/vsh-prog.c's `_MUL` zero_components and
   `_RCC` are the reference; PR #344's rows are the ground truth).
2. Apply it on both build paths: meson wrap `diff_files`, and CMake (PATCH_COMMAND on FetchContent, and the local
   checkout case). One patch file, both consumers. Prove both builds compile the patched sources (grep the build log).
3. Keep the CPU path's behaviour on finite inputs byte-identical.

## Proof
Run nxdk_vsh_tests on a handheld with the base and patched builds; vsh_score.py against the console text.
must_move: the DP/MUL/MAD zero-x-inf/NaN rows and the RCC(+inf) row agree with silicon (or the residual is named);
must_not_move: every row exact today. Register the prediction after your last merge of master.

## Done when
A READY PR (it touches android/, so it goes to audit) with the vsh_score.py before/after cited and
docs/lanes/vshcpu345/NOTES.md; or NOTES.md with the measurement that refuted the patch.

## Do not
Edit board files. Fork the upstream repository. Wait on a background task at the end of a turn: your session exits and the task dies with it.
