# cloud-297: residuals under the `blank` tag (#297)

Lane: cloud-297 (cloud-class, no device). Base: master @ 248f1312c7.
Status: **done.** This is analysis only: no hw/ file edited and no prediction registered.

## Result

| captures | px each | what the pixels are | owner |
|---|---:|---|---|
| `Depth_buffer_fixed_function/z24_C{n,y}_FZy_M{000003,3fc002,7f8001,bf4000,feffff}` (10) | 24 | the two edges the test places at kZNear; silicon draws them (z stored 0), we draw nothing | **#272**, low end of its affine z24 error (below) |
| `Depth_buffer_fixed_function/z24_C{n,y}_FZn_M000003` (2, not on #297's list) | 24 | the same 24 px, mirrored: silicon rejects them (z 8 >= 3), we draw them (z 0) | **#272**, same point |
| `Texture_BRDF/BRDF_e0_l0, _e0_l1, _e1_l0` (3) | 614 | a textured wedge in the bottom-right corner, silicon's only ink; we do not rasterise it | **#315** (opened by this lane; proposed row below) |
| scorer: `blank` rule, `score_sweep.py:229-230` | | fires on all 13 because the golden has > 4 colours | lane.toolsmith, change below |

Every figure is from run `1790359589-xbox-full6743-dry2-2802408` (thor, ref 84a67b9cf8,
apk a7b9d28e6b84, 2026-09-25). The same run on 09-14 (`z-repeat-c866527e03-*`, apk
6bf6a11955f3) gives identical pixel lists. Across 1,075 score TSVs on disk the DBFF rows
are 24 in 20 of 20 runs and BRDF is 614 in 7 of 7. The residuals are deterministic.

Reproduce:
- `locate_residuals.py <run>` gives the pixels, both censuses and the z24 under the edge.
  Output: `dry2.out`, `repeat-c866527e03.out`.
- `z24_sign_by_depth.py <run>` gives the signed z24 error by depth band. Output:
  `z24_sign_dry2.out`.
- `blank_rule_eval.py` runs today's rule and the proposed rule over every capture ever
  tagged `blank`. Output: `blank_rule_eval.out`.

## 1. Depth_buffer_fixed_function: the 24 px are the near-plane edges

The residual is the same 24 pixels in all 10 captures:

- `(502..509, 53)`, 8 px. This is the top row of the "right quad"
  (`depth_format_fixed_function_tests.cpp:189-216`): x from kRight-10 to kRight-2 = 502..510,
  top at kTop+5 = 53, `z_top = kZNear`. Golden colour ramps (0,128,0) to (97,128,97).
- `(136, 56..71)`, 16 px. This is the left column of the first small grid quad
  (`:113-155`). x_offset = kLeft+4+(384-376)/2 = 136, y_offset = 56, `z_left = kZNear`.
  Golden colour is (58,58,58), i.e. 0.25 + (-6/193)*0.75 = 0.2267, times 255.

Both are the only two edges in the scene that sit on the near plane. Silicon's colour is
the vertex colour at z_left/z_top, and ours is the black clear.

**Depth census, every one of the 10:** the golden keeps the cleared value M on 307,176 px
and stores **0** on these 24. Ours keeps M on all 307,200. The FZy scene is rejected
everywhere else on both sides, even at Mfeffff. That is not explained here, and it does not
need to be: both sides agree on it.

**The brief's falsifier does not fire as written.** The pixels are the same in all 10, but
they are at *minimum* depth (golden z24 = 0), not maximum. The fixed-point cells show they
are still #272's:

| cell (colour + _ZB, dry2) | edge px differing | z24 at the edge: golden, ours | at x=137 |
|---|---:|---|---|
| `z24_C?_FZn_M000003` | 24/24 (golden black, ours drawn) | **8**, **0** | 3, 3 (both clear) |
| `z24_C?_FZn_M{400002,800001,c00000,ffffff}` | 3/24 | **8**, **0** | 329575, 329568 |
| `z24_C?_FZy_M*` (the 10) | 24/24 (golden drawn, ours clear) | 0, M | M, M |
| `z16_*` (20 cells) | 3/24 | not decoded (RGB565) | |

The exact depth at a vertex on the near plane is 0. **Ours writes 0 there and silicon
writes 8.** With cutoff 3 in fixed point, silicon's 8 fails LESS and ours passes. That
gives the 24-px mirror residual in `FZn_M000003`, which #272's capture list does not name.
In float mode silicon stores 0, presumably 8 units flushed as an F24 subnormal (compare
`docs/investigations/f24-subnormal-flush-verified.md`), and 0 passes against any M. Ours
rejects the same fragments even against Mfeffff. The simplest reading is that our z there
is 0 *after a clamp*, i.e. at or below zero before it, which a float compare fails. That
reading is inferred, not measured.

**The signed error across #272's own captures** (`z24_sign_dry2.out`, only pixels both sides
wrote, identical in all 8 FZn _ZB cells that reach each band):

