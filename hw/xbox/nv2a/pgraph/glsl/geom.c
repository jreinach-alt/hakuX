/*
 * Geforce NV2A PGRAPH GLSL Shader Generator
 *
 * Copyright (c) 2015 espes
 * Copyright (c) 2015 Jannik Vogel
 * Copyright (c) 2020-2025 Matt Borgerson
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */

#include "qemu/osdep.h"
#include "hw/xbox/nv2a/pgraph/pgraph.h"
#include "hw/xbox/nv2a/pgraph/prim_rewrite.h"
#include "geom.h"

void pgraph_glsl_set_geom_state(PGRAPHState *pg, GeomState *state)
{
    state->polygon_front_mode = (enum ShaderPolygonMode)GET_MASK(
        pgraph_reg_r(pg, NV_PGRAPH_SETUPRASTER),
        NV_PGRAPH_SETUPRASTER_FRONTFACEMODE);
    state->polygon_back_mode = (enum ShaderPolygonMode)GET_MASK(
        pgraph_reg_r(pg, NV_PGRAPH_SETUPRASTER),
        NV_PGRAPH_SETUPRASTER_BACKFACEMODE);

    state->smooth_shading = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_3),
                                     NV_PGRAPH_CONTROL_3_SHADEMODE) ==
                            NV_PGRAPH_CONTROL_3_SHADEMODE_SMOOTH;

    state->primitive_mode = pgraph_prim_rewrite_get_draw_mode(
        (enum ShaderPrimitiveMode)pg->primitive_mode,
        state->polygon_front_mode, !state->smooth_shading);

    state->z_perspective = pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0) &
                           NV_PGRAPH_CONTROL_0_Z_PERSPECTIVE_ENABLE;
    state->noperspective = !(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0) &
                             NV_PGRAPH_CONTROL_0_TEXTUREPERSPECTIVE);
    state->aa_offset_x = pgraph_anti_aliasing_sample_offset_x(pg);
    for (int i = 0; i < 4; i++) {
        /* The bit only takes effect on an axis in WRAP address mode:
         * TextureWrapMode's CYLWRAP tile wraps U (WRAP) and leaves V
         * (MIRROR) interpolated the long way round. */
        uint32_t a = pgraph_reg_r(pg, NV_PGRAPH_TEXADDRESS0 + i * 4);
        bool u = GET_MASK(a, NV_PGRAPH_TEXADDRESS0_ADDRU) ==
                 NV_PGRAPH_TEXADDRESS0_ADDRU_WRAP;
        bool v = GET_MASK(a, NV_PGRAPH_TEXADDRESS0_ADDRV) ==
                 NV_PGRAPH_TEXADDRESS0_ADDRU_WRAP;
        bool p = GET_MASK(a, NV_PGRAPH_TEXADDRESS0_ADDRP) ==
                 NV_PGRAPH_TEXADDRESS0_ADDRU_WRAP;
        state->cylinder_wrap[i] =
            ((u && (a & NV_PGRAPH_TEXADDRESS0_WRAP_U)) ? 1 : 0) |
            ((v && (a & NV_PGRAPH_TEXADDRESS0_WRAP_V)) ? 2 : 0) |
            ((p && (a & NV_PGRAPH_TEXADDRESS0_WRAP_P)) ? 4 : 0) |
            ((a & NV_PGRAPH_TEXADDRESS0_WRAP_Q) ? 8 : 0);
    }
}

bool pgraph_glsl_need_geom(const GeomState *state)
{
    /* FIXME: Missing support for 2-sided-poly mode */
    assert(state->polygon_front_mode == state->polygon_back_mode);

    switch (state->primitive_mode) {
    case PRIM_TYPE_LINES:
    case PRIM_TYPE_TRIANGLES:
    case PRIM_TYPE_TRIANGLES_ADJACENCY:
        return true;
    default:
        return false;
    }
}

/*
 * #223: a filled triangle with EXACTLY ONE negative-w vertex N, drawn as
 * silicon draws it -- the external wedge -- rather than handed to the host
 * clipper.
 *
 * The wedge is where the w > 0 part of the homogeneous triangle projects:
 * every point of it is N + mu * (Q - N) for Q on the edge P1-P2 and mu >= 1,
 * so it lies across P1-P2 from N, between the rays N->P1 and N->P2 continued
 * past P1 and P2.  It depends on the screen positions alone, never on how
 * large the w values are.  The host clipper finds the same region by cutting
 * the triangle at w = 0, and that cut is what fails: at |w| ratios of 2^120
 * and more (W_param's prog_w_zero_inf__bitri_w-0.00 and w-1.88e-37 to
 * w-7.52e-37) Adreno draws nothing where silicon draws the wedge, and
 * llvmpipe draws the triangle's interior instead, so which answer you get is
 * the driver's.  The offline model of the wedge covers every one of the 13
 * negative-w prog_w_zero_inf__bitri goldens with 0 coverage mismatch
 * (docs/lanes/wparamclip223/wedge_price.py).
 *
 * So build the wedge here and emit it with w > 0 inside the surface, where
 * no host clipper has anything to cut:
 *
 *   - NDC q_i = gl_Position.xy / w, and the screen barycentrics lambda(p) of
 *     the triangle (q0, q1, q2).  In the wedge lambda_N <= 0 and the other two
 *     are >= 0, and mu = 1 - lambda_N.
 *   - the quadrilateral P1, N + K(P1 - N), N + K(P2 - N), P2 with K twice the
 *     largest mu over the surface's corners, which holds all of the wedge
 *     that is on screen; then Sutherland-Hodgman against the four surface
 *     edges, NDC +/-1.  Four vertices and four clips is eight at most, which
 *     is this path's max_vertices, and well inside the 18 vk/instance.c
 *     checks the device against.  P1 and P2 are copied, never recomputed, so
 *     the edge the two wedges of a W_param bitri share is the same exact edge
 *     in both, and the host's tie rule still gives each centre on it to one.
 *   - at each vertex p the homogeneous weights alpha_i = lambda_i / w_i, all
 *     >= 0 in the wedge, sum s.  The perspective-correct value of a varying at
 *     p is sum(alpha_i A_i) / s and 1/w there is s, so the vertex carries
 *     w' proportional to 1/s and those normalised weights -- the rasteriser
 *     then interpolates A/w' and 1/w' linearly across screen, which is the
 *     same field the triangle had.  NOPERSPECTIVE varyings take lambda
 *     itself, which is affine in screen.  Depth is written by the fragment
 *     shader, so z only has to be the triangle's plane: z/w = sum(lambda_i
 *     z_i / w_i).
 *   - w' is normalised to at most 1 and held at >= 2^-64 of that: the
 *     weights can span 2^128, and A/w' at 2^128 overflows a float.  Holding
 *     it moves where a varying hands over from one vertex's value to
 *     another's by less than 2^-64 of the polygon.
 *
 * Winding: the host clipper's polygon for this triangle runs P1, P2, then out
 * along P2's ray and back along P1's, which winds opposite to the screen
 * triangle (N, P1, P2) -- the sign of the homogeneous determinant.  The strip
 * below is emitted so that it winds the same way, so a culled draw culls
 * exactly what it culled before.
 *
 * A one-negative triangle whose q are finite and whose grid area is exactly
 * zero, with every |pz| < 2^19, returns true having emitted nothing: its
 * three snapped points are collinear, so the w > 0 part projects to a line
 * and silicon draws nothing (W_param ff bitri tri1 at the extreme
 * multipliers, and w_gaps, where the host clipper painted a half-plane).
 *
 * Anything else this cannot do exactly -- no negative w, two or three of
 * them, a screen triangle of zero area, or any non-finite value -- returns
 * false BEFORE emitting a vertex, and the caller emits the triangle
 * unchanged, as it always has.  Two negative vertices: the host clipper keeps the w > 0
 * part, the region round the positive vertex; three: nothing.  Both are left
 * alone -- W_param's prog and ff quads (two negative w in each half) are the
 * control, and they already match silicon.
 *
 * "Zero area" is decided on the 1/16 px grid, from v_vtxPos (pz[i].xy), the
 * screen position the vertex shader truncated and silicon rasterises -- not
 * from q_i.  q_i is (ndc * w) / w, which is not ndc again for w = -0.9, so
 * two vertices on the same grid point come back an ulp apart and the exact
 * test on q passes a triangle with no area.  Its "wedge" then spans the
 * screen (W_param's w_gaps: the -0.9 and -10.9 vertices share a grid point
 * with an infinite-w neighbour; silicon draws nothing there, and the arm
 * with the q test drew 11.7k px each in w_gaps and w_gaps_tex_persp).
 */
