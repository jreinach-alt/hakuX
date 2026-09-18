# lane.blitsafe -- #88, #91, #92, #89

Base: 55bc6c6c2beed87350cf1c02f67403afddc2acef (origin/master).
Files (yours, no others): hw/xbox/nv2a/pgraph/vk/blit.c, vk/surface.c,
vk/draw.c, hw/xbox/nv2a/pgraph/surface.h.
Issues: #88, #91, #92, #89 -- read all four bodies and territory.toml's
[lane.blitsafe] note before touching anything. #84 is NOT yours any more:
its fix is in fold right now. Do not re-fix it.

These four are ONE cluster on purpose -- the surface/clear path -- which is
why one lane holds them instead of four agents meeting in vk/draw.c.

GOAL, in this order:

1. #92 FIRST, and it is not ordered behind anything: an INSTRUMENTED RUN.
   SurfaceShape carries no address, so framebuffer_dirty() cannot see a
   DMA-context swap. Log framebuffer_dirty()'s verdict across TestSwap()'s
   SET_CONTEXT_DMA_COLOR writes. Report the log; do not change the struct.
2. #89: pgraph_vk_get_clear_color() at vk/draw.c:758-771 takes its pad-alpha
   decision from pgraph_vk_surface_drawn_format(r->color_binding) -- what the
   surface was LAST DRAWN WITH -- not pg->surface_shape.color_format. Narrow
   it to the shape. This is a NARROWING of #59's stamp, not a revert: per
   draw.c:745-751 the clear always wrote 1.0 before #59, so reverting restores
   a different defect.
3. #88 then #91. #91 regresses under #88's change, so #88's arm must be
   registered before #91 is touched or neither is attributable.

BLAST RADIUS, before any edit to surface.h: changing SurfaceShape changes
SURFACE IDENTITY FOR BOTH RENDERERS. #55 and #60 are both about
surface-binding identity. Say what you checked.

FALSIFIER for #89's fix: if the drawn_format/shape divergence is the
mechanism, Blend surface (built from the padded X_O*/X_Z* formats) moves and
Color mask blend (A8R8G8B8 only) does NOT. If both move, or neither, the
mechanism is wrong and the patch is not the answer -- say so rather than
tuning it. Name the world in which the leg fails before you run it.

DONE WHEN: #92's instrumented log is reported with its verdict; #89 has a
patch plus a registered prediction whose must-not-move names Color mask
blend; #88 and #91 each have either a patch with a bound prediction or a
written statement of what is missing. Open a draft PR from lane/blitsafe and
say which issues it closes. Do not queue device arms yourself -- register the
prediction and say it is ready; the board routes it.
