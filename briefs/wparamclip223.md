# #223: clip extreme-w triangles in the geometry shader and emit silicon's external wedge as positive-w geometry

Lane: wparamclip223            Issue: #223 (W param)
Base: origin/master
Files: hw/xbox/nv2a/pgraph/glsl/geom.c, hw/xbox/nv2a/pgraph/vk/instance.c,
docs/testing/predictions/wparamclip223-*.json, docs/lanes/wparamclip223/**
Needs device: yes (a Thor W_param arm). Needs NDK: no.

## Read first: PR #246 (lane.wparamgeom223), which refuted the previous plan

`docs/lanes/wparamgeom223/NOTES.md` is on `origin/lane/wparamgeom223`, and on
master once #246 folds. The uniform per-primitive w scale cannot work, because
the triangles we fail to draw fail on the **ratio** between their w values, not
on how small they are.

- `w-7.52e-37`, `w-3.76e-37` and `w-1.88e-37` have tri2 = {-2^-56..-2^-58 |
  2^64}, a ratio of 2^120 to 2^122.
- `w-0.00` has a ratio of 2^128.
- Every ratio-1 triangle draws today, at 2^-64 and 2^64 alike.
- A uniform scale cannot change a ratio.

`docs/lanes/wparam223/NOTES.md` section 4's table is corrected in place, and
section 5 is withdrawn. Do not rebuild the scale.

## The job: the "second step" both NOTES name

For a filled triangle with **exactly one** negative-w vertex N and positive
vertices P1 and P2, silicon draws the **external wedge**. It is bounded by the
edge P1-P2 and by the extensions of the edges P1-N and P2-N beyond N.

- Compute that wedge in the geometry shader.
- Clip it to the guard band in screen space.
- Emit it as ordinary **positive-w** geometry. The host clipper then never sees
  a negative w, and it is the host clipper that makes llvmpipe, Adreno and
  silicon disagree (wparam223 NOTES section 4).

Requirements:
- **Varyings** are extrapolated projectively across the wedge, so they stay
  perspective-correct.
- **Scope** is `glsl/geom.c`'s TRIANGLES path.
  - Quads reach it through the rewrite to `PRIM_TYPE_TRIANGLES`, which #246
    corrected. So `ff_*quad` and `prog_*quad` are in scope, and `prog_*quad`
    must STAY at 0.
  - Triangles with two or three negative vertices keep today's path. Say what
    they do, and do not change them.
- **Output limit:** check the emitted vertex count against
  `PGRAPH_GEOM_MAX_OUTPUT_VERTICES` (18, `vk/instance.c:734`) and the
  components limit beside it.
  - Raising the limit means updating the build asserts and the device-limit
    check there.
  - Audit finding L10 applies: a geometry shader that overruns a device limit
    fails to compile, and on Vulkan a failed compile **draws nothing**.
  - Prove the shader compiles for every `geom_dump` case under the NDK's
    glslc, as #246 did.

**Price it offline before writing C.** The NOTES arithmetic regenerates the
table from the test source: clamp to [2^-64, 2^64] by sign, and
`k = -trunc((emax + emin) / 2)` over the float exponents. Extend it to predict
each must-move capture's wedge coverage against the golden. If the offline
wedge does not cover what the golden shows, stop: the model of silicon's wedge
is wrong. That is a finding, not a reason to tune.

## The arm (register BEFORE building, and after the last rebase)

Thor, W_param, from wparamgeom223's NOTES:
- **must_move:**
  - `prog_w_zero_inf__bitri_w-0.00`: 271,518 (both wedges, split 142,693 tri2 +
    128,825 tri1);
  - `_w-1.88e-37` and `_w-3.76e-37`: about 143.5k each (tri2);
  - `_w-7.52e-37`: 4,768.
  - Set each bound from your offline pricing, not from these totals.
- **must_not_move:**
  - the 20 `prog_w_zero_inf__quad` at 0;
  - the positive-w `prog_..._bitri_w*` rows at 0;
  - the ratio-1 rows that pass today (the new path takes them too);
  - `nv2a_index.py blast hw/xbox/nv2a/pgraph/glsl/geom.c`, which covers
    #235's Shade model Flat captures and #13's line suites.
- **The world in which must_move fails:** silicon's wedge is not the region
  bounded by P1-P2 and the extensions through N. For example, it is clipped by
  a guard band or a coarse raster rule we do not model. Then the captures move,
  but not onto the golden. Report the per-capture residual and do not refit.

**Before trusting the verdict:**
- check both arms' `scores1.tsv` status column for `unreadable`;
- check `run1.log` for "PARTIAL COVERAGE" and UtilAcceptVsock.

An unreadable capture scores as 0, so it reads as "fixed".

## Do not

- **Score a desktop capture against these goldens.** llvmpipe, Adreno and
  silicon disagree here, because the host clipper decides.
- **Use desktop Vulkan under WSLg:** it hangs.
- **Repeat the RCC/MUL leads.** They are refuted.
- **Re-open the WASH half of W_param.** It is #38's.
- **Trigger CI as a self-check.**

## Done when

- The arm verdict is on your PR, with its status column checked.
- NOTES record the offline pricing and the result.
- `nv2a_index.json` is regenerated over the tests tree at
  `provenance.tests_commit` 6743b6a and pbkitplusplus e91d509.
- The PR has the lane template with its `Files:` line, preflight passes, and
  the PR is marked ready.
