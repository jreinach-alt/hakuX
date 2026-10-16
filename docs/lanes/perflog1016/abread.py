#!/usr/bin/env python3
"""perflog1016 (#433): read the default-path A/B, switch OFF.

    abread.py --a DIR [--a DIR] --b DIR [--b DIR] [--judge PREDICTION.json]

Each DIR is a dispatcher result dir (logcat.txt, run.log). The window is
offsets from `mark gameplay` in run.log (the ROUTE clock, which is the logcat
clock), taken from the prediction's P1/window_from_mark_s (default 20..180).

Per run, the median over the window of:
  tcpu   [rdc] render-thread CPU, ms/s (tcpu * 1000 / dt; CLOCK_THREAD_CPUTIME_ID)
  gfps   hakuX-perf gfps
  Ri     hakuX-perf renderer idle, ms per flip
Per arm, the mean of its runs. The band per reader is the largest of the
within-arm spreads (max - min over an arm's runs) and the prediction's prior.

--judge applies the prediction's rules (see its "prediction" text):
  VOID      a run with no mark gameplay or under M1/rdc_lines_min [rdc] lines
            in the window; a B run with a runtime-tier-ON or [tcg787] line
  SLOWDOWN  B-A tcpu over the max and outside the band; B-A Ri under the min
            and outside the band; or every B run's gfps median at least N
            below every A run's
  CLEARED   none of those
Exit 0 CLEARED, 1 SLOWDOWN, 2 VOID or unreadable.
"""
import argparse
import datetime
import json
import os
import re
import statistics
import sys

TS = re.compile(r"^(\d\d-\d\d) (\d\d:\d\d:\d\d\.\d+) ")
MARK = re.compile(r"ROUTE (\d\d:\d\d:\d\d\.\d+) mark gameplay\b")


def stamp(line):
    m = TS.match(line)
    if not m:
        return None
    return datetime.datetime.strptime("2026-" + m.group(1) + " " + m.group(2),
                                      "%Y-%m-%d %H:%M:%S.%f")


def mark_time(d, day):
    try:
        for line in open(os.path.join(d, "run.log"), errors="replace"):
            m = MARK.search(line)
            if m:
                return datetime.datetime.strptime(day + " " + m.group(1),
                                                  "%Y-%m-%d %H:%M:%S.%f")
    except OSError:
        pass
    return None


def read(d, lo, hi):
    """One run: (summary dict, void reasons). Medians over [lo, hi) s."""
    lc = os.path.join(d, "logcat.txt")
    try:
        first = next(l for l in open(lc, errors="replace") if TS.match(l))
    except (OSError, StopIteration):
        return None, ["no readable logcat.txt"]
    mark = mark_time(d, stamp(first).strftime("%Y-%m-%d"))
    if mark is None:
        return None, ["no mark gameplay in run.log"]
    xs = {"tcpu": [], "gfps": [], "Ri": []}
    tier_on = tcg787 = 0
    for line in open(lc, errors="replace"):
        if "runtime tier ON" in line:
            tier_on += 1
        if "[tcg787]" in line:
            tcg787 += 1
        t = stamp(line)
        if t is None:
            continue
        off = (t - mark).total_seconds()
        if not lo <= off < hi:
            continue
        if "[rdc] f=" in line:
            m = re.search(r" tcpu=([\d.]+)", line)
            dt = re.search(r" dt=(\d+)", line)
            if m and dt and int(dt.group(1)) > 0:
                xs["tcpu"].append(float(m.group(1)) * 1000.0 / int(dt.group(1)))
        elif "hakuX-perf" in line and "gfps=" in line:
            g = re.search(r"gfps=(\d+)", line)
            ri = re.search(r" Ri:([\d.]+)", line)
            if g:
                xs["gfps"].append(int(g.group(1)))
            if ri:
                xs["Ri"].append(float(ri.group(1)))
    s = {k: (statistics.median(v) if v else None) for k, v in xs.items()}
    s["n_rdc"] = len(xs["tcpu"])
    s["n_gfps"] = len(xs["gfps"])
    s["tier_on_lines"] = tier_on
    s["tcg787_lines"] = tcg787
    return s, []


