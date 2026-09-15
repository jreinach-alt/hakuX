# Depth_buffer_fixed_function is floating-point Z, and Android does not model it at all

Measured on `5b707602`, OpenGL (desktop), the 80 captures in
`/tmp/pgraph-run/score_cx_risk`, scored against
`/tmp/goldens/results/Depth_buffer_fixed_function`. 9,187,640 differing channels;
`corpus-residual-triage.md` ranks the suite fifth by actionable channels at
5,762,100.

Capture names factor the test completely -- `z16|z24` x `Cy|Cn` x `FZy|FZn` x
`M<hex>` x `{colour, _ZB}` -- and `depth_format_fixed_function_tests.cpp:286`
names the fields: `C` is `compress_z`, **`FZ` is `format.floating_point`**, and
`_ZB` is appended by the harness at `test_host.cpp:254`.

## Two axes are answered outright

**Compression is handled correctly.** `Cn` and `Cy` come out at 4,593,820
differing channels each -- equal to the digit, and equal on every derived
statistic. That is not a coincidence: comparing the pairs directly, the captures
**differ in 20 of 40 pairs** (so the flag really does something) and the
**residual is pixel-identical in all 40**. We reproduce the hardware's
compression delta exactly.

**Floating-point Z is the defect.**

| arm | n | differing | share | mean \|d\| | \|d\| <= 3 | \|d\| >= 16 |
|---|---:|---:|---:|---:|---:|---:|
| `FZy` | 40 | 8,249,254 | **89.8%** | 88.78 | 2.7% | **89.5%** |
| `FZn` | 40 | 938,386 | 10.2% | 6.86 | 55.3% | 1.5% |

Fixed-point depth is nearly clean. Crossed with the format:

| arm | n | differing | share | mean \|d\| | \|d\| <= 3 | \|d\| >= 16 |
|---|---:|---:|---:|---:|---:|---:|
| `z16/FZy` | 20 | 7,645,568 | **83.2%** | 86.86 | 2.8% | 89.1% |
| `z24/FZy` | 20 | 603,686 | 6.6% | 113.12 | 1.9% | 95.1% |
| `z24/FZn` | 20 | 543,084 | 5.9% | 6.14 | 54.0% | 1.2% |
| `z16/FZn` | 20 | 395,302 | 4.3% | 7.85 | 56.9% | 1.8% |

## The depth VALUES are wrong; the depth TEST is mostly right

| arm | n | differing | share | mean \|d\| | \|d\| <= 3 |
|---|---:|---:|---:|---:|---:|
| `z16/FZy/_ZB` | 10 | 7,384,196 | **80.4%** | 89.19 | **0.0%** |
| `z16/FZy/colour` | 10 | 261,372 | 2.8% | 20.89 | **80.7%** |

`_ZB` is not a visualisation: `TestHost::SaveZBuffer` writes **the raw depth
bytes out of guest memory**, so this compares stored depth values directly, with
no shader on either side.

**Eighty percent of the suite is stored float-Z values, with not one differing
channel within +/-3**, while the colour buffer from the same draws is 80.7%
within +/-3. The depth comparisons are landing in mostly the right places; what
we write into the buffer is not what the hardware writes.

## What the code does

`NV097_SET_CONTROL0_Z_FORMAT` reaches `NV_PGRAPH_SETUPRASTER_Z_FORMAT`
(`pgraph.c:2315`), and `gl/surface.c:2758` selects between
`kelvin_surface_zeta_float_format_gl_map` and `..._fixed_format_gl_map`. So the
float case is distinguished. What it is distinguished *into* is the finding.

**Float Z24S8 is knowingly approximated.** `gl/constants.h:410` carries its own
FIXME: *"GL does not support packing floating-point Z24S8 OOTB, so for now just
emulate this with fixed-point Z24S8."* That is `z24/FZy` -- 6.6% of the suite,
95.1% of it beyond 16 -- behaving exactly as a documented approximation should.

**Float Z16 depends on the platform, and the two platforms are not the same
renderer:**

| | `NV2A_GL_Z16_INTERNAL` | `NV2A_GL_Z16_TYPE` |
|---|---|---|
| desktop (`gl/constants.h:72-73`) | `GL_DEPTH_COMPONENT32F` | `GL_HALF_FLOAT` |
| **Android** (`gl/constants.h:32-33`) | **`GL_DEPTH_COMPONENT16`** | **`GL_UNSIGNED_SHORT`** |

On Android the float map and the fixed map become **identical entries**, so
`SET_CONTROL0_Z_FORMAT` selects between two things that are the same: **float Z16
is not modelled there at all.**

These captures are desktop, so the 80.4% above was measured on the
`DEPTH_COMPONENT32F` / `HALF_FLOAT` path -- the *better* of the two. What Android
does is read from the source here, not measured, and it is the project's actual
target.

That is the third time an `#ifdef __ANDROID__` has changed what a measurement
means in this lane, after `gl/draw.c`'s line-width clamp and the depth-readback
shader at `gl/surface.c:1064`, which is Android-only and therefore played no part
in these numbers. **A desktop capture is not evidence about Android wherever
this header differs.**

## Ownership, stated rather than assumed

- `gl/surface.c:2758`, the float/fixed selection -- **`[lane.remote]`**.
- `gl/constants.h`, both maps and the platform defines -- a **header**, which
  `gl/*.c` does not match. **Not granted.**
- `glsl/psh.c:352-366`, which turns `z_format` into `DEPTH_FORMAT_F16`/`F24` and
  is the **only** consumer of those enums in the tree -- `[free]`, **not
  granted**, and already on this lane's blocked list.

So the encoding itself is not this lane's to change, and neither is the table.
Nothing is edited here.

## Not established

- **Why** the desktop float-Z16 values are wrong. `DEPTH_COMPONENT32F` with
  `GL_HALF_FLOAT` uploads is a plausible-looking choice and it is 80.4% of the
  suite, but no measurement here isolates the encoding from the shader that
  writes it.
- **Correction: the `M<hex>` axis is not an independent axis.** It is almost
  entirely confounded with the format, so the "by M value" pivot mostly restates
  the z16/z24 split rather than adding anything:

  | cutoff | appears with |
  |---|---|
  | `M004002`, `M008001`, `M00c000`, `M00ffff` | **z16 only** (8 captures each) |
  | `M3fc002`, `M400002`, `M7f8001`, `M800001`, `Mbf4000`, `Mc00000`, `Mfeffff`, `Mffffff` | **z24 only** (4 each) |
  | `M000003` | **both** (8 + 8) |

  The test scales the cutoff to the format's range, so only `M000003` is
  comparable across formats -- and it is where all four exact captures sit. What
  the cutoff does *within* a format is still unanalysed.
- What Android actually produces. The identical-maps finding is read from the
  source.

`docs/testing/depth_buffer_pivot.py` reproduces every table above.
