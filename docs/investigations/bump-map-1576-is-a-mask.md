# #38's 1,576 is a pixel mask, not a floor and not a count

Measured offline against the goldens and the `z-tip-011-Bump_map` captures
(`88452c539d64`, the post-#10 tip), 41 captures, no device.

## The question, as #38 recorded it

#10's arm predicted its two fixed `Bump_map` captures would land in
[1,576, 3,500] on the reasoning that the residual would be #38's floor --
1,576 being the value `BumpMap_R16B16_L` and `BumpMap_R8B8` both sit at. They
came in at **668 and 711, below it**, and #38 recorded two candidate readings:

1. 1,576 is not one floor but a count of checkerboard-boundary pixels, and
   therefore a property of each image's geometry;
2. the ~900 px difference is a coincidental-agreement term that does not exist.

with the note that they are distinguishable by counting, per capture, the
pixels on a cell boundary in the golden and comparing against each residual.

## Both readings are wrong, and the third is decidable by looking

**Reading 1 is refuted by two independent measurements.**

*The boundary count is forty times the residual and moves the wrong way.* A
golden pixel is on a cell boundary if any 4-neighbour differs from it. Every
`Bump_map` golden holds exactly **four distinct colours**, and the boundary
count runs 58,609-77,712 across the 41 captures -- against residuals of 668
to 111,496. Nine captures sit at exactly 1,576 while their goldens' boundary
counts differ by 21%:

| capture | residual | golden boundary px |
|---|---:|---:|
| `BumpMap_A8` | 1,576 | 75,120 |
| `BumpMap_A8_L` | 1,576 | 75,114 |
| `BumpMap_R16B16_L` | 1,576 | 64,438 |
| `BumpMap_R8B8` | 1,576 | 64,256 |
| `BumpMap_A8Y8` | 1,576 | 62,278 |
| `BumpMap_AY8_L` | 1,576 | 62,197 |
| `BumpMap_AY8` | 1,576 | 62,083 |
| `BumpMap_Y8_L` | 1,576 | 62,084 |
| `BumpMap_Y8` | 1,576 | 61,984 |

If the residual tracked boundary geometry, 61,984 and 75,120 would not both
give exactly 1,576. And every one of the 41 captures draws the *same*
geometry, so a geometric count could not produce 668, 1,576, 2,784, 3,895,
22,374 and 111,496 in the first place.

**1,576 is one pixel SET, not a cardinality.** The nine captures' differing
masks are **byte-identical** -- pairwise XOR zero, same 1,576 coordinates,
same bounding box (rows 76-319, cols 156-493), across seven different texture
formats. So the quantity that was quoted as a floor is a specific defect
appearing wherever the decode lands on the same two-colour pair.

**Reading 2 is not what happened either.** `BumpMap_R16B16`'s 668 px is **not
the 1,576 set minus ~900**: it overlaps that set in **19 pixels of 668**. The
two sets are nearly disjoint. So #10's fix did not partially clear a floor and
did not remove a coincidental-agreement term from it -- it *replaced* the
residual with a different one. 649 of `R16B16`'s 668 differing pixels are
pixels that are correct in the nine, and 1,557 of the nine's 1,576 are correct
in `R16B16`.

## What is true

Every differing pixel lies on a golden colour boundary: **100% for 19 of the
41 captures** and 89-98% for 12 more (the exceptions are `UYVY_L`/`YUY2_L` at
47%, which are a decode defect of their own at 111,496 px). So the class is
real and it is #38's boundary-shift class -- the `DrawCheckerboardUnproject`
texel ties. It is **structural, not one-step**: within the 1,576 mask the
worst channel error is 221, which is the two cell colours swapping, i.e. the
edge placed one texel over.

## The rule this pays for

The lesson is sharper than "do not quote a floor where it was not measured".
1,576 is a **mask**, and two masks of equal cardinality can be disjoint. A
prediction that carries a residual from one capture to another is comparing
masks by their size, which is exactly the move that "a bound is not a value"
already warns about, one level down: here even the *identity* of the quantity
does not transfer, let alone its value.

So a residual quoted across captures should carry the mask, or carry nothing.
`intersection == union` over the capture set is the check, it is two lines,
and on these nine it passes exactly -- which is what makes the 19-pixel
overlap with `R16B16` a finding rather than noise.
