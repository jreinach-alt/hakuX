#!/usr/bin/env python3
"""Which pgraph captures take more than one `differing` value on ONE build
(the same apk_sha) in the results on disk that do not carry this lane's
change? Those are run-to-run noise, the captures a bit-identical pixel
prediction cannot assert. A capture that differs only across builds is not
counted: that is code moving it. Reads scores1.tsv only; this lane's own
results are excluded, and result aliases are folded. Every row with a
numeric `differing` counts, whatever its status.

Usage: unstable_caps.py [--min-builds N] [--json]
  --min-builds: builds with two or more ok runs of the capture (default 1)
"""
import collections
import csv
import json
import os
import sys

D = "/home/justin/hakux-work/dispatch/results/"
min_builds = 1
if "--min-builds" in sys.argv:
    min_builds = int(sys.argv[sys.argv.index("--min-builds") + 1])

vals = collections.defaultdict(collections.Counter)      # (capture, apk) -> values
done = set()
nres = 0
for n in sorted(os.listdir(D)):
    if "memfast" in n:
        continue
    p = os.path.join(D, n, "scores1.tsv")
    real = os.path.realpath(os.path.join(D, n))
    if not os.path.isfile(p) or real in done or "memfast" in real:
        continue
    done.add(real)
    try:
        rows = list(csv.DictReader(open(p, errors="replace"), delimiter="\t"))
    except Exception:
        continue
    nres += 1
    for r in rows:
        # Every scored row counts, whatever its status. Until 2026-10-02
        # this kept `ok` rows only, which dropped the `white-content` and
        # `label-differs` captures (ZPass_pixel_count among them) and so
        # hid their same-build variation; the second pixel arm failed on
        # 36 of them.
        if not (r.get("differing") or "").isdigit():
            continue
        vals[("%s/%s" % (r["suite"], r["test"]), r["apk_sha"])][r["differing"]] += 1

per = collections.defaultdict(lambda: [0, 0, collections.Counter()])  # builds repeated, builds unstable, values
for (k, apk), c in vals.items():
    if sum(c.values()) < 2:
        continue
    per[k][0] += 1
    if len(c) > 1:
        per[k][1] += 1
        per[k][2].update(c)
unstable = {k: v for k, v in per.items() if v[1] and v[0] >= min_builds}
if "--json" in sys.argv:
    print(json.dumps(sorted(unstable)))
    sys.exit(0)
print("results read (memfast excluded, aliases folded):", nres)
print("captures run twice or more on one build: %d" % len(per))
print("of those, more than one differing value on one build: %d" % len(unstable))
for k in sorted(unstable):
    nb, nu, top = unstable[k]
    print("  %-70s unstable on %3d of %3d builds  %s" % (k, nu, nb, dict(top.most_common(5))))
