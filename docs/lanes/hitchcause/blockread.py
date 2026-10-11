"""Read allwin.txt (hitchwin.py --all) and test what tracks the vCPU's blocked share.

blocked = 100 - run%  : the vCPU thread's time that is neither on CPU nor on a
run queue (schedstat sleep; idlehalt span - run - rq). A guest busy clock
(rr425w busy) cannot see it, because it counts wall time outside the idle loop.

Prints: the hitch windows (max >= 200 ms) against every window, medians per
group, and the Pearson r of blocked% with each counter over all windows.
Stdlib only.
"""
import math
import re
import statistics
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "allwin.txt"
FIELD = re.compile(r"(\w+)=\s*(-?[0-9.]+|nan)")
ROW = re.compile(r"^(\d\d:\d\d:\d\d\.\d\d) max=\s*([0-9.]+)")


def parse(line):
    m = ROW.match(line)
    if not m:
        return None
    d = {"t": m.group(1), "max": float(m.group(2))}
    # run%= and busy= have % signs; take them by name
    for k, v in re.findall(r"(run|busy)=\s*([0-9.]+)%", line):
        d[k] = float(v)
    for k, v in re.findall(r"(rq)=\s*([0-9.]+)ms", line):
        d[k] = float(v)
    for k, v in FIELD.findall(line):
        if k in ("max", "run", "busy", "rq"):
            continue
        if v != "nan":
            d.setdefault(k, float(v))
    d["blocked"] = 100.0 - d.get("run", 100.0)
    return d


rows = []
with open(PATH) as fh:
    for line in fh:
        r = parse(line.rstrip("\n"))
        if r:
            rows.append(r)

print("windows: %d" % len(rows))
hitch = [r for r in rows if r["max"] >= 200]
base = [r for r in rows if r["max"] < 100]
mid = [r for r in rows if 100 <= r["max"] < 200]


def med(group, key):
    xs = [r[key] for r in group if key in r]
    return statistics.median(xs) if xs else float("nan")


keys = ["blocked", "rq", "busy", "ff", "pf", "jcus", "gc", "cg", "gus", "disc",
        "tcpu", "v", "dr_mean", "dr_max", "bl_max", "slow", "vb", "G"]
print("%-9s %8s %8s %8s" % ("counter", "base<100", "100-200", ">=200"))
for k in keys:
    print("%-9s %8.2f %8.2f %8.2f" % (k, med(base, k), med(mid, k), med(hitch, k)))

print("\nhitch windows (max >= 200):")
for r in hitch:
    print("  %s max=%6.1f blocked=%5.1f rq=%5.1f ff=%-4s pf=%-5s jcus=%-4s cg=%-4s "
          "disc=%-5s dr_max=%5.1f bl_max=%7.0f tcpu=%-5s slow=%s" % (
              r["t"], r["max"], r["blocked"], r.get("rq", float("nan")),
              r.get("ff"), r.get("pf"), r.get("jcus"), r.get("cg"), r.get("disc"),
              r.get("dr_max", float("nan")), r.get("bl_max", float("nan")),
              r.get("tcpu"), r.get("slow")))


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return float("nan")
    return sxy / math.sqrt(sxx * syy)


print("\nPearson r of blocked%% vs counter (all %d windows with the field):" % len(rows))
for k in ["rq", "busy", "ff", "pf", "jcus", "gc", "cg", "gus", "disc", "tcpu", "v",
          "dr_mean", "dr_max", "bl_max", "slow", "vb", "max"]:
    pr = [(r["blocked"], r[k]) for r in rows if k in r]
    xs = [b for b, _ in pr]
    ys = [v for _, v in pr]
    print("  %-8s n=%4d r=%6.3f" % (k, len(pr), pearson(ys, xs)))
