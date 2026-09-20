# `Bump map`'s Y16 class: we render Y16 as Y8, and hardware does not

#10's remaining `Bump map` classes are YUV (111,496 px each, set aside by
[`bump-yuv-source.md`](bump-yuv-source.md)) and Y16 -- `BumpMap_Y16` and
`_Y16_L` at **22,374 px each**, which that document flagged as "a separate and
much larger problem" and left untouched. This is the Y16 half.

Everything below is offline, against `/home/justin/goldens/results` and the
post-fix capture set `z-repeat-c866527e03-011-Bump_map` (ref `c866527e03`, the
same set `nv2a_issues.toml`'s `blocker_tested` cites). Nothing in the bump
path has moved in `psh.c` since that ref -- `git diff c866527e03 origin/master
-- hw/xbox/nv2a/pgraph/glsl/psh.c` touches 305 lines and not one of them
mentions bump -- so the capture set is current for this question.

Re-run any number here with `docs/testing/bump_y16_class.py --all`.

## The finding, in one table

| | differing px, inside the four quads |
|---|---:|
| our `BumpMap_Y16` vs the **Y16** golden | 22,374 |
| our `BumpMap_Y16` vs the **Y8** golden | **1,576** |
| our `BumpMap_Y16` vs our own `BumpMap_Y8` | **0** |
| gold `BumpMap_Y16` vs gold `BumpMap_Y8` | 21,472 |

1,576 px is #38's positional floor, the number every already-correct capture in
this suite sits at. So **we render a Y16 source into a pixel-correct Y8
picture**, byte-identically to our own Y8, `Y8_L`, `AY8`, `AY8_L` and `A8Y8`
captures -- and hardware's Y16 picture is not its Y8 picture.

That localises the defect before any model: our geometry, our filtering of the
checkerboard, our blend and our combiner all reproduce hardware's Y8 output
exactly under the same draw. The only thing wrong is the *value* of the two
bump offsets we hand the stage for a 16-bit luminance source.

## The stored bytes are the same, which kills a whole family of rivals

`texture_stage.cpp:270-277` converts the test's surface to SZ_Y16 as
`trunc(trunc(0.299R + 0.587G + 0.114B) / 255 * 65535)`, and
`bump_map_tests.cpp:76`'s two colours are `0x007f4500` and `0x00804500` as SDL
RGBA8888:

| colour | R,G,B | Y8 | v16 | low byte | high byte |
|---|---|---:|---|---:|---:|
| `0x007F4500` | 0, 127, 69 | 82 | `0x5252` | 82 | 82 |
| `0x00804500` | 0, 128, 69 | 83 | `0x5353` | 83 | 83 |

`Y8 / 255 * 65535` is `Y8 * 257` exactly in float32, so **the stored word is
byte-replicated**: the low byte, the high byte and SZ_Y8's own stored byte are
the same number. SZ_Y16's view swizzle is `{ONE, R, R, ONE}` (both
`gl/constants.h:349` and `vk/constants.h:347`), and BUMPENVMAP reads components
2 and 1 (`psh.c:3045-3046`), so both offsets come from that field.

Therefore **no permutation of byte lanes or channel assignments can make a Y16
texel differ from a Y8 one in this test**. "hardware puts the low byte in dS
and the high byte in dT", "hardware reads the field big-endian", "hardware
takes the other channel" -- all of them predict our picture exactly, and our
picture is wrong. This is arithmetic, not a measurement, and it is worth
stating because those are the first three hypotheses anyone reaches for on a
16-bit format, and `bump16_oracle.py` already exists to score them.

