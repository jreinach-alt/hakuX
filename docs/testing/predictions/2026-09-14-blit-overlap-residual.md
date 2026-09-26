# Prediction: the Image_blit Overlap_* residual is not a blit defect

Registered 2026-09-14, before looking for a cause, on `b9d845d3`.

## What is measured

After the #38 divide fix and the #84 guard, Image_blit scores 16,380 differing
channels over 41 captures, max|d| = 1 everywhere. 14,720 of those are eight
`Overlap_*` captures at 1,840 each (one at 1,839).

The eight differ in **the same 1,701 pixels**. Seven masks are bit-identical to
each other; `Overlap_BL_Inside` is missing exactly one pixel. The parameter the
eight tests exist to vary -- which corner overlaps (TL/TR/BL/BR) and whether the
overlap is inside or outside -- changes the error by at most one pixel.

Per-channel: R=375, G=822, B=643, **A=0**. Alpha is byte-exact in all eight.
Signs are near-balanced: +1 = 951, -1 = 889. Bounding box y=[64,243],
x=[64,323].

## The prediction

**H-src.** The error is upstream of the blit. The blit faithfully copies a
source that is already wrong by +/-1, so the copy's parameters cannot move it.
If so, the same pixels differ in a capture that performs no blit at all, and
this residual belongs to whichever path produces the source surface -- not to
`gl/blit.c`.

**H-blit.** The error is in the copy itself and the eight masks coincide for
some other reason.

## Discriminators, fixed in advance

1. If H-src: the differing region lies in the SOURCE rect the test draws, and a
   non-blit capture in the corpus that draws the same content differs in the
   same pixels. If H-blit: the region is the DESTINATION rect and no non-blit
   capture shows it.
2. If H-src: `BlitRenderBlit`'s 1,655 differing pixels are a subset of, or
   overlap heavily with, the same mask. If H-blit: they need not.
3. If H-src: alpha being exact is explained by the source's alpha being a
   constant while RGB is computed. If H-blit: a copy defect has no reason to
   spare exactly one channel in all eight.
4. Unequal per-channel counts (375/822/643) are evidence against any uniform
   scale or shift in the copy, which would hit the three colour channels at
   comparable rates.

## What would falsify H-src

A non-blit capture drawing the same source content that is byte-exact, with
the Overlap_* region provably the destination rather than the source.

## Not yet known

Whether the source is procedurally rendered by the 3D pipeline or uploaded as
fixed data. That decides whether this is a raster/shader defect or a texture
upload one, and it is the next thing to establish -- not assumed here.

---

## Outcome, same day

**H-src confirmed on every discriminator.** Recorded against the prediction
above, not rewritten to match it.

1. **Held, and more strongly than predicted.** The differing pixels are not
   merely outside the destination rect -- the blit these tests issue is
   **1 pixel wide by 1 pixel high**, and that pixel is byte-exact in all eight.
   Every differing pixel lies inside one of the two Gouraud quads the test
   draws; ELSEWHERE = 0.
2. **Held.** `BlitRenderBlit`'s 1,524 pixels are a *disjoint* region carrying
   the same channel signature. I predicted "subset of, or overlaps heavily
   with"; the intersection is in fact zero. The prediction was right about the
   cause and wrong about the geometry -- the signature travels, the location
   does not, because it is a different quad.
3. **Held.** Alpha comes from a `SRC_ZERO` final combiner -- a constant -- and
   is exact in all eight. Only interpolated channels move.
4. **Held.** The per-channel counts are not merely unequal, they are one-sided
   with zero exceptions: G strictly low (818/818), B strictly high (641/641),
   R 310 high to 0 low on the affected triangle.

## What the prediction did not anticipate

Two separable defects, not one:

- **1,630 px** confined to the *lower* triangle of the quad (20.1% there
  against 0.8% above the diagonal), interior rather than edge.
- **64 px** on the exact column x = w/2, R only, all ours-low -- a true
  rounding tie at 127.5 where hardware gives 128 and we give 127.

## A correction to my own earlier characterisation

I had recorded this residual as "+1 = 951, -1 = 888, roughly symmetric -- a
rounding-mode shape, a different class from #38's scale error". The aggregate
is right and the reading is wrong: it is a strictly-low green and a
strictly-high blue nearly cancelling. By my own #38 test -- a scale error has a
sign, a mode difference does not -- this is a scale error after all.

Full write-up: `docs/investigations/image-blit-residual-is-not-the-blit.md`.
