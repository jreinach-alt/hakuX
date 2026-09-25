# lane.wparam223 -- #223: W param, 5,117,044 px over 110 captures

Base: master @ 82e460e863. Offline-only result: no patch, no arm, no prediction.
Data: `dispatch/results/1789968297-arms-primpv13-base-2094212` (Thor, apk
a0fe6a75cfe2), goldens `~/goldens/results/W_param` (golden repo 6e159f1).
Every number below is from `wparam_split.py` / `wash_sign.py` in this directory
and re-derives the issue's total to the pixel (5,117,044).

## 1. Classification: half the suite is wash, not a W defect

`wparam_split.py` splits every capture's differing pixels three ways:
**wash** (max-channel |d| 1..2), **coverage** (|d|>2, exactly one side is the
clear colour 0x251135), **value** (|d|>2, both sides drew).

| family | n | diff | wash | coverage | (we miss) | value |
|---|---:|---:|---:|---:|---:|---:|
| `rcc_w_zero_inf_` | 20 | 2,357,888 | **2,354,930** | 996 | 996 | 1,962 |
| `ff_w_zero_inf__bitri` | 20 | 1,146,213 | 0 | 602,374 | 127,985 | 543,839 |
| `prog_w_zero_inf__bitri` | 20 | 569,907 | 0 | 561,737 | 561,737 | 8,170 |
| `ff_w_zero_inf__quad` | 20 | 494,632 | 0 | 494,500 | 494,107 | 132 |
| `w_gaps` (+tex_persp) | 2 | 291,374 | 43,906 | 0 | 0 | 247,468 |
| `w_pos_strip` (+tex_persp) | 2 | 181,687 | 181,687 | 0 | 0 | 0 |
| `w_neg_strip` (+tex_persp) | 2 | 74,888 | 73,188 | 0 | 0 | 1,700 |
| `ff_w_zero_` | 4 | 455 | 0 | 0 | 0 | 455 |
| `prog_w_zero_inf__quad` | 20 | 0 | 0 | 0 | 0 | 0 |
| **total** | 110 | **5,117,044** | **2,653,711** | **1,659,607** | 1,184,825 | **803,726** |

The family with the most pixels, `rcc_`, is **99.87% wash**. `rcc_ z±1, ±2,
±4, ±inf` are all exactly 79,415 wash px and nothing else: the z value, and so
the RCC result, changes nothing in them. The clamp cases (`z±0`, tiny z) carry
more wash only because RCC rescales xy and the triangles are bigger.

## 2. Both leads refuted, by measurement

- **`_RCC` signed-zero clamp (vsh-prog.c:669).** Only the `rcc_` captures run
  RCC. Their non-wash residual is **2,958 px over 6 captures** (996 coverage +
  1,962 value, all in the bottom-right corner box (560,450)-(639,479)). That
  bounds what the clamp could own. It is not the 2.36M px the family scores.
- **`_MUL` zero-forcing (vsh-prog.c:571).** The `prog_` captures run
  `passthrough.vsh`, which is `mov` only (read at
  `nxdk_pgraph_tests/src/shaders/passthrough.vsh`), and `ff_` runs no program.
  The only MUL in the suite is `rcc_clamp_test.vsh`'s `mul oPos.xy`, so MUL is
  bounded by the same 2,958 px.
- **PR #225's Exceptional Float captures** are therefore not the oracle for
  this suite's pixels. They bear on at most 2,958 px, so I did not model them.

## 3. #224 shares the wash, not the structure

`Shade_model`'s `W_Fixed_*` captures (the ones #224 and this issue share) are
**100% wash, 0 coverage, 0 value**: e.g. `W_Fixed_Poly_Smooth_First` 129,076 /
129,076. So #224's largest captures share their cause with this suite's
`rcc_` / `w_pos_strip` / `w_neg_strip` wash (2,653,711 px here), and not with
the external-triangle coverage below. (`W_FixedTex_*` are value, not wash: a
separate population.)

