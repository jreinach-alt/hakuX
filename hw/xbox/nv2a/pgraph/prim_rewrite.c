/*
 * Geforce NV2A PGRAPH Primitive Index Rewrite
 *
 * Rewrites NV2A primitive types to triangle/line/point lists on CPU.
 * Handles provoking vertex placement for flat shading correctness.
 *
 * Copyright (c) 2026 Matt Borgerson
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
#include "prim_rewrite.h"

void pgraph_prim_rewrite_init(PrimRewriteBuf *buf)
{
    buf->data = NULL;
    buf->capacity = 0;
}

void pgraph_prim_rewrite_finalize(PrimRewriteBuf *buf)
{
    g_free(buf->data);
    buf->data = NULL;
    buf->capacity = 0;
}

static void ensure_capacity(PrimRewriteBuf *buf, unsigned int needed)
{
    if (needed <= buf->capacity) {
        return;
    }
    buf->capacity = MAX(needed, buf->capacity * 2);
    buf->data = g_realloc(buf->data, buf->capacity * sizeof(uint32_t));
}

enum ShaderPrimitiveMode
pgraph_prim_rewrite_get_output_mode(enum ShaderPrimitiveMode primitive_mode,
                                    enum ShaderPolygonMode polygon_mode)
{
    switch (primitive_mode) {
    case PRIM_TYPE_POINTS:
        return PRIM_TYPE_POINTS;
    case PRIM_TYPE_LINES:
    case PRIM_TYPE_LINE_STRIP:
    case PRIM_TYPE_LINE_LOOP:
        return PRIM_TYPE_LINES;
    case PRIM_TYPE_TRIANGLES:
    case PRIM_TYPE_TRIANGLE_STRIP:
    case PRIM_TYPE_TRIANGLE_FAN:
        return PRIM_TYPE_TRIANGLES;
    case PRIM_TYPE_QUADS:
    case PRIM_TYPE_QUAD_STRIP:
    case PRIM_TYPE_POLYGON:
        return polygon_mode == POLY_MODE_LINE ? PRIM_TYPE_LINES :
                                                PRIM_TYPE_TRIANGLES;
    default:
        assert(!"Unexpected primitive mode");
        return primitive_mode;
    }
}

static inline bool needs_rewrite(PrimAssemblyState mode)
{
    switch (mode.primitive_mode) {
    case PRIM_TYPE_POINTS:
        return false;
    case PRIM_TYPE_LINES:
    case PRIM_TYPE_TRIANGLES:
        return mode.last_provoking && mode.flat_shading;
    default:
        return true;
    }
}

/*
 * Does anything downstream actually READ index 0 of a rewritten triangle?
 *
 * Vulkan rasterises first-vertex-provoking (nothing in vk/ enables
 * VK_EXT_provoking_vertex) and so does the desktop GL renderer, but NOT the
 * Android one: gl/draw.c's glProvokingVertex(GL_FIRST_VERTEX_CONVENTION) sits
 * inside `#ifndef __ANDROID__ / glProvokingVertex not available in GLES 3.x`,
 * so an Android GL build keeps GLES 3.x's LAST-vertex default.  That does not
 * reach the conclusion below, for the reason the edge-list argument gives: the
 * rotation leaves every emitted line's (i0, i1) pair intact, so whichever
 * endpoint the rasteriser takes a `flat` varying from, it takes the same one
 * on both arms.  It is written out here because the sentence "both renderers
 * are first-provoking" is load-bearing prose that is false in one build.
 *
 * glsl/geom.c spells its provoking_index as the literal "0" exactly when the
 * shade mode is FLAT, as "index" otherwise.
 * So under SMOOTH shading the rotation buys nothing.  needs_rewrite() above
 * already says as much for PRIM_TYPE_TRIANGLES, which it declines to rewrite
 * AT ALL unless the draw is flat and last-provoking; the strip and the fan
 * have to be rewritten regardless, because that is a topology change, and
 * the provoking placement rode along with it.
 *
 * Under POLY_MODE_LINE the rotation is not merely useless, it is wrong.
 * geom.c splits a triangle (A, B, C) into the edges (B,C), (C,A), (A,B) in
 * that order, so rotating the triple is a pure ROTATION OF THE EDGE LIST:
 * every edge keeps both endpoints and its direction, and only the paint
 * order changes.  That paint order is the rule #13 derived from the `Line
 * width` goldens, and a TRIANGLE_FAN was arriving pre-rotated by one
 * relative to the TRIANGLES draw beside it -- which geom.c cannot
 * compensate for, because GeomState::primitive_mode is the REWRITTEN mode
 * and cannot tell a fan triangle from a list triangle.  That left the TFan
 * and QStrip/TFan classes at 73.20% and 75.84% where every other class had
 * reached 100.00% -- 8,920 decisive pixels naming the wrong edge, over the
 * 35,645 the two classes hold.  (#13's comments call the residue "32,628
 * decisive pixels"; that figure is the POPULATION of the two classes under
 * the perpendicular footprint model this emulator stopped drawing in
 * 80c23dcabe, not the pixels that are wrong inside it.)
 *
 * WHO ELSE READS INDEX 0 ON THAT PATH.  Three readers, and the third is the
 * one this comment used to miss.
 *
 * (1) vtxFogSpecial is `flat` in EVERY shade mode (glsl/common.c), but each
 * emit_line() takes it from that EDGE's own first endpoint rather than from
 * the triangle's index 0 -- geom.c:422 uses `index`, and the widened path
 * pins it to the edge's own i0 (geom.c:535).  Rotating the triple does not
 * change any edge's own endpoints, so every edge carries the value it carried
 * before, in a different order.  Unchanged.
 *
 * (2) calc_triz(0, 1, 2) takes the depth slope relative to vertex 0, so a fan
 * triangle's dz is now evaluated on the same basis a list triangle's already
 * was.  A plane's gradient is rotation-invariant, so this can move dz only by
 * rounding; it feeds triMZ, not coverage.
 *
 * (3) cylWrap DOES move, and it is a literal [0] rather than a
 * provoking_index.  When a texture unit is in WRAP address mode
 * (state->cylinder_wrap[i] non-zero, from NV_PGRAPH_TEXADDRESS0_WRAP_U/V/P/Q)
 * geom.c:293-298 emits `vtxT%d = cylWrap(v_vtxT%d[0], v_vtxT%d[index], ...)`
 * in emit_vertex() and the same `v_vtxT%d[0]` reference in emit_vertex_fs()'s
 * lerp -- in BOTH the GL and the widened Vulkan paths, and independently of
 * the shade mode.  Cylinder wrap adjusts each vertex's texture coordinate by
 * whole turns relative to the input primitive's vertex 0, so moving vertex 0
 * moves the reference.  Direction: it was the rim vertex the rotation put
 * there (v2 under last-provoking, v1 under first), which VARIES per fan
 * triangle; it is now the fan HUB, the same vertex for every triangle of the
 * fan.  A rim vertex more than half a turn from the hub but less than half a
 * turn from its old neighbour-reference (or the reverse) now takes a whole
 * turn it did not take, moving its U or V by 1.0.
 *
 * This is TOLERATED, not measured, and it is arguably the better reference --
 * one reference per fan rather than a different one per triangle is what a
 * TRIANGLES draw of the same geometry already gets, which is the consistency
 * the rest of this change is for.  But no golden here exercises it: a
 * textured wireframe fan with WRAP addressing is drawn by nothing in the
 * registered disc (`Shade_model`'s line-mode prefix is kUntexturedLM and
 * `Line width` is untextured), so the arm cannot see it either way and will
 * come back clean whether or not it matters.  If a title regresses on
 * textured wireframe geometry, start here.
 *
 * POLY_MODE_FILL and POLY_MODE_POINT keep it, because there the rotation is
 * NOT a reorder: it decides the triangle's provoking output vertex outright,
 * and with it the flat colour and vtxFogSpecial.
 *
 * So #13's trade is not abolished, it is narrowed to its one real corner --
 * a flat-shaded wireframe, where the colour must win over the paint order.
 */
