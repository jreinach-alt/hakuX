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
diagnosis arms already ran (registered as solo `Color zeta overlap::Swap` at
#88's own arm refs, but `jobs/arms.sh` never passes `--only-tests` so they
ran the full suite) and excluded cross-suite composition as the cause;
within-suite contamination from ColorIntoZeta/ColorIntoZeta_ZB remains open
-- do not re-run that arm, read its result in the status_note.

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

RESUMED 2026-09-20 (job.board): PR #148 is open, `fold-ready` + `regressed`.
The registered arm on `7980d1caa2` came back FAIL: arm B is BYTE-IDENTICAL to
arm A on all 11 captures (Color_zeta_overlap/Swap still 304,750, not the
predicted 165,447) -- the fix moved nothing. That refutes the ROUTE
(`update_surface_part()`'s gate is not how the bad word reaches Swap's
background on this policy), not the byte arithmetic (0xFE242424 -> 0x00000024
is still exactly a depth-only clear landing on colour; no other reading has
been produced).

Falsifier (5) in the registered prediction was unreadable by the auditor
(sandboxed, no run-dir access) and is the next step: `dl91_probe`'s counter
only exists in arm B (`7980d1caa2`), not arm A, so read it from arm B's own
run, not by comparing arms.

    grep -h '\[dl91\]' <arm-B run dir>/**/logcat*
    # arm B ref 7980d1caa2, result dir 1789825274-arms-clrsurf91-fix-1110297

- `n == 0`: the declined branch never fired in this suite. The mechanism is
  refuted outright, on the prediction's own terms -- the byte-identical arms
  are then fully explained (the fix had nothing to decline), and the next
  step is finding the real route to Swap's background, not patching this one
  harder.
- `n > 0` with the arms still byte-identical: the branch fired and every
  declined download would already have written the same bytes at that
  address. Read why before concluding the fix is a no-op -- this is the more
  interesting case and may point at a second site.

Read the full `[job.arms] VERDICT: FAIL` comment on PR #148 (2026-09-19T16:18Z)
before doing anything else; it has the complete falsifier list and what this
arm cannot see. Do not remove `regressed` by hand -- `arms.sh` clears it from
a fresh verdict, never from an edit to the label. If the mechanism is refuted,
say so on the PR and in `status_note`, and register what replaces it; do not
re-run the identical arm expecting a different byte-identical result.
