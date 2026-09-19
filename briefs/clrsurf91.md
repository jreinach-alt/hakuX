# lane.clrsurf91 -- #91: a stray depth-only clear is reaching the colour surface in Color_zeta_overlap::Swap

Base: origin/master (fetch it; your worktree is already on it).
Files: hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/surface.c (both
yours; both were free since lane.blitsafe retired). Nothing else without a
grant. Also read nv2a_issues.toml's #88 row -- this fix is what its fold is
gated on, though #88's own ship decision is separate and not yours.

Issue: read `gh issue view 91 --comments` and nv2a_issues.toml's #91
status_note in full before writing any code; it is long but it is the whole
investigation and re-deriving it would waste an arm.

The mechanism is already named: arm B's Swap background reads 0x00000024
against the golden/arm-A's 0xFE242424 -- bits 8-31 (Z24S8 depth) zeroed,
bits 0-7 (stencil) preserved, exactly the signature of a depth-only clear of
0 landing on the COLOUR surface. The inline clear path is already confirmed
correctly guarded (`write_zeta && r->zeta_binding` at vk/draw.c:6774 and
:6870) -- look at the fall-through PIPELINE clear path instead. Two
diagnosis arms already ran (solo `Color zeta overlap::Swap` at #88's own arm
refs) and found the regression intrinsic, not contamination from
ColorIntoZeta -- do not re-run that arm, read its result in the status_note.

Goal: find and fix the site where a depth clear reaches the colour
attachment when zeta's binding is declined (the #88 colour-wins policy:
colour may take a surface zeta holds, zeta declines one colour holds,
leaving zeta's binding absent). Do not touch #88's policy itself unless the
fix requires it -- #88 is a separate row and its ship decision is the
owner's.

Falsifier: register a prediction against Color_zeta_overlap (Swap,
ColorIntoZeta_ZB, ZetaIntoColor, Swap_ZB) with absolutes where the corpus
supports them -- #88's own prediction already has the two exact absolutes
for ColorIntoZeta_ZB/ZetaIntoColor and must_not_move for Swap; yours should
turn Swap's must_not_move into a real target (165,447, the value on both
renderers before any of this work) now that the mechanism is named.

Done when: the fix is pushed on lane/clrsurf91 with the prediction
committed, the PR body follows roles/lane.md's template, states its effect
on #88 (does the fix let #88's policy ship, or does #88 still need a
separate decision), and the PR is marked ready.
