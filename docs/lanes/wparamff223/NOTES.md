# lane.wparamff223 -- #223: the ff bitri and ff quad families of W_param

Brief: price offline whether vsh-ff.c's divide, carried homogeneously as the
prog path does, brings ff bitri (1,145,823 px) and ff quad (494,632 px) to the
goldens. Derive a two-negative rule for ff quads if one is needed. Change
geom.c only for that rule.

**Outcome (2026-09-25): analysis-only.** The quads need a vsh-ff.c hunk and
nothing in geom.c. The bitri rows need that hunk plus a geom.c rule the brief
does not grant: a one-negative triangle with zero grid area draws nothing.
Both are named below with their prices. geom.c is unchanged, and no
prediction is registered, because this lane changes no code.

Tools, both in this directory, rerun in about a minute:

- `homog_price.py`: silicon's model. float32 viewport transform
  `X = x + 320w`, then exact 2D-homogeneous rasterisation (M^-1 p >= 0 at
  pixel centres), scored as coverage against the golden with label pixels
  excluded. `--negzero-positive` reads a w of -0 as +0.
- `ff_port.py`: a float32 port of the vsh-ff.c position tail
  (vsh-ff.c:878-887), `--model today|carry`. For each vertex it reports
  gl_Position and v_vtxPos, and whether they are finite. For each triangle it
  reports what geom.c's `append_wedge()` gate does with it. It prices the
  region an ideal host clipper draws from that gl_Position.

## 1. The premise was half wrong: tri1 is degenerate on silicon too

wparamclip223 section 9 inferred that ff's divide collapses tri1, whose N
lands on P1-P2 at (320,240), and that silicon keeps it. The goldens say
otherwise.

- **tri1 draws nothing.** On `ff_..._bitri_w-1.88e-37` the golden is one red
  strip. It starts on the edge (240,320)-(400,160) and runs to the lower
  right, bounded by the rays in direction (1,1) from P1 and P2.
- **The strip is tri2's external wedge.** tri2's negative vertex vb =
  (80*2^64, 80*2^64, w = 2^64 m) projects to about -80/m px, which is 1e35 to
  inf in direction (-1,-1). So the wedge Q + t(Q - vb) is that strip.
- **The same geometry predicts the quads.** Each ff quad half (v0, P1, vb) and
  (v0, vb, P2) has two negative w. The w > 0 part of such a half projects to
  the cone at the positive vertex P spanned by (P - N1) and (P - N2). For the
  extreme rows those are the two red cones in the quad golden: at (400,160)
  spanned by (1,-1) and (1,1), and at (240,320) spanned by (-1,1) and (1,1).

`homog_price.py` scores this model against every golden in both families:

| family | today (Thor C, coverage xor G) | model S (default) | model S, ff w -0 read as +0 |
|---|---:|---:|---:|
| ff bitri (20 rows) | 601,984 | 97,671 | **2,401** |
| ff quad (20 rows) | 494,500 | 77,547 | **1,547** |
| prog bitri (20) | 0 | **0** | 271,198 |
| prog quad (20) | 0 | **0** | 221,632 |

- **The residual is edge ties.** Every ff row is at most 240 px with -0 read
  as +0. The positive-w rows, which we draw correctly today, carry the same
  32-240 px. That is the model's closed edges, not geometry.
- **Why -0 differs between the paths.** The two -0 exceptions are the w-inf
  rows: v0 has w = kMinW / -inf = -0. On ff, w goes through the composite
  multiply: w' = x*0 + y*0 + z*0 + w*1, and the nv2a multiply gives +0 for
  zero times anything. So a -0 w arrives positive. On prog, `MOV oPos, v0`
  keeps the sign. The prog columns show that exactly: -0 kept is 0, -0
  flipped is 271k and 221k.

**Falsifier (brief): not refuted.** The extreme ff bitri rows (w-0.00,
-1.50e-36, -1.88e-37, -3.76e-37, -7.52e-37) come to 240 px each under the
homogeneous model, down from ~146k. The cause is different from the brief's,
though. It is not tri1's divide. It is tri2's vertex at infinity, which the
divide overflows (section 2), plus tri1's degenerate triangle, which the
Adreno paints (section 3).

## 2. What our divide loses: tri2's vertex, and snapping past 2^124

`ff_port.py --model today --verbose` shows, for tri2's vb:

- w-0.00 and -1.88e-37: `x/w + 320` overflows float32, so the vertex is at
  -inf px.
- -1.50e-36, -3.76e-37 and -7.52e-37: `x/w` is finite, between 5e37 and 2e38.
  But `roundScreenCoords` computes `pos * 16`, which overflows past 2^124, and
  `(2 * pos - size)` overflows past 2^127. So v_vtxPos and gl_Position are
  +-inf.
