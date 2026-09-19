# lane.hilodot10 -- #10, the three remaining bump-mapping classes

Base: master @ bb4b78689e. No device used; everything below is offline against
the goldens and the post-fix capture set `z-repeat-c866527e03-010-Bump_env_lum`
/ `-011-Bump_map` (ref `c866527e03`, the same set issue.10's `blocker_tested`
cites, so the numbers are comparable to the ones already in the tracker).

## Outcome

`blocked_on`'s "NO MECHANISM IN HAND" is now **false for Y8/AY8/A8Y8**, and the
same mechanism turns out to own most of the rest of the suite. YUV and R16B16
each get a named next measurement rather than a mechanism, and R16B16 splits
into two pieces, one of which is the Y8 mechanism.

The mechanism is **not** a sign-flag mechanism, which is why the per-quad
decomposition never found it -- see "the falsifier was the wrong shape" below.

## 1. Y8/AY8/A8Y8 -- MECHANISM NAMED

### The control that localises it

`Bump_map` binds the same texture, reads the same two offset channels through
the same view swizzle with the same bump matrix, and differs from
`Bump_env_lum` only in having no luminance stage. At `c866527e03`:

    Bump_map      BumpMap_Y8      310 /   422 /   422 /   422   one-step 0 x4
                  BumpMap_AY8     310 /   422 /   422 /   422   one-step 0 x4
                  BumpMap_A8Y8    310 /   422 /   422 /   422   one-step 0 x4
                  BumpMap_A8      310 /   422 /   422 /   422   one-step 0 x4

    Bump_env_lum  BumpEnvLum_Y8 7,139 / 7,441 / 7,301 / 7,501
                  one step      6,829 / 7,019 / 6,879 / 7,079

The Y8 family is **at the floor** in `Bump_map`. So the offsets are already
exact and the entire residual belongs to the luminance stage. Note also that
the non-one-step part of the `Bump_env_lum` numbers is 7,139-6,829 = 310 and
7,441-7,019 = 422, 7,301-6,879 = 422, 7,501-7,079 = 422: **exactly the floor**.
The class is floor + a pure one-step error, nothing else.

### What the one step is

Per-channel, quad 0: R is +1 on 6,829 px and nothing else is touched except the
floor. The golden holds one flat grey there and we split it:

    BumpEnvLum_Y8   gold (23,23,23,191) x14,116   (70,16,16,191) x13,748
                    ours (23,23,23,191) x 7,339   (24,23,23,191) x 7,015
                                                  (70,16,16,191) x13,510

### The mechanism

Every literal is in the test source, so the value is computable:

* stage 1 is an A8R8G8B8 checkerboard of `0x7F0000FE` / `0x7F202122`
  (`bump_env_lum_tests.cpp:89`), i.e. texels `(254,0,0,127)` and
  `(34,33,32,127)`;
* `SetBumpEnv(0.3, 0.0, 0.0, 5.0, 0.7, 0.3)` (:103), so the colour is
  `tex1.rgb * (0.7*L + 0.3)`, alpha untouched;
* the bump texture is `0x7f014500` / `0x80034500` written as SDL RGBA8888
  (:74, :225), and `texture_stage.cpp:237` is a `static_cast`, so SZ_Y8 stores
  `trunc(0.299R + 0.587G + 0.114B)` = **46** and **47**; the quad straddles the
  step, and SZ_Y8's `{R,R,R,ONE}` view swizzle puts that byte in component 0.

With L = 46/255, the scale is 0.42627 and the grey texel gives
34*f = 14.493, 33*f = 14.067, 32*f = 13.641. With L = 47/255 it gives
14.587, 14.158, 13.729.

* **Truncated** to eight bits: (14,14,13) at both luminances, and blended at
  alpha 0x7F over the 0xFE202020 clear that is **(23,23,23)** -- the golden,
  flat, at both.
* **Rounded**: (14,14,14) at L=46 -> (23,23,23), but (15,14,14) at L=47 ->
  **(24,23,23)** -- our second colour, exactly.

