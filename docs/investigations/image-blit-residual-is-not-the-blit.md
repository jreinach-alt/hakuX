# The Image_blit residual is not blit code

Measured on `b9d845d3`, OpenGL, against `/tmp/goldens/results/Image_blit`.

After #38's divide fix and #84's format guard, Image_blit scores **16,380
differing channels over 41 captures, max|d| = 1 everywhere**. This is where the
rest of it lives, and it is not in `gl/blit.c`.

## The blit is byte-exact

`TestOverlapBarelyInclusive` (nxdk_pgraph_tests `src/tests/image_blit_tests.cpp:654`)
issues a blit of **width 1, height 1**. One pixel. It cannot account for 1,700
differing pixels, and it does not:

| test | blit dest | ours | golden | delta |
|---|---|---|---|---|
| Overlap_TL_Inside  | (64,64)   | 255,255,0,255 | 255,255,0,255 | 0,0,0,0 |
| Overlap_TL_Outside | (63,64)   | 255,255,0,255 | 255,255,0,255 | 0,0,0,0 |
| Overlap_TR_Inside  | (191,64)  | 255,255,0,255 | 255,255,0,255 | 0,0,0,0 |
| Overlap_TR_Outside | (192,64)  | 255,255,0,255 | 255,255,0,255 | 0,0,0,0 |
| Overlap_BL_Inside  | (64,191)  | 255,255,0,255 | 255,255,0,255 | 0,0,0,0 |
| Overlap_BL_Outside | (63,191)  | 255,255,0,255 | 255,255,0,255 | 0,0,0,0 |
| Overlap_BR_Inside  | (191,191) | 255,255,0,255 | 255,255,0,255 | 0,0,0,0 |
| Overlap_BR_Outside | (192,191) | 255,255,0,255 | 255,255,0,255 | 0,0,0,0 |

**All eight destination pixels are byte-exact.** The thing these eight tests
exist to test -- whether a 1x1 blit landing barely inside or barely outside a
render-to-surface region is placed correctly -- passes.

The first sign was that the eight differ in the *same* 1,701 pixels. Seven masks
are bit-identical; `Overlap_BL_Inside` is missing exactly one. The parameter the
suite varies -- corner, and inside vs outside -- moves the error by at most one
pixel. A copy defect cannot be independent of where it copies to.

## Every differing pixel is inside a Gouraud quad

The test draws a 128x128 Gouraud quad into a render-to-surface at (64,64) with
corner diffuse colours R(1,0,0), G(0,1,0), B(0,0,1) and (0.75,0.65,0.55), then a
second 4x4 quad at (320,240) to force the 3D unit to wait on the 2D blit.

Decomposing the mask against those two footprints:

    total = 1701    big quad (64,64,128x128) = 1695
                    small quad (320,240)     =    6
                    ELSEWHERE                =    0

Nothing differs outside the drawn quads. The flat `PrepareDraw(0xFF111111)`
background is exact everywhere, which is the control: a constant colour is
right, an interpolated one is not.

`DirtyOverlappedDestSurf`'s 6 differing pixels are **entirely** the small quad
(6 of 6, inside the same mask). `BlitRenderBlit`'s 1,524 are a *disjoint* region
-- y=[213,339] x=[256,380], zero intersection -- carrying the *same* channel
signature (alpha exact, G > B > R). Another quad, elsewhere.

So all 16,380 channels are accounted for by drawn geometry, and none by the copy.

## Two distinct defects, both in interpolation

### 1. The second triangle of the quad (1,630 px)

Split by the main diagonal the quad is triangulated along (TL->BR):

    X > Y  (upper triangle)     64 / 8128   =  0.8%   errors
    X < Y  (lower triangle)   1630 / 8128   = 20.1%   errors

The anti-diagonal shows no separation (11.6% vs 9.1%), so hardware and we
triangulate the *same* way. One triangle is essentially exact and the other is
20% wrong.

Per channel on the bad triangle, **with zero exceptions**:

| channel | n | ours low | ours high |
|---|---|---|---|
| R | 310 | 0 | 310 |
| G | 818 | 818 | 0 |
| B | 641 | 0 | 641 |
| A | 0 | - | - |

Alpha is byte-exact in all eight captures; the final combiner sets it from
`SRC_ZERO`, a constant. Only the interpolated channels move.

Errors are **interior, not edges**: 1,628 interior against 67 on the 1px border,
and 67/508 is *below* the 10.3% base rate. This is not a coverage or fill rule.

**This corrects an earlier characterisation of mine.** I previously recorded the
residual as "+1 = 951, -1 = 888, roughly symmetric -- a rounding-mode shape". That
aggregate is real but misleading: it is a strictly-low green and a strictly-high
blue very nearly cancelling. Per channel the error is one-sided with no
exceptions, which by the same test I used for #38 -- a scale error has a sign, a
mode difference does not -- makes this a **scale or basis difference in the
second triangle's interpolation**, not a rounding mode.

### 2. A rounding tie at the exact midpoint (64 px)

The 64 errors in the *clean* triangle are not scattered. They are a single
contiguous column at **x = 64 exactly, y = 0..63** -- the quad's vertical
centreline, top half -- in the **R channel only**, every one ours-low by 1.

R ramps 255 at x=0 (the red corner) to 0 at x=128 (the green corner), so at
x = w/2 the exact value is **127.5**, a true tie.

    ours   = 127   (all 64 pixels, all eight captures)
    golden = 128   (all 64 pixels, all eight captures)

Hardware rounds the tie **up, away from zero**. We round it down. Golden is even
and ours is odd at every one of these pixels, so neither side is round-half-even
-- this is half-up versus half-down.

**This settles a question `d843e418` had to leave open.** The 2^24 exhaustive
that fixed the BLEND_AND divide found *zero* exact half-ties in its domain, so I
recorded there that "round to nearest is all that is established, and half-up is
what is implemented". An independent test now exercises a real tie and hardware
rounds half-up. The choice made in `d843e418` matches silicon; it was not merely
unfalsified.

## What this means for ownership

The blit is done. #38's GL half closed 379,795 -> 16,380 channels and every
BLENDAND capture to byte-exact; #84 closed the narrow-format overrun. What is
left in the Image_blit score belongs to **vertex-colour interpolation**, which
lives in the shader/draw path, not `gl/blit.c`.

Not fixed here, and deliberately: `glsl/vsh.c`'s `roundScreenCoords` is
rasteriser-wide and needs the owner's approval before it changes, and `glsl/psh.c`
is not this lane's to edit. Handing both findings over rather than reaching for
them.

## Reproduce

    python3 docs/testing/blit_residual_anatomy.py [captures_dir] [goldens_dir]

Defaults to `/tmp/pgraph-run/score_blit84/blit84` and
`/tmp/goldens/results/Image_blit`. It prints every number in this document --
the per-capture scores, the eight blitted pixels, the ELSEWHERE=0
decomposition, the diagonal split, the per-channel one-sidedness, and the
midpoint tie -- so the conclusion rests on measurements that can be re-run
rather than on a reading of the code.
