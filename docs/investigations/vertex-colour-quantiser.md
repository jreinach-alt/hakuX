# The vertex-colour quantiser, measured: #38 mechanism 1 is decided and closed

Written 2026-09-12 against the goldens, on the full-corpus device sweep
(APK `fb4dfafc6d38`, refs `ce9c4eecf8` / `b63603975c`, 75 suites, 1,915
captures, `progress_log_proof` on every run). No build, no device.

Issue #38 lists four one-step mechanisms and calls the first one the only one
with a concrete candidate fix, undecided:

> **Vertex colour quantisation** — ours = hardware + 1 … Candidate fix:
> quantise the vertex shader's colour outputs the way the hardware's colour
> interpolators do, once measured on more values (**0.5 → 127 or 128 decides
> between truncation and round-half-down**).

Three things below. The rule, measured over nineteen distinct component
values instead of two. The answer to 0.5, which is **128**, and which kills
both of the rules the issue offered. And the scope: the mechanism is
**already implemented and correct**, and none of the residue the issue
attributes to it is actually it.

## 1. The rule

`vertex_colour_quantiser.py` reads the map off the goldens — flat regions,
checked uniform before use, RGBA — and scores every candidate against all of
it. Reproduce with `python3 docs/testing/vertex_colour_quantiser.py`.

| component (float32 as submitted) | 255·x | hardware | trunc | half-up | half-down | half-even | floor(256x) | round(256x) |
|---|---:|---:|---|---|---|---|---|---|
| `0.1f` | 25.5000004 | **25** | 25 | 26 ✗ | 26 ✗ | 26 ✗ | 25 | 26 ✗ |
| acc(2) 0.200000003 | 51.0000008 | **51** | 51 | 51 | 51 | 51 | 51 | 51 |
| `0.25f` | 63.7500000 | **64** | 63 ✗ | 64 | 64 | 64 | 64 | 64 |
| acc(3) 0.300000012 | 76.5000030 | **76** | 76 | 77 ✗ | 77 ✗ | 77 ✗ | 76 | 77 ✗ |
| acc(4) 0.400000006 | 102.0000015 | **102** | 102 | 102 | 102 | 102 | 102 | 102 |
| `0.5f` / acc(5) | 127.5000000 | **128** | 127 ✗ | 128 | 127 ✗ | 128 | 128 | 128 |
| `0.6f` / acc(6) | 153.0000061 | **153** | 153 | 153 | 153 | 153 | 153 | 154 ✗ |
| `0.65f` | 165.7499939 | **166** | 165 ✗ | 166 | 166 | 166 | 166 | 166 |
| acc(7) 0.700000048 | 178.5000122 | **178** | 178 | 179 ✗ | 179 ✗ | 179 ✗ | 179 ✗ | 179 ✗ |
| `0.75f` | 191.2500000 | **191** | 191 | 191 | 191 | 191 | 192 ✗ | 192 ✗ |
| acc(8) 0.800000072 | 204.0000182 | **204** | 204 | 204 | 204 | 204 | 204 | 205 ✗ |
| acc(9) 0.900000095 | 229.5000243 | **229** | 229 | 230 ✗ | 230 ✗ | 230 ✗ | 230 ✗ | 230 ✗ |
| `0.95f` | 242.2499970 | **242** | 242 | 242 | 242 | 242 | 243 ✗ | 243 ✗ |
| `1.0f` / acc(10) | 255.0000304 | **255** | 255 | 255 | 255 | 255 | 255 | 255 |

`acc(n)` is the float32 after n steps of `red = 0.1f; red += 0.1f`, which is
what `Point_size`'s `RenderPoints` actually walks. It is *not* the decimal:
`acc(7)` is 0.700000048, and the whole result lives in that difference.

**0.5 is 128.** The issue offered that as the discriminator between
truncation and round-half-down; it eliminates *both* of them, and it does not
settle the question, because `0.1f → 25` eliminates round-half-up,
round-half-even and round-half-down at the same time. Every one of the five
named candidates is dead, and so is the ×256 family that "hardware truncates"
naively suggests:

