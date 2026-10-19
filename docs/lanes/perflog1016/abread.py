#!/usr/bin/env python3
"""perflog1016 (#433): read the default-path A/B, switch OFF, and the ON leg.

    abread.py --a DIR [--a DIR ...] --b DIR [--b DIR ...] [--on DIR]
              [--judge PREDICTION.json]

Each DIR is a dispatcher result dir (logcat.txt, run.log). The window is
offsets from `mark gameplay` in run.log (the ROUTE clock, which is the logcat
clock), taken from the prediction's window_from_mark_s (default 20..180).
Rule keys are read as P2/<name>, then P1/<name>, so one reader judges both
predictions.

Per run, the median over the window of:
  tcpu   [rdc] render-thread CPU, ms/s (tcpu * 1000 / dt; CLOCK_THREAD_CPUTIME_ID)
  gfps   hakuX-perf gfps
  Ri     hakuX-perf renderer idle, ms per flip
Per arm, the mean of its runs. The band per reader is the largest of the
within-arm spreads (max - min over an arm's runs) and the prediction's prior.

Each run's shader-cache state comes from result.json. The dispatcher clears the
cache when the APK changes and keeps it on a same-APK run, so in A B B A only
B2 starts warm. When both arms have a cold run, the reader also prints B-A
over the cold runs only. Under P1 that line is a cross-check on the warm run,
not a rule. Under M1/cold_runs_only (P2, whose order alternates the arms so
every run should start cold) a warm run is listed and left out of every
figure, and an arm with fewer than M1/cold_runs_min_per_arm cold runs is VOID.

--judge applies the prediction's rules (see its "prediction" text):
  VOID      a run with no mark gameplay or under M1/rdc_lines_min [rdc] lines
            in the window; a B run with a runtime-tier-ON, [tcg787] or
            hakuX-phase line (B is the OFF path: any of those means it was on)
  SLOWDOWN  B-A tcpu over the max and outside the band; B-A Ri under the min
            and outside the band; or every B run's gfps median at least N
            below every A run's
  CLEARED   none of those

--on DIR reads the ON leg (the B build with XEMU_PERFLOG_RT=1), against the M2
rules: exactly M2/on_tier_lines 'runtime tier ON (frame N, by env)' lines and
no OFF line; from that line on, at least M2/on_phase_lines_min hakuX-phase
lines carrying TxH/Sfp/Mfp/FTx with a median Draw of at least
M2/on_phase_draw_median_min_ms (the debug.h timers booked), hakuX-cpu medians
Pull and Push of at least M2/on_cpu_pull/push_median_min_ms (pfifo.c's timers
booked), and at least M2/on_tcg787_lines_min [tcg787] lines. Its tcpu, gfps
and Ri over the same window are printed against the B mean as the ON cost;
that is descriptive, one run, not a rule.

Exit 0 CLEARED (and the ON leg a HIT, if read), 1 SLOWDOWN, 2 VOID or
unreadable, 3 ON leg MISS with the A/B not SLOWDOWN or VOID.
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
    tier_on = tcg787 = phase = 0
    for line in open(lc, errors="replace"):
        if "runtime tier ON" in line:
            tier_on += 1
        if "[tcg787]" in line:
            tcg787 += 1
        if "/hakuX-phase(" in line:
            phase += 1
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
    try:
        sc = json.load(open(os.path.join(d, "result.json"))).get("shader_cache", "")
    except (OSError, ValueError):
        sc = ""
    s["cache"] = sc.split(":", 1)[0] or "?"
    s["n_rdc"] = len(xs["tcpu"])
    s["n_gfps"] = len(xs["gfps"])
    s["tier_on_lines"] = tier_on
    s["tcg787_lines"] = tcg787
    s["phase_lines"] = phase
    return s, []


TIER = re.compile(r"\[perflog\] runtime tier (ON|OFF) \(frame \d+, by (\w+)\)")


def field(line, name):
    m = re.search(r"\b%s:([\d.]+)" % name, line)
    return float(m.group(1)) if m else None


def med(v):
    v = [x for x in v if x is not None]
    return statistics.median(v) if v else None


def read_on(d):
    """The ON leg's lines, from the first 'runtime tier ON' on: a dict, or
    None if there is no readable logcat."""
    lc = os.path.join(d, "logcat.txt")
    try:
        lines = open(lc, errors="replace").readlines()
    except OSError:
        return None
    r = {"on_env": 0, "on_other": 0, "off": 0, "phase": 0, "phase_full": 0,
         "draw": [], "pull": [], "push": [], "tcg787": 0}
    seen_on = False
    for line in lines:
        m = TIER.search(line)
        if m:
            if m.group(1) == "OFF":
                r["off"] += 1
            elif m.group(2) == "env":
                r["on_env"] += 1
            else:
                r["on_other"] += 1
            seen_on = seen_on or m.group(1) == "ON"
            continue
        if not seen_on:
            continue
        if "/hakuX-phase(" in line:
            r["phase"] += 1
            if all(" %s:" % f in line for f in ("TxH", "Sfp", "Mfp", "FTx")):
                r["phase_full"] += 1
            r["draw"].append(field(line, "Draw"))
        elif "/hakuX-cpu(" in line:
            r["pull"].append(field(line, "Pull"))
            r["push"].append(field(line, "Push"))
        elif "[tcg787]" in line:
            r["tcg787"] += 1
    r["draw"], r["pull"], r["push"] = med(r["draw"]), med(r["pull"]), med(r["push"])
    return r


def fmt(x, p=2):
    return "-" if x is None else ("%.*f" % (p, x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", action="append", default=[])
    ap.add_argument("--b", action="append", default=[])
    ap.add_argument("--on")
    ap.add_argument("--judge")
    a = ap.parse_args()
    if not a.a or not a.b:
        raise SystemExit(__doc__)
    exp = {}
    if a.judge:
        exp = json.load(open(a.judge)).get("expect", {})

    def rule(name, default):
        return exp.get("P2/" + name, exp.get("P1/" + name, default))

    lo, hi = rule("window_from_mark_s", [20, 180])
    min_rdc = exp.get("M1/rdc_lines_min", 60)
    cold_only = bool(exp.get("M1/cold_runs_only", False))
    min_cold = exp.get("M1/cold_runs_min_per_arm", 2)

    runs = {"A": [], "B": []}
    left_out = []
    void = []
    for arm, dirs in (("A", a.a), ("B", a.b)):
        for d in dirs:
            s, why = read(d, lo, hi)
            name = os.path.basename(os.path.normpath(d))
            if s is None:
                void.append("%s %s: %s" % (arm, name, "; ".join(why)))
                continue
            if arm == "B" and s["tier_on_lines"]:
                void.append("B %s: %d 'runtime tier ON' lines; B must be OFF"
                            % (name, s["tier_on_lines"]))
            if arm == "B" and s["tcg787_lines"]:
                void.append("B %s: %d [tcg787] lines; B must be OFF"
                            % (name, s["tcg787_lines"]))
            if arm == "B" and s["phase_lines"]:
                void.append("B %s: %d hakuX-phase lines; B must be OFF"
                            % (name, s["phase_lines"]))
            if cold_only and s["cache"] != "cleared":
                left_out.append((arm, name, s))
                continue
            if s["n_rdc"] < min_rdc:
                void.append("%s %s: %d [rdc] lines in the window, under %d"
                            % (arm, name, s["n_rdc"], min_rdc))
            runs[arm].append((name, s))
    if cold_only:
        for arm in ("A", "B"):
            if len(runs[arm]) < min_cold:
                void.append("arm %s: %d cold-cache runs, under %d"
                            % (arm, len(runs[arm]), min_cold))

    print("window: mark gameplay +%g..+%g s" % (lo, hi))
    print("%-4s %-40s %6s %6s %8s %6s %6s %8s" % ("arm", "run", "n_rdc", "tcpu",
                                                  "gfps", "Ri", "n_gfps", "cache"))
    for arm in ("A", "B"):
        for name, s in runs[arm]:
            print("%-4s %-40s %6d %6s %8s %6s %6d %8s"
                  % (arm, name, s["n_rdc"], fmt(s["tcpu"], 1),
                     fmt(s["gfps"], 1), fmt(s["Ri"], 2), s["n_gfps"], s["cache"]))
    for arm, name, s in left_out:
        print("%-4s %-40s %6d %6s %8s %6s %6d %8s  LEFT OUT (M1/cold_runs_only)"
              % (arm, name, s["n_rdc"], fmt(s["tcpu"], 1),
                 fmt(s["gfps"], 1), fmt(s["Ri"], 2), s["n_gfps"], s["cache"]))

    def mean(arm, k):
        v = [s[k] for _, s in runs[arm] if s[k] is not None]
        return statistics.mean(v) if v else None

    def spread(arm, k):
        v = [s[k] for _, s in runs[arm] if s[k] is not None]
        return (max(v) - min(v)) if len(v) > 1 else 0.0

    prior = {"tcpu": rule("prior_band_tcpu_ms_per_s", 14.0),
             "Ri": rule("prior_band_ri_ms", 0.2), "gfps": 0.0}
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
    # Run-to-run noise as a standard error, for the reader of the numbers;
    # the rules use the band above.
    se = {}
    for k in ("tcpu", "Ri"):
        va = [s[k] for _, s in runs["A"] if s[k] is not None]
        vb = [s[k] for _, s in runs["B"] if s[k] is not None]
        if len(va) > 1 and len(vb) > 1:
            se[k] = (statistics.variance(va) / len(va)
                     + statistics.variance(vb) / len(vb)) ** 0.5
    if se:
        print("standard error of B-A (descriptive): %s"
              % ", ".join("%s %.2f" % kv for kv in se.items()))

    cold = {arm: [s for _, s in runs[arm] if s["cache"] == "cleared"]
            for arm in ("A", "B")}
    warm = sum(1 for arm in runs for _, s in runs[arm] if s["cache"] != "cleared")
    if warm and cold["A"] and cold["B"]:
        parts = []
        for k in ("tcpu", "gfps", "Ri"):
            va = [s[k] for s in cold["A"] if s[k] is not None]
            vb = [s[k] for s in cold["B"] if s[k] is not None]
            if va and vb:
                parts.append("%s %+.2f" % (k, statistics.mean(vb) - statistics.mean(va)))
        print("cold-cache runs only (A %d, B %d; a cross-check, not a rule): B-A %s"
              % (len(cold["A"]), len(cold["B"]), ", ".join(parts)))

    on_rc = judge_on(a.on, exp, lo, hi, min_rdc,
                     {k: mean("B", k) for k in ("tcpu", "gfps", "Ri")}) if a.on else 0

    if not a.judge:
        for v in void:
            print("VOID: " + v)
        return 2 if void or on_rc == 2 else on_rc
    print()
    if void or d["tcpu"] is None or d["Ri"] is None:
        for v in void or ["a reader is missing in one arm"]:
            print("VOID: " + v)
        return 2
    fails = []
    tmax = rule("tcpu_b_minus_a_max_ms_per_s", 15.0)
    if d["tcpu"] > tmax and d["tcpu"] > band["tcpu"]:
        fails.append("tcpu B-A %+.1f ms/s > %+.1f and outside the band %.1f"
                     % (d["tcpu"], tmax, band["tcpu"]))
    rmin = rule("ri_b_minus_a_min_ms", -0.3)
    if d["Ri"] < rmin and -d["Ri"] > band["Ri"]:
        fails.append("Ri B-A %+.2f ms < %+.2f and outside the band %.2f"
                     % (d["Ri"], rmin, band["Ri"]))
    gby = rule("gfps_both_b_below_both_a_by", 1)
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
    return 2 if on_rc == 2 else on_rc


def judge_on(d, exp, lo, hi, min_rdc, b_mean):
    """Print the ON leg's verdict; 0 HIT, 3 MISS, 2 VOID."""
    name = os.path.basename(os.path.normpath(d))
    print()
    r = read_on(d)
    if r is None:
        print("ON %s: VOID: no readable logcat.txt" % name)
        return 2
    print("ON %s: tier ON by env %d, ON by other %d, OFF %d; from the ON line: "
          "hakuX-phase %d (%d with TxH/Sfp/Mfp/FTx), median Draw %s ms; "
          "hakuX-cpu median Pull %s, Push %s ms; [tcg787] %d"
          % (name, r["on_env"], r["on_other"], r["off"], r["phase"],
             r["phase_full"], fmt(r["draw"]), fmt(r["pull"]), fmt(r["push"]),
             r["tcg787"]))
    miss = []
    want = exp.get("M2/on_tier_lines", 1)
    if r["on_env"] != want or r["on_other"] or r["off"]:
        miss.append("want exactly %d 'runtime tier ON (..., by env)' and no other "
                    "tier line" % want)
    n = exp.get("M2/on_phase_lines_min", 50)
    if r["phase_full"] < n:
        miss.append("%d full hakuX-phase lines, under %d" % (r["phase_full"], n))
    for key, val, what in (("M2/on_phase_draw_median_min_ms", r["draw"], "Draw"),
                           ("M2/on_cpu_pull_median_min_ms", r["pull"], "Pull"),
                           ("M2/on_cpu_push_median_min_ms", r["push"], "Push")):
        floor = exp.get(key, 0.1)
        if val is None or val < floor:
            miss.append("median %s %s ms, under %g" % (what, fmt(val), floor))
    n = exp.get("M2/on_tcg787_lines_min", 20)
    if r["tcg787"] < n:
        miss.append("%d [tcg787] lines, under %d" % (r["tcg787"], n))

    s, why = read(d, lo, hi)
    if s is not None and s["n_rdc"] >= min_rdc:
        parts = []
        for k in ("tcpu", "gfps", "Ri"):
            if s[k] is not None and b_mean.get(k) is not None:
                parts.append("%s %s (ON-OFF %+.2f)" % (k, fmt(s[k]), s[k] - b_mean[k]))
        print("ON cost over the window, one run against the B mean "
              "(descriptive, not a rule; cache %s): %s" % (s["cache"], ", ".join(parts)))
    else:
        print("ON cost: not read (%s)" % ("; ".join(why) if s is None else
                                          "%d [rdc] lines in the window" % s["n_rdc"]))
    if miss:
        for m in miss:
            print("ON MISS: " + m)
        return 3
    print("ON HIT: the switch turned on by env, once, and the phase, pfifo and "
          "[tcg787] timers booked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