| golden z24 band | n (Mffffff) | ours - golden median | range |
|---|---:|---:|---|
| [0, 2^16) | 37 | **-8** | -8..-8 |
| [2^16, 2^20) | 329 | -7 | -8..-6 |
| [2^20, 2^22) | 1,156 | -6 | -8..0 |
| [2^22, 2^23) | 1,394 | -4 | -6..0 |
| [2^23, 3*2^22) | 2,178 | -1 | -4..+2 |
| [3*2^22, 15*2^20) | 5,516 | +1 | -1..+4 |
| [15*2^20, 2^24) | 136,846 | **+4** | -1..+6 |

This is one monotone curve from -8 at the near plane to +4..+6 near maximum. #272 filed
only its high end ("2-5 units high near maximum depth"). lane.zetaswap275
(`docs/lanes/zetaswap275/NOTES.md:56-70`) measured the same curve in coarser bands from the
same run. It could not tell whether the low half was ours or silicon's, because DBFF is ours
against silicon rather than against exact. **The near-plane edge settles that for one
point.** The exact value there is 0, ours is 0, and silicon is +8. So silicon has an additive
bias of about 8 units at w ~ 1 that no relative (1/w) error can produce, which fits
zetaswap275's report that 1,170 relative-rounding models all failed. It is a third held-out
point for #272's model, next to Swap (-4.04 at w=187) and ZetaIntoColor (-3.34 at w=199).

**Owner: #272.** Legs for #272's arm, when it has one: `z24_C?_FZn_M000003` 24 -> 0 if the
fix reproduces silicon's +8 at the near plane. `z24_C?_FZy_M*` 24 -> 0 if our float path
then passes those fragments. If the FZn pair moves and the FZy ten do not, the float path
has a defect of its own. File it then, with this table.

## 2. Texture_BRDF: a corner wedge silicon draws and we do not rasterise

The residual is the same 614 px in all three tests (`issue-19-58-at-tip-2026-09-12.md:100`
already recorded the shared mask). It is a right triangle at the bottom-right corner:
x 579..639, y 460..479, 1 px wide at row 460 and 61 at row 479, about 3 px more per row.
The golden census is complete: background (18,18,18) 304,186 + label 2,400 + this wedge 614
= 307,200. **Neither cube the test draws (`texture_brdf_tests.cpp:181-183`, at x = +/-1.5,
z = 2, camera at z = -7) appears on silicon or on ours.** The wedge colours are
(194,246,202..222) and (190,246,218..222): a BRDF-volume lookup with a varying B channel,
which is real textured geometry.

Two defects stack:

1. **`PS_TEXTUREMODES_BRDF` is unimplemented.** `hw/xbox/nv2a/pgraph/glsl/psh.c:3123-3128`
   emits `vec4 t2 = vec4(0.0)` and `NV2A_UNIMPLEMENTED`. The final combiners are TEX2 for
   colour and alpha (`texture_brdf_tests.cpp:97-98`), so a pixel we *did* rasterise there
   would come out (0,0,0,0).
2. **We do not rasterise the wedge.** Ours is the clear colour (18,18,18,254) on all
   614 px, not (0,0,0,0). The geometry that reaches the corner on silicon never reaches
   the framebuffer here.

Why silicon shows no cubes and only a corner wedge is **not established**. On paper
(PerspectiveVertexShader, fov pi/4, near 1, far 200) the cubes are in front of the camera
and centred. A wedge that runs off two screen edges is the shape #223's external wedge
produces for a triangle with one negative-w vertex. #223 folded at 8e683b3a26, *after*
every BRDF capture on disk; the newest is dry2 at 84a67b9cf8, which predates it. So:

**The discriminating run:** any Texture BRDF capture at a ref containing 8e683b3a26 (the
next full sweep will have one). Read pixel (639,479):
- (18,18,18,254): still not rasterised, so #223 is not the mechanism.
- (0,0,0,0): now rasterised, so #223 owns the geometry and only defect 1 is left.
- The golden is (194,246,2xx,255).

The differing count is 614 in both outcomes, so **a count cannot tell these apart.** Read
the pixel. No arm is registered, for the same reason: `ab_compare` scores `differing`, and
a must-not-move on 614 is blind to the one change that matters.

**Proposed tracker row for #315** (for the board; lanes do not edit `nv2a_issues.toml`):

```toml
[issue.315]
title = "Texture_BRDF: PS_TEXTUREMODES_BRDF unimplemented, and silicon's only ink (a 614-px corner wedge) is not rasterised"
disposition = "defect"
suites = ["Texture BRDF"]
status = "open"
status_note = "3 captures x 614 px, deterministic (7 of 7 runs 09-13..09-25). psh.c:3123 emits t2 = vec4(0). The wedge (x 579..639, y 460..479) is the clear colour on ours, not (0,0,0,0), so it is not rasterised either. Neither cube appears on silicon. Pixel (639,479) on a post-8e683b3a26 capture decides whether #223's wedge covers the geometry half. docs/lanes/cloud-297/NOTES.md section 2."
```

Games: low. BRDF texture mode is rare in shipped titles.

## 3. The scorer: key `blank` on what our capture lost

Today (`score_sweep.py:229-230`):

```python
blank = (counts.max() / flat.shape[0] > 0.90 and len(counts) <= 4
         and gold_colours > 4)
```

The only condition on the golden is "> 4 colours", and a golden that is 99% background
with a sliver of ink passes it. **Proposed:** keep the "ours is flat" half. Replace
`gold_colours > 4` with the ink our capture lost below the label band:

```python
BLANK_MIN_LOST = 0.01        # of the image; measured gap is 0.33% .. 21.33%
gdom = <golden's dominant rgb>;  odom = <ours' dominant rgb>
ink  = (g[..., :3] != gdom).any(axis=2);  ink[:LABEL_ROWS] = False
lost = ink & (o[..., :3] == odom).all(axis=2)
blank = (counts.max() / flat.shape[0] > 0.90 and len(counts) <= 4
         and lost.sum() >= BLANK_MIN_LOST * flat.shape[0])
```

Run over all 19 captures the current rule has ever tagged `blank`, 1,075 TSVs
(`blank_rule_eval.out`):

| capture | differing | lost | today | proposed |
|---|---:|---:|---|---|
| DBFF `z24_C?_FZy_M*` (10) | 24 | 8 (0.00%) | blank | ok |
| Texture_BRDF (3) | 614 | 614 (0.20%) | blank | ok |
| `Depth_buffer/DepthFmt_z16_C?_FZy_M00000f` (2) | 3,936 | 1,008 (0.33%) | blank | ok |
| `Texture_DXT/DXT1_plasma{,_alpha}_dxt1` (2) | 65,536 | 65,536 (21.33%) | blank | **blank** |
| `W_buffering/WBuf24D_FloorQuad_V0_ZB{0,1}_ZS1` (2) | ~230,400 | ~152,550 (49.7%) | blank | **blank** |

Every real blank stays blank and every near-exact capture is released. The gap is 65x, and
1% sits well inside it. **Side effect, not on #297's list:** the two `Depth_buffer` z16
M00000f rows also become `ok`, at 3,936 px. They were tagged `blank` in one run only, and
nobody has checked who owns them.

The DBFF "lost" is 8, not 24, because the label band hides 16 of the edge pixels
(rows 53..63). That is harmless for this rule. It is also why a region rule and a pixel
list must not be mixed up.

`score_sweep.py` is lane.toolsmith's. This lane did not edit it.

## Do not repeat

- #297's body says the rule fires "because the goldens are >= 99% one colour". The code
  tests *our* capture for flatness and the golden only for "> 4 colours". The fix belongs
  on the golden-side clause.
- Do not go looking for the DBFF residual near maximum depth. It is at z = 0.
- Do not judge a BRDF arm by its differing count (section 2).
- The FZy scene rejection away from the edges agrees on both sides. It is not a residual,
  and nothing here explains it.
