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









































bool pgraph_glsl_need_geom(const GeomState *state)
{
    /* FIXME: Missing support for 2-sided-poly mode */
    assert(state->polygon_front_mode == state->polygon_back_mode);

    switch (state->primitive_mode) {
    case PRIM_TYPE_LINES:
    case PRIM_TYPE_TRIANGLES:
        return true;
    default:
        return false;
    }
}

MString *pgraph_glsl_gen_geom(const GeomState *state, GenGeomGlslOptions opts)
{
    /* FIXME: Missing support for 2-sided-poly mode */
    assert(state->polygon_front_mode == state->polygon_back_mode);
    enum ShaderPolygonMode polygon_mode = state->polygon_front_mode;

    bool need_triz = false;
    bool need_linez = false;
    const char *layout_in = NULL;
    const char *layout_out = NULL;
    const char *body = NULL;
    const char *provoking_index = state->smooth_shading ? "index" : "0";

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
            layout_out = "layout(triangle_strip, max_vertices = 3) out;\n";
            body = "  mat4 pz = calc_triz(0, 1, 2);\n"
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
             * cannot tell a fan triangle from a list triangle.  The fan
             * arrives here already rotated by emit_tri_pv() placing the
             * provoking vertex at index 0, so this takes the Tri class to
             * 100.00% of its decisive pixels and TFan only to 70.36%; the
             * rest of TFan is rewrite_triangle_fan()'s rotation to undo,
             * and undoing it there collides with flat shading's need for
             * the provoking vertex at index 0.
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
         */
        mstring_append(output,
                       "vec4 line_clip(int index, vec2 screen) {\n"
                       "  vec4 p = gl_in[index].gl_Position;\n"
                       "  return vec4((screen * lineNdcScale - 1.0) * p.w,\n"
                       "              p.z, p.w);\n"
                       "}\n");
        /*
         * The same map for a vertex that is not an endpoint.  The cap clip
         * below cuts one corner off each end of the footprint, and the cut
         * point on the LONG side sits a fraction t of the way down the line,
         * so it has no source vertex to take z and w from.
         *
         * Interpolating w as 1/w linear in screen space, and z as its
         * perspective-correct value at that point, is what makes the
         * subdivision invisible: perspective-correct interpolation is affine
         * in (a/w, 1/w), so a vertex carrying the true (a/w, 1/w) leaves
         * every varying over both sub-polygons exactly as the unclipped
         * parallelogram had it.  Getting this wrong would tilt the colour
         * ramp along the line near the cap, which is a fresh defect in
         * exactly the pixels this change exists to fix.  At w0 == w1 -- all
         * 2D content, the Line_width suite included -- it collapses to the
         * plain screen-space lerp.
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
                       "  float z = mix(pa.z * ia * ia, pb.z * ib * ib, t) *\n"
                       "            w * w;\n"
                       "  return vec4((screen * lineNdcScale - 1.0) * w,\n"
                       "              z, w);\n"
                       "}\n"
                       "\n"
                       /* The perspective-correct line parameter for the same
                        * point, which is what the varyings interpolate by. */
                       "float line_lerp_t(int i0, int i1, float t) {\n"
                       "  float ia = 1.0 / gl_in[i0].gl_Position.w;\n"
                       "  float ib = 1.0 / gl_in[i1].gl_Position.w;\n"
                       "  return (t * ib) / mix(ia, ib, t);\n"
                       "}\n");
    }

    mstring_append(
        output,
        "void emit_vertex(int index, mat4 pz, vec4 pos) {\n"
        "  gl_Position = pos;\n");
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
        "  vtxFogSpecial = v_vtxFogSpecial[index];\n"
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
        tex_lines[0], tex_lines[1], tex_lines[2], tex_lines[3]);

    if (widen_lines) {
        /*
         * A vertex of the widened footprint that is not one of the line's two
         * endpoints.  Only the cap clip's cut point on the long side is one,
         * and only when the clip bites: at t == 0 or t == 1 this hands
         * straight back to emit_vertex() with the endpoint's own index, so
         * the unclipped four-corner case emits exactly what it emitted
         * before, bit for bit, rather than an arithmetically-equal mix().
         *
         * EVERY FLAT VARYING HERE COMES FROM i0.  Under flat shading that is
         * all of them, and it is what the four-corner strip already produced:
         * both of its triangles took their provoking vertex from the i0 side.
         * The hexagon's strip does not -- two of its four triangles are
         * provoked by a vertex on the i1 side -- so taking the flat values
         * from the emitted vertex instead would make a flat-shaded wide line
         * change colour at the cap depending on how many corners the clip
         * happened to cut.  This keeps that decision out of the geometry.
         */
        mstring_append(
            output,
            "void emit_line_vertex(int i0, int i1, float tl, mat4 pz,\n"
            "                      vec2 screen) {\n"
            "  if (tl <= 0.0) { emit_vertex(i0, pz, line_clip(i0, screen));\n"
            "                   return; }\n"
            "  if (tl >= 1.0) { emit_vertex(i1, pz, line_clip(i1, screen));\n"
            "                   return; }\n"
            "  float t = line_lerp_t(i0, i1, tl);\n"
            "  gl_Position = line_clip_lerp(i0, i1, tl, screen);\n");
        if (!opts.gles) {
            mstring_append(
                output,
                "  gl_PointSize = mix(gl_in[i0].gl_PointSize,\n"
                "                     gl_in[i1].gl_PointSize, t);\n");
        }
        if (state->smooth_shading) {
            mstring_append_fmt(
                output,
                "  vtxD0 = mix(v_vtxD0[i0], v_vtxD0[i1], t);\n"
                "  vtxD1 = mix(v_vtxD1[i0], v_vtxD1[i1], t);\n"
                "  vtxB0 = mix(v_vtxB0[i0], v_vtxB0[i1], t);\n"
                "  vtxB1 = mix(v_vtxB1[i0], v_vtxB1[i1], t);\n"
                "  vtxFog = mix(v_vtxFog[i0], v_vtxFog[i1], t);\n"
                "%s%s%s%s"
                "  vtxPointSize = mix(v_vtxPointSize[i0],\n"
                "                     v_vtxPointSize[i1], t);\n",
                tex_lerp[0], tex_lerp[1], tex_lerp[2], tex_lerp[3]);
        } else {
            /* Flat: the provoking vertex decides every one of these, so an
             * interpolated value would be discarded.  gl_in[0] for the four
             * the generator already pins there, i0 for the rest. */
            mstring_append(
                output,
                "  vtxD0 = v_vtxD0[0];\n"
                "  vtxD1 = v_vtxD1[0];\n"
                "  vtxB0 = v_vtxB0[0];\n"
                "  vtxB1 = v_vtxB1[0];\n"
                "  vtxFog = v_vtxFog[i0];\n"
                "  vtxT0 = v_vtxT0[i0];\n"
                "  vtxT1 = v_vtxT1[i0];\n"
                "  vtxT2 = v_vtxT2[i0];\n"
                "  vtxT3 = v_vtxT3[i0];\n"
                "  vtxPointSize = v_vtxPointSize[i0];\n");
        }
        mstring_append(
            output,
            "  vtxFogSpecial = v_vtxFogSpecial[i0];\n"
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
         */
        mstring_append(
            output,
            "int cap_clip(inout vec2 P[6], inout float T[6], int np,\n"
            "             bool xmaj, float bound, float dir) {\n"
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
            "      S[nq] = mix(T[i], T[j], f);\n"
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
                 * goldens, no device: docs/testing/line_cap_phase.py and
                 * docs/investigations/line-cap-phase.md.  Over the 48
                 * non-void Line_* captures it takes whole-capture coverage
                 * from 495 mismatched px to 102, no capture worse, and it is
                 * inert below w = 24 where E/2 - w/2 is under a pixel.
                 *
                 * The outward rounding is measured, not assumed: the low and
                 * the high side of the same capture disagree by exactly one
                 * pixel at the same width and slope (LLoop0 reaches 32.5 px
                 * past its endpoint where LLoop4 stops at 31.5), and a
                 * centre-sampled w/2 band -- the obvious reading -- scores
                 * 497 px, worse than the 495 it was meant to fix.
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

    mstring_append_fmt(output,
                       "\n"
                       "void main() {\n"
                       "%s"
                       "}\n",
                       body);

    return output;
}