def fmt(x, p=2):
    return "-" if x is None else ("%.*f" % (p, x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", action="append", default=[])
    ap.add_argument("--b", action="append", default=[])
    ap.add_argument("--judge")
    a = ap.parse_args()
    if not a.a or not a.b:
        raise SystemExit(__doc__)
    exp = {}
    if a.judge:
        exp = json.load(open(a.judge)).get("expect", {})
    lo, hi = exp.get("P1/window_from_mark_s", [20, 180])
    min_rdc = exp.get("M1/rdc_lines_min", 60)

    runs = {"A": [], "B": []}
    void = []
    for arm, dirs in (("A", a.a), ("B", a.b)):
        for d in dirs:
            s, why = read(d, lo, hi)
            name = os.path.basename(os.path.normpath(d))
            if s is None:
                void.append("%s %s: %s" % (arm, name, "; ".join(why)))
                continue
            if s["n_rdc"] < min_rdc:
                void.append("%s %s: %d [rdc] lines in the window, under %d"
                            % (arm, name, s["n_rdc"], min_rdc))
            if arm == "B" and s["tier_on_lines"]:
                void.append("B %s: %d 'runtime tier ON' lines; B must be OFF"
                            % (name, s["tier_on_lines"]))
            if arm == "B" and s["tcg787_lines"]:
                void.append("B %s: %d [tcg787] lines; B must be OFF"
                            % (name, s["tcg787_lines"]))
            runs[arm].append((name, s))

    print("window: mark gameplay +%g..+%g s" % (lo, hi))
    print("%-4s %-40s %6s %6s %8s %6s %6s" % ("arm", "run", "n_rdc", "tcpu",
                                             "gfps", "Ri", "n_gfps"))
    for arm in ("A", "B"):
        for name, s in runs[arm]:
            print("%-4s %-40s %6d %6s %8s %6s %6d"
                  % (arm, name, s["n_rdc"], fmt(s["tcpu"], 1),
                     fmt(s["gfps"], 1), fmt(s["Ri"], 2), s["n_gfps"]))

    def mean(arm, k):
        v = [s[k] for _, s in runs[arm] if s[k] is not None]
        return statistics.mean(v) if v else None

    def spread(arm, k):
        v = [s[k] for _, s in runs[arm] if s[k] is not None]
        return (max(v) - min(v)) if len(v) > 1 else 0.0

    prior = {"tcpu": exp.get("P1/prior_band_tcpu_ms_per_s", 14.0),
             "Ri": exp.get("P1/prior_band_ri_ms", 0.2), "gfps": 0.0}
    print()
    print("%-6s %9s %9s %9s %9s" % ("", "A mean", "B mean", "B-A", "band"))
    d = {}
    band = {}
    for k in ("tcpu", "gfps", "Ri"):
        ma, mb = mean("A", k), mean("B", k)
        band[k] = max(spread("A", k), spread("B", k), prior[k])
        d[k] = None if ma is None or mb is None else mb - ma
        print("%-6s %9s %9s %9s %9s" % (k, fmt(ma), fmt(mb),
                                        "-" if d[k] is None else "%+.2f" % d[k],
                                        fmt(band[k])))
    print("band = max(within-arm spread A, B, prior %s)" % prior)

    if not a.judge:
        return 0
    print()
    if void or d["tcpu"] is None or d["Ri"] is None:
        for v in void or ["a reader is missing in one arm"]:
            print("VOID: " + v)
        return 2
    fails = []
    tmax = exp.get("P1/tcpu_b_minus_a_max_ms_per_s", 15.0)
    if d["tcpu"] > tmax and d["tcpu"] > band["tcpu"]:
        fails.append("tcpu B-A %+.1f ms/s > %+.1f and outside the band %.1f"
                     % (d["tcpu"], tmax, band["tcpu"]))
    rmin = exp.get("P1/ri_b_minus_a_min_ms", -0.3)
    if d["Ri"] < rmin and -d["Ri"] > band["Ri"]:
        fails.append("Ri B-A %+.2f ms < %+.2f and outside the band %.2f"
                     % (d["Ri"], rmin, band["Ri"]))
    gby = exp.get("P1/gfps_both_b_below_both_a_by", 1)
    ga = [s["gfps"] for _, s in runs["A"] if s["gfps"] is not None]
    gb = [s["gfps"] for _, s in runs["B"] if s["gfps"] is not None]
    if ga and gb and max(gb) <= min(ga) - gby:
        fails.append("every B gfps median (%s) at least %d below every A's (%s)"
                     % (gb, gby, ga))
    if fails:
        for f in fails:
            print("SLOWDOWN: " + f)
        return 1
    print("CLEARED: no slowdown rule met. This bounds the OFF cost under the "
          "band (tcpu %.1f ms/s, Ri %.2f ms); it does not show zero."
          % (max(tmax, band["tcpu"]), max(-rmin, band["Ri"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