- -0.96e-34 and -3.08e-33: finite everywhere, with vb at about 8e35 and 2.5e34
  px.

gl_Position is non-finite on exactly the rows Thor gets wrong, and finite on
the two it gets right in coverage for the quads (-0.96e-34 and -3.08e-33 at
314 px).

**The natural experiment:** on those two finite rows, **the Adreno host
clipper draws tri2 correctly**, even though `append_wedge()` refuses it
(`host(area)`: its NDC cross product overflows at 2^240). In the capture the
strip is white, that is cyan plus red added, where the golden is red. On
-1.88e-37, where tri2 is at inf, the strip is cyan only, so tri2 was dropped:

| region (Thor capture, today) | -0.96e-34 (tri2 finite) | -1.88e-37 (tri2 inf) | golden |
|---|---|---|---|
| strip | 65.6k white (cyan + red) | 70.9k cyan | 68k red |
| half-plane minus strip | 79.0k cyan | 79.0k cyan | background |

So once gl_Position is finite, the host clipper handles tri2 (one negative)
and both quad halves (two negative). **No two-negative rule is needed in
geom.c.** The quads' w > 0 cone is exactly what the host clipper computes, as
the 20 `prog_..._quad` rows at 0 show. The ff quads fail only because their
vb reaches the clipper non-finite.

## 3. What remains on bitri: the Adreno paints degenerate tri1 as a half-plane

The cyan half-plane x + y > 560 (79,002 px) is the same on every extreme
bitri row, whether tri2 is finite or not, so it is tri1's.

- **What tri1 is.** v0 has x = -80 * 2^-64 and w = kMinW / m, which is
  -2^55 to -2^64. After the divide, the viewport add and the snap, it sits at
  exactly (320,240), the midpoint of P1-P2. Its gl_Position is (-0, -0, w). Its
  homogeneous determinant is exactly 0 in float32, as it is on silicon, whose
  viewport add `x + 320w` loses x.
- **What each side draws.** Silicon draws nothing. `append_wedge()` refuses
  tri1 (zero area), and the Adreno clipper paints a half-plane.
