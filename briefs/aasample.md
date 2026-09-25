# #286 (class A): make our AA-surface path transparent -- CENTER_CORNER_2 puts samples off the pixel centre

Lane: aasample            Issue: #286 (its class-A finding; PR #328 folded, docs/lanes/cloud-286/NOTES.md sec 3)
Base: origin/master @ 2dc5d1b884 (rebase to the tip before you register anything).
Files: hw/xbox/nv2a/pgraph/pgraph.h (pgraph_apply_anti_aliasing_factor), docs/lanes/aasample/**,
       docs/testing/predictions/aasample-*.json.
       vk/draw.c (viewport/scissor consumers) is lane.vtxarr262's (PR #264): name the hunk, board-request the
       grant, do not edit it. vk/surface.c is [free] but not granted: ask.
Needs device: yes for the arm; the derivation is desktop. Needs NDK: no.

## The defect (measured, not modelled)
Silicon's `AA_CENTER_CORNER_2` render-and-resolve is byte-identical to a non-AA draw on all 48 3D_primitive captures
where the smoothing flag is geometrically inert (0 px moved). Ours moves 517,872 px on the same 48.
`pgraph_apply_anti_aliasing_factor` (pgraph.h:572) models it as `width *= 2` and nothing else: sample centres land at
x+0.25 / x+0.75, neither the pixel centre. The guest's resolve draws a 640-wide quad over the 1280-wide image with
u = 2x+1, an exact texel tie (#282's territory). Net recoverable ~242,288 px (TriFan 102,828, TriStrip 65,280,
QuadStrip 54,636, Polygon 24,504, Triangles 14,180, Points 84 = the 7 dropped points). Quads GETS WORSE (-17,816 px):
our shifted sampling cancels part of Quads' own plain-arm error.

## The job
1. Re-derive the mechanism from source and the captures before believing NOTES: which sample is at the pixel centre in
   CENTER_CORNER_2, and which half-column the resolve tie selects. Read #282's NOTES (docs/lanes/cloud-282) first.
2. Design the change and name every consumer of the AA factor -- viewport, scissor, clear, resolve -- with its file and
   holder.
3. Price it offline against the 120 captures with aapath286.py / decompose286.py before touching code.

## Falsifier and arm
Falsifier: on the 48 inert captures O_X == O_P byte-exact (silicon's are). Must-not-move: the 40 plain 3D_primitive
captures, Antialiasing_tests (#274's residual), every non-AA suite; name the patch change that would move each. Points
leg: all 12 points present in every AA capture. Check `status` for `unreadable` and PARTIAL COVERAGE.

## Done when
NOTES.md holds the mechanism, the per-primitive priced result (the Quads loss included, with an owner), the exact hunks
with holders; the prediction is registered after the last rebase; the PR is ready. If the pgraph.h edit is inert without
the draw.c consumer, say so and ask for the grant; do not edit a file you do not hold.