So: **hardware truncates the luminance-scaled colour to eight bits and we round
it.** The red texel is insensitive (254*f = 108.27 / 108.97, both -> 70), which
is why the error is confined to the grey cell; and the error is confined to the
right-hand half of each quad because that is where the filtered luminance
rounds up to 47.

### Scored, not argued: `docs/testing/bump_lum_oracle.py`

New tool, built on `bump_oracle.py`'s already-validated geometry, word order
and integer blend. It models **no geometry at all** -- the picture is two flat
colours per quad, so the value question is "which colours appear", and a rule
that emits a colour the golden does not hold is refused whatever the geometry
is. (Geometry is `bump_oracle.py`'s job; mine was wrong when I tried it, and
that is a separate matter recorded under R16B16 below.)

Gate first: SZ_A8 and SZ_Y16 drive component 0 from the literal ONE, so their
scale is exactly 1.0 and **every** rival must reproduce them. All 15 do, which
is what says the table is measuring the luminance and not my blend model.

    $ python3 docs/testing/bump_lum_oracle.py --rivals \
        --capture .../z-repeat-c866527e03-010-Bump_env_lum

Result, across four independent luminance values -- the literal 1.0, 0x45 (69),
0x7f/0x80 (127/128) and Y (46/47):

| format | L | golden | we emit | `quant=round` | `quant=trunc` |
|---|---|---|---|---|---|
| A8, Y16 | 1.0 (literal) | (143,16,16) (33,32,32) | same | ok | ok |
| A8R8G8B8, A8B8G8R8 | 127/128 | (27,27,26) (98,16,16) | (27,27,27) | REFUSED | exact |
| G8B8 | 69 | (24,24,24) (78,16,16) | (25,24,24) | REFUSED | exact |
| Y8, AY8, A8Y8 | 46/47 | (23,23,23) (70,16,16) | +(24,23,23) | REFUSED | exact |

**Every `quant=round` row is refused, on every format with real luminance
data, under all five rival readings of the luminance channel itself -- 25 rows,
no exceptions.** `quant=trunc` is exact. `quant=none` (full precision into the
blend) is *also* refused, by A8R8G8B8/A8B8G8R8, which emit (99,16,16) under it.

The luminance read is **not** implicated: `round255` -- what `psh.c`'s
`bump_unsigned` already does -- survives, as do `trunc255` and `exact`. So the
fix does not touch `bump_unsigned`.

G8B8 is worth its own line because it is the tool's own falsifier. Reading its
`{R,G,R,G}` swizzle off the first stored byte predicts component 0 = the source
G, 0x01/0x03; that is **refused by every rival**, ours and the golden's
pictures alike. The byte that works is 0x45, and it is not fitted: one
parameter has to reproduce our capture under `round` and the golden under
`trunc`, four colours at once.

### The falsifier was the wrong shape, and that is the finding

issue.10's `blocker_falsifier` says a real mechanism would show the class
**concentrated in the flagged quads**, like the luminance literal's
310/14,241/422/14,187, rather than spread evenly. The mechanism named here is
spread evenly -- 7,139/7,441/7,301/7,501 -- and that is a **confirmation, not a
refutation**: a colour quantiser cannot see a sign flag, so an even spread is
what it predicts. The falsifier silently assumed any remaining mechanism would
be sign-shaped. A per-quad count answers "does a flag move this"; it is blind
to values, and the value was the whole defect. The discriminator that worked is
the colour set, and it is now written into `bump_sign_quads.py`'s docstring so
the next reader reaches for it first.

## 2. BumpEnvLum_R16B16 -- one half is the above, one half is named

    BumpEnvLum_R16B16  20,758 / 21,154 / 20,828 / 21,164
    one step            8,485 /  8,115 /  8,524 /  8,115

Its dominant colour error is **identical to A8R8G8B8's**: golden (27,27,26),
we emit (27,27,27). So the truncation above owns that part.

The remainder is a genuinely separate, and previously unnamed, shape. In the
unflagged quads 0 and 2 we emit exactly **two** colours covering the whole
quad, 14,354 + 13,510 = 27,864 px, while the golden holds (27,27,26) x7,439 and
(98,16,16) x7,095 with the other ~13,700 px spread over a graded set --
(22,22,22), (24,24,24), (31,30,30) and so on at 300-430 px each. In the flagged
quads 1 and 3 *we* produce a graded set too.

