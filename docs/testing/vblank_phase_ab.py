#!/usr/bin/env python3
"""Judge the VBLANK *phase* A/B against its registered prediction.

    vblank_phase_ab.py --a A/logcat.txt --b B/logcat.txt \
                       --expect predictions/vblank-unlock-grid.json

`vblank_ab.py` judges #65's five B legs, which are about the RATE and split on
the deferral count. These are the U legs, which are about PHASE and the unlock
grid, and they split on whether unlock mode was active -- a different axis, on
a different line, so this is a sibling rather than an edit. Breaking the B
judge would invalidate the verdict the investigation already cites.

Two things here are not in the older judge, and both come from a specific
failure:

  * Every regime figure is POOLED BY ASSERTION COUNT, not averaged over
    windows. A mean of per-window means weights a two-assertion window the
    same as a 120-assertion one, and the unlock split is uneven by
    construction because the mode comes and goes with the scene.

  * The cost leg reads the CEILING of `gfps` -- p90 and max -- and never the
    median. #64 measured the median on this queue to be a measurement of how
    busy the device is: the series is bimodal (ceiling 29-31, floor 5-20) and
    the median tracks occupancy, which moved 80% to 16-32% across one evening
    while p90 stayed at 29/29/27/29 and the max at 31/29/30/29 over four runs,
    two refs, both orders. A tolerance of 2 against a control that moved 8
    cannot discriminate.
"""
import argparse
import json
import re
import sys

VBL = re.compile(
    r"vbl n=(?P<n>\d+) win=(?P<win>\d+)ms want=(?P<want>\d+) got=(?P<got>\d+) "
    r"drift=(?P<drift>[-+]?\d+) rate=(?P<rate>[\d.]+)Hz "
    r"p1=(?P<p1>\d+) p50=(?P<p50>\d+) p90=(?P<p90>\d+) p99=(?P<p99>\d+) "
    r"min=(?P<min>\d+) max=(?P<max>\d+) "
    r"src\(tmr=(?P<tmr>\d+) smp=(?P<smp>\d+) gfx=(?P<gfx>\d+)\) "
    r"coal=(?P<coal>\d+) def=(?P<def>\d+) rast=(?P<rast>\d+)/(?P<rastmax>\d+)")

PHASE = re.compile(
    r"vblphase n=(?P<pn>\d+) period=(?P<period>\d+) mean=(?P<mean>\d+) "
    r"p50=(?P<lp50>\d+) p90=(?P<lp90>\d+) p99=(?P<lp99>\d+) "
    r"max=(?P<lmax>\d+) neg=(?P<neg>\d+) "
    r"nodef\(n=(?P<nodef_n>\d+) mean=(?P<nodef_mean>\d+) "
    r"max=(?P<nodef_max>\d+)\) "
    r"def\(n=(?P<def_n>\d+) mean=(?P<def_mean>\d+) "
    r"max=(?P<def_max>\d+)\) unl=(?P<unl>\d+) "
    r"coal=(?P<pcoal>\d+) coal_en=(?P<coal_en>\d+) "
    r"coal_short=(?P<coal_short>\d+) coal_gap=(?P<coal_gap>\d+) "
    r"en=(?P<en>\d+)")

GFPS = re.compile(r"gfps=(\d+)")


def load(path):
    """Pair the vblphase and vbl lines of each dump.

    Both are printed from one call to vbh_dump_and_reset, vblphase first, so
    the i-th of each describes the same window. A count mismatch means the
    pairing is not what it looks like -- refuse rather than zip the shorter,
    which would silently attribute one window's phase to another's intervals.
    """
    vbl, ph, gfps = [], [], []
    with open(path, errors="replace") as fh:
        for line in fh:
            m = PHASE.search(line)
            if m:
                ph.append({k: int(v) for k, v in m.groupdict().items()})
                continue
            m = VBL.search(line)
            if m:
                vbl.append({k: int(v) if str(v).isdigit() else v
                            for k, v in m.groupdict().items()})
                continue
            m = GFPS.search(line)
            if m:
                gfps.append(int(m.group(1)))
    if not vbl:
        sys.exit("no vbl lines in %s" % path)
    if not ph:
        sys.exit("no vblphase lines in %s -- this ref predates the phase "
                 "instrument, so the U legs cannot be judged on it" % path)
    if len(ph) != len(vbl):
        sys.exit("%s: %d vblphase lines against %d vbl lines; the pairing is "
                 "not one-to-one and would misattribute windows"
                 % (path, len(ph), len(vbl)))
    return [dict(a, **b) for a, b in zip(vbl, ph)], gfps


def pooled_interval(rows):
    """Mean interval weighted by the assertions each window measured."""
    n = sum(r["n"] for r in rows)
    if not n:
        return 0
    return sum(r["n"] * r["got"] for r in rows) // n


