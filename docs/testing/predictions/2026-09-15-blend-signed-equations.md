# Prediction: Blend_tests is the two signed blend equations, aliased to unsigned

Registered 2026-09-15 on `165c239f`, before measuring the offset.

## What is already measured

Baseline over the 105 `Blend_tests` captures in `/tmp/pgraph-run/score_cx_blend`
at `5b707602`, scored against `/tmp/goldens/results/Blend_tests`:

| equation | n | differing channels | share | max abs diff | exact |
|---|---:|---:|---:|---:|---:|
| `SREVSUB` | 15 | 3,540,392 | 46.2% | **255** | 0 |
| `SADD` | 15 | 3,451,745 | 45.1% | **255** | 0 |
| `ADD` | 15 | 312,916 | 4.1% | 2 | 0 |
| `SUB` | 15 | 229,386 | 3.0% | 2 | 1 |
| `MIN` | 15 | 74,250 | 1.0% | 1 | 0 |
| `REVSUB` | 15 | 51,984 | 0.7% | 1 | 0 |
| `MAX` | 15 | **0** | 0.0% | 0 | **15** |

**91.3% of the suite's residual is the two signed equations.** The other five are
at most +/-2, which is a rounding floor, and `MAX` is byte-exact in all fifteen.
Pivoted by blend factor the residual is uniform at 5.9-7.3% across all fifteen
factors, so **the factor does not matter**.

`gl/constants.h:129` says the same thing independently:

    static const GLenum pgraph_blend_equation_gl_map[] = {
        GL_FUNC_SUBTRACT, GL_FUNC_REVERSE_SUBTRACT, GL_FUNC_ADD, GL_MIN, GL_MAX,
        GL_FUNC_REVERSE_SUBTRACT,   /* [5] = FUNC_REVERSE_SUBTRACT_SIGNED */
        GL_FUNC_ADD,                /* [6] = FUNC_ADD_SIGNED */
    };

Entries 5 and 6 are the signed equations aliased to their unsigned
counterparts. The register order in `nv2a_regs.h:1013-1019` matches the table
positionally, and the two aliased entries are exactly the two broken equations.
So the defect is named; what it should do instead is not.

## The claim under test

The signed blend equations are the usual signed-arithmetic pair:

    FUNC_ADD_SIGNED               result = src*sf + dst*df - 0.5
    FUNC_REVERSE_SUBTRACT_SIGNED  result = dst*df - src*sf + 0.5

We emit plain `GL_FUNC_ADD` and `GL_FUNC_REVERSE_SUBTRACT`, so our output is the
same expression without the offset.

## Predictions

**P1.** On `SADD` captures, over pixels where our value is NOT clamped
(`0 < ours < 255`), `golden == clamp(ours - 128)` per channel, for a large
majority of differing pixels.

**P2.** On `SREVSUB` captures, over pixels where our value is not clamped,
`golden == clamp(ours + 128)` per channel.

**P3.** The offset is a CONSTANT, independent of the blend factor. Measured per
factor, the modal offset is the same 128 (or the same 127) in all fifteen.

## Controls

**C1 -- the five unsigned equations.** The model predicts no offset there, and
the baseline already shows max\|d\| <= 2. If a 128 offset shows up on `ADD` or
`MAX` too, the measurement is finding something other than the equation.

**C2 -- clamped pixels are excluded, and that exclusion is stated, not hidden.**
Our output is already clamped by GL, so where `src*sf + dst*df > 255` the
unclamped value is gone and `ours - 128` cannot recover it. Restricting to
unclamped pixels is right for testing the model and is exactly why the FIX
cannot be a post-correction -- the offset has to go inside the blend.

**C3 -- 127 vs 128.** 0.5 in 8-bit is 127.5. The measurement reports the modal
offset rather than assuming; if it is 127 or splits 127/128 by parity that is a
rounding-convention finding, not a failure.

## What kills it

- The difference is not a constant near +/-128: a scale factor, or an offset
  that varies with the blend factor, means the signed equations do something
  other than a half-unit bias and the model is wrong.
- The modal offset differs in sign between `SADD` and `SREVSUB` in the direction
  opposite to the prediction.
- A large majority of differing pixels do NOT fit even after excluding clamped
  ones: then something else is wrong with these two equations as well.

## Why it matters

7,332,519 actionable channels with **zero flat-golden pixels** -- the second
largest actionable pool in `corpus-residual-triage.md` and entirely
discriminating. `gl/*.c` is `[lane.remote]`, so unlike `Line_width` this one is
this lane's to fix if the model holds. But GL has no signed blend equation, so
knowing the exact semantics is the whole of the work before any fix is designed.

---

## Outcome: P1, P2 and P3 all FALSIFIED. The defect is confirmed; the model is not.

**The localisation held and then some.** The defect is exactly the two signed
equations, the code aliases them at `gl/constants.h:129` (and identically at
`vk/constants.h:74`, so it is renderer-independent), and our `SADD` capture is
byte-identical to our `ADD` capture apart from 140 pixels of printed label. All
of that is now in `investigations/blend-tests-is-two-signed-equations.md`.

**The semantics are not.** Measured as `golden == clamp(ours -/+ 128)` over every
differing pixel:

    P1  SADD     195,370 / 3,451,745 =  5.7%
    P2  SREVSUB    6,533 / 3,540,392 =   0.2%

**P3 falsified too**: the modal `golden - ours` per factor is not constant. For
`SADD` it takes the values -221, -192, -147, -74, -25, -7, -1 and +2 across the
fifteen factors. A half-unit bias would have given one value fifteen times.

**The controls behaved.** C1: the five unsigned equations have modal offsets of
+/-1 and `MAX` has no differing pixels, so the measurement was not picking up a
frame-wide artefact. C3: no 127/128 split to adjudicate, because neither fits.

## And the follow-up instrument was invalid, which is also recorded

Recovering `S` and `D` from `ours_ADD = clamp(S+D)` and `ours_SUB = clamp(S-D)`
assumes each pixel is ONE blend. `TestSpot` stacks quads, so each pixel is a
chain, and the `ADD` and `SUB` chains diverge after the first. The recovered
surface was visibly not a function -- `S=64, D=0` giving 4, `S=96, D=64` giving
203 -- and **no candidate form is reported from it**, including the ones that
scored best. A broken instrument cannot support a fit any more than a refutation.

That is the second time in two days a "clean" sampling assumption turned out to
be contaminated (`d913c9dd`'s segment was the first). Both were caught by a
control rather than by the numbers looking wrong, and in this case the numbers
did look wrong, which was luck.

## What this leaves

A named defect with 7.3M actionable channels and an unknown replacement value.
The next instrument is the single-blend swatch regions of `DrawColorStack`,
where `S` and `D` are known by construction, and it wants its own prediction
with candidate forms named in advance.
