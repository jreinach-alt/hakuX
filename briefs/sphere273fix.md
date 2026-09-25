# #273: SphereMap on the R texgen channel -- land the priced one-case hunk in pgraph.c

Lane: sphere273fix         Issue: #273 (Texgen with texture matrix, 262,990 px)
Base: origin/master at dispatch (rebase before you register; the base MUST contain PR #288's fold).
DISPATCH GATE: pgraph.c is lane.vshsubneg255's (PR #288, fold-ready). Start this the tick after it folds.
Files: hw/xbox/nv2a/pgraph/pgraph.c, docs/testing/predictions/sphere273fix-*.json,
       docs/lanes/sphere273fix/**
Needs device: yes for the arm (Nova or Thor). Needs NDK: no.

## What is settled -- cite it, do not redo it
docs/lanes/spheremap273/NOTES.md (+ price.py) on master: `kelvin_map_texgen` maps SPHERE_MAP on channel>=2 to
DISABLE (#28's anti-abort guard), so oT0.z = 0. Silicon's R is the reflection vector's z (r.z): the hunk in
NOTES section 4 prices SphereMap_RotateX and SphereMap_Arbitrary 131,495 -> 0 px each (max 1 LSB), the other
nine SphereMap matrices unchanged. Whether the register keeps 3 or 5 is not observable by any test.

## Goal
Apply the section-4 hunk: SPHERE_MAP on channel 2 -> REFLECTION_MAP; channel >= 3 stays unimplemented. Narrow
the comment above the switch to Q. Do not touch vsh-ff.c (another lane's); no pixel change outside the 2 captures.

## Falsifier (register BEFORE building, after the last rebase, b_ref containing the hunk)
must_move: Texgen_with_texture_matrix/SphereMap_RotateX and /SphereMap_Arbitrary, 131,495 -> 0 (<= 2/channel).
must_not_move: every other Texgen_with_texture_matrix/* capture and Texgen tests; name for each the patch change
that would move it (only the (SPHERE_MAP, channel 2) pair changes). Run the arm; a leg that fails is a refuted
hunk, not a rounding.

## Done when
The hunk is on the PR, the arm verdict is verified, must_not_move is byte-identical, and the PR states that Q
and tilted-normal disambiguation (r.z vs -u.z) have no evidence yet.