def pooled(rows, n_key, mean_key):
    n = sum(r[n_key] for r in rows)
    if not n:
        return 0, 0
    return n, sum(r[n_key] * r[mean_key] for r in rows) // n


def rate_hz(rows):
    span = sum(r["win"] for r in rows)
    n = sum(r["n"] for r in rows)
    return n * 1000.0 / span if span else 0.0


def pctile(vals, p):
    if not vals:
        return 0
    v = sorted(vals)
    i = min(len(v) - 1, max(0, int(round((p / 100.0) * (len(v) - 1)))))
    return v[i]


def leg(name, verdict, detail):
    mark = {True: "HOLDS", False: "FAILS", None: "VOID"}[verdict]
    print("  %-4s %-6s %s" % (name, mark, detail))
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
        print("  a_ref %s  b_ref %s  title %s  device %s\n"
              % (exp.get("a_ref"), exp.get("b_ref"), exp.get("title"),
                 exp.get("device")))

    a, agf = load(args.a)
    b, bgf = load(args.b)
    period = a[0]["period"]

    def split(rows, which):
        if which == "unlock":
            return [r for r in rows if r["unl"] > 0]
        if which == "locked":
            return [r for r in rows if r["unl"] == 0]
        if which == "full":
            return [r for r in rows if r["pn"] and r["unl"] == r["pn"]]
        return rows

    print("%-16s %10s %10s" % ("", "A", "B"))
    for what, f in (("windows", lambda r: len(r)),
                    ("assertions", lambda r: sum(x["n"] for x in r)),
                    ("unlock windows", lambda r: len(split(r, "unlock"))),
                    ("fully unlocked", lambda r: len(split(r, "full"))),
                    ("locked windows", lambda r: len(split(r, "locked")))):
        print("%-16s %10d %10d" % (what, f(a), f(b)))
    print()

    for label in ("all", "unlock", "locked", "full"):
        ra, rb = split(a, label), split(b, label)
        print("%-8s A %10d ns %7.3f Hz late %8d | B %10d ns %7.3f Hz "
              "late %8d" % (label,
                            pooled_interval(ra), rate_hz(ra),
                            pooled(ra, "pn", "mean")[1],
                            pooled_interval(rb), rate_hz(rb),
                            pooled(rb, "pn", "mean")[1]))
    print()

    print("legs")
    ok = []

    # U8: the validity gate. Without unlock windows in both arms the mechanism
    # legs are VOID, not failed -- the arm measured a regime it cannot reach.
    nua, nub = len(split(a, "unlock")), len(split(b, "unlock"))
    gate = nua >= 5 and nub >= 5
    leg("U8", gate if gate else False,
        "unlock-active windows A=%d B=%d (gate needs >=5 each)" % (nua, nub))

    # U0: the instrument against the arithmetic, on arm A alone. In unlock
    # mode arm A sets target = now + period, so the mean interval is exactly
    # period + mean(lateness). If those disagree the instrument is measuring
    # the wrong population and every leg below it is void.
    fa = split(a, "full")
    if fa:
        got = pooled_interval(fa) - period
        want = pooled(fa, "pn", "mean")[1]
        rel = abs(got - want) / float(want) if want else 9.9
        ok.append(leg("U0", rel <= 0.20,
                      "arm A fully-unlocked: interval-period = %d ns against "
                      "lateness mean %d ns (%.1f%% apart, tol 20%%)"
                      % (got, want, rel * 100)))
    else:
        ok.append(leg("U0", None, "arm A has no fully-unlocked window"))

    # U1: the mechanism, with its magnitude predicted from arm A's own
    # lateness. Arm A's unlock interval is period + mean(late); arm B's is the
    # period; so the fall IS arm A's mean lateness.
    ua, ub = split(a, "unlock"), split(b, "unlock")
    if gate:
        fall = pooled_interval(ua) - pooled_interval(ub)
        latea = pooled(ua, "pn", "mean")[1]
        if fall < 30000:
            ok.append(leg("U1", False,
                          "fall %+d ns is under the 30000 ns floor; the "
                          "unlock deferral cap is a whole period, so the "
                          "<= now clamp is discarding the grid anyway "
                          "(arm A lateness %d ns)" % (fall, latea)))
        else:
            rel = abs(fall - latea) / float(latea) if latea else 9.9
            ok.append(leg("U1", rel <= 0.50,
                          "unlock mean interval fell %+d ns against arm A's "
                          "own lateness mean %d ns (%.1f%% apart, tol 50%%)"
                          % (fall, latea, rel * 100)))
    else:
        ok.append(leg("U1", None, "no unlock windows to measure"))

    # U2: the headline, as a delta -- arm A's DOA3 rate has never been
    # measured on a ref carrying #65's deferral fix.
    ra, rb = rate_hz(a), rate_hz(b)
    ok.append(leg("U2", (rb - ra) >= 0.20,
                  "whole-soak rate %.3f -> %.3f Hz (%+.3f, need >= +0.200)"
                  % (ra, rb, rb - ra)))

    # U3: the within-run control, in the regime the change cannot reach.
    la, lb = split(a, "locked"), split(b, "locked")
    if la and lb:
        d = abs(pooled_interval(lb) - pooled_interval(la))
        ok.append(leg("U3", d <= 50000,
                      "locked-window mean %d -> %d, moved %d ns "
                      "(control, tol 50000)"
                      % (pooled_interval(la), pooled_interval(lb), d)))
    else:
        ok.append(leg("U3", None, "one arm has no unlock-free window"))

    # U4: the impossible row.
    neg = sum(r["neg"] for r in a) + sum(r["neg"] for r in b)
    ok.append(leg("U4", neg == 0,
                  "negative lateness count %d across both arms "
                  "(a QEMU timer cannot fire early; non-zero means an "
                  "un-inventoried writer moves the grid)" % neg))

    # U5: phase must NOT improve. The change leaves the grid alone; it does
    # not touch the deferral hold.
    _, dla = pooled(a, "def_n", "def_mean")
    _, dlb = pooled(b, "def_n", "def_mean")
    p99a = pctile([r["p99"] for r in a], 50)
    p99b = pctile([r["p99"] for r in b], 50)
    rel_d = abs(dlb - dla) / float(dla) if dla else 9.9
    rel_p = abs(p99b - p99a) / float(p99a) if p99a else 9.9
    ok.append(leg("U5", rel_d <= 0.15 and rel_p <= 0.10,
                  "deferred lateness %d -> %d (%.1f%%, tol 15%%); median "
                  "window p99 %d -> %d (%.1f%%, tol 10%%)"
                  % (dla, dlb, rel_d * 100, p99a, p99b, rel_p * 100)))

    # U6: the cost, on the ceiling and never the median.
    if agf and bgf:
        p90a, p90b = pctile(agf, 90), pctile(bgf, 90)
        mxa, mxb = max(agf), max(bgf)
        ok.append(leg("U6", (p90a - p90b) <= 2 and (mxa - mxb) <= 2,
                      "gfps p90 %d -> %d, max %d -> %d (each may fall by 2; "
                      "median %d -> %d is NOT the statistic, see #64)"
                      % (p90a, p90b, mxa, mxb,
                         pctile(agf, 50), pctile(bgf, 50))))
    else:
        ok.append(leg("U6", None, "no gfps lines"))

    # U7: the coalescing survey, on arm A, two-sided about #65's 1.56%.
    coal = sum(r["pcoal"] for r in a)
    if coal:
        cen = sum(r["coal_en"] for r in a)
        csh = sum(r["coal_short"] for r in a)
        _, cgap = pooled(a, "pcoal", "coal_gap")
        fen, fsh = cen / float(coal), csh / float(coal)
        ok.append(leg("U7", fen > 0.50 and fsh > 0.50,
                      "arm A coalesced %d of %d assertions (%.2f%%): %.0f%% "
                      "with the VBLANK bit UNMASKED, %.0f%% after a "
                      "shorter-than-period interval (mean preceding gap "
                      "%d ns against a %d ns period)"
                      % (coal, sum(r["n"] for r in a),
                         100.0 * coal / sum(r["n"] for r in a),
                         fen * 100, fsh * 100, cgap, period)))
    else:
        ok.append(leg("U7", None, "arm A coalesced nothing"))

    print()
    print("sources   A tmr=%d smp=%d gfx=%d | B tmr=%d smp=%d gfx=%d"
          % (sum(r["tmr"] for r in a), sum(r["smp"] for r in a),
             sum(r["gfx"] for r in a), sum(r["tmr"] for r in b),
             sum(r["smp"] for r in b), sum(r["gfx"] for r in b)))
    print("raster    A %d reads (max %d in a period) | B %d (max %d)"
          % (sum(r["rast"] for r in a), max(r["rastmax"] for r in a),
             sum(r["rast"] for r in b), max(r["rastmax"] for r in b)))
    print("INTR_EN   A vblank unmasked on %d of %d windows | B %d of %d"
          % (sum(r["en"] for r in a), len(a),
             sum(r["en"] for r in b), len(b)))

    held = [v for v in ok if v is True]
    failed = [v for v in ok if v is False]
    void = [v for v in ok if v is None]
    print("\nVERDICT: %d of %d legs hold, %d fail, %d void%s"
          % (len(held), len(ok), len(failed), len(void),
             "" if gate else "  (U8 GATE NOT MET -- the mechanism legs are "
                             "not judgeable on this pair)"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
