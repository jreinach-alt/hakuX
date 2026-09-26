# lane.ring53 -- #53: model the six-entry ring of stale FF lighting outputs under a vertex program

Issue: #53 (shares its mechanism with #41's RADIAL fog). Base: origin/master @ 6c25a829ef.
Files: hw/xbox/nv2a/pgraph/glsl/vsh-ff.c, hw/xbox/nv2a/pgraph/glsl/vsh-prog.c,
       docs/lanes/ring53/**, docs/testing/predictions/ring53-*.json.
       Both glsl files are RELEASED AT READY and free: vsh-prog.c by lane.dpforce345 (PR #383, ready, at audit),
       vsh-ff.c by lane.zrtz272 (PR #364, ready, at audit). Before marking your PR ready, merge master (or those PRs'
       branches if they have not folded) and re-run your arm.
       pgraph.h / pgraph.c / vk/draw.c (per-draw state, host-side carry) are NOT granted: vk/draw.c is lane.remote's.
       If the design needs one, name the hunk and board-request the grant; do not edit it.
Needs device: yes for the arm; the design and the offline pricing are desktop. Needs NDK: no.

## What silicon does (measured, PR #355, docs/testing/xbox-litprime-2026-09-25.md; PR #351 docs/testing/xbox-cf53-slots-2026-09-25.md)
Under a vertex program with LIGHTING_ENABLE, a lit corner does not take its own lighting. It reads one of the preceding
fixed-function draw's LAST SIX per-vertex lighting outputs. Each quad reads four consecutive entries (UL, UR, LR, LL) in
draw order, and the start advances +4 (mod 6) per quad, whether the quads are six draws or one. All 48 lit corners of the
priming run equal a priming vertex's value to 0.56 levels. hakux lights every VS vertex with its own normal.
Open: the ABSOLUTE PHASE at the start of a vertex-program draw (the extra -1 in #53's comment). Do not guess it: the
Specular / Specular back / Lighting control captures (102,240 px on ControlFlags_VS, 162,258 px in #53) fix it.

## The job
1. Locate first: where does a VS-mode lit vertex get its colour today (vsh-prog.c light path, the constant term), and
   what would it take to hold the previous FF draw's last six lit outputs across draws. Name every consumer and holder.
2. Design the cheapest faithful mechanism (state carry, and where). Say whether it fits in the two granted glsl files
   alone. If it needs the per-draw state files, say so early, with the hunk, and stop for the grant.
3. Price it offline against the Specular-family captures on disk before touching code (litprime_score.py, cf53_slots.py
   are the readers). Fit the phase on half of the captures and score the rest; a phase fitted on everything is a fit.

## Falsifier and arm
Mover: Specular ControlFlags_VS and _Back plus Lighting control VS rows fall toward their one-step floor. Must-not-move:
every FF-lighting capture (no vertex program), Lighting range/accumulation suites, #41's RADIAL-fog captures unless you
price them in the same commit. Name which change would move each. Check `status` for `unreadable` and PARTIAL COVERAGE.

## Done when
NOTES.md holds the mechanism, the phase with its evidence, the priced result and the hunks with holders; the hunk is
landed if the granted files carry it; the prediction is registered after the last rebase; the PR is ready.
