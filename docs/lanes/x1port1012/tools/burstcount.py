#!/usr/bin/env python3
"""Group ringtrack.py rows whose nearest image is older than the previous one
(nearest_lag > 1) into bursts: rows closer than GAP s apart share a burst.
Usage: burstcount.py <offset_s> <tsv> [<offset_s> <tsv> ...]
offset_s is the clip's start relative to the soak mark, so bursts print in
soak seconds. A burst of one row is reported separately as a singleton."""
import sys

GAP = 1.0
args = sys.argv[1:]
rows = []
span = 0.0
for off, path in zip(args[0::2], args[1::2]):
    off = float(off)
    pts = []
    for line in open(path):
        f = line.rstrip("\n").split("\t")
        if f[0] == "k":
            continue
        t = float(f[2])
        pts.append(t)
        if int(f[6]) > 1:
            rows.append((off + t, int(f[6])))
    if pts:
        span += pts[-1] - pts[0]
rows.sort()
bursts = []
for t, lag in rows:
    if bursts and t - bursts[-1][-1][0] <= GAP:
        bursts[-1].append((t, lag))
    else:
        bursts.append([(t, lag)])
multi = [b for b in bursts if len(b) > 1]
single = [b for b in bursts if len(b) == 1]
for b in multi:
    print(f"burst +{b[0][0]:.1f}..+{b[-1][0]:.1f} s: {len(b)} images, max lag {max(l for _, l in b)}")
for b in single:
    print(f"singleton +{b[0][0]:.1f} s lag {b[0][1]}")
print(f"{len(multi)} bursts, {len(single)} singletons, {len(rows)} back-images over {span:.1f} s of clip")