(`bump16_oracle.py` is also the wrong tool here for a second reason, and the
brief asked for it: it models `Test16bit`, the HILO dot-product path, which
`bump_map_tests.cpp:56-60` instantiates **only** for `SZ_R16B16`. Y16 never
reaches `dotmap_hilo_1`. That was already recorded in `nv2a_issues.toml`'s
`status_note` -- "Y16/YUV go through HILO is false, they go through
BUMPENVMAP" -- and it is still true.)

## Where the difference is: all of it in the seam region, none outside

The draw sets TEXCOORD0 to `1/w .. 3/w` (`bump_map_tests.cpp:124`), so each
168 px quad spans bump texels 1 to 3 and crosses `GenerateBumpMapSurface`'s
`x >= 2` seam at its midpoint, column 84. Counting the hardware Y16-vs-Y8
difference column by column:

| quad (gsigned, bsigned) | differing px | columns |
|---|---:|---|
| g0 b0 | 5,340 | 44..102 |
| g0 b1 | 5,398 | 44..102 |
| g1 b0 | 5,336 | 44..102 |
| g1 b1 | 5,398 | 44..102 |

**Columns 0..43 and 103..167 hold zero differing pixels, in all four quads.**
Those are the parts of the quad where the bump source is one flat value, and
there the two goldens are bit-identical.

Two more facts about the 33 differing columns of quad g0 b0:

- **all 33 are colour-inverted, not displaced.** Every column's vertical
  checker transitions land on identical rows in both goldens (4, 10, 15, 20,
  25, 31, ...) and more than 95% of its pixels swap red for grey. So the
  vertical offset is unchanged and the *horizontal* checker cell index differs
  by an odd number.
- **the inversion toggles 30 times across those 59 columns**, in fifteen runs:
  44 | 46-47 | 50 | 53-54 | 56 | 58-62 | 65 | 68-69 | 71-72 | 75-79 | 82-83 |
  87-88 | 92-93 | 96-98 | 101-102.

That last line is the size of the thing. One checker cell is 8 texels of 256,
and `psh.c` puts the horizontal displacement at `bumpMat[0][0] * dS` with the
test's `m00 = 0.3` and `dS = b / 128` -- the reading that reproduces the Y8
golden to the floor. So one cell of horizontal movement is
`(1/32) / (0.3/128) = 13.3` byte units of `b`, and thirty parity flips is at
least fifteen cells, i.e. **hardware's Y16 offset sweeps at least ~200 byte
units across the seam region while ours steps from 82 to 83**. A lower bound,
not a value: the parity is blind to even multiples of a cell, so the true
swing can only be larger.

## Three rivals that this refutes

1. **A byte-order or channel-assignment error.** Refuted by the arithmetic
   above: the stored word is byte-replicated.
2. **Anything that changes the offsets where the source is flat** -- "Y16's dS
   comes from the `ONE` in component 0", "Y16's field is read over 32768
   instead of 128", "Y16 is signed and Y8 is not". All of these change the
   offsets across the *whole* quad, and the two goldens are bit-identical over
   109 of its 168 columns.
3. **Reading the filtered 16-bit value at more than eight bits.** This is the
   obvious candidate -- `bump_signed` in `psh.c:2100` does
   `round(x * 255.0)`, which quantises the filtered value to a byte whatever
   the source's width -- and it is refuted by magnitude. A 16-bit filter
   between `0x5252` and `0x5353` differs from the rounded byte by at most half
   a byte unit, which is `0.3 * 0.5 / 128 = 1.2e-3` of the texture: **0.3 texel
   of 256, a twenty-fifth of a checker cell.** It cannot inspect, let alone
   invert, a whole column, and it certainly cannot do it thirty times.

## And the control that refutes the fourth

The rival with the right *magnitude* is "hardware filters the 16-bit field and
the bump stage reads its low byte": between `0x5252` and `0x5353` the low byte
sweeps 82 -> 255 -> 0 -> 83, a full 256-unit excursion, confined to wherever
the filter interpolates and flat outside it. It fits the magnitude and the
containment. (It does not obviously fit the band's *position*: 44..102 is not
centred on the column-84 seam, and I have no validated model of where this
suite's filter interpolates -- see the last section for why I stopped trying
to build one.)

`Bump env lum` refutes it. `BumpEnvLum_Y16` binds SZ_Y16 over the same
`GenerateBumpMapSurface` seam; its colours give Y8 = 46 and 47, so its stored
words are `0x2E2E` and `0x2F2F` -- byte-replicated in exactly the same way, and
a linear 16-bit interpolation between them crosses `0x2F00` exactly as
`Bump map`'s crosses `0x5300`. Its bump matrix is `(0.3, 0, 0, 5.0)`, the same
horizontal term and ten times the vertical one, so a low-byte sweep would fire
there harder, not softer.

| | ours vs golden |
|---|---:|
| `BumpMap_Y16` | 22,374 |
| `BumpEnvLum_Y16` | **1,576** |

`BumpEnvLum_Y16` is at the floor. Hardware's Y16 bump offsets in that suite
agree with the eight-bit reading we emit.

**And that region is not blind.** Before believing a silence, ask what the
instrument would have shown. `BumpEnvLum_Y16` against `BumpEnvLum_A8` -- two
captures that take their luminance from the same `ONE` literal and differ only
in the bump offsets -- differ by 4,770 px in columns 44..102 of quad g0 b0
(4,872 px in 0..43, 5,880 px in 103..167). The band responds to a changed
offset; it simply does not show a Y16 one.

## So the mechanism is not named, and here is the shape of what is left

What is established:

- the defect is in the two bump offsets, not in decode, geometry, blending or
  the combiner;
- it is not a stored byte, because there is only one stored byte;
- it does not exist where the source is flat, so it is a property of whatever
  hardware does *between* two texels;
- in `Bump map` that something moves the horizontal offset by at least fifteen
  checker cells across the seam;
- in `Bump env lum`, over the same format, the same seam, the same
  byte-replicated field and a larger matrix, it does not happen at all.

The last two together are the puzzle, and they are what a fix has to explain.
The difference between the two suites is the stage program (`BUMPENVMAP`
against `BUMPENVMAP_LUM`), the luminance values (82/83 against 46/47), and
`m11` (0.5 against 5.0). A rule keyed on the format alone cannot produce both
rows, so **do not patch `append_bump_channel` on a format test**: any change
there that moves `BumpMap_Y16` moves `BumpEnvLum_Y16` too, and that one is
already exact. That is a must-not-move leg with a number already attached.

### The next measurement, concretely

One capture settles which of the three suite differences carries it, and it
needs a device only in the sense that every capture does:
`bump_map_tests.cpp:112` already holds the line, commented out --

```c
    stage.SetBumpEnv(0.3, 0.0, 0.0, 0.5, 0.0, 0.0);
    // stage.SetBumpEnv(0.3, 0.0, 0.0, 5.0, 0.0, 0.0);
```

Run `Bump map` once with the second line live. If `BumpMap_Y16` collapses to
the floor, the discriminator is `m11` and the defect is a vertical-scale
interaction, not a Y16 read at all. If it stays at ~22,000, `m11` is
eliminated and the discriminator is the stage program or the luminance value,
which the existing corpus cannot separate and a second capture would.

That is a change to `nxdk_pgraph_tests`, not to the emulator, so it is a disc
build rather than an arm. Until it is run, no fix site here is unambiguous,
and `glsl/psh.c` is in any case held by `lane.remote` (`territory.toml`'s
`[lane.remote]` grant, see #138).

## Instruments that lied to me, so the next reader does not rebuild them

Three, and all three are the same mistake in different clothes -- a model of
this suite's *geometry* that was never validated against a capture it could
not already explain.

- **`bump_oracle.py` is an 80% instrument on this suite.** Its forward render
  scores 21,839 wrong of 111,496 on `BumpMap_A8R8G8B8` under its own best
  rival. That is four times the size of the whole Y16 effect, so scoring Y16
  rivals against an absolute render cannot separate a hypothesis from the
  floor. (`bump16_oracle.py`'s validation gate -- 2,616 px -- is its own, for
  the HILO path, and does not transfer.) Everything in this document compares
  two images the same geometry produced, which is why it survives.
- **A per-column vertical-phase fit reported the same phase, 0.19 texels, for
  every capture in the suite** -- ours and the goldens, formats whose `dT`
  differs by 45 byte units alike. It is measuring something real (the
  transitions genuinely land on identical rows) but it is not measuring
  `m11 * dT`, and I spent a pass trying to reconcile it with the model before
  checking that the model reproduced a capture I already had.
- **A "where does the row go constant" detector gave 126 for the gold Y8 quad
  and 77 for ours** -- images that differ by 1,576 px in total and cannot
  possibly disagree over 49 columns. The right half of each quad carries very
  little horizontal information, and any threshold-based scan across it
  reports noise with a straight face.

The one instrument that did work is the one with no model in it: compare
images pixel for pixel, and only then ask what could have produced the
difference.