| rule | verdict | killed by |
|---|---|---|
| `trunc(255x)` | **dead**, 4 of 19 | `0.25f` → 63, hardware 64 |
| `round_half_up(255x)` | **dead**, 5 of 19 | `0.1f` → 26, hardware 25 |
| `round_half_down(255x)` | **dead**, 7 of 19 | `0.1f` → 26 *and* `0.5f` → 127 |
| `round_half_even(255x)` | **dead**, 5 of 19 | `0.1f` → 26, hardware 25 |
| `floor(256x)` clamped | **dead**, 4 of 19 | `0.75f` → 192, hardware 191 |
| `round(256x)` clamped | **dead**, 10 of 19 | `0.1f` → 26, hardware 25 |
| **truncate the float's low mantissa bits, then round 255·x to nearest** | **reproduces all 19** | — |

The shape of the answer is not a rounding mode at all. Hardware rounds to
nearest, like we do; what it rounds is a value carried at *less than float32
precision*, so the upward representation error of a decimal literal — `0.1f`
is 0.100000001490116, `0.9f` accumulated is 0.900000095 — is gone before the
multiply. Wherever the intended decimal times 255 is exactly a half count,
float32 lands a hair above it and rounds up where silicon rounds down. That,
and only that, is "ours = hardware + 1".

Consequences worth keeping:

* **No rounding-mode change can fix this class.** That is why both placements
  tried in #38's first comment regressed: a `floor` breaks `0.25f`, `0.5f`
  and `0.65f`, which were already right.
* **A single additive bias cannot fix it either.** `floor(255x + c)` needs
  `c < 0.4999996` for `0.1f` and `c ≥ 0.5` for `0.5f`. The admissible
  interval is empty, and it is empty by 4·10⁻⁷ — the float32 error in `0.1f`.
  The truncation has to happen *before* the multiply.

### What the corpus bounds, and what it does not

The committed shader drops the low **10** mantissa bits. The corpus permits
dropping **4 to 14**; anything in that band reproduces all nineteen points.
An absolute (fixed-point) truncation at 2⁻ᴺ fits equally well for **N = 10 to
20**. So the goldens say *"truncate the fraction before scaling"* and bound
how coarsely; they do **not** pin ten bits, and they do not distinguish a
relative truncation from an absolute one. Do not quote 13 bits as measured.

## 2. It is already implemented

`hw/xbox/nv2a/pgraph/glsl/vsh.c`, in the generated vertex-shader prologue:

```
vec4 colorPrecision(vec4 c) {
  return uintBitsToFloat(floatBitsToUint(c) & 0xFFFFFC00u);
}
```

applied in the epilogue to all four colour outputs:

```
vtxD0 = colorPrecision(clamp(NaNToOne(oD0), 0.0, 1.0));
vtxB0 = colorPrecision(clamp(NaNToOne(oB0), 0.0, 1.0));
vtxD1 = colorPrecision(clamp(NaNToOne(oD1), 0.0, 1.0));
vtxB1 = colorPrecision(clamp(NaNToOne(oB1), 0.0, 1.0));
```