static inline bool pv_placement_observable(PrimAssemblyState mode)
{
    return mode.flat_shading || mode.polygon_mode != POLY_MODE_LINE;
}

static unsigned int max_output_indices(enum ShaderPrimitiveMode mode,
                                       enum ShaderPolygonMode polygon_mode,
                                       unsigned int input_count)
{
    switch (mode) {
    case PRIM_TYPE_LINES:
        return input_count;
    case PRIM_TYPE_LINE_STRIP:
        return (input_count >= 2) ? (input_count - 1) * 2 : 0;
    case PRIM_TYPE_LINE_LOOP:
        return (input_count >= 2) ? input_count * 2 : 0;
    case PRIM_TYPE_TRIANGLES:
        return input_count;
    case PRIM_TYPE_TRIANGLE_STRIP:
    case PRIM_TYPE_TRIANGLE_FAN:
        return (input_count >= 3) ? (input_count - 2) * 3 : 0;
    case PRIM_TYPE_POLYGON:
        if (polygon_mode == POLY_MODE_LINE) {
            return (input_count >= 2) ? input_count * 2 : 0;
        }
        return (input_count >= 3) ? (input_count - 2) * 3 : 0;
    case PRIM_TYPE_QUADS:
        if (polygon_mode == POLY_MODE_LINE) {
            return (input_count / 4) * 8;
        }
        return (input_count / 4) * 6;
    case PRIM_TYPE_QUAD_STRIP:
        if (polygon_mode == POLY_MODE_LINE) {
            return (input_count >= 4) ? ((input_count - 2) / 2) * 8 : 0;
        }
        return (input_count >= 4) ? ((input_count - 2) / 2) * 6 : 0;
    default:
        return 0;
    }
}

