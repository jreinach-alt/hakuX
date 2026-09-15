# Blend_tests is two aliased equations, and both backends have it

Measured on `5b707602`, OpenGL, the 105 `#spot_` captures in
`/tmp/pgraph-run/score_cx_blend`, scored against `/tmp/goldens/results/Blend_tests`.

`corpus-residual-triage.md` ranks `Blend_tests` second by actionable channels --
7,332,519 of 7,660,673, with **zero flat-golden pixels**, so every differing
pixel can discriminate between two wrong models.

## The residual is one defect in two equations

| equation | n | differing channels | share | max abs diff | exact captures |
|---|---:|---:|---:|---:|---:|
| `SREVSUB` | 15 | 3,540,392 | 46.2% | **255** | 0 |
| `SADD` | 15 | 3,451,745 | 45.1% | **255** | 0 |
| `ADD` | 15 | 312,916 | 4.1% | 2 | 0 |
| `SUB` | 15 | 229,386 | 3.0% | 2 | 1 |
| `MIN` | 15 | 74,250 | 1.0% | 1 | 0 |
| `REVSUB` | 15 | 51,984 | 0.7% | 1 | 0 |
| `MAX` | 15 | **0** | 0.0% | 0 | **15** |

**91.3% of the suite is `SADD` and `SREVSUB`.** The other five are at most +/-2,
which is a rounding floor, and `MAX` is byte-exact in all fifteen captures.

Pivoted the other way, by blend factor, the residual is flat: 5.9% to 7.3% across
all fifteen factors, every one of them with max abs diff 255 and exactly one
exact capture (its `MAX`). **The factor does not matter at all.**

## The blend FACTORS are provably correct, so this is only the equation

`MAX` renders `max(S, D)` byte-exactly in all fifteen captures and `MIN` is
within one step. Those two bracket both operands, so the products `S = src*sf`
and `D = dst*df` that we compute are right to within a step at every pixel, for
every one of the fifteen factors. Whatever is wrong with `SADD` and `SREVSUB` is
**not** an upstream error in the factor map feeding them.

## The code says the same thing, in three files

`nv2a_regs.h:1013-1019` defines seven equation values. `pgraph.c:2668-2670` maps
the two signed ones to indices 5 and 6. And `gl/constants.h:129`:

    static const GLenum pgraph_blend_equation_gl_map[] = {
        GL_FUNC_SUBTRACT, GL_FUNC_REVERSE_SUBTRACT, GL_FUNC_ADD, GL_MIN, GL_MAX,
        GL_FUNC_REVERSE_SUBTRACT,   /* [5] = FUNC_REVERSE_SUBTRACT_SIGNED */
        GL_FUNC_ADD,                /* [6] = FUNC_ADD_SIGNED */
    };

**Indices 5 and 6 are the signed equations aliased to their unsigned
counterparts**, and those are exactly the two equations carrying the residual.
The measurement and the source were reached independently and agree.

### Control: the alias is demonstrably what is rendering

Our `#spot_1_SADD` capture and our `#spot_1_ADD` capture differ in **140 pixels,
all of them in rows 25-40, columns 100-136** -- the printed test-name label.
Every other pixel is byte-identical. Reproduced on `srcA` (140 pixels, columns
130-166). We really are drawing `SADD` as `ADD`.

## Both backends have it, identically

`vk/constants.h:74` is the same table with the same two aliases, consumed at
`vk/draw.c:1526`. **This is renderer-independent.** It is not a GL-vs-Vulkan
discriminator, the Vulkan lane carries the identical defect, and whatever the fix
turns out to be has to land in both.

## What the signed equations actually compute is NOT established

### The obvious model is falsified

`predictions/2026-09-15-blend-signed-equations.md` registered the usual
signed-arithmetic pair -- `src*sf + dst*df - 0.5` and `dst*df - src*sf + 0.5` --
before measuring. Measured directly as `golden == clamp(ours -/+ 128)` over every
differing pixel:

    SADD     195,370 / 3,451,745 = 5.7%
    SREVSUB    6,533 / 3,540,392 =  0.2%

and the modal `golden - ours` per factor ranges over -221, -192, -147, -74, -25,
-7, -1, +2 for `SADD` rather than sitting at a constant. **P1, P2 and P3 are all
falsified.** The signed equations are not a half-unit bias on the same expression.

The controls behaved: the five unsigned equations have modal offsets of +/-1, and
`MAX` has no differing pixels at all, so the measurement was not finding a
frame-wide artefact.

### And the instrument that would have named the function is invalid

The natural next step was to recover the operands from our own captures --
`ours_ADD = clamp(S + D)` and `ours_SUB = clamp(S - D)` give `S` and `D` where
neither clamps -- and then tabulate the golden `SADD` against them.

**That instrument is wrong and its numbers are discarded.** `TestSpot` draws
*stacked* quads: `DrawAlphaStack` and `DrawColorStack` lay several quads over
each other, so a pixel is the result of a CHAIN of blends, not one. `ADD` and
`SUB` chains diverge after the first quad, so `(ADD +/- SUB)/2` recovers nothing.

It announced itself: the recovered surface had `S=64, D=0` mapping to 4 and
`S=96, D=64` mapping to 203, which is not a function of anything. No candidate
form is reported from it, including the ones that scored best, because a broken
instrument cannot support a fit any more than it can support a refutation.

## Next instrument, with its discriminator fixed in advance

The test does contain single-blend regions: `DrawColorStack` draws
non-overlapping swatches over a known `kColorSwatchBackground` (`0x33333333`),
each one quad deep with a known source colour. Those are where `S` and `D` are
known by construction rather than recovered, and where the golden names
`f(S, D)` directly. That measurement needs the swatch rectangles located in the
composited frame first -- they are rendered to a 64x256 texture and composited
at `x=16` and `x=width-80` -- and it should be registered as a prediction with
candidate forms named before it runs.

## Ownership, stated rather than assumed

`territory.toml` grants this lane `hw/xbox/nv2a/pgraph/gl/*.c`. **The table is in
`gl/constants.h`, which is a header and is not matched by `gl/*.c`.** `vk/*` and
`pgraph.c` are `[free]`. So even the one-line change, once the right value is
known, is not cleanly inside this lane's grant, and the Vulkan half certainly is
not.

Flagged rather than assumed. Nothing is edited here.
