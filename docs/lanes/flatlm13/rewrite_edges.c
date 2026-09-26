/*
 * What prim_rewrite.c emits for the line-mode QUADS / QUAD_STRIP / POLYGON
 * draws of Shade_model's ProgLM tests, flat and smooth.  Built against
 * the real prim_rewrite.c by rewrite_edges.sh; no emulator needed.
 */
#include <stdio.h>
#include "qemu/osdep.h"
#include "prim_rewrite.h"

static void run(const char *name, enum ShaderPrimitiveMode pm, bool flat,
                bool last, unsigned n)
{
    PrimRewriteBuf b;
    pgraph_prim_rewrite_init(&b);
    PrimAssemblyState m = { .primitive_mode = pm,
                            .polygon_mode = POLY_MODE_LINE,
                            .last_provoking = last,
                            .flat_shading = flat };
    int32_t s = 0, c = n;
    PrimRewrite r = pgraph_prim_rewrite_ranges(&b, m, &s, &c, 1);
    printf("%-7s %-6s %-5s:", name, flat ? "flat" : "smooth",
           last ? "last" : "first");
    for (unsigned i = 0; i < r.num_indices; i += 2) {
        printf(" (%u,%u)", r.indices[i], r.indices[i + 1]);
    }
    printf("\n");
    pgraph_prim_rewrite_finalize(&b);
}

int main(void)
{
    for (int f = 0; f < 2; f++) {
        for (int l = 0; l < 2; l++) {
            run("QUADS", PRIM_TYPE_QUADS, f, l, 8);
            run("QSTRIP", PRIM_TYPE_QUAD_STRIP, f, l, 6);
            run("POLY5", PRIM_TYPE_POLYGON, f, l, 5);
            run("POLY3", PRIM_TYPE_POLYGON, f, l, 3);
            run("POLY2", PRIM_TYPE_POLYGON, f, l, 2);
        }
    }
    return 0;
}
