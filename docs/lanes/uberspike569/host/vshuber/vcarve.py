#!/usr/bin/env python3
"""Carve vsh.c's emulator-state half out, for building the vertex generators
on the host. psh_differ's carve.py does the same for psh.c; this reuses its
brace walker with vsh.c's own list.

    vcarve.py SRC -o OUT
"""
import argparse
import importlib.util
import os
import re
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
CARVE_PY = os.path.join(HERE, "../../../../testing/psh_differ/carve.py")
spec = importlib.util.spec_from_file_location("carve", CARVE_PY)
carve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(carve)

CARVE = {
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
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    a = ap.parse_args()
    sigs = CARVE.get(a.source.name, ())
    text = a.source.read_text()
    lines = text.splitlines(keepends=True)
    offs, pos = [], 0
    for ln in lines:
        offs.append(pos)
        pos += len(ln)

    def line_of(o):
        lo, hi = 0, len(offs) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if offs[mid] <= o:
                lo = mid
            else:
                hi = mid - 1
        return lo

    blank = set()
    for sig in sigs:
        idx = text.find("\n" + sig)
        if idx < 0:
            raise SystemExit("vcarve.py: no line starts with %r in %s" % (sig, a.source))
        start = idx + 1
        end = carve.find_body_end(text, start)
        blank.update(range(line_of(start), line_of(end - 1) + 1))
    for n, ln in enumerate(lines):
        if n not in blank and re.match(r"^[A-Za-z_].*PGRAPHState \*", ln):
            raise SystemExit("vcarve.py: %s:%d reads emulator state and is not carved:\n  %s"
                             % (a.source, n + 1, ln))
    out = ['#line 1 "%s"\n' % a.source]
    out += ["\n" if n in blank else ln for n, ln in enumerate(lines)]
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text("".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
