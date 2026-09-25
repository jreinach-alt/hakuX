# lane cloud-286 -- #286 3D primitive smoothing residual

Work in progress.

## Falsifier, stated before it was run (committed ahead of the run)

Claim under test: the part of the 605,744 structural px that lies outside
silicon's own smoothed-vs-unsmoothed footprint is not smoothing.

The console set (`hardware/runs/2026-09-19-calib/full/out/run1`) is an
independent silicon run of all 160 captures. For each smoothed capture X and
its twin P, take `struct(K_X, K_P)`, the pixels where the console's smoothing
changed its own image. Intersect that with the pixels where ours is wrong
(`struct(O_X, G_X)`) that the golden-derived footprint put OUTSIDE smoothing
(classes shared / aa-path / other in `decompose286.py`).

- **A hit** is when that intersection is large: more than 1% of those
  419,000-odd px (over ~4,200), or anywhere near 175,704. It would mean the
  console's own smoothing moves pixels the golden-derived footprint called
  "not smoothing", so the footprint is too narrow and the ceiling is
  understated.
- **No hit** is when the intersection is near zero (it can only come from the
  4,546 px where console and golden disagree on the smoothed captures). Then
  the residual outside the footprint is out of any smoothing emulation's
  reach.
