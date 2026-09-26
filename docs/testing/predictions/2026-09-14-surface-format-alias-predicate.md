# Prediction: adding shape.color_format to the reuse predicate

Registered 2026-09-14 on `3cfc2790`, before building or measuring anything.

## The open question this answers

`docs/investigations/surface-format-aliasing.md` establishes the mechanism and
then stops, deliberately:

> Whether adding `shape.color_format` to the predicate is the right fix is a
> separate question: it would evict bindings that today are reused, and the
> cost of that has not been measured. Some aliased pairs may be genuinely
> interchangeable for a given draw.

That is what this measures. It is unblocked -- `gl/surface.c` is this lane's,
and nothing here needs #59's write side or the `psh.c` grant.

## What is already established, and is not being re-derived

- `check_surface_compatibility()` (`gl/surface.c:1743`) compares `color`,
  `fmt.gl_attachment`, `fmt.gl_internal_format` and `pitch`. **`shape.color_format`
  is never compared.**
- The guest->GL map is many-to-one; seven of ten guest colour formats sit in a
  group the predicate cannot tell apart.
- Probe on `iso_surf1` under GL: **110 reuses across a guest format change**,
  of which **66 are O->Z pad-bit swaps** (62x `7->6`, 44x `4->8`, 2x `5->4`,
  2x `2->1`).

Newly counted here before predicting, because a blast radius should be
enumerated rather than assumed: **65 reads of `shape.color_format` across the
tree**, 37 of them in `gl/surface.c` itself. A reused binding hands the
*creating* draw's format to every one of them, so this is not confined to the
pad bit.

## The two candidate fixes

**A (strict).** Add `s1->shape.color_format == s2->shape.color_format` to the
predicate. Catches all 110.

**B (narrow).** Compare only whether the pad bit reads as one, catching the 66
O->Z swaps and leaving the 44 `X8R8G8B8_Z8R8G8B8 -> A8R8G8B8` reuses alone.

**A is the fix and B is the overfit, and that is a prediction, not a
preference.** The guest asked for a different format; 65 sites consult the
field; reusing a binding under a different one is wrong independently of
whether today's code happens to read the difference. B is fitted to what
`dst_alpha_is_one()` currently reads and would silently rot the moment another
consumer starts caring. B is only worth taking if A's cost turns out
prohibitive, and "prohibitive" has to mean a measured regression, not a
count of evictions that merely looks large.

## Predictions, registered before the build

1. **A costs ~110 extra evictions on `iso_surf1`** -- the probe's own number,
   since every reuse it counted becomes an evict-and-reallocate. Each is a
   download, an allocation and an upload.
2. **A moves `Blend_surface::DstAlpha_XA_O1A7RGB8`** (currently +8,192), because
   62 of the 110 are exactly the `X1A7R8G8B8` O->Z swap that capture exercises.
3. **A does NOT take it to zero.** #59's write side has not landed, so the pad
   alpha is still written wrong even once the format is right. Predicting a
   partial improvement, and if it goes to zero that is evidence #59 was not
   load-bearing for this capture after all.
4. **A produces zero WORSE captures.** This is the one that would kill it: a
   capture depending on surface *contents* persisting across a format change
   would regress, and an eviction downloads and reallocates.

## What falsifies A

Any capture worse. Or an eviction count so far above 110 that the predicate is
firing on something the map does not predict -- which, per this
investigation's own lesson, would mean the instrument is wrong rather than the
arithmetic.

## Method

Change the predicate, `ninja qemu-system-i386`, run `iso_surf1` and
`iso_blendall` under the GL renderer, score against `/tmp/goldens/results`.
Count evictions with a temporary probe, then `git checkout --` it and rebuild
before any commit. Baseline first, on the unmodified binary, because a
before/after with only an after is not a measurement.

---

## Outcome, same day. Fix A is correct in principle and NOT landable.

Scored against the prediction above, not rewritten to match it. Baseline and
fix arms both `iso_surf1` under OpenGL, 236 captures each, `QEMU_EXIT=0`.

| | captures | exact | differing |
|---|---:|---:|---:|
| baseline (`3cfc2790`) | 236 | 118 | 9,776,731 |
| fix A | 236 | 118 | **9,791,067** |