static inline uint32_t idx_at(const uint32_t *idx, unsigned int i,
                              uint32_t base)
{
    return idx ? idx[i] : base + i;
}

static inline void emit_vertex(PrimRewrite *r, uint32_t v)
{
    r->indices[r->num_indices++] = v;
}

static inline void emit_line(PrimRewrite *r, uint32_t a, uint32_t b)
{
    emit_vertex(r, a);
    emit_vertex(r, b);
}

/* Place provoking vertex p at index 0. */
static inline void emit_line_pv(PrimRewrite *r, uint32_t a, uint32_t b,
                                uint32_t p)
{
    if (p == a) {
        emit_line(r, a, b);
    } else {
        emit_line(r, b, a);
    }
}

static inline void emit_tri(PrimRewrite *r, uint32_t a, uint32_t b, uint32_t c)
{
    emit_vertex(r, a);
    emit_vertex(r, b);
    emit_vertex(r, c);
}

/* Rotate provoking vertex p to index 0, preserving winding of (a, b, c). */
static inline void emit_tri_pv(PrimRewrite *r, uint32_t a, uint32_t b,
                               uint32_t c, uint32_t p)
{
    if (p == a) {
        emit_tri(r, a, b, c);
    } else if (p == b) {
        emit_tri(r, b, c, a);
    } else {
        emit_tri(r, c, a, b);
    }
}

static void rewrite_lines(PrimRewrite *r, const uint32_t *idx, uint32_t base,
                          unsigned int count, bool last_provoking)
{
    for (unsigned int i = 0; i + 1 < count; i += 2) {
        uint32_t v0 = idx_at(idx, i, base);
        uint32_t v1 = idx_at(idx, i + 1, base);
        uint32_t pv = last_provoking ? v1 : v0;

        emit_line_pv(r, v0, v1, pv);
    }
}

