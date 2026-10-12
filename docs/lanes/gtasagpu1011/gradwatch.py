"""Read a schema-8 dump: each logged draw into a small target, its inline-array
vertices decoded ("ia"), and its readbacks as per-row channel means.
usage: gradwatch.py DUMP [ADDR]   (ADDR, hex: only draws that target or sample it)"""
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fdread  # noqa: E402

# NV097_SET_VERTEX_DATA_ARRAY_FORMAT_TYPE
UB_D3D, S1, F, UB_OGL, S32K, CMP = 0, 1, 2, 4, 5, 6


def ia_vertices(ia):
    w = [int(x, 16) for x in ia["w"].split()]
    vs = ia["vs"] // 4
    out = []
    for k in range(len(w) // vs):
        v = {}
        for i, off, size, count, fmt in ia["attrs"]:
            base = k * vs + off // 4
            if fmt == F:
                v[i] = [struct.unpack("<f", struct.pack("<I", w[base + j]))[0]
                        for j in range(count)]
            elif fmt in (UB_D3D, UB_OGL) and size == 1:
                x = w[base]
                b = [(x >> s) & 0xFF for s in (0, 8, 16, 24)]
                # D3D: bytes B,G,R,A -> report as R,G,B,A
                v[i] = [b[2], b[1], b[0], b[3]] if fmt == UB_D3D else b
            else:
                v[i] = ["%08x" % w[base + j] for j in range((size * count + 3) // 4)]
        out.append(v)
    return out


def rows(base, e):
    im = fdread.load_rgba(base, e)
    if im is None:
        return None
    a = np.asarray(im.convert("RGBA"), dtype=np.float64)
    return a


def main():
    path = sys.argv[1]
    want = int(sys.argv[2], 16) if len(sys.argv) > 2 else None
    base = os.path.dirname(path)
    session, draws, frames, _ = fdread.load(path)
    print("session: schema %s spec %r watch %s" % (
        session.get("schema"), session.get("spec"), session.get("watch")))
    for d in draws:
        c = d.get("color") or {}
        caddr = int(c.get("addr", "0"), 16) if c else 0
        sampled = [int(t["off"], 16) for t in d.get("tex", []) if t.get("en")]
        rbs = d.get("rb", [])
        if want is not None and caddr != want and want not in sampled and \
                not any(int(e["addr"], 16) == want for e in rbs):
            continue
        print("f%d n%d %s count %d prim %d -> 0x%x %dx%d fmt %s sw %s | shader %s blend %s | tex %s" % (
            d["f"], d["n"], d["kind"], d["count"], d["prim"], caddr, c.get("w", 0),
            c.get("h", 0), c.get("fmt"), c.get("swizzle"), d["shader"][:8],
            d["rs"]["blend"], ",".join("0x%x" % s for s in sampled) or "-"))
        if "ia" in d:
            for k, v in enumerate(ia_vertices(d["ia"])):
                print("    v%d %s" % (k, "  ".join(
                    "a%d=%s" % (i, ",".join(("%.4g" % x) if isinstance(x, float) else str(x)
                                            for x in v[i])) for i in sorted(v))))
        for e in rbs:
            a = rows(base, e) if e.get("file") else None
            if a is None:
                print("    rb %s s%d 0x%s %dx%d: no file" % (e["k"], e["s"], e["addr"][2:], e["w"], e["h"]))
                continue
            r = a[..., 0]
            print("    rb %s s%d %s %dx%d vkfmt %d: R min %d max %d; G-R max |%d|, B-R max |%d|; A %d..%d" % (
                e["k"], e["s"], e["addr"], e["w"], e["h"], e["vkfmt"], r.min(), r.max(),
                np.abs(a[..., 1] - r).max(), np.abs(a[..., 2] - r).max(),
                a[..., 3].min(), a[..., 3].max()))
            if e["w"] <= 64 and e["h"] <= 64:
                rm = r.mean(axis=1)
                rs = r.max(axis=1) - r.min(axis=1)
                print("      row mean R: %s" % " ".join("%d" % round(x) for x in rm))
                print("      row spread R: %s" % " ".join("%d" % x for x in rs))


if __name__ == "__main__":
    main()
