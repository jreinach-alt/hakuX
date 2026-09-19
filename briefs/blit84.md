# lane.blit84 -- #84: vk/blit.c BLEND_AND hard-codes 32bpp, so a 16bpp or Y8 blend writes past the destination object

Base: origin/master (fetch it; your worktree is already on it).
Files: hw/xbox/nv2a/pgraph/vk/blit.c (yours). Nothing else without a grant.
Issue: read `gh issue view 84 --comments` first; the mechanism is stated
there and lane.blit38's notes on #38 describe the BLEND_AND path.

Goal: make the BLEND_AND path honour the destination's bytes-per-pixel
(16bpp formats and Y8) instead of assuming 32bpp, so the write stays inside
the destination object. Keep the 32bpp behaviour bit-identical: #38's
BLEND_AND verdict (Image_blit 168,245 -> 8) rests on it.

Falsifier, registered BEFORE any device run with ab_compare.py --register
and committed in docs/testing/predictions/: every Image_blit/ImgBlt_BLENDAND_*
capture must_not_move, and name the capture(s) your change is predicted to
move, or state that no golden exercises a non-32bpp BLEND_AND and register
the change as an inertness claim over Image_blit/*. Say which in NOTES.md.

Done when: the fix is pushed on lane/blit84 with the prediction committed
after the code commits (never rebase after registering), the PR body follows
roles/lane.md's template, and the PR is marked ready. The arms job runs your
prediction and posts the verdict on the PR; you do not queue arms yourself.
