#!/usr/bin/env python3
"""The guest's work per frame and the host's cost per unit of it, per window (lane.gta482, #482).

    unitcost.py <logcat> <marker> <from s> <to s> [<from s> <to s> ...]

Windows are seconds after the first hakuX-route line ending in <marker>. Each
hakuX-perf `gfps=` line closes 60 flips and is followed by a hakuX-phase and
a hakuX-cpu line for the same 60 flips. Per window, the mean over its lines:

  fps            60 flips per line over the time between lines
  Df, M          draws and PFIFO methods per frame: the GUEST's work
  Mth, Draw      PFIFO method time and renderer draw time per frame (ms)
  us/method, ms/draw   the HOST's cost per unit of that work

The same guest work at a higher unit cost is a slower host, not a heavier
scene. A window needs two lines at least.
"""
import re
import sys
from datetime import datetime

ts = lambda l: datetime.strptime(l[:18], "%m-%d %H:%M:%S.%f")


def rows(path, marker):
    mark = None
    out = []
    cur = None
    for l in open(path, errors="replace"):
        if len(l) < 19 or not l[:2].isdigit():
            continue
        if mark is None:
            if "hakuX-route" in l and l.rstrip().endswith(marker):
                mark = ts(l)
            continue
        m = re.search(r"hakuX-perf.*?gfps=(\d+) G:([\d.]+).*?Df:(\d+)", l)
        if m:
            cur = {"t": (ts(l) - mark).total_seconds(), "gfps": int(m[1]), "G": float(m[2]), "Df": int(m[3])}
            out.append(cur)
            continue
        if cur is None:
            continue
        m = re.search(r"hakuX-phase.*?Draw:([\d.]+)", l)
        if m and "Draw" not in cur:
            cur["Draw"] = float(m[1])
        m = re.search(r"hakuX-cpu.*? M:(\d+).*?Mth:([\d.]+)", l)
        if m and "M" not in cur:
            cur["M"], cur["Mth"] = int(m[1]), float(m[2])
    return mark, out


def main():
    path, marker = sys.argv[1], sys.argv[2]
    w = [float(x) for x in sys.argv[3:]]
    mark, r = rows(path, marker)
    if mark is None:
        sys.exit(f"no hakuX-route line ending in {marker!r}")
    print(f"{path}: mark {mark:%H:%M:%S}, {len(r)} perf lines after it")
    print(f"{'window':>12} {'lines':>5} {'fps':>6} {'Df':>6} {'M':>7} {'Mth ms':>7} {'Draw ms':>8} {'us/method':>10} {'ms/draw':>8}")
    for a, b in zip(w[0::2], w[1::2]):
        x = [k for k in r if a <= k["t"] <= b and "M" in k and "Draw" in k]
        if len(x) < 2:
            print(f"{a:5.0f}-{b:<6.0f} {len(x):>5}  too few lines")
            continue
        n = len(x)
        fps = 60 * (n - 1) / (x[-1]["t"] - x[0]["t"])
        y = x[1:]          # each line describes the 60 flips before it
        mean = lambda k: sum(v[k] for v in y) / len(y)
        df, m, mth, dr = mean("Df"), mean("M"), mean("Mth"), mean("Draw")
        print(f"{a:5.0f}-{b:<6.0f} {n:>5} {fps:6.2f} {df:6.1f} {m:7.0f} {mth:7.1f} {dr:8.1f} "
              f"{1000 * mth / m:10.2f} {dr / df if df else 0:8.3f}")


if __name__ == "__main__":
    main()
