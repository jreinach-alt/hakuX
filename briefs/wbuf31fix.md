# #31: anchor W-buffer slope offsets the way silicon does, now that silicon has answered

Lane: wbuf31fix            Issue: #31
Base: origin/master (fetch first).
Files: hw/xbox/nv2a/pgraph/glsl/psh.c, docs/testing/wbuf_anchor_recover.py,
       docs/testing/predictions/wbuf31fix-*.json, docs/lanes/wbuf31fix/**
Needs device: yes (the arm, queued by committing the prediction). Needs NDK: no
(the arms job builds both apks on the host).

## What silicon settled (2026-09-25, lane.xbox, the project console)

The measurements were taken on GPU rev 163 / MCP rev 212
(`docs/testing/xbox-console-provenance.md`). They are not folded yet, so read
them off their PR branches:

- PR #218, `origin/lane/xbox-wbuf31`:
  `docs/testing/xbox-wbuf31-clipf35-2026-09-25.md`. clip_top=35.
- PR #221, `origin/lane/xbox-wbuf31-clip4`:
  `docs/testing/xbox-wbuf31-clipf04-2026-09-25.md`, `docs/lanes/xbox/score_clipf04.py`.
  clip_top=4.
- #31 comments 5827960301 and 5828061497.

What they establish:

- **ClipF's SECOND triangle anchors on the absolute 4-pixel grid at phase 2,
  `4*floor(ct/4)+2`**: 34.000 at clip_top 35 and 6.001 at clip_top 4. This is
  TriH's rule. clip_top 4 refutes all 47 coarse-grid rules (8/16/32), and at 35,
  ct+2, quad-snap+2 and the phase variants are refuted.
- **ClipF's FIRST triangle anchors at 32 / 34 / 6 at clip_top 32 / 35 / 4.**
  The 4-grid fits 35 and 4. The shipped quad snap fits 32 and 35. **Neither
  fits all three.** Do NOT write "t0 keeps the quad snap". The requirement is
  that t0 must reproduce 32/34/6.
- Validity: V0 passed; every existing-test capture in both runs is
  bit-identical to its golden; the new variants' geometry is exact; the plane
  controls show 0 mismatches.
- The raw silicon captures are on this host:
  `/home/justin/hakux-work/hardware/runs/2026-09-25-wbuf31-clipf{35,04}/console-run/console/W_buffering/`.
  They hold the -035 and -004 variant pairs (ZS1 plus its ZS0 sibling), next
  to bit-identical repeats of the existing clip_tops.

## What the corpus already settled (docs/testing/wbuf_anchor_recover.py)

- All 24 TriH triangles anchor on the 4-grid at phase 2.
- Every triangle the window clip CUT anchors at the first covered pixel
  snapped to the 2x2 quad, which is what the shipped code does: Wall, Roof,
  Floor, all three ClipW, and ClipF's first triangle at the existing clip_tops.
  That is eleven of eleven.
- TriV fits NEITHER. It is a third mechanism with no candidate rule (#31's
  105,600 px). It is out of scope, and it must not get worse.

## The job: find the SELECTOR, prove it offline, then implement

The two rules are known. What is unknown is what decides which rule a
triangle gets. lane.xbox's hypothesis, which is untested: at clip_top 4 the
clip may not cut t0 at all, and an uncut triangle anchors on the 4-grid
(TriH). The candidate selectors to frame with `wbuf_anchor_recover.py --pairs`
are: the plane, whether the clip cut it, the first covered pixel, and the top
vertex.

1. **Offline first, before touching psh.c.** Your selector must reproduce every
   recovered anchor, inside hardware's own interval:
   - the 24 TriH triangles;
   - the 11 cut triangles;
   - ClipF t1 at 34 and 6;
   - ClipF t0 at 32, 34 and 6;

   These come from the goldens plus the two silicon runs above. If
   `wbuf_anchor_recover.py` cannot read the silicon runs' layout, extend it.
   It is in your row. A selector that misses one observation is wrong, and it
   is not "mostly right". Write the fit table into your NOTES.
2. **Register the arm BEFORE any device run**
   (`docs/testing/ab_compare.py --register`, file
   `docs/testing/predictions/wbuf31fix-<name>.json`). Commit and push it. That
   is what queues it.
   - **must_move:** the W_buffering captures carrying #31's residual (566,549 px
     at the last count), each with the direction and size your offline model
     predicts.
   - **must_not_move:** every other capture psh.c can reach. Use
     `python3 docs/testing/nv2a_index.py blast hw/xbox/nv2a/pgraph/glsl/psh.c`
     for the list. It includes the TriV captures and the three existing ClipF
     clip_tops.
   - Name, for each must_not_move leg, the patch change that would move it.
     If none exists, the leg discharges nothing, so drop it.
3. **Implement in `wbufSlopeStep`** (glsl/psh.c) exactly the selector the fit
   table proved, with nothing tuned to the arm.

Optional, and worth it if cheap: build the -035 and -004 variant disc from
lane.xbox's patches (`docs/testing/wbuf31_clipf_phase.patch` on master, and
`docs/lanes/xbox/wbuf31_clipf04.patch` on #221's branch). Run it through the
desktop channel or a handheld (`request.sh`, `base_iso`), and score the
emulator's variant captures against the silicon ones on this host. The
published goldens do not contain clip_top 35 or 4, so this is the only
emulator-side check of the two new observations.

## Done when

The fit table is in NOTES, the arm is registered and has come back from the
arms job (a `[job.arms]` verdict on your PR), the PR body carries the lane
template with its `Files:` line, preflight passes, and the PR is marked
ready. If the offline fit fails for every selector you can frame, stop, and
report that as the result. It is exactly as useful: it means there is a
fourth input.