- **w_gaps is the same defect.** `w_gaps` and `w_gaps_tex_persp` (145,687 px
  each, unchanged by #250) show a cyan half-plane over the lower right where
  the golden has only 1-px lines. #250 section 5 found that all of w_gaps'
  one-negative triangles have zero area on the 1/16 grid.

## 4. The two hunks, and what each is worth

### (A) vsh-ff.c, in the position tail at vsh-ff.c:878-887: requested, not edited

vsh-ff.c belongs to lane.shadetie224b (PR #263). The hunk:

```c
     mstring_append(body,
     "  oPos = tPosition * compositeMat;\n"
+    /* nv2a's multiply gives 0 for 0 * anything (vsh-prog.c _MUL); GLSL's
+     * gives NaN for 0 * inf, which a w of +-inf puts in x, y and z. Only
+     * taken for a non-finite input, so finite vertices are bit-identical. */
+    "  if (any(isinf(tPosition)) || any(isnan(tPosition))) {\n"
+    "    mat4 cm = compositeMat;\n"
+    "    for (int j = 0; j < 4; j++) {\n"
+    "      vec4 p = tPosition * cm[j];\n"
+    "      for (int i = 0; i < 4; i++) {\n"
+    "        if (tPosition[i] == 0.0 || cm[j][i] == 0.0) p[i] = 0.0;\n"
+    "      }\n"
+    "      oPos[j] = p.x + p.y + p.z + p.w;\n"
+    "    }\n"
+    "  }\n"
     "  oPos.w = clampAwayZeroInf(oPos.w);\n"
-    "  oPos.xy /= oPos.w;\n"
-    "  oPos.xy += c[" stringify(NV_IGRAPH_XF_XFCTX_VPOFF) "].xy;\n"
+    "  vec2 hPos = oPos.xy;\n"
+    "  vec2 scrPos = oPos.xy / oPos.w + c[" stringify(NV_IGRAPH_XF_XFCTX_VPOFF) "].xy;\n"
+    "  oPos.xy = scrPos;\n"
     "  oPos.xy = roundScreenCoords(oPos.xy);\n"
     "  vec4 vtxPos = vec4(oPos.xy, oPos.z / oPos.w, oPos.w);\n"
     "  oPos.z = oPos.z / clipRange.y;\n"
     "  oPos.xy = (2.0 * oPos.xy - surfaceSize) / surfaceSize;\n"
     "  oPos.xy *= oPos.w;\n"
+    /* roundScreenCoords is the identity for |pos| >= 2^19, and pos * 16
+     * overflows past 2^124: there, carry the position homogeneously, as
+     * the rasteriser receives it, instead of through the divide. */
+    "  bvec2 carry = not(lessThan(abs(scrPos), vec2(524288.0)));\n"
+    "  oPos.xy = mix(oPos.xy, 2.0 * hPos / surfaceSize\n"
+    "      + (2.0 * c[" stringify(NV_IGRAPH_XF_XFCTX_VPOFF) "].xy / surfaceSize - 1.0) * oPos.w,\n"
+    "      carry);\n"
     );
```

- **Must-not-move argument.** The multiply branch runs only on a non-finite
  input. The carry runs only where |pos| >= 2^19 or pos is not finite, and
  there snapping was already the identity, so no in-range vertex changes a
  bit.
- **Not compiled.** `compositeMat` is a macro that expands to a `mat4(...)`
  constructor (common.h:94), which is why the hunk binds it to `cm`. The
  owning lane should run it through `geom_dump`/glslc as #235 did.
- **The bvec `mix` is a select.** Its unselected operand may be inf or NaN
  (GLSL 4.50, section 8.3). That is deliberate here, and the float `mix` that
  vsh-prog.c warns about is a different overload.

Priced with `ff_port.py --model carry` under an ideal clipper: **ff bitri
1,601 and ff quad 2,126 coverage px** (today's port: 560,372 and 494,273). All
40 rows end at 0 to 235 px.

- **Without the 0 * x = 0 branch** (`--no-nvmul`) it is 128,829 and 178,517.
  The w-inf, winf, w0.00 and quad w-0.00 rows need it.
- **On Thor, (A) alone should move:**
  - the quads: w-0.00, -1.50e-36, -1.88e-37, -3.76e-37 and -7.52e-37, from
    79,174 px each to about 314 (the finite rows' value today);
  - quad w0.00 (72,012) and quad winf (25,600) to near 0;
  - bitri w-inf (114,508) to near 0 (tri2 takes the wedge, and tri1 is
    positive);
  - so about 490k of the 494,632 quad px, plus about 114k on bitri.
- **Bitri extreme rows:** (A) alone makes tri2 drawable, but tri1's
  half-plane stays, so they stay at about 146k like -0.96e-34 does today.
  bitri w-0.00 could get **worse**, 68k to about 146k. Today its tri1 is
  dropped by NaN, and a finite degenerate tri1 would be painted. (A) should
  therefore land with (B), or with the bitri rows judged by hand.

### (B) geom.c `append_wedge()`: a one-negative triangle with zero grid area draws nothing (not granted to this lane)

- **The rule.** Exactly one w < 0, every q finite, and `kahan_det` on
  `pz[i].xy` exactly 0 and finite: emit nothing and return true, instead of
  falling back to the host.
- **Why silicon draws nothing.** Silicon rasterises the snapped grid position.
  The w > 0 part of a triangle whose three projected points are collinear
  projects to a line.
- **What it is worth.**
  - Alone: bitri -0.96e-34 and -3.08e-33 go from ~146k to ~0, because tri2 is
    drawn correctly already. The four overflow rows go from ~146k to ~72k,
    with the strip still missing until (A).
  - Probably also `w_gaps` and `w_gaps_tex_persp`, 145,687 each. That is a
    lead: the golden's 1-px lines there may be those triangles on silicon, so
    run the port on w_gaps first.
  - With (A): bitri extreme rows at about 160-240 coverage.

## For the next lane

- **Do not build a two-negative rule in geom.c.** The host clipper already
  draws the cone correctly whenever gl_Position is finite (ff quad -0.96e-34
  and -3.08e-33 at 314, and all 20 prog quads at 0).
- **Do not chase tri1's divide.** tri1 is degenerate on silicon too. The ~146k
  is tri1's half-plane on the Adreno plus tri2 missing.
- **Before (B):** run `ff_port.py`'s gate on every capture a must-not-move glob
  covers, especially `w_gaps*`, as wparamclip223 section 5 learned. Count what
  the capture draws inside the discarded triangles' region; a zero-area
  one-negative triangle that today draws a line the golden also has would
  move.
- The Adreno does not produce NaN for 0 * inf the way the "today" port does:
  bitri w0.00 draws its strip, 253 px of coverage. So the "today" port is
  right on which rows are non-finite through the divide, but not on the NaN
  rows. Price those from captures.
- Do not rebuild a w scale (wparamgeom223). `rcc_w_zero_inf` is a different
  mechanism.