The signature to quote: **the golden's colour histogram is identical in all
four quads (7,439 / 7,095 in every one); ours changes with the flags.** So the
second R16B16 defect is a flag-dependent loss of gradation that hardware does
not have -- a filtering question, not a value question, and therefore not
addressable by the truncation fix.

Next measurement, concretely: re-run `bump_oracle.py --rivals` against
`BumpEnvLum_R16B16` after extending it to the `Bump env lum` bump matrix
(0.3, 0.0, 0.0, **5.0**; `Bump map` uses 0.5). The m11 = 5.0 term is ten times
`Bump map`'s, so the env lookup is swept an order of magnitude further per unit
of dT, which is exactly the condition under which a gradation either survives
or collapses. That is the rival table that would name this one.

## 3. YUV -- not a luminance defect at all, and not a rounding one

    BumpEnvLum_YUY2_L / _UYVY_L  27,864 / 27,874 / 27,874 / 27,884
    one step                          0 /      0 /      0 /      0

    golden  (16,143,16,191) x14,116   (16, 85,16,191) x13,748
    ours    (27, 27,27,191) x14,122   (98, 16,16,191) x 8,559
                                      (97, 16,16,191) x 5,183

**The golden's picture is green-dominant and every other format's is
red-dominant.** This is decisive about the class of defect: the luminance stage
multiplies all three channels by one scalar, and the two env texels are
(254,0,0) and (34,33,32), both with their large component in red. **No value of
the luminance can produce a green-dominant colour.** So the YUV defect is
upstream of the multiply and is a channel-position defect, not a decode or
rounding one -- which is consistent with the tracker's finding that the decode
is bit-exact, and explains why looking at decode found nothing.

Note the exact value: the golden's (16,143,16) is the A8 class's (143,16,16) --
the *unscaled* red texel, scale 1.0 -- with R and G transposed. The second
colour needs a green source of ~138.4, against a red-texel value of 254.

Next measurement, concretely: capture `Bump env lum` with the stage-0 format
forced to UYVY but `SetBumpEnv`'s matrix zeroed, so the env lookup cannot move
and the only thing left in the frame is which channel the texel lands in. That
separates "the offsets are wild" from "the channel is transposed" in one
capture, which the current corpus cannot do because both are live at once.

## 4. Scope: do NOT assume this is local to the luminance stage

This is the one thing I would not have the next lane take on trust. The
truncation could be specific to the BUMPENVMAP_LUM multiply, or it could be
general register-combiner output behaviour. **Nothing in issue #10's own corpus
can tell the two apart**, because the luminance multiply is the only place in
either `Bump` suite where a non-integer colour reaches the render target --
`Bump_map` has no multiply, and the A8/Y16 classes have scale exactly 1.0.

There is a second witness outside #10, and it points at "general".
`Combiner::CombinerOps` at the same ref is 13,689 wrong with **6,052 px where B
is exactly +1** -- our value one high, same direction, same magnitude, one
channel -- in a suite with no luminance stage anywhere. The rest of the other
Combiner tests (`Mux`, `Independence`, `Flags`, `ColorAlphaIndependence`,
`UnboundTexSampler`) are at zero.

That does **not** prove they are the same mechanism: `CombinerOps` also carries
+-17 on 5,337 px and +-8/+-9 residuals that are plainly something else. It does
mean "combiner-wide" is a live hypothesis with evidence, and that a one-line
patch at `psh.c:3090` would be fitted to one suite if it landed without this
being settled first.

**Named next measurement for the scope question:** run the same colour-ladder
method against `Combiner::CombinerOps` -- enumerate its combiner ops' exact
inputs from the test source and check whether its 6,052-px one-step set is
also "ours is high by one where the exact product has a fractional part". If it
is, the fix belongs at the combiner output and this suite is a symptom. This is
offline work; it needs no device.

## 5. The prediction, ready to register -- but the file is not mine

