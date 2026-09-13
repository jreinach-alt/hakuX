# `Texture border`'s `stale_px` is dead at the tip, and the defect is not

One page, because it retires an instrument that three arms were judged against
and it does so with its own control.

## The measurement

Ten runs per ref, `Texture border`, scored with `border_swatch_origin.py`
(self-check: 73,728 / 73,728 golden swatch pixels reproduced by the model) and
classified with `border_swatch_classes.py`.

| ref | runs with `stale_px > 0` |
|---|---|
| `7b63484c69` — the floor three arms were judged against, 128 commits back | **6 of 10** |
| a fresh arm A near the tip | 2 of 10 |
| `cb6fc1323f` — the tip | **0 of 10** |

The first row is the control and it is the reason the third row can be
believed: re-scoring the old result through today's pipeline reproduces its
recorded 6-of-10 exactly (146, 181, 2352, 2430, 1847, 5640 px on six runs,
`swatches` 1-3 each). The instrument still sees what it used to see. An
all-zero column with an empty `swatches` list would otherwise be
indistinguishable from a reader that found nothing -- which is the failure
mode this campaign hit twice today in other tools.

## The defect is live at the same tip

On the same refs, Crimson Skies reports `Tr:11829/19167` and `11866/19176` --
**61.7% of texture uploads lose the race**, reproducible to 0.26%, with
`Xd = 0` (impossible row) and `Vr = 0/3040` (vertex site clean).

So the two observables disagree completely, and only one reading survives both:

> **The disc's `stale_px` measures the DETECTOR, not the defect.**

`Texture border`'s eighteen draws sit inside one frame with no flip between
them. A race that a flipping title loses on three fifths of its uploads is
simply not observable there any more.

## What this does to the legs judged against it

**V1 is not merely void, it is dead.** V1 asked for `stale_px == 0` on 10 of
10. At the old floor's 6-of-10 rate a binary with no fix passes that by luck at
0.4^10 = 0.01%. At the fresh arm's 2-of-10 rate, 0.8^10 = 10.7%. **At the tip
the floor is 0 of 10, so a binary with no fix passes it with probability ~1.**
The bar never changed; the disc did, three times, in one direction.

**The mode-1 closure still stands, and not on this floor.** Its pairing was
internally valid -- its own control showed 5 of 10 in the same pair at its own
ref -- and that is what it rests on. What cannot be claimed is any magnitude
derived from the stale floor, because a stale floor credits every later arm
with whatever quietened the observable in between.

**And the replacement already exists.** `Tr` is a rate over ~19,000 uploads in
one 240 s run, reproducible to 0.26%, carrying its own impossible row and its
own negative control. It is not the same kind of number as a count of runs that
did or did not flake, and it is what this issue should have been using.

## Why the observable died

Held as a hypothesis with a named gap, not as a finding. `cdd8dc4c89` (#56's
stale-binding fix) stopped `create_texture` stamping the register cache after a
*failed* bind while clearing `texture_dirty[i]`, so textures previously left
wrongly clean are now re-uploaded. On Crimson that moved uploads +53% and races
+67% absolute -- **fixing the missed-re-upload half of #44 exposes more of the
skew half, because the skew can only lose a race on an upload that actually
happens.** On the disc, whose draws cannot flip, the same change plausibly
removes the one stale binding the suite could see. The direction and magnitudes
fit. Two refs 128 commits apart is not a bisection, and nobody has run one.
