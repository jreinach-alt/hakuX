#!/usr/bin/env python3
"""Per frame of a multi-frame dump: the light tests, their counts, the skips (#1039).

usage: perframe.py DUMP.jsonl ZREP.txt [--lo HEX] [--hi HEX] [--offs]

One line per dumped frame:
  f nv2a_frame draws skips{why:n} zw tests nz sum early stale-img lit-offsets
where
  - draws: the frame's logged draws; skips: {"t":"skip"} records by "why"
    (a draw the host did not draw: no_pipeline, shader_pending, no_vk_pipeline,
    no_surface, empty_clip);
  - zw: draws before the frame's first test that wrote the test's zeta
    (ZENABLE and ZWRITE set, same zeta address) -- the hull's depth, if any;
  - tests/nz/sum: GET_REPORTs at offsets in [lo, hi) (default Halo's light
    tests, 0x60000-0x61000), how many came back nonzero, and their total;
  - early: how many of those HAKUX_ZREP marks as answered early;
  - with --offs, the nonzero offsets and values.
A report's value is joined from HAKUX_ZREP's "r" line by its serial (rs), as
vistests.py does. The frame's image is its "image" field (null: no image).
"""
import collections
import json
import sys


def load_zrep(path):
    r = {}
    for line in open(path, errors="replace"):
        p = line.split()
        if len(p) == 6 and p[0] == "r":
            r[int(p[1])] = (p[3], int(p[4]), int(p[5]))
    return r


def zstate(d):
    c0 = int(d["rs"]["c0"], 16)
    return bool(c0 & (1 << 14)), bool(c0 & (1 << 24))


def main():
    a = sys.argv[1:]
    lo, hi = 0x60000, 0x61000
    if "--lo" in a:
        lo = int(a[a.index("--lo") + 1], 16)
    if "--hi" in a:
        hi = int(a[a.index("--hi") + 1], 16)
    offs = "--offs" in a
    pos = [x for i, x in enumerate(a)
           if not x.startswith("--") and (i == 0 or a[i - 1] not in ("--lo", "--hi"))]
    dump, zrep = pos[:2]
    r = load_zrep(zrep)

    frames = collections.OrderedDict()

    def fr(f):
        return frames.setdefault(f, {"draws": [], "reps": [], "skips": collections.Counter(),
                                     "rec": None})

    for line in open(dump, errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        t = rec.get("t")
        if t == "draw":
            fr(rec["f"])["draws"].append(rec)
        elif t == "rep":
            fr(rec["f"])["reps"].append(rec)
        elif t == "skip":
            fr(rec["f"])["skips"][rec.get("why", "?")] += 1
        elif t == "frame":
            fr(rec["f"])["rec"] = rec

    print("f nv2a draws skips zw tests nz sum early image lit")
    for f, d in frames.items():
        tests = []
        for rep in d["reps"]:
            if rep["clr"] or rep["rs"] not in r:
                continue
            off, value, early = r[rep["rs"]]
            o = int(off, 16)
            if lo <= o < hi:
                tests.append((rep, o, value, early))
        zw = "-"
        if tests:
            first_n = tests[0][0]["n"]
            zeta = None
            for dr in d["draws"]:
                if dr.get("zq", -1) >= 0 and dr.get("zeta"):
                    zeta = dr["zeta"]["addr"]
                    break
            zw = sum(1 for dr in d["draws"] if dr["n"] < first_n and dr.get("zeta")
                     and (zeta is None or dr["zeta"]["addr"] == zeta)
                     and all(zstate(dr)))
        rec = d["rec"] or {}
        nz = [(o, v) for _, o, v, _ in tests if v]
        sk = ",".join(f"{k}:{v}" for k, v in sorted(d["skips"].items())) or "-"
        img = rec.get("image") or f"none({rec.get('img_sync')})"
        line = (f"{f} {rec.get('nv2a_frame', '?')} {len(d['draws'])} {sk} {zw} "
                f"{len(tests)} {len(nz)} {sum(v for _, v in nz)} "
                f"{sum(1 for t in tests if t[3])} {img}")
        if offs and nz:
            line += " " + " ".join(f"{o:x}={v}" for o, v in nz)
        print(line)


if __name__ == "__main__":
    main()
