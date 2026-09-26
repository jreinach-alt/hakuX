#!/usr/bin/env python3
"""Judge the #382 watch-suspension A/B: two 240 s Nova soaks of 50 Cent's intro.

    abjudge.py <arm A logcat.txt> <arm B logcat.txt> [--prediction <json>]

Arm A is master, arm B the hunk. The measures are the ones
docs/lanes/fps382/judge.py takes, read over fixed windows of seconds since the
first hakuX/xemu line of each logcat:

  fps           60 gfps-line intervals / seconds between the window's first
                and last hakuX-perf gfps= line (one line per 60 guest frames)
  slow stores/s hakuX-pages "slow stores N" / seconds since the previous
                pages line, median over the pages intervals inside the window
  vCPU ms/2 s   [tlb68] cpu=, median over the window
  sd per 2 s    [tlb68] sd= (tlb_set_dirty calls), median over the window

Windows: W = 58-172 s (the brief's, the teaser span on master) and C = 62-140 s
(inside the 97 s teaser on both arms even if B reaches it a few seconds early;
W's tail can hold the 30 fps front end in B, which would flatter B's fps).

The hunk's own line, [surfwatch382] suspends= rearms= gap_writes= lost_writes=,
is read from arm B at its last print.
"""
import json
import re
import sys
from datetime import datetime

TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+\w/([\w-]+)\s*\(\s*\d+\):\s?(.*)$")
PERF = re.compile(r"gfps=(\d+) G:([\d.]+).*?Vpf:([\d.]+) Ri:([\d.]+)")
KV = re.compile(r"(\w+)=([-\w.]+)")


def read(path):
    t0 = None
    run = {"perf": [], "pages": [], "tlb": [], "watch": None}
    for line in open(path, errors="replace"):
        m = TS.match(line)
        if not m:
            continue
        tag, body = m.group(2), m.group(3)
        if not (tag.startswith("hakuX") or tag.startswith("xemu")):
            continue
        t = datetime.strptime("2026-" + m.group(1), "%Y-%m-%d %H:%M:%S.%f").timestamp()
        if t0 is None:
            t0 = t
        t -= t0
        if tag == "hakuX-perf" and body.startswith("gfps="):
            if PERF.search(body):
                run["perf"].append(t)
        elif tag == "hakuX-pages" and body.startswith("slow stores"):
            run["pages"].append((t, int(re.match(r"slow stores (\d+)", body).group(1))))
        elif body.startswith("[tlb68]"):
            kv = dict(KV.findall(body))
            run["tlb"].append((t, int(kv["cpu"]), int(kv["sd"])))
        elif "[surfwatch382]" in body:
            run["watch"] = dict((k, int(v)) for k, v in KV.findall(body))
    return run


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else float("nan")


def window(run, lo, hi):
    P = [t for t in run["perf"] if lo <= t <= hi]
    r = {"fps": round(60.0 * (len(P) - 1) / (P[-1] - P[0]), 2) if len(P) > 1 else float("nan")}
    pg = run["pages"]
    rates = [b[1] / (b[0] - a[0]) for a, b in zip(pg, pg[1:]) if lo <= a[0] and b[0] <= hi and b[0] > a[0]]
    r["slow_stores_per_s"] = round(med(rates)) if rates else float("nan")
    T = [x for x in run["tlb"] if lo <= x[0] <= hi]
    r["vcpu_ms_per_2s"] = med([x[1] for x in T])
    r["sd_per_2s"] = med([x[2] for x in T])
    return r


args = sys.argv[1:]
A, B = read(args[0]), read(args[1])
pred = json.load(open(args[args.index("--prediction") + 1])) if "--prediction" in args else None


def inst_ok(run):
    return bool(run["perf"]) and run["perf"][-1] >= 200 and len(run["pages"]) >= 10


res = {}
for name, (lo, hi) in (("W", (58, 172)), ("C", (62, 140))):
    a, b = window(A, lo, hi), window(B, lo, hi)
    res[name] = {"A": a, "B": b, "fps_ratio": round(b["fps"] / a["fps"], 3) if a["fps"] == a["fps"] and a["fps"] else float("nan")}
    print("%s %d-%d s  A %s" % (name, lo, hi, json.dumps(a)))
    print("%s %d-%d s  B %s   fps B/A %.3f" % (name, lo, hi, json.dumps(b), res[name]["fps_ratio"]))
print("A: last gfps line %.1f s, pages %d, tlb68 %d" % (A["perf"][-1] if A["perf"] else 0, len(A["pages"]), len(A["tlb"])))
print("B: last gfps line %.1f s, pages %d, tlb68 %d, surfwatch382 %s" % (
    B["perf"][-1] if B["perf"] else 0, len(B["pages"]), len(B["tlb"]), json.dumps(B["watch"])))

w = B["watch"] or {}
got = {
    "M0/both_arms_instrument_ok_is": inst_ok(A) and inst_ok(B),
    "M1/b_suspends_min": w.get("suspends", float("nan")),
    "M2/a_slow_stores_per_s_W_min": res["W"]["A"]["slow_stores_per_s"],
    "P1/b_slow_stores_per_s_W_max": res["W"]["B"]["slow_stores_per_s"],
    "P2/fps_ratio_W_min": res["W"]["fps_ratio"],
    "P3/fps_ratio_C_min": res["C"]["fps_ratio"],
    "P4/b_fps_C_min": res["C"]["B"]["fps"],
    "S1/b_lost_writes_max": w.get("lost_writes", float("nan")),
}
if pred:
    exp = pred["expect"]
    void = not (got["M0/both_arms_instrument_ok_is"] and got["M2/a_slow_stores_per_s_W_min"] >= exp.get("M2/a_slow_stores_per_s_W_min", 0))
    fails = 0
    for k in sorted(exp):
        v, want = got.get(k), exp[k]
        if v is None:
            ok = False
        elif k.endswith("_is"):
            ok = v == want
        elif k.endswith("_min"):
            ok = v == v and v >= want
        elif k.endswith("_max"):
            ok = v == v and v <= want
        else:
            ok = False
        fails += not ok
        print("%-4s %-34s got %-10s want %s%s" % ("PASS" if ok else "FAIL", k, v,
              ">= " if k.endswith("_min") else "<= " if k.endswith("_max") else "== ", want))
    print("VERDICT:", "VOID (instrument or control arm)" if void else ("PASS" if not fails else "FAIL (%d)" % fails))
else:
    for k in sorted(got):
        print("%-34s %s" % (k, got[k]))
