# Depth readback: one scale, four disagreements

**Scope:** issue #16, `Depth surface readback converts incorrectly`. Vulkan
renderer, measured on a Retroid Pocket Nova (Adreno) against
`nxdk_pgraph_tests` goldens captured from XBOX 1.0 silicon.

**Resolved by** `a33fa42bc3` and `23a8962df2`.

## What was wrong

A guest Z24S8 depth word could not survive a trip through the host depth
buffer. Four places had an opinion about the scale it was stored at, and no
two of them agreed:

| where | what it did | scale |
|---|---|---|
| `glsl/psh.c:1646` | `floor(zvalue) / 16777216.0`, then `+ 1u` on the bits | 2^24, nudged |
| `glsl/vsh-prog.c:761`, `glsl/vsh-ff.c:487` | `oPos.z / clipRange.y` | 0xFFFFFF |
| `pgraph.c:4302` | `z / (float)0xFFFFFF` | 0xFFFFFF |
| `vk/surface-compute.c:86` | `int(depth * float(0xffffff))` | 0xFFFFFF |

Each pairing is within one unit of the next, which is exactly enough to be
wrong and not enough to be obvious.

**VERIFIED.** The float zeta formats were worse than inconsistent: the
fragment shader's depth switch handled `D16` and `D24` and let `F24` and `F16`
fall through to `gl_FragDepth = zvalue / clipRange.y`, where `clipRange.y` for
F24 is `f24_max` = 1e30. A W-buffered `zvalue` of 325 was written as 3.25e-28,
so every drawn pixel read back as zero. Hardware has `0x874500` there, which
is f24 for exactly 325.0.

## Why no single scale was enough

**VERIFIED, by construction.** `gl_FragDepth` is a float32. In the top octave
its grid is 2^-24; a 24 bit unorm image's grid is 1/(2^24-1). The two are half
a unit out of phase around z = 2^23, so the nearest float to a depth word `Z`
decodes to `Z + (1 - (Z+1)/2^24)` — for `Z = 0x800007` that is
`Z + 0.4999995`. Which integer the driver stores is then decided by how it
rounds, and there is no float32 that lands anywhere safer:

    for Z in [2^23, 2^24), the only candidate is k = Z+1, and it decodes to
    Z + (1 - k/2^24), which tends to Z + 0.5 as Z tends to 2^23.

Adreno rounds up. A buffer cleared to `0x800007` read back as `0x800008`, on
304,284 of 307,200 pixels. On a correctly-rounding implementation the same
code is exact, which is why this had not been caught: the margin is 4.8e-7 and
the failure is a driver-by-driver coin flip.

**Falsified along the way.** Three separate hypotheses measured plausibly and
were wrong before this one held up:

1. *The pack shader multiplies by 2^24 somewhere.* It does not — every pack
   path in `surface-compute.c` used `0xFFFFFF`. The `x2^24` model happened to
   predict the observed values because that is what the phase error looks
   like.
2. *The unorm path can be fixed by choosing a better float to write.* It
   cannot; see the derivation above. Simulating 60,000 depth words showed the
   old code round-tripping exactly in IEEE arithmetic, which is precisely why
   the bug is invisible to reasoning that stops at the spec.
3. *Making the shader and readback agree at 2^24 is enough.* Two builds said
   no, byte for byte identical results, because `check_surface_internal_formats_supported`
   was picking `D24_UNORM_S8_UINT` and the float branch was never taken. One
   `fprintf` at `vk/surface.c:3363` settled in one run what two builds of
   inference had not.

## The fix

Prefer `VK_FORMAT_D32_SFLOAT_S8_UINT` for Z24S8. There is no quantiser, every
guest depth word is exactly representable, and the readback is exact in both
directions. Scale by 2^24 consistently in all four places whenever that is the
host format; `PGRAPHState::zeta_stored_as_float` is what they agree on.
`D24_UNORM_S8_UINT` remains the fallback with the ULP nudge the unorm scale
needs, so a device without the float format behaves as before. It costs 8
bytes a pixel against 4.

The float zeta formats store their **encoding** rather than their value. IEEE
bit patterns of non-negative floats are monotonic in the value, so the depth
test still orders correctly; 24 bits of guest depth still fit 24 bits of host
depth; and the readback needs no float case at all.

## Measured

Depth captures (`*_ZB`) against the goldens, one test per disc:

| suite | before | after |
|---|---|---|
| `Depth_buffer` (72) | 11,721,972 px differing, 10 blank | 505,280 px, 0 blank |
| `Depth_buffer_fixed_function` (40) | 6,746,610 px | 317,130 px |
| `W_buffering` (265) | 29,881,554 px, 24 blank | see #16 |

Every z24 fixed-point clear now round-trips exactly, 18 of 18, against 16 of
18 before. Z16 was exact before and after — it has one scale everywhere and
always did, which is the control that made the Z24S8 phase error legible.

## UNRESOLVED

Two classes of difference remain, and neither is the conversion:

- **Interpolated depth lands a unit either side of hardware.** On
  `DepthFmt_z24_Cn_FZn_Mffffff` 56,959 pixels are `+1` and 781 are `-1`; the
  count scales with the depth range under test (21 px at `M055564`, 57,741 at
  `Mffffff`). We interpolate depth in float32 where the NV2A uses a fixed
  point interpolator. Not filed separately yet.
- **Slope-scaled polygon offset under W buffering.** 48 of the 54 remaining
  large `W_buffering` errors have `ZS1` set. `glsl/psh.c` already carries the
  FIXME: the slope is computed per pixel where the Xbox appears to use the
  slope at the first visible pixel in top-left order.
