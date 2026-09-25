# lane.zdepth272 -- #272 (+#275): silicon's fixed-function depth arithmetic

Status: **derived, priced and hunk written; arm not registered because `vsh-ff.c` is held.**
Base: master @ 8af1bbb18e. Analysis only on this branch: no `hw/` file edited.
The hunk is `vsh-ff-zrtz.patch`. It applies to master and merges cleanly over
lane.wparamcode223's #321.

## Result in one paragraph

Silicon computes the fixed-function screen z with **every step rounded toward zero (RTZ)**:
the z-column products, their sums, w, a 24-bit reciprocal of w, and the final
`z_clip * rcp(w)`. We round every step to nearest (RNE), and our GPU does `z * rcp(w)`, not a
divide. That one difference explains:
- the whole #272 curve: ours−silicon is −8 at the near plane and +4 near max depth;
- #275's Swap: silicon is 4 below exact;
- ZetaIntoColor's depth word: 3 below exact;
- cloud-297's near-plane 8.

The mechanism is visible in the matrix. With the XDK default matrices, the composite's z
column has one live product, `z_clip = z*C22 + C32`, with C22 = 16,861,522 and
**C32 = 6*C22 + 4** (float32 replay of the test's own matrix code). At the near plane
(z = −6), `−6*C22 = −101,169,132` is an exact float32 tie at ULP 8. RNE rounds it to
−101,169,136, so z_clip = 0 and we store 0. RTZ rounds it to −101,169,128, so z_clip = 8, and
**silicon stores 8.**

## The arithmetic

    p   = RTZ24(z * C22)            (and the x, y products: 0 here)
    zc  = RTZ24(p + C32)            (sums RTZ)
    w   = RTZ24(z*C23 + C33)        (= z + 7 here)
    r   = RTZ24(1 / w)              (reciprocal, truncated to 24 bits)
    zs  = RTZ24(zc * r)             -> the rasteriser interpolates zs screen-linearly and floors

The replay is `dbff.py` plus `model.py`. Vertices snap with `trunc(16*(x+0.53125))/16` onto
pixel-centre half-integers, so a 16-px quad samples depth at exactly t = k/16. There is no
sub-pixel ambiguity to fit.

### How it was chosen: training on DBFF, held out on the rest

1. **Our own model first.** RNE throughout with `z*rcp(w)` reproduces our capture of
   `z24_Cn_FZn_Mffffff_ZB` exactly on the bottom, right and big quads, and on 299,795 of
   307,200 px overall. The rest is ±1 where our GPU's rcp is off by a ULP. The same replay
   matches our z16 FZn and FZy captures on 307,200/307,200. So the instrument sees what we
   draw.
2. **The search** (`search.py`) scored the two `z24_C?_FZn_Mffffff_ZB` goldens only.
   Candidates: mul/add ∈ {RNE, RTZ}, final ∈ {RNE, RTZ, exact}, and divide or rcp with rcp ∈
   {RNE, RTZ, exact} × {22..25} bits (156 models). Exact pixels out of 294,912 drawn:

   | model | exact px | Σ\|d\| |
   |---|---:|---:|
   | **all RTZ, rcp RTZ 24-bit** | **199,042** | 102,916 |
   | all RTZ, rcp RTZ 25-bit | 146,092 | 158,276 |
   | all RTZ, rcp RTZ 23-bit | 138,862 | 180,930 |
   | ours (all RNE, true divide) | ~4,400 | ~1.0 M |

3. **Held out** (never used to choose). All three land on silicon's stored word:

   | point | w | exact | ours (RNE) | RTZ model | silicon |
   |---|---:|---:|---:|---:|---:|
   | near plane (DBFF edge, cloud-297) | 1 | 4.0 | 0 | **8** | 8 |
   | `Color_zeta_overlap/Swap` | 187 | 16,771,353.45 | 0xFFE91A | **0xFFE916** | 0xFFE916 |
   | `ZetaIntoColor` depth word | 199 | 16,776,790.75 | 0xFFFE57 | **0xFFFE54** | 0xFFFE54 |
   | `ColorIntoZeta` (depth never shown, see below) | 7 | 14,452,733.71 | 14,452,734 | 14,452,732 | (mixture) |

   zetaswap275's "exact" values assumed an ideal matrix. The values above use the float32
   matrix the XBE actually uploads, which is why they differ from its table by about 0.6.

4. **Per-vertex check** (`vfit.py`). Silicon's depth at each of 644 vertices is fitted
   (least squares on column medians, region not point). Median silicon − RTZ model by w band
   is −0.22 at w=1 and |≤0.13| for every band from 1 to 195. Silicon − exact over the same
   bands runs +3.8 → −3.9.

### What the model does not capture: the reciprocal sits slightly low

About 17% of vertices are one reciprocal-ULP below the model. `vcand.py` shows the cause:
this happens where the truncated 1/w was already very close to the true value.

| remainder of RTZ(1/w), ULP | vertices | model matches | model−1 rcp-ULP matches |
|---|---:|---:|---:|
| [0.0, 0.1) | 59 | 20% | 73% |
| [0.1, 0.2) | 56 | 45% | 38% |
| [0.2, 0.3) | 70 | 66% | 20% |
| ≥ 0.5 | 311 | 78–89% | 0–2% |

So silicon's reciprocal is an approximation up to about 0.3 ULP below 1/w, then truncated. It
is **not** a constant deficit. Any constant from 1/16 to 1/4 ULP gains at most 5% on training,
and every one of them breaks the near-plane point: RCP(1) must be exactly 1, and
nxdk_vsh_tests' `ILU_RCP` on silicon confirms rcp(1)=1. Those constants also break
ZetaIntoColor from 1/8 up. Modelling the approximation needs silicon's reciprocal algorithm,
for example an RCP sweep on the console. This is the stated residual below; do not fit it
with a constant.

## Priced, every depth capture on disk

The scoreboard run `z-c866527e03-023-*`, the newest sweep `0-a-now-8e683b3a26-*` and dry2
`1790359589-*` are **identical** on every row (`price.out`). "After" is the pure model replay.
In brackets is the conservative transfer: our capture + (model − our model). All counts are
the scorer's `differing`, which equals raw word inequality here.

| capture (×2 = Cn and Cy) | now | after | moved away |
|---|---:|---:|---:|
| `z24_C?_FZn_Mffffff_ZB` | 144,566 | **47,935** (53,852) | 309 |
| `z24_C?_FZn_Mc00000_ZB` | 4,834 | 989 (1,037) | 85 |
| `z24_C?_FZn_M800001_ZB` | 2,868 | 520 (568) | 16 |
| `z24_C?_FZn_M400002_ZB` | 1,506 | 113 (145) | 0 |
| `z24_C?_FZn_M000003` and `_ZB` | 24 | **0** | 0 |
| `z24_C?_FZy_M*_ZB` (10) | 24 | **0** | 0 |
| `z24_C?_FZy_M*` colour (10) | 24 | **3** | 0 |
| `z16_C?_FZn_M00ffff_ZB` | 2,840 | 424 (456) | 0 |
| `z16_C?_FZn_M{004002,008001,00c000}_ZB` | 16 / 32 / 32 | **0** | 0 |
| `z16_C?_FZy_M00ffff_ZB` | 495 | **392** | 0 |
| `z16_C?_FZy_M{008001,00c000}_ZB` | 13 / 34 | **0** | 0 |
| `z16_C?_FZ?_M000003_ZB`, `z16_C?_FZy_M004002_ZB` (exact today) | 0 | 0 | 0 |
| `z24_C?_FZn_Mffffff` colour | 43,005 | 43,004 | 0 |
| `z16_C?_FZn_M00ffff` colour | 42,966 | 42,957 | 0 |
| other DBFF colour captures | unchanged | unchanged | 0 |
| `Color_zeta_overlap/Swap` | 165,447 | **0** | 0 |

Totals, pure replay:
- DBFF `_ZB`: 314,760 → 100,746 over both compression halves (−214,014).
- DBFF colour: −278 (139 per half).
- Swap: −165,447.

**About −380k px in all.**
**No capture on disk moves the wrong way beyond the "moved away" column.** Those are pixels
where the model's exact floor lands one off a golden that sits in silicon's own ±1 edge walk
or on the reciprocal tail; each capture is still net better by a wide margin.

Out-of-sample strength: nothing z16 was used to fit. The z16 fixed and float cells move
**only toward** the golden (2,384 of 2,384, and 103 of 103). The z24 FZy edge (stored 0,
drawn) is predicted without reference to it. Our near-plane z there is −6.0e23 under RNE,
which a float compare rejects, and exactly 0 under RTZ. That confirms cloud-297's inference.

### What it cannot see (named, not priced)

- **`W_buffering/ZBuf24D_FloorQuad_V0_*_ZB`** (FF, z-buffer): ours−gold is +1/+2 on
  154–162k px per capture near max depth, the sign of this defect. Only z*C22 is live there
  (y = 0, C02 = 0), so the same mechanism applies. The quad crosses the near plane, though,
  and the clipper's arithmetic is not replayed, so the magnitude is unpriced. It is on the arm
  as `must_not_regress`, predicted better.
- **`W_buffering/WBuf*_V0`** reads `vtxPos.w`, which the hunk does not touch. WBuf24F
  FloorQuad V0 has a +1..+4 signature suggesting silicon's w also truncates, but that is W
  buffering (#266, lane.wbufdepth24) and deliberately out of scope here.
- **ColorIntoZeta_ZB / ZetaIntoColor**: our capture shows the colour word where silicon's
  shows a colour/depth mixture (#91's colour-wins). Our depth value is not visible, so the
  model moves neither.
- **Dot-product order** for more than one nonzero product (tilted cameras): silicon's
  accumulation order is unmeasured. The hunk uses x, y, z, w sequential RTZ. Every capture
  priced here has one live product.
- **Programmable shaders** (`vsh-prog.c`): not touched and not measured.
- **Depth_Clamp `*_VSH0`**, Depth_function, Stencil*, ZPass_pixel_count: not replayed. Their
  current `_ZB` residuals (`survey_zb.out`) are not this signature. They are on the arm as
  `must_not_regress`.

## The hunk, per holder

**Only `hw/xbox/nv2a/pgraph/glsl/vsh-ff.c`, function `pgraph_glsl_gen_vsh_ff`.** `psh.c` is
not needed: its D24/D16 `zfloor` is already the exact floor of the interpolated vertex z
(#16/#52), and only the vertex z feeding it was wrong. lane.wbufdepth24 is unaffected.

`vsh-ff-zrtz.patch`, +87 lines, two insertions:

1. After the `GLSL_DEFINE(texPlane…)` header block (master line 767), GLSL helpers:
   - `ffTwoProd`: Dekker, no fma, `precise`, as psh.c's floor already assumes.
   - `ffMulRtz`, `ffAddRtz` (TwoSum), `ffDotRtz`: step one ULP toward zero when the exact
     error points there.
   - `ffRcpRtz`: `1.0/w` corrected by the exact residual to the largest r with |w|·r ≤ 1,
     three steps each way.
   - `ffScreenZ(p)`: `RTZ(dot(p, cm[2])) * rcpRtz(clampAwayZeroInf(RTZ(dot(p, cm[3]))))`.
2. After the position block (master line 1015, after #321's carry block), one statement:
   `vtxPos.z = ffScreenZ(tPosition)` for finite tPosition. **Only `vtxPos.z` changes.**
   `oPos` (the GL clip position), `vtxPos.w` (W buffering, perspective-correct varyings) and
   x/y are untouched.

**Proven offline.** `verify_glsl.py` transcribes the GLSL op for op into numpy float32 (RNE,
unfused) and compares it with exact-rational RTZ:
- 0 mismatches over 93,080 vertex cases: 4 depth formats × every DBFF vertex, Swap, ZIC and
  4,000 random z, each with the host reciprocal forced −2..+2 ULP off;
- 0 mismatches over 60,000 random mul/add/rcp operands.

Two steps of correction were not enough at +2 ULP (8,148 mismatches); three are.

GLSL context checked: `c[]` uniforms are emitted before the FF header, `clampAwayZeroInf` is
defined before it, and `precise` is already used unconditionally by psh.c under the same
`pgraph_glsl_append_version`. **Not checked:** an actual shader compile. There is no
glslang on the host; the arm's build and first draw are that check.

**Merge.** `git merge-file` of #321's `vsh-ff.c` (lane/wparamcode223) with this patch: 0
conflicts. The hunks are disjoint, so either can fold first.

## The arm (to register once vsh-ff.c is granted, after the last rebase)

a_ref = the tip the fix commit sits on; b_ref = the fix commit (`git apply vsh-ff-zrtz.patch`).
Disc: Depth_buffer_fixed_function, Color_zeta_overlap, W_buffering, Depth_buffer,
Depth_Clamp, Depth_function, Stencil, Stencil_func, ZPass_pixel_count, Clear, Blend_surface,
Surface_format.

    docs/testing/ab_compare.py --register docs/testing/predictions/zdepth272-rtz.json \
      --who lane.zdepth272 --issue 272 --a-ref <A> --b-ref <B> --disc-from <A result dir> \
      --prediction "FF screen z RTZ (see docs/lanes/zdepth272/NOTES.md)" \
      --expect-value 'Color_zeta_overlap/Swap=0' \
      --expect-value 'Depth_buffer_fixed_function/z24_C?_FZn_M000003=0' \
      --expect-value 'Depth_buffer_fixed_function/z24_C?_FZn_M000003_ZB=0' \
      --expect-value 'Depth_buffer_fixed_function/z24_C?_FZy_M*_ZB=0' \
      --expect-value 'Depth_buffer_fixed_function/z24_C?_FZy_M??????=3' \
      --expect-value 'Depth_buffer_fixed_function/z16_C?_FZn_M00[48c]00?_ZB=0' \
      --expect-value 'Depth_buffer_fixed_function/z16_C?_FZn_M000003_ZB=0' \
      --expect-value 'Depth_buffer_fixed_function/z16_C?_FZy_M00[048c]00?_ZB=0' \
      --expect-value 'Depth_buffer_fixed_function/z16_C?_FZy_M00ffff_ZB=392' \
      --must-not-move 'Blend_surface/*' --must-not-move 'Surface_format/*' \
      --must-not-move 'W_buffering/WBuf*' --must-not-move 'W_buffering/*_V1_*' \
      --must-not-move 'Depth_buffer/*' \
      --must-not-move 'Color_zeta_overlap/ColorIntoZeta*' \
      --must-not-move 'Color_zeta_overlap/ZetaIntoColor*' \
      --must-not-move 'Color_zeta_overlap/Swap_ZB' --must-not-move 'Color_zeta_overlap/Adjacent*'

Legs `ab_compare --register` cannot express, to go in the prose and be judged by reading the
table:
- `must_not_regress`: `z24_C?_FZn_M{400002,800001,c00000,ffffff}_ZB`,
  `z16_C?_FZn_M00ffff_ZB`, every other DBFF capture, `W_buffering/ZBuf*_V0_*`, Depth_Clamp,
  Depth_function, Stencil, Stencil_func, ZPass_pixel_count, Clear.
- Stated bands:

  | capture | predicted | band (pure .. delta) |
  |---|---|---|
  | `z24_C?_FZn_Mffffff_ZB` | 144,566 → 47,935 | 47,935 .. 53,852 |
  | `…Mc00000_ZB` | 4,834 → 989 | 989 .. 1,037 |
  | `…M800001_ZB` | 2,868 → 520 | 520 .. 568 |
  | `…M400002_ZB` | 1,506 → 113 | 113 .. 145 |
  | `z16_C?_FZn_M00ffff_ZB` | 2,840 → 424 | 424 .. 456 |

  A value outside its band means the replay's assumption failed: that the host's arithmetic
  plus the three-step correction gives exact RTZ, and that interpolation is psh.c's exact
  floor.

(`--must-not-regress` is not a flag of `ab_compare --register` today; the JSON has a
`must_not_regress` list that the judge reads. Add it by hand to the registered file before
committing it, or ask lane.toolsmith for the flag.)

**Failing worlds.**
- The Swap leg lands but an exact z16 row moves: the z16 exact-today `_ZB` legs above are
  `=0`.
- W_buffering `WBuf*` or any `_V1_` row moves: the hunk touched w or the programmable path.
- `Depth_buffer/*` moves: programmable passthrough was reached.
- The FZy colour legs read 0 instead of 3: our colour interpolation changed, and that is not
  this hunk.

Read `scores1.tsv` `status` for `unreadable` on every leg, and read the run log for PARTIAL
COVERAGE, before believing any `=0`.

## Do not repeat

- Do not fit a constant reciprocal deficit (1/16..1/4 ULP). It gains ≤5% on training and
  breaks rcp(1) = 1, which silicon measurably has.
- Do not model Swap/ZIC with an ideal (real-valued) matrix. The uploaded float32 matrix
  (C32 = 6·C22 + 4) is what produces the near-plane 8, and it moves every "exact" value by
  about 0.6.
- zetaswap275's 1,170 models all rounded the product to nearest. The product's rounding is
  the first-order term: it is the whole near-plane 8.
- Point samples on the steep near-plane quads are about 329k units per pixel. Only region
  fits (`vfit.py`) or exact-t replay (`dbff.py`) mean anything there.
- The DBFF grid in this suite is 18×18 quads of 16 px, x0 = 136 + 20i, y0 = 56 + 20j.
  `depth_exact_floor.py`'s geometry (8×8 at 134 + 12i) is the other Depth buffer suite.

## Files

`mat.py` matrix replay · `model.py` rounding model · `dbff.py` frame replay · `search.py` training
search · `vfit.py`/`vcand.py` per-vertex fits · `price.py`/`price_f16.py`/`after.py` pricing ·
`fzy.py` float-cell edge · `survey.py` (+`survey_zb.out`) other depth suites · `verify_glsl.py`
hunk transcription check · `vsh-ff-zrtz.patch` the hunk · `price.out` pricing output.