static void rewrite_line_strip(PrimRewrite *r, const uint32_t *idx,
                               uint32_t base, unsigned int count,
                               bool last_provoking)
{
    for (unsigned int i = 0; i + 1 < count; i++) {
        uint32_t v0 = idx_at(idx, i, base);
        uint32_t v1 = idx_at(idx, i + 1, base);
        uint32_t pv = last_provoking ? v1 : v0;

        emit_line_pv(r, v0, v1, pv);
    }
}

static void rewrite_line_loop(PrimRewrite *r, const uint32_t *idx,
                              uint32_t base, unsigned int count,
                              bool last_provoking)
{
    if (count < 2) {
        return;
    }

    for (unsigned int i = 0; i + 1 < count; i++) {
        uint32_t v0 = idx_at(idx, i, base);
        uint32_t v1 = idx_at(idx, i + 1, base);
        uint32_t pv = last_provoking ? v1 : v0;

        emit_line_pv(r, v0, v1, pv);
    }

    uint32_t v_last = idx_at(idx, count - 1, base);
    uint32_t v_first = idx_at(idx, 0, base);
    uint32_t pv = last_provoking ? v_first : v_last;

    emit_line_pv(r, v_last, v_first, pv);
}

static void rewrite_triangles(PrimRewrite *r, const uint32_t *idx,
                              uint32_t base, unsigned int count,
                              bool last_provoking)
{
    for (unsigned int i = 0; i + 2 < count; i += 3) {
        uint32_t v0 = idx_at(idx, i, base);
        uint32_t v1 = idx_at(idx, i + 1, base);
        uint32_t v2 = idx_at(idx, i + 2, base);
        uint32_t pv = last_provoking ? v2 : v0;

        emit_tri_pv(r, v0, v1, v2, pv);
    }
}

/*
 * DELIBERATELY NOT given the pv_placement_observable() treatment the fan gets
 * below, though the same reasoning reaches it: under POLY_MODE_LINE a strip
 * triangle is pre-rotated relative to a list triangle too, and geom.c cannot
 * tell them apart either.  The difference is evidence.  The odd-i case below
 * is a REFLECTION (v1, v0, v2), not a rotation, so its composition with
 * geom.c's edge order is a different derivation from the fan's -- and the
 * `Line width` corpus, which is what pins these orders to the pixel, draws no
 * TRIANGLE_STRIP at all under POLY_MODE_LINE.  So the strip's order is not
 * decisively scored by that corpus, and only weakly by
 * Shade_model/ProgLM_TriStrip_* -- four real POLY_MODE_LINE strip captures,
 * but at the default line width, where overlap is confined to a handful of
 * corner pixels.  That is evidence, just not enough to price a change on; the
 * reflection-vs-rotation half of the argument stands on its own.  The next
 * lane can price this rather than read it as settled.
 * See docs/lanes/primpv13/NOTES.md.
 */
static void rewrite_triangle_strip(PrimRewrite *r, const uint32_t *idx,
                                   uint32_t base, unsigned int count,
                                   bool last_provoking)
{
    for (unsigned int i = 0; i + 2 < count; i++) {
        uint32_t v0 = idx_at(idx, i, base);
        uint32_t v1 = idx_at(idx, i + 1, base);
        uint32_t v2 = idx_at(idx, i + 2, base);
        uint32_t pv = last_provoking ? v2 : v0;

        if (i & 1) {
            emit_tri_pv(r, v1, v0, v2, pv);
        } else {
            emit_tri_pv(r, v0, v1, v2, pv);
        }
    }
}

/*
 * `place_pv` is pv_placement_observable(): with it false the fan triangle is
 * handed on in its natural (hub, v1, v2) order, which is the same order a
 * TRIANGLES draw arrives in, so geom.c's one derived edge order fits both.
 * The emission COUNT is identical either way, so -- exactly as for the three
 * rewrite_*_line() functions below -- no counter can tell the two apart and
 * only the captures can.
 */
