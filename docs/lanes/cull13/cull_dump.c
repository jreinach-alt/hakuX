/*
 * cull_dump -- print the line-mode triangle geometry shaders with each
 * GeomState.line_cull_face / line_front_ccw pair, for glslc.
 *
 * Built against docs/testing/geom_dump's objects (run `make` there first):
 *
 *     ./check.sh
 *
 * Copyright (c) 2026 hakuX contributors
 * SPDX-License-Identifier: GPL-2.0-or-later
 */

#include "qemu/osdep.h"
#include "hw/xbox/nv2a/pgraph/pgraph.h"
#include "geom.h"

int main(int argc, char **argv)
{
    if (argc != 5) {
        fprintf(stderr, "usage: cull_dump vk|gl cull_face front_ccw smooth\n");
        return 2;
    }
    GeomState s = {
        .primitive_mode = PRIM_TYPE_TRIANGLES,
        .polygon_front_mode = POLY_MODE_LINE,
        .polygon_back_mode = POLY_MODE_LINE,
        .smooth_shading = atoi(argv[4]) != 0,
        .line_cull_face = (uint8_t)atoi(argv[2]),
        .line_front_ccw = atoi(argv[3]) != 0,
    };
    GenGeomGlslOptions o = { .vulkan = !strcmp(argv[1], "vk") };
    MString *m = pgraph_glsl_gen_geom(&s, o);
    fputs(mstring_get_str(m), stdout);
    mstring_unref(m);
    return 0;
}
