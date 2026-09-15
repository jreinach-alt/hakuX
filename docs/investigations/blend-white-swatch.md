# What is left in `Blend tests` on Adreno is one swatch: white

Measured 2026-09-12 on the #19 sweep's own `Blend tests` arm, APK
`f9b5a5df2776`, after the surface-as-texture decode fix landed.

## The number, and the prediction it was checked against

`blend_model.py` reproduces silicon exactly on the 75 unsigned `#spot_`
captures, so it is an oracle. Before the decode fix our Adreno captures matched
it on 10,026 of 18,000 sampled pixels; the remote lane predicted **16,379**
afterwards (10,026 plus the 6,353 the R/B exchange explained).

Measured: **16,409 of 18,000**. Within 30 of the prediction, and the exchange
now explains **zero** of the remaining misses — the channel asymmetry is gone
(R 1,529 / G 1,529 / B 1,197, against 7,580 / 1,559 / 7,912 before). The fix
did what it claimed.

## The residue is entirely one swatch

Each `#spot_` cell draws four `DrawColorStack` swatches. Grouping the 1,591
remaining misses by swatch:

| swatch | source colour | misses / sampled |
|---|---|---:|
| 0 | `(0, 221, 0, 221)` | **0** / 4,500 |
| 1 | `(0, 0, 221, 221)` | **0** / 4,500 |
| 2 | `(221, 0, 0, 221)` | **0** / 4,500 |
| **3** | **`(255, 255, 255, 221)`** | **1,591** / 4,500 |

Every single one. Three swatches at 221 in one channel are exact everywhere,
and the fourth — the only one at **full range, 255, in all three channels** —
carries the whole residual.

Everything else about the distribution is flat, which is what makes the swatch
the answer rather than one contributor among several:

* **Equations**: MAX 450, ADD 375, SUB 355, MIN 225, REVSUB 186 — in
  proportion to how often each is sampled. `MIN` and `MAX` do not consult the
  blend factors at all and still miss, at the highest rate.
* **Source factors**: 118 for eight of the fifteen, 95 at the low end. Flat.
* **Destination factors**: 109 at the top, 95 at the bottom, over fifteen. Flat.
* **Direction**: one-sided low. R-low 1,355 against R-high 174; B-low 1,133
  against B-high 64.
* **Size**: not one miss is within one or two steps. The smallest is 6, the
  largest 221, with spikes of 357 samples at Δ221 and 272 at Δ177.

So this is not the blend unit, not a factor mapping, and not a rounding mode:
it is what happens to a **full-range source colour** somewhere in the
blend-store-blit chain, and nothing else in the suite reaches it.

## Why this is worth someone's time

It is 8.8% of the sampled pixels in the suite that carries the largest
non-precision population in the corpus, it is localised to one input value, and
it is host-specific in shape: the desktop lane's remaining 1,375 misses are all
**exactly one step**, where not one of ours is within two. Whatever this is, it
happens on the hardware that ships and not on lavapipe.

It is also adjacent to something already known. The remote lane's #43 work
found that on a zero destination "every source gives 0 including white", and
their signed-blend rule reads the source as a signed byte — under which
`signed(255) = -1`. Full-range white is the value where a signed read and an
unsigned read diverge most, and it is exactly the swatch that fails here in the
*unsigned* equations. Whether those are the same mechanism is not established
and should not be assumed; it is the first thing to test.

## What has been ruled out, with numbers

| candidate | why not |
|---|---|
| channel order | the exchange explains 0 of 1,591 now; it explained 6,353 of 7,974 before the fix |
| rounding mode | round/round fits us best, 16,409, as it fits silicon; floor variants are worse (14,282 / 10,267 / 9,060) |
| precision floor | zero misses within one or two steps |
| the blend equation | flat across all five, and `MIN`/`MAX` ignore the factors |
| a factor mapping | flat across all fifteen source and fifteen destination factors |

`docs/testing/blend_channel_order.py` produces the first three rows; the swatch
grouping is four lines against `blend_model.sample_points()`.
