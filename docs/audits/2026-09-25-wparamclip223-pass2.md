# Audit pass 2: PR #250, lane wparamclip223 (#223, external wedge)

Auditor: job.cloud, 2026-09-25. Head checked: `83ff6eec9f`, which is the
pass-1 commit itself. Pass 1 audited `3c3f845719`.

**Verdict: clean. The PR goes to fold-ready.** Pass 1 found no HIGH and no
MEDIUM, so no scenario could still fire and block the fold. Nothing changed
in the code after pass 1. Each of the four LOWs is still true as written and
is recorded below as deliberately left.

## What changed since pass 1

`git diff 3c3f845719 83ff6eec9f` adds only
`docs/audits/2026-09-25-wparamclip223-pass1.md`. The geometry shader at head
is the one pass 1 read. It is also the one the `[job.arms]` PASS on
`wparamclip223-wedge-grid.json` measured: pass 1 showed that nothing under
`hw/` in the geometry path changed after that arm's b_ref.

## The pass-1 findings

| Finding | Still occurs? | Disposition |
|---|---|---|
| L1: GLES without `GL_NV_shader_noperspective_interpolation` gets a third interpolation answer | Yes. The weights are still chosen in C from `state->noperspective`. | Left. It needs GLES, no extension, perspective off and one negative w. No arm runs GLES, and the old answer was also wrong. The remedy is in pass 1: guard the `lam` choice with a GLSL `#if`. |
| L2: `max_vertices` goes from 3 to 8 with no frame-time number | Yes. NOTES records the 8 against the Vulkan limit of 18, but gives no timing. | Left, with a follow-up recommended: take one before/after frame-time sample on the Thor in a geometry-heavy title. This is a performance risk, not a correctness one. No golden can see it. |
| L3: `vtxFogSpecial` is taken from v0, while `emit_vertex()` on Android GLES uses v2 | Yes. NOTES:111 states the v0 choice. | Left. v0 is the guest's provoking vertex after the rewrite, so this is arguably the more correct answer. |
| L4: the N->P ray-edge seams are not bit-shared between neighbouring wedges | Yes, in principle. | Left. The expected effect is well under one pixel per edge, and the host clipper made no watertightness promise either. |

Pass 1 asked for each deliberate leave to be written into the lane's NOTES.
NOTES covers L2 (the vertex count) and L3 (the v0 source) only in passing. It
does not cover L1 or L4. An audit may push only its audit file to the lane
branch, so this table is the record for all four. It folds with the PR.

## Fold readiness

- A test merge against `origin/master` (`git merge-tree`) conflicts in
  exactly one file: `docs/testing/nv2a_index.json`. That is the generated
  index. `fold.sh` regenerates a stale index over the pinned trees, so this
  conflict does not need the lane.
- Nothing in this pass needs a device.
