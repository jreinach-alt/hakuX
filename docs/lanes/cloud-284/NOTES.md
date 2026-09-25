# cloud-284: can NV2A's anisotropic filter be modelled in the shader? (#284)

Desktop analysis over goldens and captures already on disk. No device run and no
build. Tool: `docs/lanes/cloud-284/aniso_model.py`.

## Outcome in two sentences

**Yes, for what this suite exercises.** On a point-sampled LOD0 texture, NV2A takes
probes one minor-axis width apart along the major axis, with a fractional outer
pair, from per-2x2-quad derivatives, and caps the count at the register's N by
widening the spacing. That model takes the x2 golden from **15,496 to 404**
differing pixels (the falsifier needed < 7,748), x4 from 21,981 to 2,488 and x8
from 22,617 to 5,444, and it leaves x1 untouched.

## Backends: which number came from where

| source | backend | x1 | x2 | x4 | x8 |
|---|---|---:|---:|---:|---:|
| `anisotropy-is-the-hosts-filter-not-ours.md` (whole frame) | desktop GL, llvmpipe, 09-15 | 14 | 24,908 | 32,098 | 33,160 |
| `z-repeat-c866527e03-077-Texture_anisotropy` (apk 6bf6a11955f3, 09-14) | Vulkan, Adreno (thor) | 11 | 15,496 | 21,981 | 22,617 |
| `1790359589-xbox-full6743-dry2` (apk a7b9d28e6b84, 09-25) | Vulkan, Adreno (thor) | byte-identical to the row above | | | |
| `hardware/runs/2026-09-19-calib/full/out/run1` | **console silicon** | 0 | 0 | 0 | 0 |
| model (this lane) | offline numpy | 141 | **404** | **2,488** | **5,444** |

All counts are differing pixels in rows 245..364 (any channel differs). On both
Vulkan captures every differing pixel is inside those rows. The console row is a
second silicon run that matches the goldens byte-for-byte at every level, so
silicon is deterministic here and the golden is a sound oracle.

**The llvmpipe study's premise does not hold on the current fleet.** On
Vulkan/Adreno, Anisotropy-2/4/8 are **byte-identical to Anisotropy-1** (0
differing pixels between them). With `minFilter = NEAREST` the Adreno sampler
ignores `maxAnisotropy` entirely. So the fleet does not run "the host's filter,
different from NV2A's". It runs no anisotropic filter at all, and the whole
residual is NV2A's missing probes.

## The test, from source

`texture_anisotropy_tests.cpp` + pbkitplusplus `texture_stage.h`:

- One `PRIMITIVE_QUADS`, FF path, `SetXDKDefaultViewportAndFixedFunctionMatrices`:
  LookAtLH from (0,0,-7), fovY pi/4, aspect 4/3, near 1, far 200. The viewport
  offset is 0.53125.
- Plane y = -1.5, x in [-4, 4] (u 0..1), z from 200 (v = 0) to 0 (v = 32). So
  **t depends only on the row**: every pixel in a row shares one t-phase.
- Texture 128x128 SZ_A8R8G8B8 checker, 4-texel boxes, yellow 0xFFFFFF00 / brown
  0xFF663333, WRAP. `SetAnisotropy(1 << shift)` only.
- The filter word stays at `Reset()`'s `0x1012000`: **MIN = MAG = BOX_LOD0
  (point)**, `mipmap_levels_ = 1`. So each probe is a point sample. A pixel is
  yellow/brown/mix, and the golden's yellow share reads straight off R:
  w = (R - 102)/153. G and B give two more independent readings.

The offline rasterizer projects the four vertices, snaps them to 1/16, and
interpolates s/w, t/w, 1/w per triangle. With the sample point at +0.5 after the
viewport offset it reproduces **x1 to 141 px**. All of those are checker-edge
ties (0-4 per row) plus 3 plane-edge pixels. The optimum is sharp: moving the
sample point by 1/32 either way costs 2,300-2,600 px at x1. The 141 is this
rasterizer's precision, not the probe model's, because at x1 the model is the
point sample. Our emulator's own x1 is 11 px.

## What the goldens say, as regions

Golden weights per 20-row band (in 1/64 units):

- **x2: every plane pixel is 0, 1/2 or 1**, in all six bands. So there are two
  equal probes and no bilinear.