The wash is **not a symmetric +-1 floor** (`wash_sign.py`, ours - golden):

| capture | R | G | B |
|---|---|---|---|
| rcc z1.00 | -1:15,361 +1:21,960 | **-1:19,031, +1:0** | -2:11,211 -1:33,720 +1:21,153 |
| w_pos_strip | **+1:58,889 +2:3,458, -1:0** | mixed | mixed |
| Shade W_Fixed_Poly_Smooth_First | **0 on all 129,076** | -1:46,204 +1:31,924 | -1:76,230 +1:6,251 |

The sign is one-sided per channel per capture, so it is a gradient-direction
or rounding bias, not noise. This is the #12/#58 interpolator population
(tracker disposition `precision-floor`). If anyone reopens it, start from the
one-signed channels. They are a lead, not a finding.

## 4. The structural residual: external triangles at extreme w

Everything non-wash of size is in `ff_w_zero_inf` and `prog_w_zero_inf__bitri`:
2,210,752 px, of which 1,658,611 coverage. These tests draw triangles with
**one negative-w vertex**. Silicon rasterises such a triangle projectively, as
the **external wedge**: the region across the opposite edge, bounded by the
extensions of the two edges through the negative vertex. I checked this
against every prog golden by eye: tri1 fills x<480, y<390, above the diagonal;
tri2 fills x>160, y>70, below it.

We emit the negative w to the host and rely on the host clipper, which yields
the same wedge **when the arithmetic is well conditioned**. `prog_..._w-1.00` and
`_w-inf` match to 666/670 px. Per triangle, `prog_w_zero_inf__bitri`, clamp
range [2^-64, 2^64]. **tri1's positive vertices are at kMinW = 2^-64 and
tri2's at kMaxW = 2^64** (`w_param_tests.cpp:646-706`: tri1 = {kMinW / m,
kMinW, kMinW}, tri2 = {kMaxW * m, kMaxW, kMaxW}). This table first gave 2^-64
for both, and lane.wparamgeom223 built a fix on that and had to withdraw it
(`docs/lanes/wparamgeom223/NOTES.md`):

| capture | tri1 {neg \| pos} | ratio | tri1 | tri2 {neg \| pos} | ratio | tri2 |
|---|---|---|---|---|---|---|
| w-1.00 | {-2^-64 \| 2^-64} | 1 | drawn | {-2^64 \| 2^64} | 1 | drawn |
| w-inf | {-2^-64 (from -0) \| 2^-64} | 1 | drawn | {-2^64 (from -inf) \| 2^64} | 1 | drawn |
| w-0.00 | {-2^64 (from -inf) \| 2^-64} | 2^128 | **missing** | {-2^-64 (from -0) \| 2^64} | 2^128 | **missing** |
| w-1.88e-37 | {-2^58 \| 2^-64} | 2^122 | drawn | {-2^-58 \| 2^64} | 2^122 | **missing** |
| w-3.76e-37 | {-2^57 \| 2^-64} | 2^121 | drawn | {-2^-57 \| 2^64} | 2^121 | **missing** |
| w-7.52e-37 | {-2^56 \| 2^-64} | 2^120 | drawn | {-2^-56 \| 2^64} | 2^120 | 4,025 px missing |
| w-1.50e-36 | {-2^55 \| 2^-64} | 2^119 | drawn | {-2^-55 \| 2^64} | 2^119 | drawn |

- **Every missing triangle has a |w| ratio of 2^120 or more, and every
  ratio-1 triangle draws**, at 2^-64 and at 2^64 alike. So the failure goes
  with the ratio, not the magnitude. It is asymmetric: a *small* negative
  vertex against large positive ones fails from 2^120, while a *large*
  negative against small positives still draws at 2^122 and fails only at
  2^128.
- A clip parameter t = d+/(d+ - d-) near 2^-120 is a factor of 2^6 above
  FLT_MIN, so a flush-to-zero clipper that multiplies it by a coordinate
  difference of 2^-2 to 2^-6 before use could collapse the clipped vertex.
  That fits both triangles, but it is an unvalidated model of Adreno's
  clipper.
