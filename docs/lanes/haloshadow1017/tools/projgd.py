#!/usr/bin/env python3
"""The projection draws' guest state side by side across dumps (#1038).

  projgd.py DUMP.jsonl [F]   per projection draw (BLEND 0x30a, stage 0 SZ_R5G6B5 128x128): the
                             vertex constants ("c", slot -> float), the per-draw uniform attribute
                             values ("va", float), the gd path fields, and the texture matrix
                             / texgen registers in "r" decoded as floats where they are floats
Prints one block per draw; diff two runs' outputs to see what the guest handed the GPU.
"""
import json, struct, sys


def f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xffffffff))[0]


def pairs(a):
    return list(zip(a[0::2], a[1::2]))


def is_proj(d):
    t = d["tex"][0] if d.get("tex") else {}
    return d["rs"]["blend"] == "0x0000030a" and t.get("fmt") == "0x0771058a"


def main():
    want = int(sys.argv[2]) if len(sys.argv) > 2 else None
    for ln in open(sys.argv[1]):
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if d.get("t") != "draw" or not is_proj(d) or (want is not None and d["f"] != want):
            continue
        g = d.get("gd", {})
        print(f"f{d['f']} n{d['n']} shader {d.get('shader')} count {d.get('count')} kind {d.get('kind')}")
        print("  gd " + " ".join(f"{k}={g[k]}" for k in g if k not in ("r", "c", "p", "va")))
        c = pairs(g.get("c", []))
        print("  c  " + " ".join(f"{s}:{f32(v):.5g}" for s, v in c))
        print("  va " + " ".join(f"{s}:{f32(v):.5g}" for s, v in pairs(g.get("va", []))))
        print("  vr " + json.dumps(d.get("vr")))


if __name__ == "__main__":
    main()
