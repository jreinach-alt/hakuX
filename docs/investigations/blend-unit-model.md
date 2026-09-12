# What silicon's blend unit actually does, and what is left in #14

Scope: `Blend tests`, the 75 `#spot_` captures whose equation is not
`FUNC_ADD_SIGNED` or `FUNC_REVERSE_SUBTRACT_SIGNED` (those 30 belong to #43).
Measured on the desktop lane, lavapipe.

## VERIFIED: the blend unit is textbook, quantised round to nearest

`docs/testing/blend_model.py` walks the whole chain of a `#spot_` capture:

    blend -> 8 bit store -> byte reinterpretation -> alpha blit -> 8 bit store

evaluated in exact rational arithmetic, with the quantiser at each of the two
8 bit stores as a parameter. Sampling four pixels per `DrawColorStack` swatch,
18,000 pixels over all 75 captures:

| blend store | blit store | matches silicon |
|---|---|---|
| round | round | **18,000 / 18,000** |
| round | floor | 11,538 |
| floor | round | 15,789 |
| floor | floor | 10,283 |

So silicon applies the ordinary OpenGL/Vulkan factor definitions and equations
with **round to nearest** at each store, and there is no mapping to discover:
`pgraph_blend_factor_vk_map[]` and `pgraph_blend_equation_vk_map[]`
(`vk/constants.h:54`, `:72`) are correct for all fifteen factors and all five
unsigned equations. The `0` at index 11 of the factor map is a real hole in the
hardware encoding, not a missing entry -- `NV_PGRAPH_BLEND_SFACTOR_*`
(`nv2a_regs.h:367`) runs 0..10 then 12..15.

Confirming that separately: after the surface decode fix
(`surface-as-texture-decode.md`) all fifteen `MAX` captures are byte-exact, and
`MIN`'s colour swatches are byte-exact in every capture.

## VERIFIED: what remains is the 8 bit store, not the arithmetic

Against the same 18,000 samples we match 16,625 and deviate on 1,375, every one
of them by one step. Recovering the render-target byte from the screen byte (the
blit's alpha is 221/255, so one step in the target moves the screen by 0.867 and
the inverse is unique almost everywhere) puts 2,071 of 54,000 channel samples
one below the model, 148 one above.

The deviation never happens where the exact result is 0 or 255, never in `MIN`
or `MAX`, and is led by the `ONE_MINUS_*` factors:

| sfactor | deviating samples |
|---|---|
| `1-cRGB`, `1-cA` | 209 each |
| `srcRGB`, `srcA` | 168 each |
| `1-srcA` | 101 |
| `0` | 20 |

That is the shape of float32 representation error, and the mechanism is
visible in the cases where the exact result is a whole number. `1 - 85/255` in
float32 is 0.66666665673, a hair under two thirds; times the 51 of the
background it gives 33.99999797 where silicon, working in fixed point, gives
exactly 34. Restricting to exact-integer results with an unambiguous recovery:

| float32 lands | we land on N | we land on N-1 |
|---|---|---|
| above N | 6,654 | 138 |
| below N, within 1e-5 | 162 | 640 |
| below N, further | 282 | 192 |

A store that rounded would give N in every row; one that truncated would give
N-1 in both "below" rows. Neither is what happens, which says the host's blend
arithmetic is not bit-for-bit the float32 model either -- unsurprising, and not
something the emulator chooses.

## INFERRED: disposition

Nothing here is a rule we could implement. Reproducing silicon exactly would
mean doing the blend in fixed point, which fixed-function blending cannot
express; it would need programmable blending, which is disproportionate for a
one step difference. #14's remaining material is a precision floor.

## UNRESOLVED

- **The magnitude is a lavapipe number.** Whether Adreno splits the same way at
  the store is unmeasured. Run `blend_model.py --captures` on a device capture
  set to find out; if Adreno lands on N where lavapipe lands on N-1, the
  residual is smaller on the target than this document says and the disposition
  is `host-dependent` rather than `precision-floor`.
- The model covers the `DrawColorStack` column only, where alpha is written with
  blending off. `DrawColorAndAlphaStack` and `DrawAlphaStack` blend alpha as
  well, and `MIN`'s remaining 4,950 pixels per capture are entirely in the
  latter. They are the same one step shape, but the model does not yet walk them.
