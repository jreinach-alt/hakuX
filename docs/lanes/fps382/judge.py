#!/usr/bin/env python3
"""Judge a 50 Cent: Bulletproof intro soak against fps382-intro-soak.json.

    judge.py <logcat.txt> [--prediction <json>]

Spans come from the always-on `hakuX-perf gfps=` line, printed every 60th
guest frame (profile.c), so consecutive lines 60 frames apart give 60 / dt
frames per second with no smoothing. A SLOW interval is <= 12 fps, a FAST one
>= 25 fps. The slow span is the longest contiguous run of slow intervals, the
fast span the longest run of fast ones. Everything else is read inside those
spans:

  renderer busy   1 - Ri/G, median over the span's gfps lines
  flips >= 4 VBL  hakuX-pace v4 / (v0..v4), summed over the span's pace lines
  slow stores/s   hakuX-pages "slow stores N ... since last", divided by the
                  time since the previous pages line, both lines in the span
  sd per 2 s      [tlb68] sd= (tlb_set_dirty calls), median over the span
  vCPU ms per 2 s [tlb68] cpu= (vCPU thread CPU time), median over the span
  GPU / record ms perflog only: xemu-gpu Tot, hakuX-phase fields, medians

With --prediction it checks every `expect` rule and prints PASS/FAIL per rule
and VOID if the instrument rule fails. Rules ending _min are lower bounds,
_max upper bounds, and _is an exact boolean.
"""
import json
import re
import sys
from datetime import datetime

TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+\w/([\w-]+)\s*\(\s*\d+\):\s?(.*)$")
PERF = re.compile(r"gfps=(\d+) G:([\d.]+).*?Vpf:([\d.]+) Ri:([\d.]+)")
PACE = re.compile(r"f=(\d+) v0=(\d+) v1=(\d+) v2=(\d+) v3=(\d+) v4=(\d+) vb=(\d+) max=([\d.]+) ms=([\d.]+)")
KV = re.compile(r"(\w+)=([-\w.]+)")
PH = re.compile(r"(\w+):([\d.]+)")

args = sys.argv[1:]
path = args[0]
pred = json.load(open(args[args.index("--prediction") + 1])) if "--prediction" in args else None

t0 = None
perf, pace, tlb, pages, gpu, phase = [], [], [], [], [], []
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
        p = PERF.search(body)
        if p:
            perf.append((t, float(p.group(2)), float(p.group(4))))
    elif tag == "hakuX-pace":
        p = PACE.search(body)
        if p:
            pace.append((t,) + tuple(int(p.group(k)) for k in range(2, 7)))
    elif tag == "hakuX" and body.startswith("[tlb68]"):
        kv = dict(KV.findall(body))
        tlb.append((t, int(kv["cpu"]), int(kv["sd"])))
    elif tag == "hakuX-pages" and body.startswith("slow stores"):
        s = re.match(r"slow stores (\d+)", body)
        pages.append((t, int(s.group(1))))
    elif tag == "xemu-gpu":
        g = re.search(r"Tot:([\d.]+)", body)
        if g:
            gpu.append((t, float(g.group(1))))
    elif tag == "hakuX-phase":
        phase.append((t, dict((k, float(v)) for k, v in PH.findall(body))))


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else float("nan")


def longest(pred_fn):
    """Longest contiguous run of gfps-line intervals whose fps passes pred_fn."""
    best, cur = (0.0, 0.0, 0), None
    for a, b in zip(perf, perf[1:]):
        dt = b[0] - a[0]
        ok = 0 < dt < 30 and pred_fn(60.0 / dt)
        if ok:
            cur = (cur[0], b[0], cur[2] + 1) if cur else (a[0], b[0], 1)
            if cur[1] - cur[0] > best[1] - best[0]:
                best = cur
        else:
            cur = None
    return best


def span_stats(lo, hi, n):
    r = {"from_s": round(lo, 1), "to_s": round(hi, 1), "len_s": round(hi - lo, 1)}
    r["fps"] = round(60.0 * n / (hi - lo), 2) if hi > lo else float("nan")
    F = [p for p in perf if lo <= p[0] <= hi]
    r["renderer_busy_pct"] = round(100.0 * (1 - med([p[2] for p in F]) / med([p[1] for p in F])), 1) if F else float("nan")
    P = [p for p in pace if lo < p[0] <= hi]
    flips = sum(sum(p[1:6]) for p in P)
    r["pace_lines"] = len(P)
    r["flips_ge4vbl_pct"] = round(100.0 * sum(p[5] for p in P) / flips, 1) if flips else float("nan")
    rates = [(b[1] / (b[0] - a[0])) for a, b in zip(pages, pages[1:]) if lo <= a[0] and b[0] <= hi and b[0] > a[0]]
    r["slow_stores_per_s"] = round(med(rates)) if rates else float("nan")
    T = [x for x in tlb if lo <= x[0] <= hi]
    r["sd_per_2s"] = med([x[2] for x in T]) if T else float("nan")
    r["vcpu_ms_per_2s"] = med([x[1] for x in T]) if T else float("nan")
    G = [g[1] for g in gpu if lo <= g[0] <= hi]
    r["gpu_ms"] = med(G) if G else None
    Ph = [p[1] for p in phase if lo <= p[0] <= hi]
    if Ph:
        r["phase_medians"] = dict((k, med([p[k] for p in Ph if k in p])) for k in Ph[0])
    return r


end = perf[-1][0] if perf else 0.0
windows = int(end // 2)
inst_ok = bool(perf) and end >= 200 and len([x for x in tlb if x[0] >= 20]) >= 0.9 * max(1, (end - 20) / 2 - 1) and len(pages) >= 10
slow = longest(lambda f: f <= 12)
fast = longest(lambda f: f >= 25)
S = span_stats(*slow)
Fs = span_stats(*fast)
print("run: last gfps line at %.1f s; perf %d, pace %d, tlb68 %d, pages %d, gpu %d, phase %d lines" % (
    end, len(perf), len(pace), len(tlb), len(pages), len(gpu), len(phase)))
print("slow span:", json.dumps(S))
print("fast span:", json.dumps(Fs))

got = {
    "M0/instrument_ok_is": inst_ok,
    "P2/slow_span_len_s_min": S["len_s"],
    "P2/fast_span_len_s_min": Fs["len_s"],
    "P3/renderer_busy_slow_pct_max": S["renderer_busy_pct"],
    "P3/renderer_busy_fast_pct_max": Fs["renderer_busy_pct"],
    "P4/flips_ge4vbl_slow_pct_min": S["flips_ge4vbl_pct"],
    "P5/slow_stores_per_s_slow_min": S["slow_stores_per_s"],
    "P5/slow_stores_per_s_fast_max": Fs["slow_stores_per_s"],
    "P6/vcpu_ms_per_2s_slow_min": S["vcpu_ms_per_2s"],
    "B/brief_emulator_cost_renderer_is": (S["renderer_busy_pct"] >= 90 and not Fs["renderer_busy_pct"] >= 90),
}
if pred:
    exp = pred["expect"]
    void = not inst_ok
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
        print("%-4s %-38s got %-10s want %s%s" % ("PASS" if ok else "FAIL", k, v,
              ">= " if k.endswith("_min") else "<= " if k.endswith("_max") else "== ", want))
    print("VERDICT:", "VOID (instrument)" if void else ("PASS" if not fails else "FAIL (%d)" % fails))
else:
    for k in sorted(got):
        print("%-38s %s" % (k, got[k]))
