# lane.blit83b -- #83, second pass. ANALYSIS ONLY, and it is nearly closed.

Base: origin/master (fetch it; 55bc6c6c2b was the first pass's base).
Files: NONE, and this time not as a compromise. lane.blit83 looked and said
so in writing: "I didn't request vk/blit.c -- on this evidence an edit there
would target a defect that isn't in it." Do not ask for it.

READ FIRST: https://github.com/jreinach-alt/hakuX/issues/83#issuecomment-5737707468
and `[issue.83]` on the board branch. Both were rewritten 2026-09-19 and the
issue TITLE is now wrong; do not re-derive from the title.

WHAT THE FIRST PASS SETTLED, so you do not repeat it:
  - #83's "each 1 px low" was a COLUMN MISREAD. The header is
    `differing max_rgb max_a pixels off_by_one`; the row is
    `1650 1 0 307200 1650`. The 1 is max_rgb, the max CHANNEL delta. Five
    on-disk measurements read 1,573 / 1,650 / 1,650 / 1,701 / 1,701
    DIFFERING PIXELS. Nothing on disk reads 1 as a count. The figure
    propagated through the issue, the prediction JSON, 24a75d6e3c's commit
    message and an investigation doc without ever being a scored row.
  - The blit is 1x1 (TestOverlapBarelyInclusive), so ONE PIXEL is the
    ceiling on any copy-extent mechanism and the measurement is three orders
    of magnitude above it. All eight destination pixels are byte-exact;
    ELSEWHERE = 0. All ten Clip_*/SRCCOPY_* captures score exactly 0.
  - So the residual is NOT the blit. The standing candidate is vertex-colour
    interpolation in the Gouraud quad.
  - The BLEND_AND control leg is SOUND BUT INERT and #38's PASS stands.

THE ONE THING READING COULD NOT SETTLE, and it is the whole job: which
pixels differ on a DEVICE capture at a ref carrying dca3c94b98. Every
"which pixels" datum so far is desktop, and dca3c94b98 is in arm A's
ancestry and not in b9d845d3's, so the existing comparison confounds the
commit with desktop-vs-device.

GRANTED, because the first pass was blocked on it and nobody holds it:
read access to the judged pair's captures and goldens outside your worktree.
Run `docs/testing/blit_residual_anatomy.py <captures> <goldens>`. Find the
pair under /tmp/pgraph-run and the golden tree; `docs/testing/captures.py`
locates them. No device, no arm, no build -- these captures already exist.

DATE WHAT YOU READ. A capture older than dca3c94b98, or a golden newer than
the run, reads exactly like a live defect and has cost this project a suite
twice. Print the capture set's own date and the ref it was built from before
you use a single number from it.

FALSIFIER: if the differing pixels on the device capture fall INSIDE the 1x1
blit rect, the "not the blit" conclusion is refuted and this issue goes back
to vk/blit.c with a real count. Say which way it came out either way.

DONE WHEN: a comment on #83 giving the device capture's date and ref, the
differing-pixel count and their location relative to the blit rect, and a
recommendation to CLOSE, RETITLE or RE-FILE. If it is the Gouraud quad, say
which open issue already owns that mechanism. No commits to hw/.
