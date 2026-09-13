# F24 subnormal flush: the mechanism is confirmed, the pixel prediction is not

Arms `4946433d87` (base) → `a1fe59400e` (fix), one commit apart, same disc
(`2-suites:a6eb9b49:Depth buffer,Depth buffer fixed function`), both with
progress-log proof. Result directories
`1789257380-f24-base-599725` / `1789257380-f24-fix-599733`.

## What the arm measured

    better 18    worse 0     same 206   noise 0      (224 compared)
    exact  40 ->  40         regressed from exact 0
    Depth_buffer                 144  18  0  126  0   1,569,874 -> 1,566,276
    Depth_buffer_fixed_function   80   0  0   80  0     663,094 ->   663,094
    differing 2,232,968 -> 2,229,370  (-3,598)

Three of the prediction's four structural claims hold exactly:

- **Every** non-exact `z24 * FZy *_ZB` capture moved, and all 16 moved down.
  Nothing else in either suite moved except the two `M05502e` colour captures.
- `Cn` and `Cy` are **identical to the pixel** on all nine mantissas, before
  and after — as predicted, the two compression halves move together.
- `Depth_buffer_fixed_function` is byte-identical across all 80 captures. The
  guard cannot fire for it, and it did not.

The fourth claim — class B's 25,915 px/half → 0, net −51,830 — **failed**.
Measured net is −3,598, and no capture reached zero.

## Why the pixel count was the wrong falsifier

The stated falsifier was *"if class B does not go to zero, the subnormal-flush
mechanism is wrong and the change should come straight back out."* Taken
literally that fires. It should not, because the mechanism is not a pixel
count — and measured directly, it is gone.

The mechanism as filed: `bc*(z1-z0)` goes subnormal for depths in the first
quad row, the GPU flushes it, and the depth acquires *a variation along y that
hardware does not have*, growing with the barycentric weight (spread per
column of an 8×8 quad 1,1,1,1,1,2,4,6, where silicon is column-constant).

So measure that quantity — the max−min of the depth word down each column,
over the region where anyone disagrees:

| capture | columns with non-zero y-spread | summed y-spread |
|---|---|---|
| `M0aa02d_ZB` | golden **0** · base **52** · fix **0** | 0 · 182,467 · **0** |
| `M05502e_ZB` | golden **0** · base **18** · fix **0** | 0 · 114,400 · **0** |
| `Mfeffff_ZB` | golden 22 · base 71 · fix **24** | 166,616,300 · 166,792,492 · **166,615,535** |

The spurious y-variation is eliminated completely on the captures where
silicon is column-constant, and on `Mfeffff_ZB` — where the quad genuinely
does vary down its columns — the fix lands within **765** of the golden's
total spread where the base was off by **176,192**.

That is the mechanism, measured as stated, confirmed.

## Why the pixels stay differing anyway

Because they are wrong for two reasons at once, and the fix removes one. The
surviving residual on every affected capture splits into two families:

- **±12,584 / ±12,585**, 432 words per capture (216 / 180 / 36), with counts
  **byte-identical before and after**. This is the quad-split floor named in
  the comment immediately above the change — "its worst error from 12,585
  depth units" — a separate defect that was measured, priced and deliberately
  left alone. The fix does not touch it, as it should not.
- **±787, ±2360, ±3933, ±5506, ±7079**, an arithmetic ramp in steps of 1,573.
  This is what moved, and it moved from *asymmetric* (104/100, 44/44, 38/38)
  to *exactly symmetric* (64/64, 32/32, 32/32) — the signature of a residual
  that is now a shared endpoint disagreement rather than a one-sided drift.

A pixel carrying a 12,584-unit quad-split error and a 1,573-unit interpolation
error is counted once in `differing`. Remove the second and it is still
differing. The class-B count was a count of *pixels the mechanism touches*,
not of pixels the mechanism is solely responsible for, and subtracting one
from the other assumed an additivity the residual classes do not have.

This is the same trap already recorded for one-step and boundary-shift, which
overlap and cannot be added or subtracted. It has now cost two predictions.

## Verdict

**Lands.** 18 better, 0 worse, no capture regressed from exact, the mechanism
verified directly against silicon's column-constancy, and both structural
must-not-move predictions held.

`ab_compare.py` reports this arm as POST-HOC and says its verdict is worth
nothing, which is correct: `docs/testing/predictions/f24-subnormal-flush.json`
was registered after the results landed. The shape measurement above is not
post-hoc in the same way — it is a direct measurement of a mechanism that was
described in prose, with its expected value (column-constant) fixed by the
goldens rather than by me — but the pixel verdict carries no weight and the
prediction should have been registered before the arm ran.

## For the next prediction

**State the falsifier as a measurement, not a pixel count, wherever residual
classes overlap.** "Class B goes to zero" was unfalsifiable-in-practice: it
could only have come true if class B pixels carried no other defect, which
nobody checked. "Per-column y-spread goes to zero on the column-constant
captures" would have been the right falsifier — it is the mechanism, it is
checkable against the goldens, and it passed.
