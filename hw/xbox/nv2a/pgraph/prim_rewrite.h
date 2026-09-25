/*
 * Geforce NV2A PGRAPH Primitive Index Rewrite
 *
 * Rewrites NV2A primitive types to triangle/line/point lists on CPU.
 * Handles provoking vertex placement for flat shading correctness, and
 * emits flat quads as triangles-with-adjacency so the provoking vertex
 * need not be a vertex of the triangle it colours.
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

#ifndef HW_XBOX_NV2A_PGRAPH_PRIM_REWRITE_H
#define HW_XBOX_NV2A_PGRAPH_PRIM_REWRITE_H

#include <stdbool.h>
#include <stdint.h>
#include "vsh_regs.h"

typedef struct PrimRewriteBuf {
    uint32_t *data;
    unsigned int capacity; /* in elements */
} PrimRewriteBuf;

typedef struct PrimRewrite {
    uint32_t *indices; /* points into PrimRewriteBuf; do NOT free */
    unsigned int num_indices;
} PrimRewrite;

typedef struct PrimAssemblyState {
    enum ShaderPrimitiveMode primitive_mode;
    enum ShaderPolygonMode polygon_mode;
    bool last_provoking;
    bool flat_shading;
    /* Set only by a renderer that draws without a geometry shader (GLES
     * without GL_EXT_geometry_shader): adjacency topology has nothing to
     * consume it there, so flat quads keep the v3-provoking diagonal. */
    bool no_adjacency;
} PrimAssemblyState;

void pgraph_prim_rewrite_init(PrimRewriteBuf *buf);
void pgraph_prim_rewrite_finalize(PrimRewriteBuf *buf);
/* The topology CLASS of the rewritten stream: points, lines or triangles.
 * PRIM_TYPE_TRIANGLES_ADJACENCY reads as PRIM_TYPE_TRIANGLES here. */
enum ShaderPrimitiveMode
pgraph_prim_rewrite_get_output_mode(enum ShaderPrimitiveMode primitive_mode,
                                    enum ShaderPolygonMode polygon_mode);
/* The topology the rewritten stream is actually DRAWN with, which is what
 * the geometry shader and the draw call must agree on.  It differs from
 * get_output_mode() only for a flat, filled QUADS or QUAD_STRIP draw, which
 * is PRIM_TYPE_TRIANGLES_ADJACENCY. */
enum ShaderPrimitiveMode
pgraph_prim_rewrite_get_draw_mode(enum ShaderPrimitiveMode primitive_mode,
                                  enum ShaderPolygonMode polygon_mode,
                                  bool flat_shading);

PrimRewrite pgraph_prim_rewrite_indexed(PrimRewriteBuf *buf,
                                        PrimAssemblyState mode,
                                        const uint32_t *input_indices,
                                        unsigned int num_input_indices);

PrimRewrite pgraph_prim_rewrite_ranges(PrimRewriteBuf *buf,
                                       PrimAssemblyState mode,
                                       const int32_t *starts,
                                       const int32_t *counts,
                                       unsigned int num_ranges);

static inline PrimRewrite pgraph_prim_rewrite_sequential(PrimRewriteBuf *buf,
                                                         PrimAssemblyState mode,
                                                         int32_t start,
                                                         int32_t count)
{
    return pgraph_prim_rewrite_ranges(buf, mode, &start, &count, 1);
}

#endif