- **x4 and x8 are identical to each other on rows 325..364, and both are
  identical to x2 on rows 345..364.** So near the camera the probe count is set
  by the footprint, not by the register.
- Rows 305..344 carry off-grid weights (4/64, 5/64, 9/64, 15/64, ...). These are
  fractional probes.

**Kernel readout.** At the centre columns the major axis is pure t, so each row's
mix is set by where one box edge falls inside that row's probe line. Tabulating
the golden weight against (edge - t_centre)/Py, row by row, gives:

- x2: the two probes sit at +-Pmaj/4 when Pmaj > 2 texels. Below that they close
  in to +-(Pmaj - 1)/2, so the half-weight band shrinks to ~7% of rows near the
  camera (5,649 / 5,645 / 860 in rows 345..364).
- x4 with 2 < Py < 3.4: the far-probe weight is **(Py - 2)/2 / Py**. It matches
  within 1/64 on seven rows (Py 2.25 -> 0.056 vs 0.0625; 2.78 -> 0.140 vs 0.14;
  3.34 -> 0.200 vs 0.203).
- **Rows sharing a 2x2 quad carry identical golden weights** (310/311, 328/329,
  296/297). So the footprint comes from per-quad (coarse) derivatives. The
  scores agree: at x4, coarse derivatives give 2,488 and central differences
  give 6,553.

## The model

Per pixel, from coarse derivatives in texels:

```
Px = |d(s,t)/dx|, Py = |d(s,t)/dy|; Pmaj = max, Pmin = min; axis = the Pmaj column / Pmaj
Pe = max(Pmin, 1.0, Pmaj / N)          # N = 1 << TEXCTL0 MAX_ANISOTROPY; the cap widens the spacing
nf = clamp(Pmaj / Pe, 1, N)            # fractional probe count
if nf < 2:  two probes at +-(nf-1)/2 * Pe, weight 1/2 each (nf = 1 -> one point sample)
else:       2*floor(nf/2) probes at +-(k+1/2) * Pe, weight 1/nf each,
            plus a pair at +-(floor(nf/2)+1/2) * Pe, weight (nf - 2*floor(nf/2)) / 2 / nf each
colour = sum(weight * point_sample(centre + offset * axis))
```

`Pmin` is floored at 1 texel because LOD0 cannot go finer. This is the classic
"probe spacing = minor axis" scheme with a fractional end pair.

### Per-level numbers (rows 245..364; px, and the |d| split)

| level | capture (Adreno) | model | model: \|d\|=1 | 2..8 | >8 |
|---|---:|---:|---:|---:|---:|
| x1 (control) | 11 | 141 (rasterizer ties; the model is the point sample here) | 0 | 0 | 141 |
| x2 | 15,496 | **404** (-97.4%) | 0 | 0 | 404 |
| x4 | 21,981 | **2,488** (-88.7%) | 2,022 | 3 | 463 |
| x8 | 22,617 | **5,444** (-75.9%) | 4,229 | 463 | 752 |