static void rewrite_triangle_fan(PrimRewrite *r, const uint32_t *idx,
                                 uint32_t base, unsigned int count,
                                 bool last_provoking, bool place_pv)
{
    if (count < 3) {
        return;
    }

    uint32_t hub = idx_at(idx, 0, base);

    for (unsigned int i = 0; i + 2 < count; i++) {
        uint32_t v1 = idx_at(idx, i + 1, base);
        uint32_t v2 = idx_at(idx, i + 2, base);

        if (!place_pv) {
            emit_tri(r, hub, v1, v2);
            continue;
        }

        emit_tri_pv(r, hub, v1, v2, last_provoking ? v2 : v1);
    }
}

static void rewrite_quads(PrimRewrite *r, const uint32_t *idx, uint32_t base,
                          unsigned int count, bool flat_shading)
{
    for (unsigned int i = 0; i + 3 < count; i += 4) {
        uint32_t v0 = idx_at(idx, i, base);
        uint32_t v1 = idx_at(idx, i + 1, base);
        uint32_t v2 = idx_at(idx, i + 2, base);
        uint32_t v3 = idx_at(idx, i + 3, base);

        if (flat_shading) {
            /* Use v1-v3 diagonal so provoking vertex v3 is in both triangles.
             * This gives correct flat shading color but slightly different
             * depth slope vs hardware. */
            emit_tri(r, v3, v0, v1);
            emit_tri(r, v3, v1, v2);
        } else {
            /* v0-v2 diagonal: matches hardware quad tessellation */
            emit_tri(r, v0, v1, v2);
            emit_tri(r, v0, v2, v3);
        }
    }
}

/*
 * Silicon's edge order for a polygon rasterised in POLY_MODE_LINE, derived
 * from the `Line width` goldens -- the suite disables the depth test and every
 * palette entry is opaque, so the colour at a pixel covered by several wide
 * edges names the edge silicon drew LAST.  The rule is one sentence:
 *
 *   triangulate exactly as the FILL path does, drop the tessellation's
 *   internal edges, and for each triangle (a, b, c) emit the edge opposite a,
 *   then the edge opposite b, then the edge opposite c -- (b,c), (c,a), (a,b).
 *
 * That single sentence yields a different permutation for each primitive
 * because the tessellations differ, and nothing below is tuned per primitive.
 * It is correct on 100.00% of 225,558 decisive pixels, in each of eleven
 * candidate classes separately, against 78.51% for the order that was here
 * before -- which the goldens refute rather than merely beat.  See
 * docs/investigations/line-width-residual.md.
 *
 * The emission COUNT is unchanged in all three functions, so no counter can
 * tell the two orders apart; only the captures can.
 */
static void rewrite_quads_line(PrimRewrite *r, const uint32_t *idx,
                               uint32_t base, unsigned int count)
{
    for (unsigned int i = 0; i + 3 < count; i += 4) {
        uint32_t v0 = idx_at(idx, i, base);
        uint32_t v1 = idx_at(idx, i + 1, base);
        uint32_t v2 = idx_at(idx, i + 2, base);
        uint32_t v3 = idx_at(idx, i + 3, base);

        /* rewrite_quads() tessellates as (v0,v1,v2) and (v0,v2,v3) on the
         * v0-v2 diagonal, so opposite-a/b/c per triangle, less that diagonal,
         * is (v1,v2), (v0,v1) then (v2,v3), (v3,v0).  The goldens confirm the
         * diagonal too: on a v1-v3 diagonal the same rule would emit (v3,v0)
         * first, and (v3,v0) loses to (v0,v1) on 5,780 pixels.
         */
        emit_line(r, v1, v2);
        emit_line(r, v0, v1);
        emit_line(r, v2, v3);
        emit_line(r, v3, v0);
    }
}

