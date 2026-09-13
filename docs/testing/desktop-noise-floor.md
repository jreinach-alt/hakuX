# The desktop lane's run-to-run noise floor is one capture wide

Measured 2026-09-13: **five runs of one unchanged binary** over the 236
captures of `iso_surf1` under `renderer = 'OPENGL'`.

**235 of 236 captures are bit-reproducible across all five runs.** Exactly
one is not:

| capture | run 1 | 2 | 3 | 4 | 5 | band |
|---|---:|---:|---:|---:|---:|---|
| `Surface_pitch::Swizzle` | 15,360 | 14,848 | 15,360 | 15,360 | 15,360 | **14,848–15,360, spread 512** |

Every other capture hashes identically run to run. So a delta of ±512 on
`Surface_pitch::Swizzle` alone is a coin flip and must be classed NOISE, not
better or worse; a delta anywhere else, of any size, is signal.

## Why this needed measuring

The capture moved in four consecutive arms on 2026-09-13 — the #70 clip
fix, two of #60's arms, and the `noperspective` probe — always by exactly
512 and always between those two values. Four unrelated changes producing
the same ±512 on one capture is not four findings, and taking it at face
value cost three misreported results before the re-run of one binary
settled it. `ab_compare.py`'s own docstring had warned about exactly this
("a delta inside the run-to-run band is a coin flip"), from the device
lane; it was not known that the desktop lane had a band at all, because
until #66 the OpenGL disc had never run to completion for anyone to
re-run.

## What it corrects

* **#70**: reported 9 captures better. It is **8 better**;
  `Surface_pitch::Swizzle` 15,360 → 14,848 was noise. The registered legs
  did not name it and are unaffected.
* **#72** (`noperspective` probe): reported 6 better and 1 worse, with one
  registered leg failed. It is **6 better, 0 worse**, and the leg holds.
* **#60**: reported 4 captures regressed. It is **3**. The two control arms
  that refuse the `A8R8G8B8` surface-to-texture row landed
  `Surface_pitch::Swizzle` at 12,224 and 10,176 — both far outside the
  band, so those findings and #71 stand, but their deltas carry a ±512
  uncertainty from the baseline.
* **The GL blit range download**: reported 8 better and 1 worse. It is
  **8 better, 0 worse**.

## How to use it

Class a move on `Surface_pitch::Swizzle` of |512| or less as NOISE. Do not
class a move on any other capture as noise without re-measuring: the band
is per capture, and on this lane every other capture's band is zero.

The right fix is to find out why that one capture is unstable, which is
worth doing — a non-deterministic capture is a defect in its own right, and
this one is in `Surface_pitch`, a suite of one. Until then this file is the
band.
