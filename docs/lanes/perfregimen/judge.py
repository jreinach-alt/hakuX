#!/usr/bin/env python3
"""Judge a held_session.sh output dir against the pilot prediction.

    judge.py <session-dir> --prediction <prediction.json> [--window 135,245]

Reads idle.log (the idle probe), each arm<N>-<rest|max>/ (logcat.txt,
perf_regimen.json, samples.txt), and prints one line per leg and a verdict.
The fps is the gfps-line cadence (hakuX-perf `gfps=`, one line per 60 guest
flips) inside the window, in seconds from the first hakuX line of the arm --
the same reader as docs/lanes/blinx372c/stallread.py.
"""
import argparse, glob, json, os, re, statistics, sys
from datetime import datetime

TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d{3}) [VDIWEF]/([^(]+?)\s*\(\s*\d+\): (.*)")
KV = re.compile(r"(\w+)=(-?\d+)")


def ts(s):
    return datetime.strptime("2026-" + s, "%Y-%m-%d %H:%M:%S.%f").timestamp()


def arm_fps(path, lo, hi):
    t0, g = None, []
    for line in open(path, errors="replace"):
        m = TS.match(line)
        if not m:
            continue
        t, tag, body = ts(m.group(1)), m.group(2), m.group(3)
        if t0 is None and tag.startswith("hakuX"):
            t0 = t
        if t0 is None:
            continue
        if tag == "hakuX-perf" and body.startswith("gfps=") and lo <= t - t0 < hi:
            g.append(t - t0)
    fr, sp = 0, 0.0
    for a, b in zip(g, g[1:]):
        if 0 < b - a < 30:
            fr += 60
            sp += b - a
    return (fr / sp if sp else float("nan")), len(g)


def samples(path, skip=6):
    rows = []
    for line in open(path, errors="replace") if os.path.exists(path) else []:
        d = {k: int(v) for k, v in KV.findall(line)}
        if "gpuclk" in d:
            rows.append(d)
    return rows[skip:]


def med(rows, k):
    xs = [r[k] for r in rows if k in r]
    return statistics.median(xs) if xs else float("nan")


def idle(path):
    """[(perf, fan, snapshot-dict)] for each `set perf=P fan=F` step."""
    out, cur = [], None
    for line in open(path, errors="replace"):
        m = re.search(r"set perf=(\d+) fan=(\d+)", line)
        if m:
            cur = (int(m.group(1)), int(m.group(2)))
            continue
        if cur and "gpu_min_mhz=" in line:
            out.append((cur[0], cur[1], {k: int(v) for k, v in KV.findall(line)}))
            cur = None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--prediction", required=True)
    ap.add_argument("--window", default="135,245")
    o = ap.parse_args()
    lo, hi = map(float, o.window.split(","))
    exp = json.load(open(o.prediction))["expect"]
    res, legs = {}, []

    def leg(name, ok, what):
        legs.append((name, ok))
        print("%-5s %-4s %s" % (name, "PASS" if ok else "FAIL", what))

    steps = idle(os.path.join(o.dir, "idle.log"))
    by_perf = {}
    by_fan = {}
    for p, f, d in steps:
        if f == exp["rest_fan"]:
            by_perf.setdefault(p, []).append(d)
        if p == exp["rest_perf"]:
            by_fan.setdefault(f, []).append(d)
    print("idle GPU floor by performance_mode:",
          {p: [d.get("gpu_min_mhz") for d in v] for p, v in sorted(by_perf.items())})
    print("idle fan duty/state/rpm by fan_mode:",
          {f: [(d.get("fan_duty"), d.get("fan_state"), d.get("fan_rpm")) for d in v]
           for f, v in sorted(by_fan.items())})

    arms = []
    for ad in sorted(glob.glob(os.path.join(o.dir, "arm*-*"))):
        kind = ad.rsplit("-", 1)[1]
        fps, n = arm_fps(os.path.join(ad, "logcat.txt"), lo, hi) \
            if os.path.exists(os.path.join(ad, "logcat.txt")) else (float("nan"), 0)
        try:
            pr = json.load(open(os.path.join(ad, "perf_regimen.json")))
        except (OSError, ValueError):
            pr = {}
        sm = samples(os.path.join(ad, "samples.txt"))
        arms.append(dict(dir=os.path.basename(ad), kind=kind, fps=fps, lines=n, pr=pr,
                         gpuclk=med(sm, "gpuclk"), gpu_min=med(sm, "gpu_min_mhz"),
                         duty=med(sm, "fan_duty"), rpm=med(sm, "fan_rpm"),
                         c7=med(sm, "c7"), gpuss0=med(sm, "gpuss0"), n_samples=len(sm)))
    print("\n| arm | fps %g-%gs | gfps lines | ran at | restored | gpu MHz med | GPU floor | fan duty | fan rpm | cpu7 kHz | gpuss-0 mC |" % (lo, hi))
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for a in arms:
        print("| %s | %.2f | %d | %s/%s | %s | %.0f | %.0f | %.0f | %.0f | %.0f | %.0f |" % (
            a["dir"], a["fps"], a["lines"], a["pr"].get("perf_mode"), a["pr"].get("fan_mode"),
            a["pr"].get("perf_restored"), a["gpuclk"] / 1e6, a["gpu_min"], a["duty"], a["rpm"],
            a["c7"], a["gpuss0"]))
    print()

    want = {"rest": (exp["rest_perf"], exp["rest_fan"]), "max": (exp["max_perf"], exp["max_fan"])}
    m0 = bool(arms) and all(
        a["lines"] >= exp["M0/gfps_lines_min"]
        and (a["pr"].get("perf_mode"), a["pr"].get("fan_mode")) == want[a["kind"]]
        and a["pr"].get("perf_restored") is True for a in arms) \
        and {a["kind"] for a in arms} == {"rest", "max"}
    leg("M0", m0, "every arm has >= %d gfps lines in the window, ran at its modes, restored REST"
        % exp["M0/gfps_lines_min"])

    f0 = [d.get("gpu_min_mhz", -1) for d in by_perf.get(exp["rest_perf"], [])]
    f2 = [d.get("gpu_min_mhz", -1) for d in by_perf.get(exp["max_perf"], [])]
    leg("P1", bool(f0 and f2) and min(f2) > max(f0),
        "idle GPU floor at performance_mode %d %s > at %d %s" % (exp["max_perf"], f2, exp["rest_perf"], f0))

    dmax = [d.get("fan_duty", -1) for d in by_fan.get(exp["max_fan"], [])]
    others = {f: max(d.get("fan_duty", -1) for d in v) for f, v in by_fan.items() if f != exp["max_fan"]}
    leg("P2", bool(dmax) and bool(others) and min(dmax) >= max(others.values()),
        "idle fan duty at fan_mode %d %s >= every other mode %s" % (exp["max_fan"], dmax, others))

    rest = [a for a in arms if a["kind"] == "rest"]
    mx = [a for a in arms if a["kind"] == "max"]
    if rest and mx:
        rf = statistics.mean(a["fps"] for a in rest)
        mf = statistics.mean(a["fps"] for a in mx)
        leg("P3", all(m["gpu_min"] > r["gpu_min"] for m in mx for r in rest)
            and all(m["duty"] > r["duty"] for m in mx for r in rest),
            "under the title, MAX's GPU floor and fan duty exceed every REST arm's")
        spread = (max(a["fps"] for a in rest) - min(a["fps"] for a in rest)) / rf if rf else 1
        leg("P4", spread <= exp["P4/rest_spread_max"],
            "the REST arms agree: spread %.1f%% <= %.0f%%" % (100 * spread, 100 * exp["P4/rest_spread_max"]))
        leg("P5", mf >= exp["P5/max_over_rest_min"] * rf,
            "MAX fps %.2f >= %.2f x REST %.2f (non-inferiority)" % (mf, exp["P5/max_over_rest_min"], rf))
        leg("P6", mf >= exp["P6/max_over_rest_guess"] * rf,
            "GUESS: MAX fps %.2f >= %.2f x REST %.2f (gain %+.1f%%)"
            % (mf, exp["P6/max_over_rest_guess"], rf, 100 * (mf / rf - 1)))
    if not m0:
        print("VERDICT: VOID (M0)")
    else:
        bad = [n for n, ok in legs if not ok]
        print("VERDICT: %s" % ("PASS" if not bad else "FAIL " + ",".join(bad)))


main()
