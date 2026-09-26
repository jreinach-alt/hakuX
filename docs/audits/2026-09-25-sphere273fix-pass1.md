# Audit pass 1 -- PR #330 lane/sphere273fix (#273)

Auditor: job.cloud, 2026-09-25. Head audited: f7d0c8f2f3.

**Verdict: no HIGH, no MEDIUM, two LOW.** The PR goes to `needs-audit-2`.

## What was read

GitHub's `gh pr diff 330` lists about 80 files, because it diffs against a stale
merge base. The lane's own diff is `git diff origin/master...HEAD`, with
origin/master at a3a001f7c3. It has four files:

- `hw/xbox/nv2a/pgraph/pgraph.c`: 14 lines in `kelvin_map_texgen`.
- `docs/testing/predictions/sphere273fix-rz.json`: new.
- `docs/lanes/sphere273fix/NOTES.md`: new.
- `docs/testing/nv2a_index.json`: regenerated.

## The code change, checked

`(SET_TEXGEN_* = SPHERE_MAP, channel 2)` now returns
`NV_PGRAPH_CSV1_A_T0_S_REFLECTION_MAP` (5) where it used to return DISABLE (0).
Channel 3 still returns DISABLE and logs UNIMPLEMENTED. Channels 0 and 1 still
return SPHERE_MAP (3).

- **Register width.** The R field is `NV_PGRAPH_CSV1_A_T0_R = 0x1C00`, which is
  3 bits wide, so the value 5 fits. The T1 masks and the CSV1_B masks have the same
  shape.
- **Reaching the shader.** Both `glsl/vsh.c:56` and `vk/renderer.c:1278` read the
  field straight into `enum VshTexgen`. There, 5 is `TEXGEN_REFLECTION_MAP`
  (`vsh_regs.h` order: DISABLE, EYE, OBJECT, SPHERE, NORMAL, REFLECTION). The
  value is part of the shader key, so no stale-key path exists within a run.
- **No new crash path.** In `vsh-ff.c:848`, the REFLECTION_MAP case asserts
  `j < 3`, and j == 2 passes it. It emits `oT.z = r.z`. The `assert(j < 2)` in the
  SPHERE_MAP case can no longer be reached from R, and it never could be (R was
  mapped away before). Q keeps the DISABLE path, which has no assert.
- **Other modes.** No other `(mode, channel)` pair changes. EYE_LINEAR,
  OBJECT_LINEAR, NORMAL_MAP, REFLECTION_MAP and default are byte-identical.
- **Tested binary is the head's.** `git log 0965b30a26..HEAD -- pgraph.c` is
  empty, so the file the fix arm ran (b_ref 0965b30a26) is the file at head. Both
  a_ref and b_ref are ancestors of head.
- **Prediction.** The must_not_move list names every group in the suite except
  the two movers. Each group comes with the patch change that would move it. The
  refusal of an exact `=0` leg is argued from the 56-603 px 1-LSB floor of the
  other SphereMap captures, which is correct. The arm posted PASS 71/71, and the
  hand-judged table (126 and 125 px, all 1 LSB) meets the stated bound of
  <= 1,000 px at max_rgb <= 2.

## Findings

### LOW 1 -- the code comment states r.z as settled; the PR says it is not

`pgraph.c` inner comment: "Sphere mapping on R gives the reflection vector's z
... both goldens match r.z to 1 LSB". The PR body and NOTES say correctly that on
this quad n = (0,0,1), so r.z = -u.z exactly, and the goldens cannot separate the
two. **Scenario:** a later lane adds a tilted-normal test and sees R disagree. The
comment reads as a hardware fact, not as one of two fits, so that lane debugs the
wrong layer before it suspects this mapping. **Fix:** one clause in the comment,
e.g. "(or -u.z: with n = (0,0,1) these quads cannot tell them apart)". This
changes no behaviour.

### LOW 2 -- the NOTES `## State` section is stale at head

NOTES ends with "It merges cleanly ... so I did not merge again". The head is now
7579be4bd4 (a merge of origin/master) plus f7d0c8f2f3 (index regen), both after
that line. **Scenario:** a pass-2 auditor or the folder reads State and concludes
that head == the verified merge. It does not. That is harmless here, because
pgraph.c is unchanged since b_ref (checked above), but the reader cannot learn
that from the NOTES. **Fix:** a line saying that the merge brought only master's
files and the index, and that pgraph.c is unchanged since b_ref.

## Not findings (checked, recorded so pass 2 does not redo them)

- **CSV1 readback.** CSV1 now reads 5 in R, not 3. `kelvin_map_texgen` already
  translates method values to register encodings, so readback never mirrored the
  guest's method value. NOTES and the PR body say this is unobservable by any
  test. Without a guest that reads CSV1 back, there is no failure scenario.
- **Q.** Q is unchanged and is disclosed as no-evidence.
- **nv2a_index.json.** It is a regenerated artifact. The NOTES records `check`
  matching at tests_commit 6743b6ab. CI's `check` job is SUCCESS on this head,
  and `build` was pending when this audit was written.

## What pass 2 should verify

Pass 2 checks whether each LOW was addressed or explicitly declined. Neither LOW
blocks folding.