- Pixel split of `w-0.00`'s 271,518 px against the fix run of PR #235
  (`1790332452-arms-shadeflat224-fix-1762588`): 142,693 in tri2's colour
  (37,209,245) and 128,825 in tri1's (229,17,53). `w-1.88e-37`'s 143,546 is
  tri2's alone.
- **Three renderers, three answers.** Desktop llvmpipe GL (binary d1ec4af687,
  desktop channel, run `wparam223_prog_wm0_gl`) renders `w-0.00` as tri2's
  *interior* (upper-left of the diagonal). Adreno renders nothing. Silicon
  renders both external wedges. So the outcome is set by the host driver's
  clipper, and a desktop run cannot score this family.
- The depth test is off in these tests (`test_suite.cpp:283`, W_param never
  enables it), so no depth interaction is involved.
- `ff_` is the same class through `vsh-ff.c`'s divide path (`w-0.00` quads:
  golden has two red external wedges, we draw nothing). `ff_...bitri_w-*e-3x`
  *over*-draws: 79,014 px where silicon draws nothing, plus 67k value.

## 5. What the next lane should do (not done here)

**WITHDRAWN (lane.wparamgeom223, 2026-09-25).** The uniform scale below was
built on the section 4 table's wrong positive w for tri2. A uniform scale
cannot change a ratio, and every failing triangle is a ratio case. At
w-1.88e-37 the scale multiplies tri2 {-2^-58, 2^64} by 2^-3, not the 2^61
assumed below. What remains is clipping the triangle in the geometry shader
itself. See `docs/lanes/wparamgeom223/NOTES.md`. The original text is kept
below so the arm and its reasoning can still be read:

The one rendering-invariant lever is a **per-primitive uniform positive scale
of the three clip-space vertices** in the geometry shader. Homogeneous
invariance leaves position and every perspective-correct varying unchanged, and
it moves |w| away from 2^-64. Scale so that sqrt(max|w| * min|w|) = 1. That
fixes tri2's small-magnitude cases (e.g. {-2^-58, 2^-64} -> {-8, 1/8}). It
cannot fix a 2^128 ratio (tri1 in w-0.00), which needs the triangle clipped in
the geometry shader itself.

- **Where:** `hw/xbox/nv2a/pgraph/glsl/geom.c`. That is **not in this lane's
  Files**, so it needs a territory grant.
- **Scope:** it only reaches TRIANGLES (`pgraph_glsl_need_geom`). Quads (`ff_..._quad`)
  get no geometry shader and are out of its reach.
- **Arm it needs:** a Thor W_param arm. **must_move:** `prog_w_zero_inf__bitri_w-1.88e-37`
  (143,546 -> < 5,000), `_w-3.76e-37` (143,494 -> < 5,000), `_w-7.52e-37`
  (4,768 -> < 1,000). **must_not_move:** `prog_w_zero_inf__bitri_w-0.00` (271,518: the
  ratio case, which the scale can't reach; it fails if the model is wrong
  about ratio vs magnitude), the 20 `prog_w_zero_inf__quad` at 0, and the
  vertex-shader suites that pass today. **The world in which the must_move leg
  fails:** tri2's failure is not magnitude-driven (e.g. an Adreno guard-band
  or binning effect keyed on screen extent), and then the scale changes
  nothing.
- **Do not repeat:** the RCC/MUL leads (section 2); scoring a desktop capture
  against these goldens (section 4). Desktop Vulkan under WSLg (`DISPLAY=:0
  SDL_VIDEODRIVER=x11`) hangs before the guest boots; the channel's offscreen
  path refuses Vulkan ("Failed to create main window"), and no `xvfb-run` is
  installed on this host.

## Files

- `wparam_split.py`: wash / coverage / value split per capture and family,
  any suite (`--suite`).
- `wash_sign.py`: signed per-channel histogram of the wash.
