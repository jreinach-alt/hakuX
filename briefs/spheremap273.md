# #273: SphereMap_Arbitrary and SphereMap_RotateX draw the whole quad wrong (262,990 px)

Lane: spheremap273         Issue: #273 (Texgen with texture matrix)
Base: origin/master @ 8e683b3a26 (rebase to the tip before you register anything).
Files: docs/lanes/spheremap273/**, docs/testing/predictions/spheremap273-*.json
       (LOCATE-FIRST: the guessed area, vsh-ff.c:699, is lane.shadetie224b's. Name the function and the
       change and ask the board for the path.)
Needs device: yes for the arm (Nova or Thor); the analysis is desktop. Needs NDK: no.

## The defect
Both captures wrong over the whole 455x289 quad (131,495 px each, 0 exact); the other seven matrices in
the suite are exact or within 455 px. One mechanism. Guess: how sphere-map r/q reach the texture matrix.

## Read first; the guess is a claim
1. Read the test source (nxdk_pgraph_tests, Texgen with texture matrix): which matrix, which texgen mode,
   which texture coordinates, and why RotateX/Arbitrary differ from the seven that pass.
2. Derive silicon's sphere-map value per vertex from the golden region (not a point sample), then compare
   to what vsh-ff.c produces. Say where the first difference is.
3. Price the fix offline in numpy before asking for a grant.

## The arm (register BEFORE building, after the last rebase)
must_move: the two SphereMap captures exact, or a stated residual. must_not_move: the other seven matrices
and every other sphere-map texgen capture; name the change that would move each.

## Done when
The mechanism and the exact hunk are in NOTES.md with the priced result, the arm is registered, and the PR
is ready. Analysis plus the requested hunk is a complete outcome while vsh-ff.c is held.
