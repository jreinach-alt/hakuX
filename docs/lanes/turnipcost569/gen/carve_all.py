#!/usr/bin/env python3
"""psh_differ's carve.py, extended to every generator file the Vulkan path uses.

    carve_all.py <source.c> -o <out.c>

Same contract as docs/testing/psh_differ/carve.py (which this imports): the
functions that read PGRAPHState are blanked line for line, and anything else
taking a PGRAPHState stops the build.
"""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location(
    "carve", REPO / "docs/testing/psh_differ/carve.py")
carve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(carve)

carve.CARVE.update({
    "vsh.c": (
        "static void set_fixed_function_vsh_state(PGRAPHState *pg,",
        "static void set_programmable_vsh_state(PGRAPHState *pg,",
        "void pgraph_glsl_set_vsh_state(PGRAPHState *pg, VshState *vsh)",
        "static float ff_radial_fog_coord(PGRAPHState *pg)",
        "static unsigned int ring_draw_vertex_count(PGRAPHState *pg)",
        "unsigned int pgraph_glsl_ring_fill(PGRAPHState *pg)",
        "static float ring_phase(PGRAPHState *pg, const VshState *state)",
        "bool pgraph_glsl_ring_uniforms_stale(PGRAPHState *pg, const VshState *state)",
        "void pgraph_glsl_set_vsh_uniform_values(PGRAPHState *pg, const VshState *state,",
    ),
    "geom.c": (
        "void pgraph_glsl_set_geom_state(PGRAPHState *pg, GeomState *state)",
    ),
    "vsh-ff.c": (),
    "vsh-prog.c": (),
})

if __name__ == "__main__":
    sys.exit(carve.main())
