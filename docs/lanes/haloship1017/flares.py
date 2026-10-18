#!/usr/bin/env python3
"""What the guest gave each flare quad, per frame (#1039).

usage: flares.py DUMP.jsonl F0 F1 [--shader PREFIX ...]

Halo draws its light flares as inline_buffer quads (prim 7, count 4) with the
depth test OFF (r4b: 12 quads of shader 7d6aedad, texture 8d84860d, and two of
a5aae408, after the light tests, in the behind frame and in the front frames
alike). So the hull cannot hide them on the GPU: what hides a flare is what
the CPU put in its vertices. The dump has no inline_buffer vertex data, but
schema 9's gd "va" is every attribute's inline value as of the draw, as
deltas from the previous logged draw; replayed, it is the LAST vertex of the
quad (SET_VERTEX_DATA writes inline_value, then the vertex is appended).

Prints, per flare draw in frames [F0, F1]: f n shader, attr0 (position),
attr3 (diffuse), attr4 (specular), attr9 (tex0), as floats.
"""
import json
import struct
import sys

NAMES = {0: "pos", 3: "dif", 4: "spec", 9: "t0"}


def f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


def main():
    a = sys.argv[1:]
    shaders = []
    while "--shader" in a:
        i = a.index("--shader")
        shaders.append(a[i + 1])
        del a[i:i + 2]
    shaders = shaders or ["7d6aedad", "a5aae408"]
    dump, f0, f1 = a[0], int(a[1]), int(a[2])
    va = [0] * (16 * 4)
    for line in open(dump, errors="replace"):
        if '"t": "draw"' not in line and '"t":"draw"' not in line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        d = rec.get("va") or (rec.get("gd") or {}).get("va") or []
        for i in range(0, len(d) - 1, 2):
            va[d[i]] = d[i + 1]
        if not (f0 <= rec.get("f", -1) <= f1):
            continue
        if not any(rec["shader"].startswith(s) for s in shaders):
            continue
        parts = [f"f{rec['f']} n{rec['n']} {rec['shader'][:8]}"]
        for at, nm in NAMES.items():
            v = [f32(va[at * 4 + c]) for c in range(4)]
            parts.append(f"{nm}=(" + ",".join(f"{x:.3g}" for x in v) + ")")
        print(" ".join(parts))


if __name__ == "__main__":
    main()
