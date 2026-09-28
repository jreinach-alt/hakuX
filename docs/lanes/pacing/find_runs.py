#!/usr/bin/env python3
"""List recent dispatch soak results for a title substring: device, apk,
seconds, and gfps median over the run (from hakuX-perf lines). Scratch aid
for choosing #526's arm titles."""
import glob, json, os, re, statistics, sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
pats = [p.lower() for p in sys.argv[1].split(",")]
rows = []
for rj in glob.glob(os.path.join(D, "results", "*", "result.json")):
    try:
        r = json.load(open(rj))
    except Exception:
        continue
    t = str(r.get("title") or "")
    if not any(p in t.lower() for p in pats):
        continue
    d = os.path.dirname(rj)
    g = []
    for lc in glob.glob(os.path.join(d, "*logcat*")):
        try:
            for line in open(lc, errors="replace"):
                m = re.search(r"hakuX-perf.*gfps=(\d+)", line)
                if m:
                    g.append(int(m.group(1)))
        except Exception:
            pass
    rows.append((os.path.getmtime(rj), os.path.basename(d), t[:28], r.get("device_label") or r.get("device"),
                 r.get("seconds"), r.get("route"), len(g),
                 statistics.median(g) if g else None,
                 statistics.median(g[len(g) // 2:]) if g else None))
for row in sorted(rows, key=lambda r: (r[2], r[0]))[-int(sys.argv[2] if len(sys.argv) > 2 else 12):]:
    print(*row[1:], sep="\t")
