#!/usr/bin/env python3
"""Read a title soak's logcat into 30 s buckets of the always-on pacing lines.

    soakread.py <logcat.txt> [--from S] [--to S]

Per bucket: time-weighted gfps (each hakuX-pace window weighted by its wall
time ms=, frames f / span), G (guest flip-to-flip, smoothed), Ri (renderer
thread idle per guest frame, ms), Tq (texture dirty-bitmap queries per guest
frame), Vpf, and the hakuX-pages inval line's ev/cg if present. Over the
window [from, to) it also prints the summary the #372 doc quotes.

Time zero is the first hakuX line of the xemu process (the boot), so offsets
match the issue's "116 s in".
"""
import re
import sys
from datetime import datetime

args = sys.argv[1:]
path = args[0]
lo = float(args[args.index("--from") + 1]) if "--from" in args else 120.0
hi = float(args[args.index("--to") + 1]) if "--to" in args else 1e9

TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})\s+\w/([\w-]+)\(\s*\d+\):\s?(.*)$")
PERF = re.compile(r"gfps=(\d+) G:([\d.]+)\(([\d.]+)-([\d.]+)\).*?S:([\d.]+) J:([\d.]+) "
                  r"Df:(\d+).*?Vpf:([\d.]+) Ri:([\d.]+) Tq:(\d+)")
PACE = re.compile(r"f=(\d+) v0=(\d+) v1=(\d+) v2=(\d+) v3=(\d+) v4=(\d+) vb=(\d+) "
                  r"max=([\d.]+) ms=([\d.]+)")
PHASE = re.compile(r"(\w+):([\d.]+)")


def ts(s):
    return datetime.strptime("2026-" + s, "%Y-%m-%d %H:%M:%S.%f").timestamp()


t0 = None
perf, pace, phase, pages = [], [], [], []
for line in open(path, errors="replace"):
    m = TS.match(line)
    if not m:
        continue
    t, tag, body = ts(m.group(1)), m.group(2), m.group(3)
    if t0 is None and tag.startswith("hakuX"):
        t0 = t
    if t0 is None:
        continue
    t -= t0
    if tag == "hakuX-perf" and body.startswith("gfps="):
        p = PERF.search(body)
        if p:
            perf.append((t,) + tuple(float(x) for x in p.groups()))
    elif tag == "hakuX-pace":
        p = PACE.search(body)
        if p:
            pace.append((t,) + tuple(float(x) for x in p.groups()))
    elif tag == "hakuX-phase":
        phase.append((t, body))
    elif tag == "hakuX-pages" and body.startswith("inval"):
        kv = dict(PHASE.findall(body.replace("=", ":")))
        pages.append((t, kv))


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else float("nan")


def tw_fps(rows):
    """Frames over wall time: 60 frames per pace window / its ms span."""
    fr = sum(60 for r in rows if r[9] > 0)
    ms = sum(r[9] for r in rows if r[9] > 0)
    return 1000.0 * fr / ms if ms else float("nan")


print("pace windows %d, perf lines %d, phase lines %d, pages lines %d" %
      (len(pace), len(perf), len(phase), len(pages)))
print("%5s %5s %6s %6s %6s %6s %6s %5s" %
      ("t", "n", "twfps", "G", "Ri", "Tq", "Vpf", "vmax"))
end = max([r[0] for r in pace] + [r[0] for r in perf] + [0])
b = 0.0
while b <= end:
    pr = [r for r in pace if b <= r[0] < b + 30]
    fr = [r for r in perf if b <= r[0] < b + 30]
    print("%5.0f %5d %6.1f %6.1f %6.1f %6.0f %6.2f %5.0f" % (
        b, len(pr), tw_fps(pr), med([r[2] for r in fr]), med([r[9] for r in fr]),
        med([r[10] for r in fr]), med([r[8] for r in fr]),
        max([r[8] for r in pr] + [0])))
    b += 30

W = [r for r in pace if lo <= r[0] < hi]
F = [r for r in perf if lo <= r[0] < hi]
print("\nwindow [%.0f, %.0f) s: pace windows %d" % (lo, min(hi, end), len(W)))
if W:
    spans = [r[9] for r in W]
    print("  time-weighted gfps %.1f; per-window gfps min %.1f max %.1f" % (
        tw_fps(W), min(60000 / s for s in spans), max(60000 / s for s in spans)))
    vb = [sum(r[k] for r in W) for k in range(2, 7)]
    print("  flips per VBLANK v0..v4: %s (of %d flips); worst flip gap %.1f ms" % (
        vb, sum(vb), max(r[8] for r in W)))
if F:
    G = [r[2] for r in F]
    Ri = [r[9] for r in F]
    print("  G median %.1f ms; Ri median %.1f ms -> renderer busy %.0f%% of a guest frame" % (
        med(G), med(Ri), 100.0 * (1 - med(Ri) / med(G))))
    print("  Tq median %.0f queries/frame; Df last %d" % (med([r[10] for r in F]), F[-1][7]))
P = [p for p in phase if lo <= p[0] < hi]
if P:
    keys = []
    for k, _ in PHASE.findall(P[0][1]):
        if k not in keys:
            keys.append(k)
    vals = dict((k, []) for k in keys)
    for _, body in P:
        seen = set()
        for k, v in PHASE.findall(body):
            if k in seen:
                continue
            seen.add(k)
            vals[k].append(float(v))
    print("  phase medians (%d lines): %s" % (
        len(P), " ".join("%s=%.1f" % (k, med(vals[k])) for k in keys)))
