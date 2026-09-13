#!/usr/bin/env python3
"""Judge a VBLANK-timing A/B against its registered prediction.

    vblank_ab.py --a A/logcat.txt --b B/logcat.txt --expect predictions/x.json

`ab_compare.py` cannot score this. It compares captures, and no golden capture
can see VBLANK timing -- that blindness is the reason the guest-timing stream
exists at all. So this does the same job on the `vbl` lines instead: per
regime, never pooled, and against a prediction file whose commit date is the
binding that `--expect`'s content hash would otherwise provide.

The regimes are the split that matters: the adaptive deferral only runs while
the guest is mid-frame, so any title alternates between windows it touches and
windows it does not. The no-deferral windows are the **within-run control** --
the change under test cannot reach them, so if they move, something else did.
"""
import argparse
import json
import re
import statistics
import sys

VBL = re.compile(
    r"vbl n=(?P<n>\d+) win=(?P<win>\d+)ms want=(?P<want>\d+) got=(?P<got>\d+) "
    r"drift=(?P<drift>[-+]?\d+) rate=(?P<rate>[\d.]+)Hz "
    r"p1=(?P<p1>\d+) p50=(?P<p50>\d+) p90=(?P<p90>\d+) p99=(?P<p99>\d+) "
    r"min=(?P<min>\d+) max=(?P<max>\d+) "
    r"src\(tmr=(?P<tmr>\d+) smp=(?P<smp>\d+) gfx=(?P<gfx>\d+)\) "
    r"coal=(?P<coal>\d+) def=(?P<def>\d+) rast=(?P<rast>\d+)/(?P<rastmax>\d+)")
GFPS = re.compile(r"gfps=(\d+)")
UL = re.compile(r"Ul:([YN])")


def load(path):
    rows, gfps, ul = [], [], []
    with open(path, errors="replace") as fh:
        for line in fh:
            m = VBL.search(line)
            if m:
                rows.append({k: int(v) if v.isdigit() else v
                             for k, v in m.groupdict().items()})
            m = GFPS.search(line)
            if m:
                gfps.append(int(m.group(1)))
            m = UL.search(line)
            if m:
                ul.append(m.group(1))
    if not rows:
        sys.exit("no vbl lines in %s" % path)
    return rows, gfps, ul


def regime(rows, lo, hi):
    return [r for r in rows if lo <= r["def"] <= hi]


def mean_interval(rows):
    return sum(r["got"] for r in rows) // len(rows) if rows else 0


def rate_hz(rows):
    span = sum(r["win"] for r in rows)
    n = sum(r["n"] for r in rows)
    return n * 1000.0 / span if span else 0.0


def leg(name, verdict, detail):
    mark = {True: "HOLDS", False: "FAILS", None: "UNMEASURED"}[verdict]
    print("  %-4s %-11s %s" % (name, mark, detail))
    return verdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--expect")
    args = ap.parse_args()

    if args.expect:
        exp = json.load(open(args.expect))
        print("prediction registered %s by %s, issue #%s"
              % (exp.get("registered_utc"), exp.get("who"), exp.get("issue")))
        print("  a_ref %s  b_ref %s\n" % (exp.get("a_ref"), exp.get("b_ref")))

    a, agf, aul = load(args.a)
    b, bgf, bul = load(args.b)

    print("%-14s %8s %8s" % ("", "A", "B"))
    print("%-14s %8d %8d" % ("windows", len(a), len(b)))
    print("%-14s %8d %8d" % ("assertions", sum(r["n"] for r in a),
                             sum(r["n"] for r in b)))
    print("%-14s %8s %8s" % ("unlock Y",
                             aul.count("Y"), bul.count("Y")))
    print()

    rows = []
    for label, lo, hi in (("def==0", 0, 0), ("def 1-20", 1, 20),
                          ("def>20", 21, 10 ** 9), ("all", 0, 10 ** 9)):
        ra, rb = regime(a, lo, hi), regime(b, lo, hi)
        rows.append((label, ra, rb))
        print("%-9s A %10d ns %7.3f Hz  n=%-5d | B %10d ns %7.3f Hz  n=%-5d"
              % (label, mean_interval(ra), rate_hz(ra), len(ra),
                 mean_interval(rb), rate_hz(rb), len(rb)))
    print()

    ma = {lbl: (mean_interval(ra), mean_interval(rb))
          for lbl, ra, rb in rows}
    aall = [r for r in a]
    ball = [r for r in b]

    print("legs")
    ok = []
    # B1: the def>20 mean falls by at least 1,000,000 ns; under 300,000 fails.
    d1 = ma["def>20"][0] - ma["def>20"][1]
    ok.append(leg("B1", d1 >= 1000000 if d1 >= 300000 else False,
                  "def>20 mean %d -> %d, a fall of %+d ns"
                  % (ma["def>20"][0], ma["def>20"][1], d1)))
    # B2: whole-soak rate above 58.000 Hz.
    r2 = rate_hz(ball)
    ok.append(leg("B2", r2 > 58.0, "whole-soak rate %.3f -> %.3f Hz"
                  % (rate_hz(aall), r2)))
    # B3: the control. def==0 must not move.
    d3 = abs(ma["def==0"][1] - ma["def==0"][0])
    ok.append(leg("B3", d3 <= 50000,
                  "def==0 mean %d -> %d, moved %d ns (control)"
                  % (ma["def==0"][0], ma["def==0"][1], d3)))
    # B4: the cost. Median gfps must not fall by more than 2.
    if agf and bgf:
        g0, g1 = statistics.median(agf), statistics.median(bgf)
        ok.append(leg("B4", (g0 - g1) <= 2,
                      "median gfps %.1f -> %.1f (%+.1f)" % (g0, g1, g1 - g0)))
    else:
        ok.append(leg("B4", None, "no gfps lines"))
    # B5: deferrals per window rise.
    p0 = sum(r["def"] for r in aall) / len(aall)
    p1 = sum(r["def"] for r in ball) / len(ball)
    ok.append(leg("B5", p1 > p0, "defers per window %.1f -> %.1f" % (p0, p1)))

    print()
    print("coalesced   A %d of %d (%.2f%%)  B %d of %d (%.2f%%)"
          % (sum(r["coal"] for r in aall), sum(r["n"] for r in aall),
             100.0 * sum(r["coal"] for r in aall) / sum(r["n"] for r in aall),
             sum(r["coal"] for r in ball), sum(r["n"] for r in ball),
             100.0 * sum(r["coal"] for r in ball) / sum(r["n"] for r in ball)))
    print("p99 median  A %d ns   B %d ns"
          % (statistics.median(r["p99"] for r in aall),
             statistics.median(r["p99"] for r in ball)))

    held = [v for v in ok if v is True]
    failed = [v for v in ok if v is False]
    print("\nVERDICT: %d of %d legs hold, %d fail%s"
          % (len(held), len(ok), len(failed),
             ", %d unmeasured" % ok.count(None) if None in ok else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