**Falsifier (the brief's):** the model must beat the capture on the level-2
golden by more than half its differing pixels. 15,496 -> 404 is 97.4%. **Passes.**
Control: x1 is not touched. At N = 1, nf = 1 and the model is one point sample.
In a shader implementation the N = 1 path is unchanged code, so it stays at
today's 11 px by construction.

What remains:

- **>8 residual (404 / 463 / 752):** single pixels where a probe lands within
  float precision of a box edge. It is the same class as the x1 control's 141
  and the #282 tie rule. This rasterizer cannot resolve it further.
- **|d| = 1 rows at x4/x8 (2,022 / 4,229):** the probe structure is right, but
  the fixed-point arithmetic of the fractional weight is off by 1 LSB on whole
  rows. Inverting each row's golden RGB into an interval for the outer weight
  gives silicon's Py as a nearly constant ~0.994 x ours. A global scale on Pmaj
  or on the minor floor does **not** reduce the total (0.996: 2,632 / 5,385;
  0.99: 4,536 / 7,370), so it is not a scale. Quantising the final weight to 8
  bits (round) gives 1,654 / 4,021. Quantising each probe weight to 8 bits gives
  1,605 / 4,666. Neither pins it. A shader will land somewhere in this band
  whatever its float arithmetic.

### How much of this is fitted to the data it scores

The discrete choices (probe rule x derivative mode x cap rule, 12 variants, all
in `--sweep`) were picked on these three goldens. The sample offset was
calibrated on x1 only. `Pmin` floor = 1 and the probe spacing were fixed from the
kernel readout on x4's rows 309..329, not tuned to the score. The x2 result and
most of x8 are therefore partly held out. No continuous parameter is fitted to
the x2 score.

## What is NOT covered (read this before extending the model to games)

- **Filtering mode.** Only MIN = BOX_LOD0, one mip level. No suite in
  nxdk_pgraph_tests sets anisotropy except this one (`SetAnisotropy` appears
  only here and in the stage reset). So nothing on disk says what a probe is
  under TENT (bilinear) or with mipmaps: the LOD from `Pe`, trilinear per probe,
  the LOD bias. Games use linear + mips. The probe *layout* probably carries
  over, but that is **unmeasured**. A console run of this test with
  `SetFilter(..., MIN_TENT_TENT_LOD, MAG_TENT_LOD0)` and `SetMipMapLevels(8)`
  would settle it. That needs an XBE change, so it is `lane.xbox`'s surface,
  not a cloud lane's.
- **Diagonal axes and an x-major footprint.** `Px > Py` on 0 of 41,202 plane
  pixels. The major axis leans off t by 7.4 deg at the median and 23.3 deg at
  most, so the direction is exercised only mildly. The `hypot` norm is an
  untested guess; NV2A may use L1 or L-inf.
- **Cube, 3D and projective-bump stages.** Not exercised.

## The hunk for the board (not edited here; glsl/psh.c and vk/texture.c are held)

1. **`hw/xbox/nv2a/pgraph/glsl/psh.c:493-507`** (`pgraph_glsl_get_psh_state`,
   the TEXFILTER block): add `state->tex_aniso[i]` =
   `1 << GET_MASK(TEXCTL0_0 + i*4, MAX_ANISOTROPY)`. Set it only when MIN is a
   point-LOD0 filter (`BOX_LOD0`), so the measured case is the only one that
   changes. It must be a `PshState` field, since it changes the generated
   shader (see AGENTS.md on cache keys with fixed register lists).
2. **`hw/xbox/nv2a/pgraph/glsl/psh.c:2968-2972`** (PROJECT2D, 2D, non-cube,
   non-convolution): when `tex_aniso[i] > 1`, replace the single `textureProj`
   with the probe loop above:
   - uv = pT.xy/pT.w + texelTieBias;
   - `dFdxCoarse`/`dFdyCoarse` x texture size. Coarse matters: fine/central
     costs 2x-3x;
   - up to N + 2 `textureLod(..., 0.0)` taps with the weights above.
   The existing `texelTieBias` (#282) applies per probe.
3. **`hw/xbox/nv2a/pgraph/vk/texture.c:2445-2461`**: set `anisotropyEnable =
   VK_FALSE` for a stage the shader filters. Today it is inert on Adreno under
   NEAREST, but it would double-filter on a driver that honours it. The GL twin
   is `gl/texture.c:631-638`.

Expected effect if granted and implemented as modelled: Texture_anisotropy
60,105 -> about 8,347 px on the Adreno fleet (the three model rows plus x1's
11; the issue's 60,074 is the inventory scorer's figure for the same captures). Treat this as a bound from an offline float model, not a value; the
shader's own float arithmetic decides the |d| = 1 band. The issue's tracker
`impact_px` of 0 ("low recoverability") is contradicted by this measurement.

## Do not repeat

- Do not model the host's filter. On Vulkan/Adreno it is not running
  (x2/4/8 are byte-identical to x1).
- Central/analytic derivatives: 869 / 6,553 / 11,847. The goldens are per-quad.
- Equal-weight probe counts (`ceil`, `round`) instead of the fractional end
  pair: x4 7,498-9,020, x8 12,770-15,518.
- Keeping the spacing at Pmin and truncating the count at N, instead of
  widening: x2 about 7,200.
- A global scale on Pmaj, or a minor floor above 1, to chase the |d| = 1 rows:
  worse at every value tried.

## Reproduce

```
python3 docs/lanes/cloud-284/aniso_model.py \
  --capture /home/justin/hakux-work/dispatch/results/z-repeat-c866527e03-077-Texture_anisotropy/captures1 \
  --capture /home/justin/hakux-work/hardware/runs/2026-09-19-calib/full/out/run1 --sweep
```

Needs numpy and PIL, and the goldens at `/home/justin/goldens/results`
(`--goldens` to override).