static void append_wedge(MString *output, const GeomState *state,
                         GenGeomGlslOptions opts)
{
    mstring_append(
        output,
        "int wedge_clip(inout vec2 P[8], int np, bool y, float bound) {\n"
        "  vec2 Q[8];\n"
        "  int nq = 0;\n"
        "  for (int i = 0; i < np; i++) {\n"
        "    int j = (i + 1 == np) ? 0 : i + 1;\n"
        "    float da = sign(bound) * (bound - (y ? P[i].y : P[i].x));\n"
        "    float db = sign(bound) * (bound - (y ? P[j].y : P[j].x));\n"
        "    if (da >= 0.0 && nq < 8) {\n"
        "      Q[nq] = P[i]; nq++;\n"
        "    }\n"
        "    if (((da < 0.0) != (db < 0.0)) && nq < 8) {\n"
        "      vec2 c = mix(P[i], P[j], da / (da - db));\n"
        "      if (y) { c.y = bound; } else { c.x = bound; }\n"
        "      Q[nq] = c; nq++;\n"
        "    }\n"
        "  }\n"
        "  for (int i = 0; i < nq; i++) {\n"
        "    P[i] = Q[i];\n"
        "  }\n"
        "  return nq;\n"
        "}\n"
        "\n"
        "float wedge_cross(vec2 a, vec2 b) {\n"
        "  return a.x * b.y - a.y * b.x;\n"
        "}\n"
        "\n");

    mstring_append(output,
                   "void emit_wedge_vertex(vec3 a, vec4 pos, mat4 pz) {\n"
                   "  gl_Position = pos;\n");
    if (!opts.gles) {
        mstring_append(output,
                       "  gl_PointSize = gl_in[0].gl_PointSize;\n");
    }
    static const char *const colours[] = { "vtxD0", "vtxD1", "vtxB0",
                                            "vtxB1" };
    for (int i = 0; i < 4; i++) {
        const char *c = colours[i];
        if (state->smooth_shading) {
            mstring_append_fmt(output,
                               "  %s = a.x * v_%s[0] + a.y * v_%s[1] +"
                               " a.z * v_%s[2];\n",
                               c, c, c, c);
        } else {
            /* Flat: the provoking vertex, gl_in[0], as emit_vertex(). */
            mstring_append_fmt(output, "  %s = v_%s[0];\n", c, c);
        }
    }
    mstring_append(output,
                   "  vtxFog = dot(a, vec3(v_vtxFog[0], v_vtxFog[1],"
                   " v_vtxFog[2]));\n"
                   "  vtxFogSpecial = v_vtxFogSpecial[0];\n");
    for (int i = 0; i < 4; i++) {
        uint8_t w = state->cylinder_wrap[i];
        if (w) {
            char bv[64];
            snprintf(bv, sizeof(bv), "bvec4(%s, %s, %s, %s)",
                     (w & 1) ? "true" : "false", (w & 2) ? "true" : "false",
                     (w & 4) ? "true" : "false", (w & 8) ? "true" : "false");
            mstring_append_fmt(
                output,
                "  vtxT%d = a.x * cylWrap(v_vtxT%d[0], v_vtxT%d[0], %s) +\n"
                "          a.y * cylWrap(v_vtxT%d[0], v_vtxT%d[1], %s) +\n"
                "          a.z * cylWrap(v_vtxT%d[0], v_vtxT%d[2], %s);\n",
                i, i, i, bv, i, i, bv, i, i, bv);
        } else {
            mstring_append_fmt(output,
                               "  vtxT%d = a.x * v_vtxT%d[0] + a.y * v_vtxT%d[1]"
                               " + a.z * v_vtxT%d[2];\n",
                               i, i, i, i);
        }
    }
    mstring_append(
        output,
        "  vtxPos0 = pz[0];\n"
        "  vtxPos1 = pz[1];\n"
        "  vtxPos2 = pz[2];\n"
        "  triMZ = (isnan(pz[3].x) || isinf(pz[3].x)) ? 0.0 : pz[3].x;\n"
        "  vtxPointSize = dot(a, vec3(v_vtxPointSize[0], v_vtxPointSize[1],"
        " v_vtxPointSize[2]));\n"
        "  EmitVertex();\n"
        "}\n"
        "\n");

    mstring_append_fmt(
        output,
        "bool wedge_bad(float v) {\n"
        "  return isnan(v) || isinf(v);\n"
        "}\n"
        "\n"
        "bool emit_wedge(mat4 pz) {\n"
        "  vec3 w = vec3(gl_in[0].gl_Position.w, gl_in[1].gl_Position.w,\n"
        "                gl_in[2].gl_Position.w);\n"
        "  bvec3 neg = lessThan(w, vec3(0.0));\n"
        "  if (int(neg.x) + int(neg.y) + int(neg.z) != 1) { return false; }\n"
        "  vec2 q[3];\n"
        "  vec3 zq;\n"
        "  for (int i = 0; i < 3; i++) {\n"
        "    q[i] = gl_in[i].gl_Position.xy / w[i];\n"
        "    zq[i] = gl_in[i].gl_Position.z / w[i];\n"
        "    if (wedge_bad(q[i].x) || wedge_bad(q[i].y) || wedge_bad(zq[i])) {\n"
        "      return false;\n"
        "    }\n"
        "  }\n"
        "  int n = neg.x ? 0 : (neg.y ? 1 : 2);\n"
        "  vec2 N = q[n];\n"
        "  vec2 P1 = q[(n + 1) %% 3];\n"
        "  vec2 P2 = q[(n + 2) %% 3];\n"
        "  float area = wedge_cross(q[1] - q[0], q[2] - q[0]);\n"
        "  vec2 g1 = pz[1].xy - pz[0].xy;\n"
        "  vec2 g2 = pz[2].xy - pz[0].xy;\n"
        "  float garea = kahan_det(g1.x, g2.y, g2.x, g1.y);\n"
        /* Zero area on the grid: silicon draws nothing, and the host would
         * paint a half-plane or the like from the ulp-off q.  Only below
         * 2^19, where pz is the snapped grid and its differences are exact;
         * a vertex at 1e35 px swallows the others' offsets. */
        "  vec2 pmax = max(max(abs(pz[0].xy), abs(pz[1].xy)), abs(pz[2].xy));\n"
        "  if (garea == 0.0 && max(pmax.x, pmax.y) < 524288.0) { return true; }\n"
        "  if (!(abs(garea) > 0.0) || wedge_bad(garea)) { return false; }\n"
        "  if (!(abs(area) > 0.0) || wedge_bad(area)) { return false; }\n"
        /* mu = 1 - lambda_N; the corners bound it over the surface. */
        "  float mu = 1.0;\n"
        "  for (int c = 0; c < 4; c++) {\n"
        "    vec2 k = vec2((c & 1) == 0 ? -1.0 : 1.0, c < 2 ? -1.0 : 1.0);\n"
        "    mu = max(mu, 1.0 - wedge_cross(P1 - k, P2 - k) / area);\n"
        "  }\n"
        "  float K = 2.0 * mu;\n"
        "  vec2 P[8];\n"
        "  P[0] = P1;\n"
        "  P[1] = N + K * (P1 - N);\n"
        "  P[2] = N + K * (P2 - N);\n"
        "  P[3] = P2;\n"
        "  if (wedge_bad(K) || wedge_bad(P[1].x) || wedge_bad(P[1].y) ||\n"
        "      wedge_bad(P[2].x) || wedge_bad(P[2].y)) {\n"
        "    return false;\n"
        "  }\n"
        "  int np = 4;\n"
        "  np = wedge_clip(P, np, false, 1.0);\n"
        "  np = wedge_clip(P, np, false, -1.0);\n"
        "  np = wedge_clip(P, np, true, 1.0);\n"
        "  np = wedge_clip(P, np, true, -1.0);\n"
        "  vec3 A[8];\n"
        "  float S[8];\n"
        "  float Z[8];\n"
        "  float smin = 3.4e38;\n"
        "  for (int k = 0; k < np; k++) {\n"
        "    vec2 p = P[k];\n"
        "    vec3 lam = vec3(wedge_cross(q[1] - p, q[2] - p),\n"
        "                    wedge_cross(q[2] - p, q[0] - p),\n"
        "                    wedge_cross(q[0] - p, q[1] - p)) / area;\n"
        "    vec3 al = max(lam / w, vec3(0.0));\n"
        "    S[k] = al.x + al.y + al.z;\n"
        "    A[k] = %s;\n"
        "    Z[k] = dot(lam, zq);\n"
        "    if (!(S[k] > 0.0) || wedge_bad(S[k]) || wedge_bad(Z[k]) ||\n"
        "        wedge_bad(A[k].x) || wedge_bad(A[k].y) || wedge_bad(A[k].z)) {\n"
        "      return false;\n"
        "    }\n"
        "    smin = min(smin, S[k]);\n"
        "  }\n"
        /* A strip over a convex polygon, 0, n-1, 1, n-2, ...: its triangles
         * wind opposite to the polygon's order, and the polygon runs P1, far
         * P1, far P2, P2, so the strip winds as the host clipper's did. */
        "  for (int k = 0; k < np; k++) {\n"
        "    int j = ((k & 1) == 0) ? (k >> 1) : (np - 1 - (k >> 1));\n"
        "    float W = max(smin / S[j], 5.421011e-20);\n"
        "    emit_wedge_vertex(A[j], vec4(P[j] * W, Z[j] * W, W), pz);\n"
        "  }\n"
        "  EndPrimitive();\n"
        "  return true;\n"
        "}\n",
        state->noperspective ? "lam" : "al / S[k]");
}