Landed 2026-09-11 as `5c2b26db2f` ("nv2a: carry vertex colours at the
precision the hardware does"), from the `Point_size` goldens. The rounding
itself is the UNORM8 attachment conversion, which already rounds to nearest;
the shader only removes the sub-precision excess before it. This is the same
rule the table above recovers, from six suites the commit did not use.

**So there is no patch to write for #38 mechanism 1.** The measurement
confirms the committed shader rather than proposing a change to it.

It is verified, not assumed. Every capture in the corpus whose colour is a
flat float-specified vertex colour is now pixel-exact against silicon:

| capture | submitted | byte | result |
|---|---|---|---|
| `Surface_clip/x*_A8R8G8B8` (9 of 9) | `SetDiffuse(0.1f, 0.6f, 0.1f)` | 25, 153, 25 | exact |
| `Null_surface/XemuBug893` | same | 25, 153, 25 | exact |
| `SetVertexData/*` (7 of 7) | `4F_M`/`2F_M` = 0.25, 0.5, 0.75, 1.0 | 64, 128, 191, 255 | exact |
| `Stencil_func/*` (16 of 16) | `SetDiffuse(0, 0.75f, 0)` | 191 | exact |
| `Antialiasing_tests/FBSurfaceWithCenter1` | `SetDiffuse(0.25f, 0.95f, 0.75f)` | 64, 242, 191 | exact |
| `Point_size/*` (21 captures) | the 0.1f walk | 25…255 | every colour exact; all 21 residuals are point-edge `boundary-shift` |

The captures also date themselves behaviourally, which is stronger than the
metadata: without `colorPrecision` the `Surface_clip` A8R8G8B8 captures would
read 26 in two channels over ~296,000 px each, and they read 25.

## 3. Scope: the issue's guess is wrong on both suites

Classified over the whole sweep (`docs/testing/classify_residuals.py`,
1,915 captures, 74,682,372 differing channels):

| class | captures | channels |
|---|---:|---:|
| exact | 339 | 0 |
| boundary-shift | 244 | 153,954 |
| **one-step-hi** (ours = hw + 1) | **24** | **2,532,808** |
| one-step-lo | 70 | 1,768,004 |
| one-step-sym | 201 | 4,763,447 |
| structural | 1,037 | 65,464,159 |

The whole `ours = hardware + 1` class is 24 captures, and **none of it is
vertex-colour quantisation**:

| suite | captures | channels | what it actually is |
|---|---:|---:|---|
| `Surface_clip` (`rt_*`) | 7 | 2,351,482 | 5-bit UNORM texel expansion, below |
| `Lighting_normals` | 12 | 114,164 | the Gouraud interpolator, already derived in #38's third comment |
| `Pixel_shader/BumpEnvMapLuminance` | 1 | 67,070 | bump arithmetic across 1,753 golden colours |
| `Texgen_with_texture_matrix` | 4 | 92 | 54 of 92 channels are `boundary-shift`; an edge |

### `Surface_clip`: 18 → 7, and the 7 are a different mechanism

All seven are the `rt_*` render-target variants and all seven hold **exactly
one** gold/ours colour pair over 1,175,741 px:

```
gold (24, 154, 24, 255)  ->  ours (25, 154, 25, 255)
```

`golden_colours = 1` on every row, so the golden is flat across the entire
disagreement. The test renders `SetDiffuse(0.1f, 0.6f, 0.1f)` into an
**R5G6B5** surface and then samples that surface as a texture. The 8-bit
value is right (25, 153, 25 — the A8R8G8B8 variants prove it). Packing gives
R5 = 3 and G6 = 38 under either truncation or rounding. Unpacking is where we
part:

| 5-bit v | bit replication `(v<<3)|(v>>2)` | exact ratio `round(255v/31)` |
|---|---|---|
| 3 | **24** | 25 |
| 7 | 57 | 58 |
| 11 | 90 | 91 |

Hardware gives 24; we give 25. Green agrees at 154 because replication and
ratio coincide for v = 38. **Silicon expands narrow UNORM components by bit
replication; the Vulkan-native `VK_FORMAT_R5G6B5_UNORM_PACK16` path expands
by exact ratio.** They differ for 8 of the 32 five-bit codes (v ≡ 3 mod 4)
and for some six-bit codes (v = 50: 203 vs 202).

This is a texture-decode rule, not a vertex-colour rule, and it is the
largest single one-step-hi residue in the corpus. It is a separate lead; it
is *not* #38 mechanism 1, and fixing mechanism 1 harder will not touch it.

Where it lives matters before anyone specifies a patch, and I have not
settled it: `hw/xbox/nv2a/pgraph/vk/texture.c` has both a CPU upload path
(`pgraph_convert_texture_data`, which returns NULL for the 16-bit formats so
they go to Vulkan as `VK_FORMAT_R5G6B5_UNORM_PACK16` — see
`pgraph/vk/constants.h`) and a direct `bind_surface_as_texture` /
`surface_view_decodes_as_texture` path. `Surface_clip`'s `rt_*` test renders
*into* the R5G6B5 surface and then samples it, so it is the second path, and
a converter added to the first would not move a pixel of this. Do not write
the patch against the upload path on the strength of this residue.

### `W_buffering`: the guess is wrong twice over

The issue says "by the look of it, the 48 `W_buffering` ones", citing
`WBuf24D_LargeZ_V1_ZB0_ZS0_ZB` at 87 vs 86.

1. `wbuf_tests.cpp` submits **only** `SetDiffuse(1.0f, 1.0f, 0.0f)` and
   `SetDiffuse(1.0f, 0.0f, 0.0f)`. Every component is 0 or 1, exactly
   representable, and no quantiser of any kind can move them. The suite
   cannot exhibit this mechanism.
2. The cited capture's name ends in `_ZB`: it is a depth capture, and 87 vs
   86 is a depth word, not a colour. On the 2026-09-12 coverage run
   (`cov_W_buffering.tsv`, 530 rows), the one-step captures split:

   | | one-step captures | px |
   |---|---:|---:|
   | colour captures | **0** | 0 |
   | `_ZB` captures | 66 | 992,326 |

   Not one colour capture in the suite is one-step. That residue is #16.

## 4. The other three mechanisms in #38

Separate causes, and the sign distribution says so: 24 one-step-hi against 70
one-step-lo and 201 one-step-sym. A single rounding rule is one-directional
by construction and cannot produce that.

* **Mechanism 2 (Gouraud interpolation)** — genuinely separate, and it is
  what `Lighting_normals` is: the endpoints are provably right (#38's third
  comment measured the flat lit triangle exact in all 28 captures) and the
  ramp between them is not. `colorPrecision` quantises the *endpoints*;
  nothing in the vertex stage can change how the host interpolates between
  them.
* **Mechanism 3 (blend / blit rounding)** — separate and opposite in sign:
  `Image_blit` is 17 one-step-lo captures against 0 one-step-hi.
* **Mechanism 4 (depth capture conversion)** — separate, and it is where
  `W_buffering`'s one-step rows actually live. #16.

## 5. What is least certain

**The precision width.** The corpus bounds the truncation to dropping 4–14
mantissa bits and cannot pin it, and cannot tell a relative truncation from
an absolute one at 2⁻¹⁰…2⁻²⁰. Every value in the corpus that sits near a
half count sits within ~3·10⁻⁵ of it, which any width in the band clears.
Separating them needs a component whose 255·x lands between roughly 10⁻⁴ and
10⁻² above a half count — no test submits one. The capture that would expose
a wrong choice first is `Point_size/PointSmoothOff_16_FF`: it is the only one
holding ten values from a single accumulating walk, so a width chosen too
coarse breaks `acc(6)`/`acc(8)` there (drop 16 gives 152 and 203) before it
breaks anything else.

**`Texgen_with_texture_matrix`'s 4 captures** are the one group I have not
resolved to a mechanism. 92 channels total, 54 of them already classed
`boundary-shift`, so the remainder is 38 channels; too small to fit anything
to and too small to matter, but it is the only one-step-hi row left whose
cause I am asserting from its size rather than from a measurement.

## Falsifier

`python3 docs/testing/vertex_colour_quantiser.py` must print

```
mantissa13_half_up   reproduces all 19
OK: surviving rules = ['mantissa13_half_up'], as recorded
```

and, specifically, must read these bytes from these goldens:

| golden | region | channel | hardware byte |
|---|---|---|---|
| `Surface_clip/x0y0_w640h480_A8R8G8B8` | x 60–580, y 80–440 | R (`0.1f`) | **25** |
| `SetVertexData/SET_VERTEX_DATA2F_M` | x 216–218, y 200–330 | R (`0.5f`) | **128** |
| `Antialiasing_tests/FBSurfaceWithCenter1` | x 230–410, y 150–330 | R (`0.25f`) | **64** |
| `Degenerate_begin_end/BeginWithoutEnd` | x 484–505, y 122–135 | R (`0.75f`) | **191** |
| `Point_size/PointSmoothOff_16_FF` | x 376–432, y 265–319 | B (`acc(7)`) | **178** |
| `Point_size/PointSmoothOff_16_FF` | x 504–560, y 393–447 | B (`acc(9)`) | **229** |
| `Point_size/PointSmoothOff_16_FF` | any block | G (`0.65f`) | **166** |

If any of those reads differently, the goldens changed and this document is
void. If they read as stated and a candidate other than
`mantissa13_half_up` survives, the probe set grew and the rule needs
re-deciding.