static void rewrite_quad_strip(PrimRewrite *r, const uint32_t *idx,
                               uint32_t base, unsigned int count,
                               bool flat_shading)
{
    if (count < 4) {
        return;
    }

    for (unsigned int i = 0; i + 3 < count; i += 2) {
        uint32_t v0 = idx_at(idx, i, base);
        uint32_t v1 = idx_at(idx, i + 1, base);
        uint32_t v2 = idx_at(idx, i + 2, base);
        uint32_t v3 = idx_at(idx, i + 3, base);

        if (flat_shading) {
            /* Use v0-v3 diagonal so provoking vertex v3 is in both triangles.
             * This gives correct flat shading color but slightly different
             * depth slope vs hardware. */
            emit_tri(r, v3, v2, v0);
            emit_tri(r, v3, v0, v1);
        } else {
            /* v1-v2 diagonal: matches hardware quad strip tessellation */
            emit_tri(r, v0, v1, v2);
            emit_tri(r, v2, v1, v3);
        }
    }
}

static void rewrite_quad_strip_line(PrimRewrite *r, const uint32_t *idx,
                                    uint32_t base, unsigned int count)
{
    if (count < 4) {
        return;
    }

    for (unsigned int i = 0; i + 3 < count; i += 2) {
        uint32_t v0 = idx_at(idx, i, base);
        uint32_t v1 = idx_at(idx, i + 1, base);
        uint32_t v2 = idx_at(idx, i + 2, base);
        uint32_t v3 = idx_at(idx, i + 3, base);

        /* rewrite_quad_strip() tessellates as (v0,v1,v2) and (v2,v1,v3) on
         * the v1-v2 diagonal, so opposite-a/b/c per triangle, less that
         * diagonal, is (v2,v0), (v0,v1) then (v1,v3), (v3,v2) -- our previous
         * boundary walk rotated by one.  This is the one primitive whose
         * goldens separate "opposite a, b, c" from "opposite a, c, b"
         * (100.00% against 79.46%); the two agree everywhere else.
         */
        emit_line(r, v2, v0);
        emit_line(r, v0, v1);
        emit_line(r, v1, v3);
        emit_line(r, v3, v2);
    }
}

static void rewrite_polygon(PrimRewrite *r, const uint32_t *idx, uint32_t base,
                            unsigned int count)
{
    if (count < 3) {
        return;
    }

    uint32_t hub = idx_at(idx, 0, base);

    for (unsigned int i = 0; i + 2 < count; i++) {
        uint32_t v1 = idx_at(idx, i + 1, base);
        uint32_t v2 = idx_at(idx, i + 2, base);

        emit_tri(r, hub, v1, v2);
    }
}

static void rewrite_polygon_line(PrimRewrite *r, const uint32_t *idx,
                                 uint32_t base, unsigned int count)
{
    if (count < 2) {
        return;
    }

    /* A 2-gon has no triangle for the rule to order; it is the one degenerate
     * case, and its single edge is emitted once.
     */
    if (count == 2) {
        emit_line(r, idx_at(idx, 0, base), idx_at(idx, 1, base));
        return;
    }

    /* rewrite_polygon() fans from v0, so triangle t is (v0, vt, vt+1) and
     * opposite-a/b/c is (vt,vt+1), (vt+1,v0), (v0,vt).  Of the two spokes,
     * (v0,vt) survives only for t == 1 and (vt+1,v0) only for t == count-2;
     * every other spoke is internal to the tessellation and is not drawn,
     * which the goldens confirm at width 1 (the polygon has no fan spokes).
     *
     * This is NOT "swap the first two edges": at count == 3 there is no
     * internal edge at all and the order is the bare triangle's, (v1,v2),
     * (v2,v0), (v0,v1).  The loop below gets that right because both
     * conditions fire in the same iteration, in the rule's own order.
     */
    for (unsigned int t = 1; t + 1 < count; t++) {
        emit_line(r, idx_at(idx, t, base), idx_at(idx, t + 1, base));
        if (t == count - 2) {
            emit_line(r, idx_at(idx, count - 1, base), idx_at(idx, 0, base));
        }
        if (t == 1) {
            emit_line(r, idx_at(idx, 0, base), idx_at(idx, 1, base));
        }
    }
}