MString *pgraph_glsl_gen_geom(const GeomState *state, GenGeomGlslOptions opts)
{
    /* FIXME: Missing support for 2-sided-poly mode */
    assert(state->polygon_front_mode == state->polygon_back_mode);
    enum ShaderPolygonMode polygon_mode = state->polygon_front_mode;

    bool need_triz = false;
    bool need_linez = false;
    bool need_wedge = false;
    const char *layout_in = NULL;
    const char *layout_out = NULL;
    const char *body = NULL;
    const char *provoking_index = state->smooth_shading ? "index" : "0";
    /*
     * #224: a flat, filled quad arrives as triangles-with-adjacency,
     * (a, v3, b, v3, c, v3) -- see flat_quad_adjacency() in prim_rewrite.c.
     * The triangle is slots 0, 2, 4 and v3 sits in slot 1, so every flat
     * varying comes from slot 1, vtxFogSpecial included: it is `flat` in
     * every shade mode, and slot 1 is the v3 the old v3-first triangles
     * handed a first-vertex-provoking rasteriser.
     */
    bool adjacency = state->primitive_mode == PRIM_TYPE_TRIANGLES_ADJACENCY;
    if (adjacency) {
        assert(!state->smooth_shading && polygon_mode == POLY_MODE_FILL);
        provoking_index = "1";
    }

    /*
     * #13: silicon's wide line is NOT the perpendicular rectangle the API's
     * native line draws, so generate the footprint here instead of asking
     * for a line width.  The rule is derived and independently reproduced
     * against the goldens -- 20,946 clean cuts, 100.0000% exact on BOTH
     * endpoints, 0 wrong, of which 12,056 are widths <= 5 that no #13
     * derivation had ever looked at (docs/investigations/line-extent-phase.md,
     * docs/testing/line_extent_phase.py).  Three discrete choices, no fitted
     * constant:
     *
     *   1. vertex screen coordinates truncate to 1/16 px.  ALREADY DONE, in
     *      roundScreenCoords() in vsh.c, and v_vtxPos carries the truncated
     *      value -- so this stage inherits choice 1 for free and must widen
     *      from v_vtxPos rather than from gl_Position.
     *   2. the MINOR-axis extent is E = w * (max + min/2) / max, with max and
     *      min the larger and smaller of |dx|, |dy|.  This is the
     *      alpha-max-plus-beta-min hypot approximation, evaluated in fixed
     *      point.
     *   3. a pixel is lit iff its CENTRE lies in the LOW-OPEN band
     *      (c - E/2, c + E/2] around the edge centre c at that scanline.
     *
     * Rivals on the same cuts: tie-break variants 95.3-95.4%, snap variants
     * 98.5-99.4%, beta=1 63.1%, Bresenham 58.6%, and the perpendicular
     * rectangle we drew until now 74.0%.
     *
     * VULKAN ONLY.  The GL renderer keeps the native glLineWidth path: the
     * parameters below arrive as a push constant, which has no GL spelling,
     * and gl/shaders.c is another lane's file.  A GL-only fix would read the
     * same lineParams from a plain uniform; nothing here forecloses it.
     *
     * A POLYGON MODE DECIDES NOTHING FOR A LINE PRIMITIVE, and reading the
     * test below by its name cost this lane an arm.  state->primitive_mode
     * is the OUTPUT mode: pgraph_prim_rewrite_get_output_mode() maps
     * LINE_LOOP and LINE_STRIP to PRIM_TYPE_LINES whatever polygon_mode
     * says, and only QUADS/QUAD_STRIP/POLYGON consult it.  So a draw that
     * set NV097_SET_FRONT_POLYGON_MODE_V_FILL can still land in the widened
     * path, and one does: the Line_width suite's Fill_0000/0001/0032
     * captures are named for that FILL mode and draw a 16-segment LINE_LOOP
     * at the suite's line width alongside their five filled blocks.  Every
     * pixel of those goldens that depends on LINE_WIDTH is the loop's --
     * 12,021 of 12,021 between Fill_0000.0 and Fill_0032.0, bar 59 in the
     * guest's printed label (line_cap_phase.py --fills, audit finding N4).
     */
    bool widen_lines =
        opts.vulkan && (state->primitive_mode == PRIM_TYPE_LINES ||
                        (state->primitive_mode == PRIM_TYPE_TRIANGLES &&
                         polygon_mode == POLY_MODE_LINE));

    switch (state->primitive_mode) {
    case PRIM_TYPE_POINTS: return NULL;
    case PRIM_TYPE_LINES:
        need_linez = true;
        layout_in = "layout(lines) in;\n";
        layout_out = widen_lines ?
            "layout(triangle_strip, max_vertices = 6) out;\n" :
            "layout(line_strip, max_vertices = 2) out;\n";
        body = "  emit_line(0, 1, 0.0);\n";
        break;
    case PRIM_TYPE_TRIANGLES:
        need_triz = true;
        layout_in = "layout(triangles) in;\n";
        if (polygon_mode == POLY_MODE_FILL) {
            /* 8: the external wedge of emit_wedge() below, a quadrilateral
             * clipped by four surface edges, or the triangle itself. */
            need_wedge = true;
            layout_out = "layout(triangle_strip, max_vertices = 8) out;\n";
            body = "  mat4 pz = calc_triz(0, 1, 2);\n"
                   "  if (emit_wedge(pz)) { return; }\n"
                   "  emit_vertex(0, pz, gl_in[0].gl_Position);\n"
                   "  emit_vertex(1, pz, gl_in[1].gl_Position);\n"
                   "  emit_vertex(2, pz, gl_in[2].gl_Position);\n"
                   "  EndPrimitive();\n";
        } else if (polygon_mode == POLY_MODE_LINE) {
            need_linez = true;
            /*
             * 18 is the largest max_vertices this generator can emit -- three
             * edges times SIX vertices per widened line, up from four when the
             * cap clip made the footprint a hexagon rather than a
             * parallelogram -- and it is what
             * vk/instance.c checks the device's maxGeometryOutputVertices and
             * maxGeometryTotalOutputComponents against at device init, and
             * what it build-asserts against the Vulkan required minimums.
             * RAISING IT, or adding a varying to pgraph_glsl_get_vtx_header()
             * in glsl/common.c, means updating PGRAPH_GEOM_MAX_OUTPUT_VERTICES
             * / PGRAPH_GEOM_VTX_COMPONENTS there.  A geometry shader that
             * overruns a device limit fails to compile, and a failed compile
             * on the Vulkan path draws NOTHING rather than raising an error
             * (audit finding L10).
             */
            layout_out = widen_lines ?
                "layout(triangle_strip, max_vertices = 18) out;\n" :
                "layout(line_strip, max_vertices = 6) out;\n";
            /* Silicon's edge order for a triangle rasterised in
             * POLY_MODE_LINE, derived from the Line_width goldens on
             * 225,558 decisive pixels (#13, docs/investigations/
             * line-width-residual.md): for a triangle (a, b, c) it paints
             * the edge OPPOSITE a, then opposite b, then opposite c --
             * (b,c), (c,a), (a,b).  The last one painted wins where two
             * wide edges overlap, and that is what the goldens measure.
             *
             * This block, not the driver, is what decides the order: a
             * TRIANGLES draw under POLY_MODE_LINE keeps PRIM_TYPE_TRIANGLES
             * through pgraph_prim_rewrite_get_output_mode() and is
             * decomposed here.  #13's derivation assumed Turnip ordered it
             * and therefore priced the fix as a rewrite-to-LINES change;
             * measuring our own emitted order refuted that.
             *
             * Note this also reorders TRIANGLE_STRIP and TRIANGLE_FAN,
             * because GeomState::primitive_mode is the REWRITTEN mode and
             * cannot tell a fan triangle from a list triangle.  That used to
             * cost the fan: it arrived here already rotated by emit_tri_pv()
             * placing the provoking vertex at index 0, which left TFan at
             * 70.36% of its decisive pixels where Tri reached 100.00%, and
             * this comment recorded that undoing it in prim_rewrite.c would
             * collide with flat shading's need for the provoking vertex at
             * index 0.
             *
             * SUPERSEDED, and deliberately corrected here rather than only in
             * the PR that changed it: prim_rewrite.c's
             * pv_placement_observable() now gates that rotation on
             * `flat_shading || polygon_mode != POLY_MODE_LINE`, so under a
             * SMOOTH wireframe the fan arrives UNROTATED, in the same
             * (hub, v1, v2) order a TRIANGLES draw arrives in, and the one
             * edge order derived here fits both.  The collision was real but
             * narrower than stated -- it is only the flat-shaded wireframe
             * corner, which is the predicate's first term.  TFan and
             * QStrip/TFan reach 100.00% with the rest; see
             * docs/lanes/primpv13/NOTES.md for the arm.  (#13's older
             * "32,628 decisive pixels" for the residue is the POPULATION of
             * those two classes under the perpendicular footprint model this
             * emulator stopped drawing in 80c23dcabe; the pixels actually
             * naming the wrong edge were 8,920.)
             */
            body = "  float dz = calc_triz(0, 1, 2)[3].x;\n"
                   "  emit_line(1, 2, dz);\n"
                   "  emit_line(2, 0, dz);\n"
                   "  emit_line(0, 1, dz);\n";
        } else {
            assert(polygon_mode == POLY_MODE_POINT);
            layout_out = "layout(points, max_vertices = 3) out;\n";
            body = "  mat4 pz = calc_triz(0, 1, 2);\n"
                   "  emit_vertex(0, mat4(pz[0], pz[0], pz[0], pz[3]), gl_in[0].gl_Position);\n"
                   "  EndPrimitive();\n"
                   "  emit_vertex(1, mat4(pz[1], pz[1], pz[1], pz[3]), gl_in[1].gl_Position);\n"
                   "  EndPrimitive();\n"
                   "  emit_vertex(2, mat4(pz[2], pz[2], pz[2], pz[3]), gl_in[2].gl_Position);\n"
                   "  EndPrimitive();\n";
        }
        break;
    case PRIM_TYPE_TRIANGLES_ADJACENCY:
        need_triz = true;
        layout_in = "layout(triangles_adjacency) in;\n";
        layout_out = "layout(triangle_strip, max_vertices = 3) out;\n";
        body = "  mat4 pz = calc_triz(0, 2, 4);\n"
               "  emit_vertex(0, pz, gl_in[0].gl_Position);\n"
               "  emit_vertex(2, pz, gl_in[2].gl_Position);\n"
               "  emit_vertex(4, pz, gl_in[4].gl_Position);\n"
               "  EndPrimitive();\n";
        break;
    default:
        assert(false);
        return NULL;
    }

    assert(layout_in);
    assert(layout_out);
    assert(body);
    MString *output = mstring_new();
    pgraph_glsl_append_version(output, opts.vulkan, opts.gles,
                               opts.gles_version);
    if (widen_lines) {
        /*
         * (2/surfaceWidth, 2/surfaceHeight, line width in guest px, one
         * rasteriser subpixel quantum in guest px).  The first two undo
         * vsh.c's screen->NDC map so a screen-space offset can be put back
         * into clip space; nothing else in this stage knows the surface size,
         * and nothing in it knows the device's subPixelPrecisionBits either.
         * Offset 0, 16 bytes, GEOMETRY stage -- the same range
         * create_pipeline() and create_push_descriptor_resources() in the
         * Vulkan renderer declare unconditionally, with the vertex stage's
         * inline-attribute range moved up past it.
         */
        mstring_append(output,
                       "layout(push_constant) uniform GeomPushConstants {\n"
                       "    vec4 lineParams;\n"
                       "};\n"
                       "#define lineNdcScale lineParams.xy\n"
                       "#define lineHalfExtentScale (0.5 * lineParams.z)\n"
                       "#define lineTieBias lineParams.w\n"
                       "\n");
    }

    mstring_append_fmt(output,
                       "%s"
                       "%s"
                       "\n"
                       "#define v_vtxPos v_vtxPos0\n"
                       /* Cylinder wrap (NV097_SET_TEXTURE_ADDRESS WRAP_U/V/P/Q):
                        * the coordinate is interpolated the short way round
                        * the unit cylinder, so a vertex more than half a turn
                        * from the first vertex's value moves by a whole turn
                        * before interpolation.  D3D's texture-wrap render
                        * state; TextureWrapMode's CYLWRAP tile. */
                       "vec4 cylWrap(vec4 ref, vec4 c, bvec4 on) {\n"
                       "  vec4 d = c - ref;\n"
                       "  vec4 adj = vec4(greaterThan(d, vec4(0.5))) - vec4(lessThan(d, vec4(-0.5)));\n"
                       "  return c - adj * vec4(on);\n"
                       "}\n"
                       "\n",
                       layout_in, layout_out);
    pgraph_glsl_get_vtx_header(output, opts.vulkan, state->smooth_shading,
                               state->noperspective, true, true, true);
    pgraph_glsl_get_vtx_header(output, opts.vulkan, state->smooth_shading,
                               state->noperspective, false, false, false);

    char tex_lines[4][160];
    /* The same four assignments for a vertex that lies a fraction t of the
     * way along a line rather than on one of its endpoints -- the cap clip's
     * cut point.  cylWrap() is a per-vertex adjustment against gl_in[0]'s
     * coordinate, so the two adjusted values are what interpolates, exactly
     * as the rasteriser interpolates them between two adjusted corners. */
    char tex_lerp[4][320];
    for (int i = 0; i < 4; i++) {
        uint8_t w = state->cylinder_wrap[i];
        if (w) {
            const char *u = (w & 1) ? "true" : "false";
            const char *v = (w & 2) ? "true" : "false";
            const char *p = (w & 4) ? "true" : "false";
            const char *q = (w & 8) ? "true" : "false";
            snprintf(tex_lines[i], sizeof(tex_lines[i]),
                     "  vtxT%d = cylWrap(v_vtxT%d[0], v_vtxT%d[index], bvec4(%s, %s, %s, %s));\n",
                     i, i, i, u, v, p, q);
            snprintf(tex_lerp[i], sizeof(tex_lerp[i]),
                     "  vtxT%d = mix(cylWrap(v_vtxT%d[0], v_vtxT%d[i0], bvec4(%s, %s, %s, %s)),\n"
                     "               cylWrap(v_vtxT%d[0], v_vtxT%d[i1], bvec4(%s, %s, %s, %s)), t);\n",
                     i, i, i, u, v, p, q, i, i, u, v, p, q);
        } else {
            snprintf(tex_lines[i], sizeof(tex_lines[i]),
                     "  vtxT%d = v_vtxT%d[index];\n", i, i);
            snprintf(tex_lerp[i], sizeof(tex_lerp[i]),
                     "  vtxT%d = mix(v_vtxT%d[i0], v_vtxT%d[i1], t);\n",
                     i, i, i);
        }
    }

    if (widen_lines) {
        /*
         * Screen (guest pixels, already truncated to 1/16 by
         * roundScreenCoords) back to clip space.  vsh.c's map is
         * ndc = (2 * screen - surfaceSize) / surfaceSize, i.e.
         * ndc = screen * lineNdcScale - 1, and gl_Position is that times w.
         * z and w come from the source vertex unchanged: the widening is a
         * pure screen-space displacement, and a line's depth does not vary
         * across its width.
         *
         * aaScreen(s) is the anti-aliasing sample shift (pgraph.h) that
         * vsh.c adds to gl_Position: screen came from v_vtxPos, which is
         * taken before that shift, so a footprint rebuilt from it must add
         * it again or a CC2 line would sit a quarter pixel left of the
         * triangles around it.  Added in guest px, before the map, where it
         * is exact on the 1/16 grid.  The identity at 0.
         */
        if (state->aa_offset_x != 0.0f) {
            mstring_append_fmt(output,
                       "#define aaScreen(s) ((s) + vec2(%f, 0.0))\n",
                       state->aa_offset_x);
        } else {
            mstring_append(output, "#define aaScreen(s) (s)\n");
        }
        mstring_append(output,
                       "vec4 line_clip(int index, vec2 screen) {\n"
                       "  vec4 p = gl_in[index].gl_Position;\n"
                       "  return vec4((aaScreen(screen) * lineNdcScale - 1.0)"
                       " * p.w,\n"
                       "              p.z, p.w);\n"
                       "}\n");
        /*
         * The same map for a vertex that is not an endpoint.  The cap clip
         * below cuts one corner off each end of the footprint, and the cut
         * point on the LONG side sits a fraction t of the way down the line,
         * so it has no source vertex to take z and w from.
         *
         * TWO QUANTITIES, AND BOTH ARE LINEAR IN SCREEN SPACE -- this is not
         * the perspective-correct rule the varyings follow.  1/w is affine in
         * window coordinates, and so is window-space depth, which is what the
         * rasteriser interpolates across a primitive.  So the cut vertex must
         * carry
         *
         *     1/w    = mix(1/wa, 1/wb, t)
         *     z_clip = w * mix(za/wa, zb/wb, t)
         *
         * -- one factor of 1/w inside the mix and one w outside, not two of
         * each.  A vertex carrying those leaves the depth over both
         * sub-polygons exactly as the unclipped parallelogram had it, and,
         * because 1/w is then right, leaves every perspective-correct varying
         * right as well.
         *
         * Interpolating z perspective-correctly instead -- which is what this
         * did until audit finding H1 -- agrees only when wa == wb.  At
         * wa = 1, wb = 4 with endpoint NDC depths 0.2 and 0.8 it reads 0.32 at
         * the screen midpoint where the true value is 0.50, so the cap of a
         * wide line sorts against other geometry differently from the body of
         * the same line, and z can leave [-w, w] and invoke clipping the
         * parallelogram never met.  Nothing here reads depth -- the offline
         * model scores ink coverage -- so the check is explicit:
         * `line_cap_phase.py --depth`, which evaluates this expression
         * against the screen-space lerp and trips on the old one.
         *
         * At w0 == w1 -- all 2D content, the Line_width suite included -- it
         * collapses to the plain screen-space lerp.
         */
        mstring_append(output,
                       "vec4 line_clip_lerp(int i0, int i1, float t,\n"
                       "                    vec2 screen) {\n"
                       "  vec4 pa = gl_in[i0].gl_Position;\n"
                       "  vec4 pb = gl_in[i1].gl_Position;\n"
                       "  float ia = 1.0 / pa.w;\n"
                       "  float ib = 1.0 / pb.w;\n"
                       "  float q = mix(ia, ib, t);\n"
                       "  float w = 1.0 / q;\n"
                       "  float z = mix(pa.z * ia, pb.z * ib, t) * w;\n"
                       "  return vec4((aaScreen(screen) * lineNdcScale - 1.0)"
                       " * w,\n"
                       "              z, w);\n"
                       "}\n"
                       "\n");
        if (!state->noperspective) {
            mstring_append(output,
                       /* The perspective-correct line parameter for the same
                        * point, which is what the varyings interpolate by
                        * while they carry the default `smooth` qualifier.
                        * Under NOPERSPECTIVE they do not, and this is not
                        * emitted: see emit_line_vertex(). */
                       "float line_lerp_t(int i0, int i1, float t) {\n"
                       "  float ia = 1.0 / gl_in[i0].gl_Position.w;\n"
                       "  float ib = 1.0 / gl_in[i1].gl_Position.w;\n"
                       "  return (t * ib) / mix(ia, ib, t);\n"
                       "}\n");
        }
    }

    /*
     * vtxFogSpecial is `flat` in EVERY shade mode (glsl/common.c), so the
     * value that reaches the fragment shader is the one the provoking output
     * vertex carried -- and the cap clip below moves which vertex that is.
     * The widened-line path therefore emits through emit_vertex_fs(), whose
     * second argument names the flat source separately from the vertex being
     * emitted, and gives every vertex of one footprint the same source; then
     * no output convention can be observed.  Everything else is unchanged,
     * and the non-widened path still generates the three-argument
     * emit_vertex() verbatim.
     */
    const char *emit_vertex_sig =
        widen_lines ? "void emit_vertex_fs(int index, int fs, mat4 pz,\n"
                      "                    vec4 pos) {\n"
                    : "void emit_vertex(int index, mat4 pz, vec4 pos) {\n";
    const char *fog_special_index = widen_lines ? "fs" :
                                    adjacency   ? provoking_index :
                                                  "index";

    mstring_append_fmt(
        output,
        "%s"
        "  gl_Position = pos;\n",
        emit_vertex_sig);
    if (!opts.gles) {
        mstring_append(output,
            "  gl_PointSize = gl_in[index].gl_PointSize;\n");
    }
    mstring_append_fmt(
        output,
        "  vtxD0 = v_vtxD0[%s];\n"
        "  vtxD1 = v_vtxD1[%s];\n"
        "  vtxB0 = v_vtxB0[%s];\n"
        "  vtxB1 = v_vtxB1[%s];\n"
        "  vtxFog = v_vtxFog[index];\n"
        "  vtxFogSpecial = v_vtxFogSpecial[%s];\n"
        "%s%s%s%s"
        "  vtxPos0 = pz[0];\n"
        "  vtxPos1 = pz[1];\n"
        "  vtxPos2 = pz[2];\n"
        "  triMZ = (isnan(pz[3].x) || isinf(pz[3].x)) ? 0.0 : pz[3].x;\n"
        "  vtxPointSize = v_vtxPointSize[index];\n"
        "  EmitVertex();\n"
        "}\n",
        provoking_index,
        provoking_index,
        provoking_index,
        provoking_index,
        fog_special_index,
        tex_lines[0], tex_lines[1], tex_lines[2], tex_lines[3]);

    if (widen_lines) {
        /*
         * A vertex of the widened footprint that is not one of the line's two
         * endpoints.  Only the cap clip's cut point on the long side is one,
         * and only when the clip bites: at t == 0 or t == 1 this hands
         * straight back to emit_vertex_fs() with the endpoint's own index, so
         * the unclipped four-corner case emits exactly what it emitted
         * before, bit for bit, rather than an arithmetically-equal mix().
         *
         * That is a statement about the case where the clip does not bite,
         * NOT about narrow lines: until the half-pixel deadband in cap_clip()
         * the clip bit on lines as narrow as w = 0.625, where the offline
         * model says no pixel can change, and the device disagreed with the
         * model eight captures' worth.  The deadband is what ties the two
         * together; read it before trusting this paragraph about any
         * particular width.
         *
         * WHICH VARYINGS ARE INTERPOLATED IS THE QUALIFIER TABLE IN
         * glsl/common.c, NOT THE SHADE MODE.  Only vtxD0/D1/B0/B1 follow the
         * shade mode; vtxFog, vtxT0..T3 and vtxPointSize carry `smooth` (or
         * `noperspective`) unconditionally and are interpolated even under
         * flat shading, so the cut vertex must carry their interpolated value
         * in BOTH arms below.  Pinning them to an endpoint -- which is what
         * this did until audit finding H2 -- hands a flat-shaded textured wide
         * line the texture coordinate from the far end of the line over the
         * two triangles that touch the cap, and drops the cylWrap()
         * adjustment with it.
         *
         * THE FLAT SOURCE IS DECIDED ONCE FOR THE WHOLE FOOTPRINT, on both
         * paths.  vtxD0/D1/B0/B1 under flat shading come from gl_in[0], which
         * prim_rewrite.c has already made the guest's provoking vertex
         * (needs_rewrite() rewrites a LINES draw exactly when it is flat and
         * PROVOKING_VERTEX_LAST).  vtxFogSpecial is `flat` in every shade mode
         * and comes from i0 here and from emit_vertex_fs()'s `fs` argument
         * there.  Since every vertex of one footprint then carries the same
         * value, the pipeline's own provoking convention -- first-vertex,
         * because nothing in vk/ enables VK_EXT_provoking_vertex -- cannot be
         * observed, and a flat-shaded wide line does not change colour
         * depending on how many corners the clip happened to cut.  The
         * four-corner strip got that by accident (both its triangles provoked
         * from the i0 side); the hexagon's does not, which is audit finding
         * M1.
         *
         * THE INTERPOLATION PARAMETER FOLLOWS THE SAME TABLE.  Under
         * state->noperspective the rasteriser interpolates those varyings
         * linearly in SCREEN space, so the value the unclipped parallelogram
         * produced at the cut point is the one at the screen fraction tl;
         * otherwise it is the perspective-correct value at
         * line_lerp_t(tl).  Using the perspective-correct parameter under
         * NOPERSPECTIVE is audit finding M2: at wa = 1, wb = 4 a cut at screen
         * fraction 0.5 would be given the value for parameter 0.8.
         */
        mstring_append_fmt(
            output,
            "void emit_line_vertex(int i0, int i1, float tl, mat4 pz,\n"
            "                      vec2 screen) {\n"
            "  if (tl <= 0.0) {\n"
            "    emit_vertex_fs(i0, i0, pz, line_clip(i0, screen));\n"
            "    return;\n"
            "  }\n"
            "  if (tl >= 1.0) {\n"
            "    emit_vertex_fs(i1, i0, pz, line_clip(i1, screen));\n"
            "    return;\n"
            "  }\n"
            "  float t = %s;\n"
            "  gl_Position = line_clip_lerp(i0, i1, tl, screen);\n",
            state->noperspective ? "tl" : "line_lerp_t(i0, i1, tl)");
        if (!opts.gles) {
            mstring_append(
                output,
                "  gl_PointSize = mix(gl_in[i0].gl_PointSize,\n"
                "                     gl_in[i1].gl_PointSize, t);\n");
        }
        if (state->smooth_shading) {
            mstring_append(
                output,
                "  vtxD0 = mix(v_vtxD0[i0], v_vtxD0[i1], t);\n"
                "  vtxD1 = mix(v_vtxD1[i0], v_vtxD1[i1], t);\n"
                "  vtxB0 = mix(v_vtxB0[i0], v_vtxB0[i1], t);\n"
                "  vtxB1 = mix(v_vtxB1[i0], v_vtxB1[i1], t);\n");
        } else {
            /* Flat: these four, and only these four, are decided by the
             * provoking vertex, so an interpolated value would be discarded.
             * gl_in[0] is where the generator already pins them. */
            mstring_append(
                output,
                "  vtxD0 = v_vtxD0[0];\n"
                "  vtxD1 = v_vtxD1[0];\n"
                "  vtxB0 = v_vtxB0[0];\n"
                "  vtxB1 = v_vtxB1[0];\n");
        }
        mstring_append_fmt(
            output,
            "  vtxFog = mix(v_vtxFog[i0], v_vtxFog[i1], t);\n"
            "%s%s%s%s"
            "  vtxPointSize = mix(v_vtxPointSize[i0],\n"
            "                     v_vtxPointSize[i1], t);\n"
            "  vtxFogSpecial = v_vtxFogSpecial[i0];\n",
            tex_lerp[0], tex_lerp[1], tex_lerp[2], tex_lerp[3]);
        mstring_append(
            output,
            "  vtxPos0 = pz[0];\n"
            "  vtxPos1 = pz[1];\n"
            "  vtxPos2 = pz[2];\n"
            "  triMZ = (isnan(pz[3].x) || isinf(pz[3].x)) ? 0.0 : pz[3].x;\n"
            "  EmitVertex();\n"
            "}\n"
            "\n");
        /*
         * Sutherland-Hodgman against one minor-axis half-plane, in place.  A
         * convex n-gon clipped by a half-plane has at most n + 1 vertices, so
         * the parallelogram's two clips reach 6 and no more; the `< 6` guards
         * are for the floating-point case where a near-degenerate polygon
         * would otherwise index past the array, which in GLSL is undefined
         * rather than an error.
         *
         * A cut on one of the two SHORT edges has T[i] == T[j] -- both ends of
         * a cap edge sit at the same point along the line -- and that exact
         * endpoint parameter is taken rather than mix()ed, because mix(1, 1,
         * f) is (1 - f) + f and is not required to be exactly 1.  A T of
         * 1 - eps misses emit_line_vertex()'s endpoint early-out and
         * synthesises a vertex where an endpoint's own values were available.
         *
         * THE HALF-PIXEL DEADBAND, and why it is not a fudge factor.  A plane
         * the polygon pokes past by less than half a GUEST pixel is not
         * clipped at all: the four corners are handed straight back,
         * unrounded and in their original order.  The bounds below are WHOLE
         * PIXEL INDICES -- floor() and ceil() + 1 of the endpoints' extended
         * minor coordinate -- and this renderer rasterises at one sample per
         * pixel, at the pixel CENTRE (every rasterizationSamples in
         * pgraph/vk/ is VK_SAMPLE_COUNT_1_BIT).  So at one device pixel per
         * guest pixel the nearest centre to an integer bound is half a pixel
         * away, the removed sliver of a shallower cut provably contains no
         * sample, and the clip can only re-quantise geometry that was
         * previously exact.
         *
         * THE HYPOTHESIS IN THAT PROOF IS surface_scale_factor == 1, which
         * the paragraph above asserted without stating until audit finding
         * A1.  The two sentences are in different coordinate spaces: this
         * stage works in GUEST pixels -- vk/draw.c's geom_line_params() says
         * so in its own comment and divides lineTieBias by
         * surface_scale_factor for exactly that reason, and vsh.c scales only
         * oPts by it, never the position -- while the samples are DEVICE
         * pixel centres, 1/scale of a guest pixel apart.  At the user's
         * Rendering Scale of 2 (g_config.display.quality.surface_scale,
         * default 1, offered as 1x-4x by the Android settings UI) the nearest
         * sample to a bound is a QUARTER of a guest pixel away, not half.
         *
         * 0.5 is therefore EXACT at scale 1 and CONSERVATIVE above it, and
         * the error is one-directional by construction: 0.5 > 0.5/scale for
         * every scale >= 1, so the deadband can only suppress MORE cutting
         * than it should, never less.  A suppressed cut hands back master's
         * own four corners, so no configuration is made worse than master and
         * the re-quantisation this deadband exists to stop cannot come back
         * through it at any scale.  What is given up above 1x is part of the
         * cap fix itself, and it is measured rather than waved at --
         * `line_cap_phase.py --scale-cost`, over the same 48 non-void
         * captures, modelling the tie bias and the subpixel grid at the scale
         * too:
         *
         *   scale   suppressed cuts   device samples over-reached   lost
         *     1                   0                             0      0
         *     2                 191                           278    112
         *     3                 295                           860    298
         *     4                 337                          1666    568
         *
         * `lost` is the column that means anything: the over-reached samples
         * that no other edge's footprint covers anyway.  The cap rule removes
         * 393 guest px at scale 1 (--controls), so scaled for comparison the
         * deadband gives up on the order of a twelfth of the clip's own work
         * above 1x, on 26 to 30 captures from w = 6 up.  Scale 1 is the
         * control row and must read zero on every column, since 0.5/1 is 0.5.
         *
         * THAT ZERO IS ABOUT COVERAGE, AND THE SCALE-1 COST IS NOT ZERO --
         * audit finding N5.  The half-pixel argument bounds which SAMPLES
         * fall inside the footprint; it says nothing about the value at a
         * sample that stays covered, and taking a cut does more than move an
         * edge.  It synthesises a vertex and re-triangulates the strip, so
         * the varyings interpolate differently across a sample the cut never
         * uncovered.  Measured on the device at surface_scale_factor 1:
         * suppressing a cut in Line_width/Fill_0032.0 costs TWO pixels that
         * the pre-deadband build shaded exactly right -- (271,93)
         * 51,154,152 -> 51,155,151 and (264,123) 51,227,79 -> 51,228,78,
         * with the golden at the first value in both -- against four pixels
         * that capture gains from the clip.  It wins less there; it does not
         * lose.  At both pixels the deadbanded build holds master's own
         * value, which is the one-directional argument above doing exactly
         * what it claims.  No instrument in
         * docs/testing/line_cap_phase.py reports that class: --rivals,
         * --controls, --shader, --quantise, --scale-cost and --fills all
         * score coverage, and --depth is value-aware for z alone.  It is a
         * known limit, not a measured zero.
         *
         * The fix, if that twelfth is ever worth it, is NOT a smaller
         * constant -- 0.125 would be exact at scale 4 and would reintroduce
         * the device's own FAIL at scale 1, which is the scale every arm and
         * every golden here is measured at.  It is 0.5 / surface_scale_factor
         * pushed in, and the cost is a fifth push-constant component: the
         * geometry range would have to grow from 16 bytes to 32, because the
         * vertex range that follows it holds a vec4 array and needs 16-byte
         * alignment, and vk/instance.c's note applies -- that range is
         * declared on EVERY graphics pipeline layout, whether or not it has a
         * geometry stage, since two layouts are compatible for a descriptor
         * set only if their push-constant ranges match.  A known, measured,
         * one-directional limit was judged the better trade against that.
         *
         * Which is not free, and the device said so.  Without this deadband
         * the clip bit on 9 to 20 of each capture's 57 edges all the way down
         * to w = 0.625, cutting slivers a few hundredths of a pixel deep;
         * every offline instrument in docs/testing/line_cap_phase.py scored
         * that as inert because it rasterises in double precision at exact
         * centres, and the device scored EIGHT captures at w = 4 to 14 worse
         * ([job.arms] VERDICT: FAIL on PR #141, 2026-09-19).  Silicon cuts at
         * f = da / (da - db) in float32 from a sliver-sized da and then snaps
         * the result to 1/256 of a pixel, so a centre a thousandth of a pixel
         * inside the cut edge goes one way here and the other there.
         *
         * `line_cap_phase.py --quantise` is the instrument that can see this
         * -- the same polygon with its vertices snapped to the 1/256 grid
         * before the coverage test -- and it carries the deadband-at-zero
         * mutant inside it, so a check that stopped discriminating would say
         * so.
         */
        mstring_append(
            output,
            "int cap_clip(inout vec2 P[6], inout float T[6], int np,\n"
            "             bool xmaj, float bound, float dir) {\n"
            "  float deep = 0.0;\n"
            "  for (int i = 0; i < np; i++) {\n"
            "    deep = max(deep, -dir * ((xmaj ? P[i].y : P[i].x) - bound));\n"
            "  }\n"
            "  if (deep < 0.5) { return np; }\n"
            "  vec2 Q[6];\n"
            "  float S[6];\n"
            "  int nq = 0;\n"
            "  for (int i = 0; i < np; i++) {\n"
            "    int j = (i + 1 == np) ? 0 : i + 1;\n"
            "    float da = dir * ((xmaj ? P[i].y : P[i].x) - bound);\n"
            "    float db = dir * ((xmaj ? P[j].y : P[j].x) - bound);\n"
            "    if (da >= 0.0 && nq < 6) {\n"
            "      Q[nq] = P[i]; S[nq] = T[i]; nq++;\n"
            "    }\n"
            "    if (((da < 0.0) != (db < 0.0)) && nq < 6) {\n"
            "      float f = da / (da - db);\n"
            "      Q[nq] = mix(P[i], P[j], f);\n"
            "      S[nq] = (T[i] == T[j]) ? T[i] : mix(T[i], T[j], f);\n"
            "      nq++;\n"
            "    }\n"
            "  }\n"
            "  for (int i = 0; i < nq; i++) {\n"
            "    P[i] = Q[i]; T[i] = S[i];\n"
            "  }\n"
            "  return nq;\n"
            "}\n"
            "\n");
    }

    if (need_triz) {
        mstring_append(
            output,
            // Kahan's algorithm for computing a*b - c*d using FMA for higher
            // precision. See e.g.:
            // Muller et al, "Handbook of Floating-Point Arithmetic", 2nd ed.
            // or
            // Claude-Pierre Jeannerod, Nicolas Louvet, and Jean-Michel Muller,
            // Further analysis of Kahan's algorithm for the accurate
            // computation of 2x2 determinants,
            // Mathematics of Computation 82(284), October 2013.
            "float kahan_det(float a, float b, float c, float d) {\n"
            "  precise float cd = c*d;\n"
            "  precise float err = fma(-c, d, cd);\n"
            "  precise float res = fma(a, b, -cd) + err;\n"
            "  return res;\n"
            "}\n");

        if (state->z_perspective) {
            mstring_append(
                output,
                "mat4 calc_triz(int i0, int i1, int i2) {\n"
                "  mat2 m = mat2(v_vtxPos[i1].xy - v_vtxPos[i0].xy,\n"
                "                v_vtxPos[i2].xy - v_vtxPos[i0].xy);\n"
                "  precise vec2 b = vec2(v_vtxPos[i0].w - v_vtxPos[i1].w,\n"
                "                        v_vtxPos[i0].w - v_vtxPos[i2].w);\n"
                "  b /= vec2(v_vtxPos[i1].w, v_vtxPos[i2].w) * v_vtxPos[i0].w;\n"
                // The following computes dzx and dzy same as
                // vec2 dz = b * inverse(m);
                "  float det = kahan_det(m[0].x, m[1].y, m[1].x, m[0].y);\n"
                "  float dzx = kahan_det(b.x, m[1].y, b.y, m[0].y) / det;\n"
                "  float dzy = kahan_det(b.y, m[0].x, b.x, m[1].x) / det;\n"
                "  float dz = max(abs(dzx), abs(dzy));\n"
                "  return mat4(v_vtxPos[i0], v_vtxPos[i1], v_vtxPos[i2], dz, vec3(0.0));\n"
                "}\n");
        } else {
            mstring_append(
                output,
                "mat4 calc_triz(int i0, int i1, int i2) {\n"
                "  mat2 m = mat2(v_vtxPos[i1].xy - v_vtxPos[i0].xy,\n"
                "                v_vtxPos[i2].xy - v_vtxPos[i0].xy);\n"
                "  precise vec2 b = vec2(v_vtxPos[i1].z - v_vtxPos[i0].z,\n"
                "                        v_vtxPos[i2].z - v_vtxPos[i0].z);\n"
                // The following computes dzx and dzy same as
                // vec2 dz = b * inverse(m);
                "  float det = kahan_det(m[0].x, m[1].y, m[1].x, m[0].y);\n"
                "  float dzx = kahan_det(b.x, m[1].y, b.y, m[0].y) / det;\n"
                "  float dzy = kahan_det(b.y, m[0].x, b.x, m[1].x) / det;\n"
                "  float dz = max(abs(dzx), abs(dzy));\n"
                "  return mat4(v_vtxPos[i0], v_vtxPos[i1], v_vtxPos[i2], dz, vec3(0.0));\n"
                "}\n");
        }
    }

    if (need_linez) {
        mstring_append(
            output,
            // Calculate a third vertex by rotating 90 degrees so that triangle
            // interpolation in fragment shader can be used as is for lines.
            // vtxPos0/1/2 stay the LINE's synthetic triangle whether or not
            // the line is widened below: psh.c reconstructs depth from them
            // and its own fragment position, so the emitted geometry decides
            // coverage only, never the value interpolated over it.
            "void emit_line(int i0, int i1, float dz) {\n"
            "  vec2 delta = v_vtxPos[i1].xy - v_vtxPos[i0].xy;\n"
            "  vec2 v2 = vec2(-delta.y, delta.x) + v_vtxPos[i0].xy;\n"
            "  mat4 pz = mat4(v_vtxPos[i0], v_vtxPos[i1], v2, v_vtxPos[i0].zw, dz, vec3(0.0));\n");
        if (widen_lines) {
            mstring_append(
                output,
                /*
                 * The footprint is the intersection of two bands: the edge
                 * offset by +/- E/2 along the MINOR axis, and the slab
                 * between the two perpendiculars through the endpoints (the
                 * butt cap).  Two bands intersect in a parallelogram, and
                 * these four corners are exact.  A THIRD constraint -- the
                 * cap clip, below -- cuts one corner off each end, so what is
                 * finally emitted is a hexagon where it bites.
                 *
                 * Its corner offset works out free of any major-axis branch.
                 * Writing u for the unit edge direction and n for the
                 * minor-axis offset -- (0, E/2) when x is major, (E/2, 0)
                 * when y is -- the corner offset is n's component
                 * perpendicular to u:
                 *
                 *   n - (n.u)u  =  (w/2) * (max + min/2) / |d|^2 * (-dy, dx)
                 *
                 * with max, min the larger and smaller of |dx|, |dy|.  Both
                 * cases collapse to that one expression because E's
                 * denominator max cancels a numerator |dx| or |dy| that is
                 * max either way.  Check it at zero degrees:
                 * (w/2)|dx|/dx^2 * (0, dx) = (0, +/- w/2).
                 */
                "  float l2 = dot(delta, delta);\n"
                /* A zero-length line covers no pixel centre, and would divide
                 * by zero here. */
                "  if (l2 == 0.0) { return; }\n"
                "  vec2 ad = abs(delta);\n"
                "  vec2 n = (lineHalfExtentScale *\n"
                "            (max(ad.x, ad.y) + 0.5 * min(ad.x, ad.y)) / l2) *\n"
                "           vec2(-delta.y, delta.x);\n"
                /*
                 * Choice 3, the LOW-OPEN band.  4.562% of the goldens' band
                 * edges -- 1,911 of 41,892 -- land EXACTLY on a pixel centre,
                 * and getting those wrong costs 550-580 of the 8,890 fit-set
                 * cuts on its own (93.81% instead of 100%).  Vulkan does not
                 * say which way a rasteriser breaks that tie: 27.9 requires
                 * only that a shared edge belong to exactly one polygon, and
                 * permits rather than mandates top-left.  So do not rely on
                 * it in either direction -- shift the whole parallelogram
                 * towards INCREASING minor index, which excludes a centre
                 * sitting on the low edge and includes one on the high edge
                 * under a closed rule and a top-left rule alike.
                 *
                 * THE SHIFT MUST BE EXACTLY ONE SUBPIXEL QUANTUM, which is
                 * why it is a uniform rather than a literal.  Below one, the
                 * rasteriser's own vertex quantisation swallows it and the
                 * ties come back: simulated against the goldens' runs at
                 * subPixelPrecisionBits = 8, a bias of 1/512 scores 93.75%
                 * and a bias of 1/1024 scores 93.64%, against 93.41% for no
                 * bias at all.  Above one, it starts flipping cuts the rule
                 * gets right, because 143 band edges sit within 1/256 of a
                 * pixel centre without being on one: 1/128 scores 99.28% and
                 * 1/64 scores 97.93%, against 99.75% at exactly 1/256.
                 *
                 * That 99.75% is a CEILING SET BY THE DEVICE, not by this
                 * rule.  The same simulation with the quantisation removed
                 * reproduces the goldens on 8,890 of 8,890 fit-set cuts;
                 * at subPixelPrecisionBits = 12 it reaches 99.89%, and at 16
                 * 99.97%.  docs/testing/line_extent_subpixel.py is the
                 * simulation, and the prediction registered for this arm
                 * quotes it.
                 */
                "  vec2 tie = (ad.x >= ad.y) ? vec2(0.0, lineTieBias)\n"
                "                            : vec2(lineTieBias, 0.0);\n"
                /*
                 * THE CAP.  The parallelogram above is right in its body and
                 * too big at its two tips, and the goldens say by how much:
                 * the footprint never reaches, on the MINOR axis, past the
                 * endpoints' own minor coordinates extended by w/2 -- the
                 * line WIDTH, not the widened extent E -- with those two
                 * bounds rounded OUTWARD to whole pixel indices:
                 *
                 *   minor index i is lit only if
                 *     floor(m_min - w/2) <= i <= ceil(m_max + w/2)
                 *
                 * so the geometry has to cover those pixels' centres and no
                 * others, which is the half-open span [floor(...),
                 * ceil(...) + 1) in coordinates.  Derived offline from the
                 * goldens, no device: docs/testing/line_cap_phase.py, with
                 * the corner table it was read off in
                 * docs/lanes/linecap13/NOTES.md.
                 *
                 * WHERE IT BITES, AND WHERE IT MUST NOT.  The first capture
                 * whose COVERAGE this changes is w = 24, because below that
                 * every sliver it would remove is shallower than the half
                 * pixel between an integer bound and the nearest sample.  It
                 * does not follow that the change cannot reach a narrower
                 * line, and an earlier version of this comment said it did:
                 * the clip still BIT there, on up to 20 of a capture's 57
                 * edges down to w = 0.625, re-quantising exact corners for no
                 * modelled gain, and the device scored eight captures between
                 * w = 4 and w = 14 worse for it.  cap_clip()'s half-pixel
                 * deadband is what makes the inertness a property of the
                 * emitted geometry and not only of the offline model; see the
                 * derivation there, and `--quantise` for the check.
                 *
                 * w = 24 IS THE FIRST BITE AT EVERY RENDERING SCALE, which is
                 * worth saying because the deadband's own limit (audit A1,
                 * and the table in cap_clip()'s comment) is that it does not
                 * scale: the cut threshold is 0.5 guest px whatever
                 * surface_scale_factor is, so which cuts happen at all is a
                 * property of the geometry alone.  Measured at scales 1 to 4
                 * -- same 48 captures, tie bias modelled at each scale -- the
                 * first capture with a cut is Line_0024.0 and 19 captures cut,
                 * identically, in all four.  The scale changes how much a
                 * SUPPRESSED cut costs, never which cuts are suppressed.
                 *
                 * EVERY NUMBER BELOW NAMES THE INSTRUMENT THAT PRODUCED IT,
                 * because two instruments score this rule and they do not
                 * agree, over the same 48 non-void Line_* captures and their
                 * 1,967,133 golden ink px:
                 *
                 *   --rivals  the ANALYTIC MODEL, no tie bias.  Whole-capture
                 *             coverage 495 mismatched px without this clip,
                 *             102 with it, no capture worse.
                 *   --shader  emit_line()'s OWN polygon, rasterised at pixel
                 *             centres with the tie bias the device pushes
                 *             (1/256 at subPixelPrecisionBits = 8): 935 px
                 *             without the clip, 544 with it.  At an epsilon
                 *             bias, which isolates the geometry from the
                 *             quantisation, 414 and 21.
                 *
                 * The device sees the second instrument's world, so ~544 --
                 * not 21 and not 102 -- is what the registered prediction
                 * bounds.
                 *
                 * The outward rounding is measured, not assumed: the low and
                 * the high side of the same capture disagree by exactly one
                 * pixel at the same width and slope (LLoop0 reaches 32.5 px
                 * past its endpoint where LLoop4 stops at 31.5), and the
                 * obvious reading -- a centre-sampled w/2 band -- scores 645
                 * px on --rivals, worse than the 495 it was meant to fix.
                 *
                 * The clip planes are computed from v_vtxPos, NOT from the
                 * tie-shifted corners: they are silicon's grid, and they land
                 * on integers, half a pixel from any centre, so the tie bias
                 * that the band edges need cannot reach them.
                 *
                 * Clipping a parallelogram by two parallel planes gives a
                 * HEXAGON, which is why max_vertices went 4 -> 6 and 12 -> 18
                 * and why vk/instance.c's PGRAPH_GEOM_MAX_OUTPUT_VERTICES
                 * moved with them.  Where the clip does not bite, cap_clip()
                 * returns the same four corners in the same order and the
                 * emitted strip is byte for byte the one this shader emitted
                 * before.
                 */
                "  vec2 P[6];\n"
                "  float T[6];\n"
                "  P[0] = v_vtxPos[i0].xy + n + tie; T[0] = 0.0;\n"
                "  P[1] = v_vtxPos[i1].xy + n + tie; T[1] = 1.0;\n"
                "  P[2] = v_vtxPos[i1].xy - n + tie; T[2] = 1.0;\n"
                "  P[3] = v_vtxPos[i0].xy - n + tie; T[3] = 0.0;\n"
                "  int np = 4;\n"
                "  bool xmaj = ad.x >= ad.y;\n"
                "  vec2 m = xmaj ? vec2(v_vtxPos[i0].y, v_vtxPos[i1].y)\n"
                "                : vec2(v_vtxPos[i0].x, v_vtxPos[i1].x);\n"
                "  np = cap_clip(P, T, np, xmaj,\n"
                "                floor(min(m.x, m.y) - lineHalfExtentScale),\n"
                "                1.0);\n"
                "  np = cap_clip(P, T, np, xmaj,\n"
                "                ceil(max(m.x, m.y) + lineHalfExtentScale) +\n"
                "                    1.0,\n"
                "                -1.0);\n"
                /* A convex polygon as one triangle strip: 0, n-1, 1, n-2, ...
                 * At np == 4 that is P0, P3, P1, P2 -- the order the four
                 * corners were emitted in before this clip existed. */
                "  for (int k = 0; k < np; k++) {\n"
                "    int j = ((k & 1) == 0) ? (k >> 1) : (np - 1 - (k >> 1));\n"
                "    emit_line_vertex(i0, i1, T[j], pz, P[j]);\n"
                "  }\n"
                "  EndPrimitive();\n"
                "}\n");
        } else {
            mstring_append(
                output,
                "  emit_vertex(i0, pz, gl_in[i0].gl_Position);\n"
                "  emit_vertex(i1, pz, gl_in[i1].gl_Position);\n"
                "  EndPrimitive();\n"
                "}\n");
        }
    }

    if (need_wedge) {
        append_wedge(output, state, opts);
    }

    mstring_append_fmt(output,
                       "\n"
                       "void main() {\n"
                       "%s"
                       "}\n",
                       body);

    return output;
}