**Net +14,336. Worse.** Two captures moved, one each way:

| capture | before | after | |
|---|---:|---:|---|
| `Surface_pitch::Swizzle` | 32,768 | 22,528 | **−10,240** |
| `Blend_surface::DstAlpha_XA_O1A7RGB8` | 311,296 | 335,872 | **+24,576** |

### Prediction 1 — WRONG, and the error is the interesting part

I predicted ~110 extra evictions, taking the number straight from the
investigation's probe. The measured count is **7**: four `7 -> 6`, one `5 -> 4`,
one `4 -> 8`, one `2 -> 1` -- the same four transitions, two orders of
magnitude fewer.

The two numbers measure different things and I conflated them. The
investigation's probe is **passive**: it counts every reuse the predicate
permits, and the offending binding is never corrected, so one aliased binding
is counted again on every subsequent draw. The fix is **active**: the first
rejection evicts and reallocates with the right format, and the same binding
then matches. 110 is how often the wrong format was *used*. 7 is what fixing it
*costs*. A passive probe's count is an upper bound on the active fix's cost,
never an estimate of it.

### Prediction 2 — held, in the wrong direction

`Blend_surface::DstAlpha_XA_O1A7RGB8` moved, as predicted, and it is one of the
`X1A7R8G8B8` O->Z pairs. It moved the wrong way: +24,576.

### Prediction 3 — not reached

Moot: the capture got worse, so whether it would have gone to zero does not
arise.

### Prediction 4 — FALSIFIED, by exactly the failure mode it named

I wrote that a WORSE capture would kill this, and that the mechanism to fear was
"a capture depending on surface *contents* persisting across a format change
would regress, and an eviction downloads and reallocates." That is precisely
what happened, and it is proven rather than inferred:

- The regression is **colour only**. R, G and B each gain exactly 8,192
  differing channels; **alpha is unchanged at 65,536 in both arms.**
- `max|d|` goes from 74 to **255**.
- The 8,192 newly-wrong pixels are a contiguous **128x64 rectangle**,
  y=[156,219] x=[32,159].
- In that rectangle: the golden is `(0,0,0,255)` for all 8,192 pixels, the
  baseline is `(0,0,0,255)` for all 8,192 -- byte-exact -- and the fix arm is
  `(255,255,255,255)` for all 8,192.

A perfect rectangle going uniformly white is not a rendering error. **It is a
surface that came up without its contents.**

### So this is not the pad-bit story

Alpha does not move at all, which rules out the `dst_alpha_is_one()` path that
motivated looking here. #59's write side is irrelevant to this result. The
predicate change is orthogonal to #60's mechanism and lands on a different
defect entirely.

## What this actually found

**A second defect in `gl/surface.c`: evicting a binding does not preserve its
contents.** Today that is invisible, because the aliasing bug means these
bindings are never evicted -- the wrong predicate is masking the broken
eviction. Correcting the predicate unmasks it, and the unmasked defect costs
more than the masked one.

So the order is forced: **eviction must preserve contents before the predicate
can compare `shape.color_format`.** Fixing the predicate alone is a net
regression and must not land.

Fix B (compare only the pad-bit semantics) is not a way around this. It would
reduce 7 rejections to some smaller number and hit the same content loss on
whichever ones remain -- fewer occurrences of the same regression, which is
worse than useless because it would look like a partial success.

## Not taken

The eviction content-loss defect is real, is in this lane's file, and is not
fixed here. It wants its own prediction and its own measurement rather than
being folded into a change whose result is already recorded.

## Reproduce

    bash /tmp/pgraph-run/runx_gl.sh <bin> /tmp/pgraph-run/iso_surf1.iso <tag> surf1

then score `score_<tag>/<tag>` against `/tmp/goldens/results`. The predicate is
`check_surface_compatibility()` at `gl/surface.c:1743`; the change is one
clause, `s1->color && s1->shape.color_format != s2->shape.color_format`, guarded
on `s1->color` because a zeta binding's `shape.color_format` is not meaningful.
The tree is left unmodified: this is a recorded negative, not a staged change.
