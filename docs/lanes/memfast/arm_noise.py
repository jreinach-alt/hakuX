#!/usr/bin/env python3
"""Across every arms result on disk: how do the six moved captures score on
builds that do not carry this lane's change? Reads scores1.tsv only."""
import collections
import csv
import json
import os

D = "/home/justin/hakux-work/dispatch/results/"
WANT = {
    "GeometrySuperscreen_0.4999", "GeometrySuperscreen_0.5626",
    "Stencil_ZERO", "Stencil_ZERO_ST_DT", "Stencil_ZERO_ST_DT_ZB", "Stencil_ZERO_ST_ZB",
}
seen = collections.defaultdict(collections.Counter)
where = collections.defaultdict(list)
hdr = None
nres = 0
done = set()
tot = collections.defaultdict(collections.Counter)
for n in sorted(os.listdir(D)):
    if "memfast" in n:
        continue
    p = os.path.join(D, n, "scores1.tsv")
    if not os.path.isfile(p):
        continue
    real = os.path.realpath(os.path.join(D, n))
    if real in done or "memfast" in real:
        continue
    done.add(real)
    dev = ref = "?"
    try:
        rj = json.load(open(os.path.join(D, n, "request.json")))
        dev = str(rj.get("device", "?"))
        ref = str(rj.get("ref", rj.get("sha", "?")))[:10]
    except Exception:
        pass
    try:
        rows = list(csv.reader(open(p, errors="replace"), delimiter="\t"))
    except Exception:
        continue
    if not rows:
        continue
    if hdr is None:
        hdr = rows[0]
        print("header", hdr)
    nres += 1
    for r in rows[1:]:
        hit = [w for w in WANT if w in r]
        if hit:
            key = hit[0]
            val = tuple(r[2:9])
            seen[(key, dev)][val] += 1
            tot[(r[0], key)][r[4]] += 1
            where[(key, dev, val)].append((n, ref))
print("results with scores1.tsv (memfast excluded, aliases folded):", nres)
print("\nTOTALS over all devices: capture, runs, not exact, differing-px values")
for (suite, key), c in sorted(tot.items()):
    runs = sum(c.values())
    bad = runs - c.get("0", 0)
    vals = ", ".join(f"{v} ({k})" for v, k in sorted(c.items(), key=lambda x: -x[1]) if v != "0")
    print(f"  {suite}/{key}: {runs} runs, {bad} not exact: {vals}")
for (key, dev), c in sorted(seen.items()):
    print(f"\n{key}  device={dev}: {sum(c.values())} runs, {len(c)} distinct score rows")
    for val, k in c.most_common(6):
        ex = where[(key, dev, val)]
        print(f"   {k:4d}x {val}   e.g. {ex[-1][0]} ref {ex[-1][1]}")
