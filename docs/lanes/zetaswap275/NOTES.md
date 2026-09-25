# lane zetaswap275 -- #275 Color zeta overlap Swap

Status: **located, not fixed.** Analysis only; no hw/ file edited, no arm registered.
Base: master @ d709a8d1fa.

## Result in one paragraph

What is left of `Color_zeta_overlap/Swap` (165,447 px) is **not a surface or aliasing
defect.** It is the fixed-function perspective depth transform: for this quad we write
24-bit depth `0xFFE91A` where silicon writes `0xFFE916`. That is 4 units high, the same
defect as **#272** (Depth buffer fixed function, 24-bit, 2-5 units high near max depth)
and the "V0 +2 is the fixed-function z transform" leftover in #266. Swap is that defect's
cleanest sample: one quad at constant depth, 165,447 px at a single value, deterministic
on silicon. The code site is `hw/xbox/nv2a/pgraph/glsl/vsh-ff.c:884`
(`vtxPos.z = oPos.z / oPos.w`, which is exact), consumed by the `zfloor` path in
`glsl/psh.c`. Silicon's arithmetic there is **not established**: no simple model fits
both constant-depth captures (below), so there is nothing to patch yet.

## What TestSwap draws (from `color_zeta_overlap_tests.cpp:140`)

- `PrepareDraw(0xFE242424, 0)` clears the colour buffer to `0xFE242424` and depth to 0.
- `SET_CONTEXT_DMA_COLOR <- zeta channel (10)` and `SET_CONTEXT_DMA_ZETA <- colour channel (9)`.
  So colour renders into the old depth buffer (never displayed), and **zeta renders into the
  displayed framebuffer.**
- One quad with diffuse `0x00A8BF00`, world z = 180, x/y scaled by 30. The suite
  `Initialize()` sets depth test on, mask on, func ALWAYS, the XDK default matrices (eye at
  z=-7, FOV pi/4, zn=1, zf=200) and a Z24S8 surface.
- The DMAs are swapped back and the label is printed. The capture is the framebuffer.

So every quad pixel in the capture is a **Z24S8 depth word**: `depth24 << 8 | stencil`,
where the stencil byte `0x24` survives from the clear. The test's own label prints the
expected colour as `C=0xFF2416E9`, whose channels are the golden quad's E9/16/24.

## Region histograms, not point samples

| source | quad | background | label |
|---|---|---|---|
| golden | (233,22,36,255) x 165,447 | (36,36,36,254) x 139,303 | 2,450 |
| console 09-19 calib, 09-20 run1 | identical to the golden | identical | identical |
| ours: clrwb91 fix, clrwin88 base, clrwin88 fix | **(233,26,36,255)** x 165,447 | identical | identical |

The extents match exactly. Only the quad's value differs: word `0xFFE91624` against
`0xFFE91A24`, i.e. depth24 `0xFFE916` against `0xFFE91A`.

## The exact depth is ours, not silicon's

view z = 180 + 7 = 187 = w. z_clip = 16777215 * 200/199 * (187 - 1).
screen z = 16777215 * (200/199) * (186/187) = **16,771,354.04**, exact rational.
Its floor is `0xFFE91A`, and the float32 chain as the XBE builds the composite gives the
same value. **Silicon is 4.04 below exact.**

ZetaIntoColor gives a second constant-depth point: world z = 192, so w = 199. Exact is
16,776,791.34, floor `0xFFFE57`. Our pre-colour-wins capture has `0xFFFE57`; all four
silicon captures (golden, calib, czo run1 and run2) have `0xFFFE54`. **3.34 below exact.**

A third, independent data source is `Depth_buffer_fixed_function/z24_Cn_FZn_Mffffff_ZB`.
It uses the same XDK matrices and w of about 135-200. Ours minus silicon there
(run `1790359589-xbox-full6743-dry2-2802408`), by golden depth band:

