#!/usr/bin/env python3
"""Produce a copy of glsl/geom.c with the one PGRAPHState reader removed.

Same split, and the same reason, as psh_differ/carve.py: the generator half
(`pgraph_glsl_gen_geom`, `pgraph_glsl_need_geom`) turns a GeomState into GLSL
and reads nothing else, while `pgraph_glsl_set_geom_state` fills a GeomState
in from a live PGRAPHState and needs the real header.  Each removed line
becomes a blank line so surviving lines keep their numbers.

Exits non-zero if the signature stops matching, rather than carving something
unexpected -- and if a NEW function starts reading PGRAPHState it will fail to
compile here rather than be silently included.
"""

import argparse
import sys
from pathlib import Path

CARVE = ("void pgraph_glsl_set_geom_state(PGRAPHState *pg, GeomState *state)",)


def carve(text, sig):
    i = text.find(sig)
    if i < 0:
        sys.exit(f"carve.py: signature no longer present: {sig}")
    j = text.find("{", i)
    depth, k = 0, j
    while k < len(text):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                k += 1
                break
        k += 1
    cut = text[i:k]
    return text[:i] + "\n" * cut.count("\n") + text[k:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    text = Path(a.source).read_text()
    for sig in CARVE:
        text = carve(text, sig)
    Path(a.output).write_text(text)


if __name__ == "__main__":
    main()
