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

    state->primitive_mode = pgraph_prim_rewrite_get_output_mode(
        (enum ShaderPrimitiveMode)pg->primitive_mode,
        state->polygon_front_mode);

    state->smooth_shading = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_3),
                                     NV_PGRAPH_CONTROL_3_SHADEMODE) ==
                            NV_PGRAPH_CONTROL_3_SHADEMODE_SMOOTH;

    state->z_perspective = pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0) &
                           NV_PGRAPH_CONTROL_0_Z_PERSPECTIVE_ENABLE;
    state->noperspective = !(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0) &
                             NV_PGRAPH_CONTROL_0_TEXTUREPERSPECTIVE);
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

    switch (state->primitive_mode) {
    case PRIM_TYPE_POINTS: return NULL;
    case PRIM_TYPE_LINES:
        need_linez = true;
        layout_in = "layout(lines) in;\n";
        layout_out = "layout(line_strip, max_vertices = 2) out;\n";
        body = "  emit_line(0, 1, 0.0);\n";
        break;
    case PRIM_TYPE_TRIANGLES:
        need_triz = true;
        layout_in = "layout(triangles) in;\n";
        if (polygon_mode == POLY_MODE_FILL) {
            layout_out = "layout(triangle_strip, max_vertices = 3) out;\n";
            body = "  mat4 pz = calc_triz(0, 1, 2);\n"
                   "  emit_vertex(0, pz);\n"
                   "  emit_vertex(1, pz);\n"
                   "  emit_vertex(2, pz);\n"
                   "  EndPrimitive();\n";
        } else if (polygon_mode == POLY_MODE_LINE) {
            need_linez = true;
            layout_out = "layout(line_strip, max_vertices = 6) out;\n";
            body = "  float dz = calc_triz(0, 1, 2)[3].x;\n"
                   "  emit_line(0, 1, dz);\n"
                   "  emit_line(1, 2, dz);\n"
                   "  emit_line(2, 0, dz);\n";
        } else {
            assert(polygon_mode == POLY_MODE_POINT);
            layout_out = "layout(points, max_vertices = 3) out;\n";
            body = "  mat4 pz = calc_triz(0, 1, 2);\n"
                   "  emit_vertex(0, mat4(pz[0], pz[0], pz[0], pz[3]));\n"
                   "  EndPrimitive();\n"
                   "  emit_vertex(1, mat4(pz[1], pz[1], pz[1], pz[3]));\n"
                   "  EndPrimitive();\n"
                   "  emit_vertex(2, mat4(pz[2], pz[2], pz[2], pz[3]));\n"
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
    for (int i = 0; i < 4; i++) {
        uint8_t w = state->cylinder_wrap[i];
        if (w) {
            snprintf(tex_lines[i], sizeof(tex_lines[i]),
                     "  vtxT%d = cylWrap(v_vtxT%d[0], v_vtxT%d[index], bvec4(%s, %s, %s, %s));\n",
                     i, i, i, (w & 1) ? "true" : "false", (w & 2) ? "true" : "false",
                     (w & 4) ? "true" : "false", (w & 8) ? "true" : "false");
        } else {
            snprintf(tex_lines[i], sizeof(tex_lines[i]),
                     "  vtxT%d = v_vtxT%d[index];\n", i, i);
        }
    }

    mstring_append(
        output,
        "void emit_vertex(int index, mat4 pz) {\n"
        "  gl_Position = gl_in[index].gl_Position;\n");
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
            "void emit_line(int i0, int i1, float dz) {\n"
            "  vec2 delta = v_vtxPos[i1].xy - v_vtxPos[i0].xy;\n"
            "  vec2 v2 = vec2(-delta.y, delta.x) + v_vtxPos[i0].xy;\n"
            "  mat4 pz = mat4(v_vtxPos[i0], v_vtxPos[i1], v2, v_vtxPos[i0].zw, dz, vec3(0.0));\n"
            "  emit_vertex(i0, pz);\n"
            "  emit_vertex(i1, pz);\n"
            "  EndPrimitive();\n"
            "}\n");
    }

    mstring_append_fmt(output,
                       "\n"
                       "void main() {\n"
                       "%s"
                       "}\n",
                       body);

    return output;
}