| band | px | mean | mode |
|---|---:|---:|---:|
| 0x000000.. | 713 | -7.1 | -7 |
| 0x400000.. | 777 | -3.9 | -4 |
| 0x800000.. | 1,017 | -1.2 | -2 |
| 0xC00000.. | 2,185 | +0.6 | +1 |
| 0xE00000.. | 140,177 | **+3.6** | **+4** |

Swap (+4 at 0xFFE9xx) and ZetaIntoColor (+3 at 0xFFFExx) sit on that curve. (This DBFF
comparison is ours against silicon, not against exact, so its low-depth half may include
error of our own. The two constant-depth points are both against exact.)

## Silicon's arithmetic: not found, and why I did not patch

`.scratch/models.py` (not committed; the model is described here) tried 1,170
combinations: z_clip as float32, fused or exact; 1/w as exact, float32 RNE, or float32
truncated to 10-22 mantissa bits; the product exact, RNE or truncated; final floor or
round. **None hits both points.** The best models miss by +1 on one point and -1 to -3 on
the other. A pure relative error in 1/w also cannot produce DBFF's sign change at low
depth, where silicon sits *above* ours. The needed relative error is -1.8e-7 to -2.4e-7
for w=187 and -1.5e-7 to -2.1e-7 for w=199. Those ranges overlap, but no rounding rule I
tried lands in both.

With two constant-depth points and a curve, any patch now would be a fit. The model has to
come from the DBFF grid: 992 quads with vertex depths known from the test's own float32
`UnprojectPoint` replay, the same idea as `docs/testing/depth_exact_floor.py`, but for the
perspective suite. Then both constant-depth captures here act as held-out checks.

## The hypotheses in the brief, measured

- **"SurfaceShape has no address" (#92).** This was already measured, although the brief
  says it was not. lane.blitsafe's `[surf92]` probe, 2026-09-19 on #92, saw addrchg=0
  across 40,960 upload-side updates on a disc containing TestSwap. The capture refutes it
  a second way: a surface miskey would move a population boundary or replace whole words.
  Here all three populations match silicon to the pixel, and one word differs by 4 in its
  lowest depth byte. "Identical on GL and Vulkan" (#92's motivation) fits better with the
  shared GLSL vertex path (`glsl/vsh-ff.c`), which both renderers compile.
- **#91's colour-wins trade.** This does not touch it. The background (139,303 px) is on
  the golden's `FE242424` since #237, and the fix class here is depth arithmetic in the
  shaders, not surface binding. Whoever implements the depth fix should still register
  `Color_zeta_overlap/{ColorIntoZeta_ZB,ZetaIntoColor,Swap_ZB}` as must_not_move: a shader
  depth change moves ZetaIntoColor's depth-word population too (silicon `FFFE54`).

## Where the fix goes (for the lane that takes #272)

- `hw/xbox/nv2a/pgraph/glsl/vsh-ff.c`, the fixed-function position block at line 878-888.
  It computes `vtxPos.z = oPos.z / oPos.w`, and that per-vertex screen z is the input to
  `psh.c`'s `zhi`/`zfloor`. As of this lane no brief listed vsh-ff.c as held.
- Maybe `glsl/psh.c`'s D24 `zfloor` block too, if silicon's error turns out to be in
  interpolation rather than in the vertex divide. That file is lane.wbufdepth24's.
- Programmable vertex shaders (`vsh-prog.c:850`) take a different route. Whether they
  share silicon's bias is unmeasured.

## Do not repeat

- Do not chase a surface-cache or aliasing mechanism for Swap. The populations are exact.
- Do not fit 1/w truncation to Swap alone: trunc-21 reaches Swap within 0-1 and misses
  ZetaIntoColor by 1-3.
- `psh.c:2831` already says silicon's sub-exact ULP was "undecidable on this suite, which
  has no primitive of constant depth". Swap and ZetaIntoColor are such primitives. Use them
  as the held-out check.

## Not chased

ZetaIntoColor's colour/depth mixture (nondeterministic on silicon) and ColorIntoZeta_ZB
(inside silicon's run-to-run spread), as the brief says. Also the programmable-shader
depth path.
