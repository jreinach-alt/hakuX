#!/usr/bin/env python3
"""Judge the unlock-mode `defer_cap` A/B against its registered prediction.

    vblank_defercap_ab.py --a A/logcat.txt --b B/logcat.txt \
                          --expect predictions/vblank-unlock-defercap.json

A sibling of `vblank_ab.py` (#65's B legs, rate, split on the deferral count)
and `vblank_phase_ab.py` (#65's U legs, phase, split on unlock occupancy).
A third file rather than an edit, for the reason the second one gives: the
investigation cites both verdicts, and breaking either judge would invalidate
a result that is already published.

What is new here is the `clamp=` field on the `vblphase` line, and why it had
to exist.

#65 attributed the residual +3.03 s/min in unlock mode to `max_defer =
poll_interval * defer_cap = (period/16)*16 = period`, and it is right, but the
size of the effect cannot be read off the drift figure -- because the grid's
clamp does not discard the EXCESS over a period, it discards the WHOLE
lateness:

    d->vblank_next_target_ns += period;          /* t + period       */
    if (d->vblank_next_target_ns <= now) {
        d->vblank_next_target_ns = now + period; /* t + late + period */
    }

So the grid moves forward by `late`, not by `late - period`, and mean drift
per assertion is `E[late * 1(late > period)]` -- a quantity dominated by the
few assertions over the threshold, not by the mean. Reasoning from the excess
instead (as this judge's author first did) under-predicts the available gain
by roughly 12x and would have registered a leg that called a working fix
inert. The counter exists so the mechanism is READ rather than inferred: the
clamp either fires or it does not.

Every regime figure is pooled BY ASSERTION COUNT, and the cost leg reads the
`gfps` CEILING and never the median, both for the reasons `vblank_phase_ab.py`
records.
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
    r"coal=(?P<coal>\d+) def=(?P<defers>\d+) rast=(?P<rast>\d+)/(?P<rastmax>\d+)")

# `clamp=` is OPTIONAL on purpose. A ref that predates the counter still
# parses, so this judge can be pointed at the older soaks in
# docs/investigations/guest-visible-vblank.md for the regime figures; the legs
# that need the counter then report VOID rather than a wrong number.
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
    r"en=(?P<en>\d+)(?: clamp=(?P<clamp>\d+))?")

GFPS = re.compile(r"gfps=(\d+)")


def load(path):
    vbl, ph, gfps = [], [], []
    with open(path, errors="replace") as fh:
        for line in fh:
            m = PHASE.search(line)
            if m:
                d = m.groupdict()
                row = {k: (int(v) if v is not None else None)
                       for k, v in d.items()}
                ph.append(row)
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
                 "instrument" % path)
    if len(ph) != len(vbl):
        sys.exit("%s: %d vblphase lines against %d vbl lines; the pairing is "
                 "not one-to-one and would misattribute windows"
                 % (path, len(ph), len(vbl)))
    return [dict(a, **b) for a, b in zip(vbl, ph)], gfps


def has_clamp(rows):
    return all(r["clamp"] is not None for r in rows)


def pooled_interval(rows):
    n = sum(r["n"] for r in rows)
    return sum(r["n"] * r["got"] for r in rows) // n if n else 0


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


def split(rows, which):
    if which == "unlock":
        return [r for r in rows if r["unl"] > 0]
    if which == "locked":
        return [r for r in rows if r["unl"] == 0]
    if which == "full":
        return [r for r in rows if r["pn"] and r["unl"] == r["pn"]]
    return rows


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
    poll = period // 16

    print("period %d ns   poll_interval (period/16) %d ns" % (period, poll))
    print("old max_defer (cap 16) %d   new max_defer (cap 15) %d\n"
          % (poll * 16, poll * 15))

    print("%-18s %10s %10s" % ("", "A", "B"))
    for what, f in (("windows", lambda r: len(r)),
                    ("assertions", lambda r: sum(x["n"] for x in r)),
                    ("unlock windows", lambda r: len(split(r, "unlock"))),
                    ("fully unlocked", lambda r: len(split(r, "full"))),
                    ("locked windows", lambda r: len(split(r, "locked")))):
        print("%-18s %10d %10d" % (what, f(a), f(b)))
    print()

    for label in ("all", "unlock", "locked", "full"):
        ra, rb = split(a, label), split(b, label)
        print("%-8s A %10d ns %7.3f Hz drift %+9d clamp/win %5.2f | "
              "B %10d ns %7.3f Hz drift %+9d clamp/win %5.2f"
              % (label,
                 pooled_interval(ra), rate_hz(ra),
                 pooled_interval(ra) - period if ra else 0,
                 (sum(r["clamp"] or 0 for r in ra) / len(ra)) if ra else 0,
                 pooled_interval(rb), rate_hz(rb),
                 pooled_interval(rb) - period if rb else 0,
                 (sum(r["clamp"] or 0 for r in rb) / len(rb)) if rb else 0))
    print()

    print("legs")
    ok = []

    fa, fb = split(a, "full"), split(b, "full")

    # D8: the validity gate. Both arms must actually enter unlock mode, or
    # every mechanism leg is VOID rather than failed.
    gate = len(fa) >= 5 and len(fb) >= 5
    leg("D8", gate if gate else False,
        "fully-unlocked windows A=%d B=%d (gate needs >=5 each)"
        % (len(fa), len(fb)))

    clamp_ok = has_clamp(a) and has_clamp(b)
    if not clamp_ok:
        print("  (one arm predates the clamp counter; D0/D1/D9 are VOID)")

    # D0: the instrument against the arithmetic, on arm A alone. Over windows
    # whose deferrals are cap-bound (def_mean > period, which at a cap of one
    # whole period means essentially every deferral ran to the cap), each
    # clamp discards one whole lateness, so
    #     drift * n / clamp  ==  def_mean.
    # Forced by the code and by QEMU timer semantics, not by the patch.
    capb = [r for r in fa if r["def_n"] and r["def_mean"] > period]
    if not clamp_ok:
        ok.append(leg("D0", None, "no clamp counter in arm A"))
    elif not capb:
        ok.append(leg("D0", None,
                      "arm A has no fully-unlocked window whose deferrals are "
                      "cap-bound (def_mean > period)"))
    else:
        cl = sum(r["clamp"] for r in capb)
        n = sum(r["n"] for r in capb)
        drift = pooled_interval(capb) - period
        dn, dm = pooled(capb, "def_n", "def_mean")
        implied = drift * n / float(cl) if cl else 0
        rel = abs(implied - dm) / float(dm) if dm else 9.9
        relc = abs(cl - dn) / float(dn) if dn else 9.9
        ok.append(leg("D0", rel <= 0.30 and relc <= 0.20,
                      "arm A cap-bound windows: drift*n/clamp = %d ns against "
                      "def_mean %d ns (%.1f%%, tol 30%%); clamp %d against "
                      "def_n %d (%.1f%%, tol 20%%)"
                      % (implied, dm, rel * 100, cl, dn, relc * 100)))

    # D1: THE MECHANISM. The clamp stops firing in unlock mode. It can still
    # fire, on a host stall longer than a period, or on a device whose timer
    # round trip exceeds period/16 = 1.04 ms -- so this is not forced by the
    # patch.
    if not clamp_ok or not gate:
        ok.append(leg("D1", None, "gate or counter missing"))
    else:
        ca = sum(r["clamp"] for r in fa) / float(sum(r["n"] for r in fa))
        cb = sum(r["clamp"] for r in fb) / float(sum(r["n"] for r in fb))
        ok.append(leg("D1", cb <= 0.10 * ca if ca else None,
                      "fully-unlocked clamp rate %.4f -> %.4f per assertion "
                      "(need <= 10%% of arm A's)" % (ca, cb)))

    # D2: the headline. Arithmetic from arm B of #65's unlock arm predicts
    # 843,164 ns -> ~0.
    if not gate:
        ok.append(leg("D2", None, "gate not met"))
    else:
        da = pooled_interval(fa) - period
        db = pooled_interval(fb) - period
        ok.append(leg("D2", (da - db) >= 500000,
                      "fully-unlocked drift %+d -> %+d ns, fell %d "
                      "(need >= 500000); rate %.3f -> %.3f Hz"
                      % (da, db, da - db, rate_hz(fa), rate_hz(fb))))

    # D3: the within-run control, in the regime the change cannot reach.
    la, lb = split(a, "locked"), split(b, "locked")
    if la and lb:
        d = abs(pooled_interval(lb) - pooled_interval(la))
        ok.append(leg("D3", d <= 50000,
                      "locked-window mean %d -> %d, moved %d ns "
                      "(control, tol 50000)"
                      % (pooled_interval(la), pooled_interval(lb), d)))
    else:
        ok.append(leg("D3", None, "one arm has no unlock-free window"))

    # D4: the impossible row.
    neg = sum(r["neg"] for r in a) + sum(r["neg"] for r in b)
    ok.append(leg("D4", neg == 0,
                  "negative lateness count %d across both arms" % neg))

    # D5: the hold shrinks by one poll interval and no more. Half forced by
    # the patch (a cap-bound hold must shrink by exactly that), half not: a
    # hold bounded by `remaining` rather than by the cap would not move.
    ra = [r for r in fa if r["def_n"]]
    rb = [r for r in fb if r["def_n"]]
    if ra and rb:
        _, ma = pooled(ra, "def_n", "def_mean")
        _, mb = pooled(rb, "def_n", "def_mean")
        fall = ma - mb
        rel = abs(fall - poll) / float(poll)
        ok.append(leg("D5", rel <= 0.25,
                      "deferred hold %d -> %d ns, fell %d against one poll "
                      "interval %d (%.1f%%, tol 25%%)"
                      % (ma, mb, fall, poll, rel * 100)))
    else:
        ok.append(leg("D5", None, "one arm has no deferral in unlock mode"))

    # D6: the cost, on the ceiling and never the median.
    if agf and bgf:
        pa, pb_ = pctile(agf, 90), pctile(bgf, 90)
        xa, xb = max(agf), max(bgf)
        ok.append(leg("D6", (pa - pb_) <= 2 and (xa - xb) <= 2,
                      "gfps p90 %d -> %d, max %d -> %d (each may fall by at "
                      "most 2); median %d -> %d reported and NOT judged"
                      % (pa, pb_, xa, xb, pctile(agf, 50), pctile(bgf, 50))))
    else:
        ok.append(leg("D6", None, "no gfps samples in one arm"))

    # D7: the regime must stay comparable. If shortening the cap stopped
    # deferral happening at all, D2's improvement would be a regime change
    # rather than the mechanism.
    if gate:
        pa = sum(r["defers"] for r in fa) / float(len(fa))
        pb_ = sum(r["defers"] for r in fb) / float(len(fb))
        rel = abs(pb_ - pa) / float(pa) if pa else 9.9
        ok.append(leg("D7", rel <= 0.60,
                      "defers per fully-unlocked window %.1f -> %.1f "
                      "(%.1f%%, tol 60%%)" % (pa, pb_, rel * 100)))
    else:
        ok.append(leg("D7", None, "gate not met"))

    # D9: the residual, attributed. Any clamp left in arm B's unlock windows
    # should be a host stall, which is rare, and not the deferral.
    if not clamp_ok or not gate:
        ok.append(leg("D9", None, "gate or counter missing"))
    else:
        worst = max(r["clamp"] for r in fb)
        ok.append(leg("D9", worst <= 2,
                      "worst fully-unlocked window in arm B clamps %d times "
                      "(need <= 2; the remainder is the host stall tail, "
                      "whose max lateness is %d ns = %.1fx a period)"
                      % (worst, max(r["lmax"] for r in fb),
                         max(r["lmax"] for r in fb) / float(period))))

    held = sum(1 for v in ok if v is True)
    failed = sum(1 for v in ok if v is False)
    void = sum(1 for v in ok if v is None)
    print("\n%d hold, %d FAIL, %d void" % (held, failed, void))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