`glsl/psh.c` is held by another lane (`territory.toml:217`, granted outright at
wave 87), so I have not touched it and no arm is registered. **Board request:
either grant `hw/xbox/nv2a/pgraph/glsl/psh.c` to this lane, or route the change
below to the lane that holds it.** (A lane cannot write into the dispatch dir
from its sandbox, so this note and the PR comment are the channel.)

The change, at `psh.c:3090`, is to truncate the luminance-scaled colour to
eight bits instead of leaving it to the render target's round-to-nearest:

    t%d.rgb = floor(clamp(t%d.rgb * (bumpScale[%d] * dsdtl%d.p
                                     + bumpOffset[%d]), 0.0, 1.0) * 255.0)
              / 255.0;

and `bump_unsigned` is left alone -- the oracle clears it.

Prediction legs, all machine-checkable and all already computed above:

* **L1, the mechanism leg.** `BumpEnvLum_A8R8G8B8` must stop emitting
  (27,27,27) and emit (27,27,26); `BumpEnvLum_G8B8` (25,24,24) -> (24,24,24);
  `BumpEnvLum_Y8`/`_AY8`/`_A8Y8` must stop emitting (24,23,23) entirely. These
  are colour-set assertions, which `bump_lum_oracle.py --capture` checks
  directly; they are not a differing-pixel total, because a total cannot say
  *which* colour moved.
* **L2, the must-not-move guard.** `BumpEnvLum_A8`, `_A8_L`, `_Y16`, `_Y16_L`
  are at 1,576 and `_DXT1` at 1,924; their scale is exactly 1.0, so truncation
  and rounding agree and they must stay **byte-identical**. This is the leg
  that fails if the change is written as a general output truncation instead of
  one confined to this multiply -- which is the point of §4, and is why it is
  a real guard and not an inert one.
* **L3, `Bump_map` untouched.** The whole `Bump_map` suite has no luminance
  stage, so every test there must stay byte-identical. `BumpMap_Y8`/`_AY8`/
  `_A8Y8`/`_A8` at 310/422/422/422 and `BumpMap_R16B16` at 126/196/140/206 are
  the rows to pin.
* Expected direction on the suite: the 38 non-floor `Bump env lum` tests all
  improve; R16B16 improves but does **not** reach the floor, because §2's
  second defect is untouched. A prediction that claims R16B16 reaches the floor
  is wrong and would fail for the right reason.

## 6. Also found, not in the brief, not yet tracked

* **`BumpMap_Y16` is 22,374 wrong** (5,534 / 5,634 / 5,572 / 5,634, zero
  one-step) at `c866527e03`. `BumpEnvLum_Y16` is fixed and at the floor, and
  issue.10's `status_note` records the `Bump_map` arm only for R16B16 and _B,
  so this row appears in no entry. It is a *different* defect from everything
  above -- zero one-step, and `Bump_map` has no luminance stage.
* **The whole `Bump env lum` suite is broken except A8/Y16/DXT1**: 38 of 42
  tests, 29k-111k px each. The tracker names Y8 and R16B16 as what remains, but
  A8R8G8B8 and friends at 52,764 each are the larger share and were unnamed.
  Most of that total is §1's mechanism.

## What the next lane should not repeat

* Do not reach for a sign model on this suite. Three classes read as
  "flat across the four quads, therefore no mechanism"; all three were value
  defects, and a per-quad count cannot see a value. Compare the colour sets
  first -- it takes one command.
* Do not trust `BumpEnvLum_A8R8G8B8` as a reference picture. It is 52,764
  wrong. I spent a pass assuming it was the clean one.
* Do not model the geometry of `Bump env lum` unless you need to. I wrote a
  full forward render first and it scored 43,164 against the A8 golden that the
  emulator itself matches at 1,576 -- m11 = 5.0 amplifies any slip in dT, so
  the geometry is unforgiving and it was not what the question needed. The
  value ladder answered it with no geometry at all.
* `0026f00534` and the `z-tip` sweep are PRE-FIX. `bump_sign_quads.py`'s
  docstring said "Measured at 0026f00534" without saying so; it now does.
