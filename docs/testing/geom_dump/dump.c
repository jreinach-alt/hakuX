/*
 * geom-dump -- print the GLSL pgraph_glsl_gen_geom() actually emits.
 *
 * A geometry shader that fails to compile draws NOTHING on the Vulkan path,
 * and does it silently: pgraph_vk_compile_glsl_to_spv() returns NULL and
 * shader_module_cache_entry_gen() leaves module_info NULL, with no VkResult to
 * check (audit finding L10, and the reason vk/instance.c carries the geometry
 * limits).  Neither CI job compiles this GLSL.  So print it, and feed it to a
 * GLSL front end offline:
 *
 *     make run > /tmp/geom.glsl.txt      # every case, with banners
 *     make run -- --only lines_smooth_vk # one case, bare, for a validator
 *
 * Copyright (c) 2026 hakuX contributors
 * SPDX-License-Identifier: GPL-2.0-or-later
 */

#include "qemu/osdep.h"
#include "hw/xbox/nv2a/pgraph/pgraph.h"
#include "geom.h"

typedef struct {
    const char *name;
    GeomState state;
    GenGeomGlslOptions opts;
} Case;

int main(int argc, char **argv)
{
    const char *only = NULL;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--only") && i + 1 < argc) {
            only = argv[++i];
        }
    }

    Case cases[] = {
        { "lines_smooth_vk",
          { .primitive_mode = PRIM_TYPE_LINES,
            .polygon_front_mode = POLY_MODE_FILL,
            .polygon_back_mode = POLY_MODE_FILL,
            .smooth_shading = true },
          { .vulkan = true } },
        { "lines_flat_vk",
          { .primitive_mode = PRIM_TYPE_LINES,
            .polygon_front_mode = POLY_MODE_FILL,
            .polygon_back_mode = POLY_MODE_FILL,
            .smooth_shading = false },
          { .vulkan = true } },
        { "lines_smooth_zpersp_cylwrap_vk",
          { .primitive_mode = PRIM_TYPE_LINES,
            .polygon_front_mode = POLY_MODE_FILL,
            .polygon_back_mode = POLY_MODE_FILL,
            .smooth_shading = true,
            .z_perspective = true,
            .noperspective = true,
            .cylinder_wrap = { 3, 0, 5, 8 } },
          { .vulkan = true } },
        { "tri_polymode_line_smooth_vk",
          { .primitive_mode = PRIM_TYPE_TRIANGLES,
            .polygon_front_mode = POLY_MODE_LINE,
            .polygon_back_mode = POLY_MODE_LINE,
            .smooth_shading = true },
          { .vulkan = true } },
        { "tri_polymode_line_flat_vk",
          { .primitive_mode = PRIM_TYPE_TRIANGLES,
            .polygon_front_mode = POLY_MODE_LINE,
            .polygon_back_mode = POLY_MODE_LINE,
            .smooth_shading = false },
          { .vulkan = true } },
        { "tri_fill_smooth_vk",
          { .primitive_mode = PRIM_TYPE_TRIANGLES,
            .polygon_front_mode = POLY_MODE_FILL,
            .polygon_back_mode = POLY_MODE_FILL,
            .smooth_shading = true },
          { .vulkan = true } },
        /* The GL renderer keeps the native line path: no widening, and this
         * case is what shows that nothing above reached it. */
        { "lines_smooth_gl",
          { .primitive_mode = PRIM_TYPE_LINES,
            .polygon_front_mode = POLY_MODE_FILL,
            .polygon_back_mode = POLY_MODE_FILL,
            .smooth_shading = true },
          { .vulkan = false } },
        { "tri_polymode_line_smooth_gl",
          { .primitive_mode = PRIM_TYPE_TRIANGLES,
            .polygon_front_mode = POLY_MODE_LINE,
            .polygon_back_mode = POLY_MODE_LINE,
            .smooth_shading = true },
          { .vulkan = false } },
    };

    for (unsigned i = 0; i < ARRAY_SIZE(cases); i++) {
        if (only && strcmp(only, cases[i].name)) {
            continue;
        }
        if (!pgraph_glsl_need_geom(&cases[i].state)) {
            if (!only) {
                printf("=== %s: no geometry shader\n", cases[i].name);
            }
            continue;
        }
        MString *s = pgraph_glsl_gen_geom(&cases[i].state, cases[i].opts);
        if (!s) {
            if (!only) {
                printf("=== %s: generator returned NULL\n", cases[i].name);
            }
            continue;
        }
        if (!only) {
            printf("=== %s\n", cases[i].name);
        }
        fputs(mstring_get_str(s), stdout);
        mstring_unref(s);
    }
    return 0;
}
