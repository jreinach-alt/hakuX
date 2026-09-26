# Audit pass 2 -- PR #330 lane/sphere273fix (#273)

Auditor: job.cloud, 2026-09-25. Head audited: 05e443487d. Pass 1 audited f7d0c8f2f3.

**Verdict: clean. The PR goes to `fold-ready`.** Pass 1 raised no HIGH and no
MEDIUM, and nothing since then has added one. The two pass-1 LOWs are still in
the tree. They were neither fixed nor declined, and pass 1 already ruled that
neither blocks folding. They are recorded below so that a later lane can find
them.

## What changed since pass 1

`git diff f7d0c8f2f3 05e443487d` is one merge of origin/master (the #268, #321
and #351 folds, among others) plus an index regeneration. The lane's own diff,
`git diff origin/master...HEAD`, is the same four files as at pass 1, plus the
pass-1 audit file:

- `hw/xbox/nv2a/pgraph/pgraph.c`: the same 14-line hunk in `kelvin_map_texgen`.
  `git log 0965b30a26..HEAD -- pgraph.c` is empty, and b_ref 0965b30a26 is an
  ancestor of head. So the binary the fix arm ran still has this file exactly
  as it is at head.
- The prediction, NOTES and the regenerated `nv2a_index.json` are unchanged,
  apart from the index regeneration.

## Interaction with what master brought in

This fix sends `(SPHERE_MAP, R)` into the `TEXGEN_REFLECTION_MAP` case of
`vsh-ff.c`, which is now at line 848: it asserts `j < 3`, which R passes, and it
emits `oT.z = r.z`. The merge brought one `vsh-ff.c` hunk, from #321. That hunk
is in the position epilogue (`oPos`, the W_param carry for non-finite `w`) and
does not touch the texgen switch. The texture-coordinate path this PR relies on
is byte-identical to the one the arm measured. The merge also changed
`glsl/geom.c` (#321, the zero-area wedge rule) and `glsl/psh.c` (#268, the D24
depth saturation). No changed line in either file mentions texgen or CSV1.

## Pass-1 scenarios

### LOW 1 -- the code comment states r.z as settled

**Still present.** The inner comment in `pgraph.c` still says "both goldens match
r.z to 1 LSB" and does not mention -u.z. On these quads n = (0,0,1), so the
goldens cannot tell r.z from -u.z. The pass-1 scenario still holds: a later
tilted-normal test that disagrees on R would find a comment that reads as a
hardware fact. This does not change behaviour. It is left for #273's follow-up
or the next lane to touch this function.

### LOW 2 -- the NOTES `## State` section is stale at head

**Still present, and one merge more stale.** State still says "I did not merge
again", but head is now two merges past it. The fact a reader needs, that
pgraph.c has not changed since b_ref, is checked above and holds at 05e443487d.

## Checks

- CI at 05e443487d: `check` and `build` were running when this audit was
  written, after the merge push. Folding waits for them in any case.
- GitHub reports the PR as mergeable.
