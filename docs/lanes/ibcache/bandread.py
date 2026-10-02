#!/usr/bin/env python3
"""Read a multi-run pgraph arm pair as a flip band (ibcache-probe-band.json).

For each capture: the set of image hashes each arm drew over its runs.
A capture self-identical in both arms and different between them is the
outcome that kills the change; a capture that flips inside an arm is band.
Usage: bandread.py <result dir A> <result dir B>
"""
import hashlib
import os
import sys


def hashes(r):
    out = {}
    i = 1
    while os.path.isdir(os.path.join(r, f"captures{i}")):
        d = os.path.join(r, f"captures{i}")
        for root, _, fs in os.walk(d):
            for f in fs:
                if f.endswith(".png"):
                    p = os.path.join(root, f)
                    k = os.path.relpath(p, d)
                    h = hashlib.sha256(open(p, "rb").read()).hexdigest()[:10]
                    out.setdefault(k, {})[i] = h
        i += 1
    return out, i - 1


def main():
    a, na = hashes(sys.argv[1])
    b, nb = hashes(sys.argv[2])
    keys = sorted(set(a) | set(b))
    print(f"runs A={na} B={nb} captures={len(keys)}")
    kill, flip_a, flip_b, moved, missing = [], [], [], [], []
    for k in keys:
        ra, rb = a.get(k, {}), b.get(k, {})
        if len(ra) != na or len(rb) != nb:
            missing.append(k)
        sa, sb = set(ra.values()), set(rb.values())
        if len(sa) > 1:
            flip_a.append(k)
        if len(sb) > 1:
            flip_b.append(k)
        if len(sa) == 1 and len(sb) == 1 and sa != sb:
            kill.append(k)
        if sa != sb:
            moved.append(k)
            print(f"  {k}: A={[ra.get(i) for i in range(1, na + 1)]} "
                  f"B={[rb.get(i) for i in range(1, nb + 1)]}")
    print(f"missing in some run: {len(missing)} {missing}")
    print(f"flip inside A: {len(flip_a)}")
    print(f"flip inside B: {len(flip_b)}")
    print(f"image sets differ A vs B: {len(moved)}")
    print(f"KILL (self-identical in each arm, different between): "
          f"{len(kill)} {kill}")


if __name__ == "__main__":
    main()
