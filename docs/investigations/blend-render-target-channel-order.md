# Blend tests' big residual is a channel order, not arithmetic

Measured 2026-09-11. Provisional in one respect, named at the end.

## What was asked

The remote lane derived a closed-form model of what silicon does in `Blend
tests`' `#spot_` captures (`docs/testing/blend_model.py`, commit `3b4499f746`)
and asked for the number it produces against our device captures, to decide
whether #14's remainder is a precision floor or host-dependent.

The model walks the whole chain in exact rational arithmetic — blend, 8-bit
store, the byte reinterpretation of an A8R8G8B8 render target sampled as
A8B8G8R8, the alpha blit, the second store — with the quantiser at each store
as a parameter. Round-to-nearest at both reproduces silicon on **18,000 of
18,000** sampled pixels across the 75 captures that are not
`FUNC_ADD_SIGNED`/`FUNC_REVERSE_SUBTRACT_SIGNED`. Confirmed here independently
against this machine's copy of the goldens, so the model is sound and it is
silicon's own behaviour that it encodes.

## The number, and why it is not a precision floor

Our Adreno captures match the model on **10,026 of 18,000** sampled pixels.

That alone reads as "a big residual". The distribution of what is left is the
part that matters:

| |delta| against silicon | samples |
|---|---:|
| 0 | 10,026 |
| **1** | **0** |
| **2** | **0** |
| 3 or more | 7,974 (tail to 221) |

**Not one sampled pixel is off by a single step.** A precision floor is made of
one-step misses; there are none. Nor is it the quantiser: of the four
combinations the model exposes, the one that fits our output best is the same
round/round that fits silicon, and the others are all worse.

| our output vs the model | hit | miss |
|---|---:|---:|
| blend round / blit round | 10,026 | 7,974 |
| blend floor / blit round | 9,233 | 8,767 |
| blend round / blit floor | 7,699 | 10,301 |
| blend floor / blit floor | 7,253 | 10,747 |

## What it is

The misses are not spread evenly over the channels:

| channel wrong | samples |
|---|---:|
| R | 7,580 |
| B | 7,912 |
| G | 1,559 |

R and B wrong five times as often as G is not what arithmetic error looks
like. It is what a byte-order disagreement looks like — and this chain has a
byte-order step in it, the A8R8G8B8 target sampled as A8B8G8R8, which
exchanges R and B and leaves G alone.

So: exchange R and B in our own capture and ask again.

| | samples |
|---|---:|
| exact as captured | 10,026 |
| **exact once R and B are exchanged** | **6,353** |
| still wrong either way | 1,621 |

**Four fifths of the residual is R and B the wrong way round**, and what
remains is 1,621 of 18,000 — 9%, the same order as the desktop lane's own
residual. The swap-explained misses are spread across all five equations in
proportion to how often each is sampled:

| equation | swap-explained | of missed |
|---|---:|---:|
| MAX | 1,800 | 2,250 |
| ADD | 1,497 | 1,902 |
| SUB | 1,412 | 1,767 |
| MIN | 900 | 1,125 |
| REVSUB | 744 | 930 |

No equation is special, which is the second reason to stop looking at the blend
unit. `MAX` and `MIN` do not consult the blend factors at all, and they are
the *worst* two by rate.

## Where it comes from in the code

`hw/xbox/nv2a/pgraph/vk/texture.c`:

* `check_surface_to_texture_compatiblity()` admits a surface as a texture when
  the dimensions match and `surface->host_fmt.host_bytes_per_pixel ==
  vk_format_texel_size(tex_vkf.vk_format)` — **equal texel size, nothing about
  channel order**. An A8R8G8B8 surface sampled as A8B8G8R8 is four bytes
  either way, so it passes.
* `can_direct_bind` is unconditionally true for every colour surface, so the
  copy path (`copy_surface_to_texture`, which does go through the texture's
  own format) is reached only by stencil-bearing depth surfaces.
* `bind_surface_as_texture()` then binds `surface->image_view`. That view
  carries the **surface's** format and component mapping. The texture's
  requested `color_format` is never consulted, so the reinterpretation
  silicon performs is simply not performed.

`kelvin_color_format_vk_map[]` in `vk/constants.h` already carries a
`VkComponentMapping component_map` per texture format — the direct path ignores
the field that would fix it.

## The fix this implies

Bind a view that reinterprets, instead of the surface's own view: when the
texture's format differs in channel order from the surface's, create (and
cache) an image view whose format and `components` come from
`kelvin_color_format_vk_map[shape->color_format]`. Among same-texel-size pairs
every difference is a component permutation or a constant — A8R8G8B8 against
A8B8G8R8 is R↔B, X8R8G8B8 against A8R8G8B8 is `SWIZZLE_ONE` in alpha — so a
view swizzle expresses all of them, and no copy is needed. Pairs that differ in
bit layout have different texel sizes and the compatibility check already
rejects them.

The conservative alternative — make the compatibility check demand equal
channel order, and let the mismatches fall through to
`copy_surface_to_texture` — is fewer lines and gives up the optimisation on
exactly the draws that currently render wrong.

## What is still provisional

The captures scored here are `res_full0907`, the 2026-09-07 full-corpus run, so
they predate a day of fixes. Nothing in those fixes touched this path and the
code above is current, but the numbers must be re-measured on one binary before
they are quoted: tonight's `overnight_19.sh` group `g2` produces a fresh
`Blend tests` arm on APK `90dc70ac3f0a`, and re-running
`blend_model.py --captures` over it is the check.

Two further things this does not settle. Whether the same swap is present on
the desktop lane — if it is not, the two lanes have been fitting rules to
differently-ordered data, which would explain a brute-force fit that tops out
at 44.6%. And the 1,621 samples the swap does not explain, which are the
candidate for the actual precision floor and are where the
`FUNC_*_SIGNED` work in #43 should be aimed once the order is right.

Scripts: `docs/testing/blend_channel_order.py`.
