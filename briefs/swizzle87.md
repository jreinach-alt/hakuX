# lane.swizzle87 -- #87 and #85

Base: 55bc6c6c2beed87350cf1c02f67403afddc2acef (origin/master).
Files (yours, and gl/surface.c is GRANTED -- the grant was made at wave 86 and
only now written into the machine-checked field, which was the board's error
and not yours): hw/xbox/nv2a/pgraph/vk/texture.c,
hw/xbox/nv2a/pgraph/gl/surface.c.
hw/xbox/nv2a/pgraph/swizzle.c is in [free]. If you need it, say so in the PR
and take it -- you will not be told to ask twice.

You were dispatched analysis-only last time and derived the mechanism without
writing a line. NOW IMPLEMENT. The fix is yours to write.

GOAL:

1. #87, the swizzled render-target layout. Legs 1-6 are drafted, including the
   corrected control partition: 17 _L captures MAY move, 24 non-_L and all
   1,673 Blend_tests MUST NOT, and Vertex_shader_rounding has ZERO goldens so
   it cannot be a leg either way. The fix must land on BOTH backends or its
   arm is void -- that is why the two files are one claim. Gates are at
   gl/surface.c:1131 and :1487, in surface_to_texture_can_fastpath() and its
   caller.
2. #85, small and fully specified: the mem_dirty half of the surface-upload
   gate at gl/surface.c:2874-2892 in update_surface_part() has no reachable
   true branch. Either delete the dead half or make it reachable AND test it.
   It is ~1,400 lines from #87's gates, verified at the tip, so the two edits
   do not meet. Do it second and commit it separately.

EVIDENCE ALREADY ON DISK, needs no device: at HEAD with no bound the Vulkan
renderer reproduces #39's skew-bound digest exactly (15845fa9e1e40032), so
Vulkan loses the race the same way every time and its capture IS the race-free
image. Against the golden it has an IDENTICAL COLOUR MULTISET over 10,240
differing pixels -- right pixels, wrong places, runs of 16/32/64/80 px, no
single translation explaining more than 40%.

FALSIFIER: the run-length signature is a constraint on tile geometry. If your
layout model is right, the predicted permutation reproduces those run lengths
exactly on the captured image OFFLINE, before any build. If it does not, the
model is wrong -- do not compile a guess. A leg your own patch forces true
tests nothing.

DONE WHEN: a patch on both backends, a prediction registered AFTER your last
rebase (a rebase silently un-ancestors a b_ref), the control partition above
written into it verbatim, and #85 committed separately with its reachability
answered either way. Draft PR from lane/swizzle87. Do not queue the arm.