static void rewrite_indices(PrimRewrite *r, const PrimAssemblyState *mode,
                            const uint32_t *idx, uint32_t base,
                            unsigned int num_indices)
{
    switch (mode->primitive_mode) {
    case PRIM_TYPE_LINES:
        rewrite_lines(r, idx, base, num_indices, mode->last_provoking);
        break;
    case PRIM_TYPE_LINE_STRIP:
        rewrite_line_strip(r, idx, base, num_indices, mode->last_provoking);
        break;
    case PRIM_TYPE_LINE_LOOP:
        rewrite_line_loop(r, idx, base, num_indices, mode->last_provoking);
        break;
    case PRIM_TYPE_TRIANGLES:
        rewrite_triangles(r, idx, base, num_indices, mode->last_provoking);
        break;
    case PRIM_TYPE_TRIANGLE_STRIP:
        rewrite_triangle_strip(r, idx, base, num_indices, mode->last_provoking);
        break;
    case PRIM_TYPE_TRIANGLE_FAN:
        rewrite_triangle_fan(r, idx, base, num_indices, mode->last_provoking,
                             pv_placement_observable(*mode));
        break;
    case PRIM_TYPE_QUADS:
        if (mode->polygon_mode == POLY_MODE_LINE) {
            rewrite_quads_line(r, idx, base, num_indices);
        } else {
            rewrite_quads(r, idx, base, num_indices, mode->flat_shading);
        }
        break;
    case PRIM_TYPE_QUAD_STRIP:
        if (mode->polygon_mode == POLY_MODE_LINE) {
            rewrite_quad_strip_line(r, idx, base, num_indices);
        } else {
            rewrite_quad_strip(r, idx, base, num_indices, mode->flat_shading);
        }
        break;
    case PRIM_TYPE_POLYGON:
        if (mode->polygon_mode == POLY_MODE_LINE) {
            rewrite_polygon_line(r, idx, base, num_indices);
        } else {
            rewrite_polygon(r, idx, base, num_indices);
        }
        break;
    default:
        assert(!"Unexpected primitive mode");
        break;
    }
}

PrimRewrite pgraph_prim_rewrite_ranges(PrimRewriteBuf *buf,
                                       PrimAssemblyState mode,
                                       const int32_t *starts,
                                       const int32_t *counts,
                                       unsigned int num_ranges)
{
    PrimRewrite result = { 0 };

    assert(mode.polygon_mode != POLY_MODE_POINT ||
           mode.primitive_mode != PRIM_TYPE_POLYGON);

    if (!needs_rewrite(mode)) {
        return result;
    }

    unsigned int total_max_output = 0;
    for (unsigned int r = 0; r < num_ranges; r++) {
        total_max_output += max_output_indices(mode.primitive_mode,
                                               mode.polygon_mode, counts[r]);
    }

    if (total_max_output == 0) {
        return result;
    }

    ensure_capacity(buf, total_max_output);
    result.indices = buf->data;

    for (unsigned int r = 0; r < num_ranges; r++) {
        if (counts[r] == 0) {
            continue;
        }

        rewrite_indices(&result, &mode, NULL, starts[r], counts[r]);
    }

    return result;
}

PrimRewrite pgraph_prim_rewrite_indexed(PrimRewriteBuf *buf,
                                        PrimAssemblyState mode,
                                        const uint32_t *input_indices,
                                        unsigned int num_input_indices)
{
    PrimRewrite result = { 0 };

    assert(mode.polygon_mode != POLY_MODE_POINT ||
           mode.primitive_mode != PRIM_TYPE_POLYGON);

    if (!needs_rewrite(mode)) {
        return result;
    }

    unsigned int max_output = max_output_indices(
        mode.primitive_mode, mode.polygon_mode, num_input_indices);

    if (max_output == 0) {
        return result;
    }

    ensure_capacity(buf, max_output);
    result.indices = buf->data;

    rewrite_indices(&result, &mode, input_indices, 0, num_input_indices);

    return result;
}
