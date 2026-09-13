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
records -- now with a second demonstration on disk, contributed by the
performance lane: two Galleon soaks, same device, both `gfps max=29 p90=29`,
medians **27 and 17**.

`--a` and `--b` are REPEATABLE, and that is the other thing this judge does
differently. A soak has no oracle, so `orchestration.md` requires two runs for
any claim made from one -- and the replicate is the RUN, not the window. The
performance lane measured absolute per-window counts varying 3-5x WITHIN a
single run, so a rule computed over all of one run's windows tightens with
every window a longer soak happens to produce, which is not a property of the
mechanism. Every leg here is therefore computed per run and judged on the
worst run of the arm, with all runs printed. #65's own "least certain" was
exactly this: one run per arm, with the unlock occupancy differing 27.7%
against 12.4% between them, and it is the confound that broke U5.
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


def metrics(rows, gfps, cap=16):
    """Everything the legs need, from ONE run of one arm.

    Per run and not per window: the performance lane measured absolute
    per-window counts varying 3-5x inside a single soak, so a figure pooled
    over a run's windows is a property of that run, and a rule judged over all
    windows of all runs tightens with every window a longer soak happens to
    produce. The run is the replicate.
    """
    period = rows[0]["period"]
    full = split(rows, "full")
    locked = split(rows, "locked")
    unlock = split(rows, "unlock")
    # CAP-BOUND: a window whose deferrals ran to the cap. `max_defer` is
    # `poll_interval * defer_cap`, so this test is a function of the cap the
    # run was BUILT with -- it is `> period` only because the first arm ever
    # judged here was cap 16, where `max_defer` IS a period to the nanosecond.
    # Hardcoding that silently misclassifies every other cap: at 12 the
    # threshold is 12,512,808 ns and a window meaning to be cap-bound reads as
    # window-bound, which would make the mechanism leg pass by being empty.
    max_defer = (period // 16) * cap
    capb = [r for r in full if r["def_n"] and r["def_mean"] > max_defer]
    have_clamp = has_clamp(rows)

    m = dict(period=period, windows=len(rows),
             n=sum(r["n"] for r in rows),
             full_windows=len(full), locked_windows=len(locked),
             unlock_windows=len(unlock),
             have_clamp=have_clamp,
             rate_all=rate_hz(rows),
             drift_all=pooled_interval(rows) - period if rows else 0,
             neg=sum(r["neg"] for r in rows),
             gfps_p50=pctile(gfps, 50), gfps_p90=pctile(gfps, 90),
             gfps_max=max(gfps) if gfps else 0)

    m["full_n"] = sum(r["n"] for r in full)
    m["full_drift"] = (pooled_interval(full) - period) if full else None
    m["full_rate"] = rate_hz(full) if full else None
    m["locked_interval"] = pooled_interval(locked) if locked else None
    m["hold"] = pooled([r for r in full if r["def_n"]],
                       "def_n", "def_mean")[1] or None
    m["defers_per_full_window"] = (sum(r["defers"] for r in full) / len(full)
                                   if full else None)
    m["lmax"] = max((r["lmax"] for r in full), default=0)

    if have_clamp and full:
        m["clamp_rate_full"] = (sum(r["clamp"] for r in full)
                                / float(m["full_n"])) if m["full_n"] else 0.0
        m["clamp_worst_full"] = max(r["clamp"] for r in full)
    else:
        m["clamp_rate_full"] = None
        m["clamp_worst_full"] = None

    # D0's identity, on the windows where it is well posed.
    if have_clamp and capb:
        cl = sum(r["clamp"] for r in capb)
        n = sum(r["n"] for r in capb)
        m["d0_capb_windows"] = len(capb)
        m["d0_clamp"] = cl
        m["d0_def_n"] = sum(r["def_n"] for r in capb)
        m["d0_def_mean"] = pooled(capb, "def_n", "def_mean")[1]
        m["d0_implied"] = ((pooled_interval(capb) - period) * n / float(cl)
                           if cl else None)
    else:
        m["d0_capb_windows"] = 0
        m["d0_implied"] = None
    return m


def fmt(v, w=12):
    if v is None:
        return "%*s" % (w, "-")
    if isinstance(v, float):
        return "%*.4f" % (w, v) if abs(v) < 1 else "%*.3f" % (w, v)
    return "%*d" % (w, v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, action="append",
                    help="arm A logcat; repeat for each run of the arm")
    ap.add_argument("--b", required=True, action="append",
                    help="arm B logcat; repeat for each run of the arm")
    ap.add_argument("--expect")
    # The caps the two arms were BUILT with. Defaults are the first step this
    # judge was written for (16 -> 15) so every verdict it has already
    # published reproduces unchanged; pass them for any other step.
    ap.add_argument("--cap-a", type=int, default=16,
                    help="defer_cap in arm A's binary (default 16)")
    ap.add_argument("--cap-b", type=int, default=15,
                    help="defer_cap in arm B's binary (default 15)")
    args = ap.parse_args()

    if args.expect:
        exp = json.load(open(args.expect))
        print("prediction registered %s by %s, issue #%s"
              % (exp.get("registered_utc"), exp.get("who"), exp.get("issue")))
        print("  a_ref %s  b_ref %s  title %s  device %s\n"
              % (exp.get("a_ref"), exp.get("b_ref"), exp.get("title"),
                 exp.get("device")))

    A = [metrics(*load(p), cap=args.cap_a) for p in args.a]
    B = [metrics(*load(p), cap=args.cap_b) for p in args.b]
    period = A[0]["period"]
    poll = period // 16

    print("period %d ns   poll_interval (period/16) %d ns" % (period, poll))
    print("arm A max_defer (cap %d) %d   arm B max_defer (cap %d) %d" %
          (args.cap_a, poll * args.cap_a, args.cap_b, poll * args.cap_b))
    print("expected deferred-hold fall = %d poll intervals = %d ns" %
          (args.cap_a - args.cap_b, poll * (args.cap_a - args.cap_b)))
    print("runs: A=%d  B=%d   (the replicate is the RUN, not the window)\n"
          % (len(A), len(B)))

    hdr = ("%-3s %-26s" + "%12s" * max(len(A), len(B))) % (
        "", "", *["run %d" % (i + 1) for i in range(max(len(A), len(B)))])
    for arm, rows in (("A", A), ("B", B)):
        print(hdr if arm == "A" else "")
        for label, key in (("windows", "windows"),
                           ("assertions", "n"),
                           ("fully-unlocked windows", "full_windows"),
                           ("fully-unlocked drift ns", "full_drift"),
                           ("fully-unlocked rate Hz", "full_rate"),
                           ("clamp/assertion (full)", "clamp_rate_full"),
                           ("worst window clamps", "clamp_worst_full"),
                           ("deferred hold ns", "hold"),
                           ("defers/full window", "defers_per_full_window"),
                           ("locked interval ns", "locked_interval"),
                           ("whole-soak rate Hz", "rate_all"),
                           ("gfps p90 / max / p50", None),
                           ("late max (periods)", None)):
            if key is None:
                if label.startswith("gfps"):
                    vals = ["%4d/%4d/%4d" % (r["gfps_p90"], r["gfps_max"],
                                             r["gfps_p50"]) for r in rows]
                else:
                    vals = ["%12.1f" % (r["lmax"] / float(period))
                            for r in rows]
                print("%-3s %-26s%s" % (arm, label,
                                        "".join("%14s" % v for v in vals)))
                continue
            print("%-3s %-26s%s" % (arm, label,
                                    "".join(fmt(r[key], 14) for r in rows)))
    print()

    print("legs  (judged on the WORST run of the arm; every run printed above)")
    ok = []

    # D8: the validity gate, per run.
    okA = min(r["full_windows"] for r in A)
    okB = min(r["full_windows"] for r in B)
    gate = okA >= 5 and okB >= 5
    leg("D8", gate if gate else False,
        "fully-unlocked windows, worst run: A=%d B=%d (gate needs >=5 each)"
        % (okA, okB))

    clamp_ok = (all(r["have_clamp"] for r in A)
                and all(r["have_clamp"] for r in B))
    if not clamp_ok:
        print("  (one arm predates the clamp counter; D0/D1/D9 are VOID)")

    # D0: the instrument against the arithmetic, arm A only.
    capb = [r for r in A if r["d0_implied"] is not None]
    if not clamp_ok:
        ok.append(leg("D0", None, "no clamp counter in arm A"))
    elif not capb:
        ok.append(leg("D0", None, "no arm A run has a cap-bound "
                                  "fully-unlocked window"))
    else:
        worst_rel = worst_relc = 0.0
        detail = []
        for i, r in enumerate(capb):
            rel = abs(r["d0_implied"] - r["d0_def_mean"]) / float(r["d0_def_mean"])
            relc = abs(r["d0_clamp"] - r["d0_def_n"]) / float(r["d0_def_n"])
            worst_rel = max(worst_rel, rel)
            worst_relc = max(worst_relc, relc)
            detail.append("run%d %d vs %d (%.1f%%), clamp %d vs def_n %d (%.1f%%)"
                          % (i + 1, r["d0_implied"], r["d0_def_mean"],
                             rel * 100, r["d0_clamp"], r["d0_def_n"],
                             relc * 100))
        ok.append(leg("D0", worst_rel <= 0.30 and worst_relc <= 0.20,
                      "drift*n/clamp against def_mean, tol 30%/20%: "
                      + "; ".join(detail)))

    # D1: the mechanism, worst B run against best A run.
    if not clamp_ok or not gate:
        ok.append(leg("D1", None, "gate or counter missing"))
    else:
        ca = min(r["clamp_rate_full"] for r in A)
        cb = max(r["clamp_rate_full"] for r in B)
        ok.append(leg("D1", cb <= 0.10 * ca if ca else None,
                      "clamp rate per assertion, fully-unlocked: A min %.4f, "
                      "B max %.4f (need B <= 10%% of A)" % (ca, cb)))

    # D2: the headline, worst case both ways.
    if not gate:
        ok.append(leg("D2", None, "gate not met"))
    else:
        da = min(r["full_drift"] for r in A)
        db = max(r["full_drift"] for r in B)
        ok.append(leg("D2", (da - db) >= 500000,
                      "fully-unlocked drift: A min %+d, B max %+d, worst-case "
                      "fall %d (need >= 500000); rate A %.3f-%.3f -> B "
                      "%.3f-%.3f Hz"
                      % (da, db, da - db,
                         min(r["full_rate"] for r in A),
                         max(r["full_rate"] for r in A),
                         min(r["full_rate"] for r in B),
                         max(r["full_rate"] for r in B))))

    # D3: the within-run control, in the regime the change cannot reach.
    la = [r["locked_interval"] for r in A if r["locked_interval"]]
    lb = [r["locked_interval"] for r in B if r["locked_interval"]]
    if la and lb:
        d = max(abs(y - x) for x in la for y in lb)
        ok.append(leg("D3", d <= 50000,
                      "locked-window mean A %s B %s, worst pairwise move %d ns "
                      "(control, tol 50000)"
                      % ("/".join(str(x) for x in la),
                         "/".join(str(x) for x in lb), d)))
    else:
        ok.append(leg("D3", None, "an arm has no unlock-free window"))

    # D4: the impossible row, across every run of both arms.
    neg = sum(r["neg"] for r in A) + sum(r["neg"] for r in B)
    ok.append(leg("D4", neg == 0,
                  "negative lateness count %d across all %d runs"
                  % (neg, len(A) + len(B))))

    # D5: the constant, measured. Half forced by the patch; see the prediction.
    ha = [r["hold"] for r in A if r["hold"]]
    hb = [r["hold"] for r in B if r["hold"]]
    if ha and hb:
        steps = args.cap_a - args.cap_b
        want = poll * steps
        falls = [x - y for x in ha for y in hb]
        worst = max(abs(f - want) for f in falls) / float(want)
        # Cross-paired (the worst of the product) is the registered form and
        # it FAILED at 16 -> 15, because arm A's own hold moved 1,227,019 ns
        # between two runs of one binary while the effect was 1,042,734. At a
        # larger step the effect grows and the spread does not, so the
        # run-paired figure is printed alongside rather than instead: a leg
        # that fails cross-paired and holds run-paired is a statement about
        # the control's spread, not about the change.
        paired = [x - y for x, y in zip(ha, hb)] if len(ha) == len(hb) else []
        pworst = (max(abs(f - want) for f in paired) / float(want)
                  if paired else None)
        ok.append(leg("D5", worst <= 0.25,
                      "deferred hold A %s -> B %s; worst pairwise fall vs %d "
                      "poll interval(s) = %d ns is %.1f%% off (tol 25%%)%s"
                      % ("/".join(str(x) for x in ha),
                         "/".join(str(x) for x in hb), steps, want,
                         worst * 100,
                         "" if pworst is None
                         else "; RUN-PAIRED %.1f%% off" % (pworst * 100))))
    else:
        ok.append(leg("D5", None, "an arm has no deferral in unlock mode"))

    # D6: THE COST, on the ceiling and never the median.
    if all(r["gfps_max"] for r in A) and all(r["gfps_max"] for r in B):
        pa, pb_ = max(r["gfps_p90"] for r in A), min(r["gfps_p90"] for r in B)
        xa, xb = max(r["gfps_max"] for r in A), min(r["gfps_max"] for r in B)
        ok.append(leg("D6", (pa - pb_) <= 2 and (xa - xb) <= 2,
                      "gfps p90 best-A %d vs worst-B %d, max best-A %d vs "
                      "worst-B %d (each may fall by at most 2). Medians "
                      "A %s B %s reported and NOT judged -- two Galleon soaks "
                      "on one device gave medians 27 and 17 at an identical "
                      "p90 of 29."
                      % (pa, pb_, xa, xb,
                         "/".join(str(r["gfps_p50"]) for r in A),
                         "/".join(str(r["gfps_p50"]) for r in B))))
    else:
        ok.append(leg("D6", None, "no gfps samples in one arm"))

    # D7: the regime must stay comparable.
    if gate and all(r["defers_per_full_window"] for r in A + B):
        pa = [r["defers_per_full_window"] for r in A]
        pb_ = [r["defers_per_full_window"] for r in B]
        worst = max(abs(y - x) / x for x in pa for y in pb_)
        ok.append(leg("D7", worst <= 0.60,
                      "defers per fully-unlocked window A %s -> B %s, worst "
                      "pairwise %.1f%% (tol 60%%)"
                      % ("/".join("%.1f" % x for x in pa),
                         "/".join("%.1f" % x for x in pb_), worst * 100)))
    else:
        ok.append(leg("D7", None, "gate not met or a run has no deferral"))

    # D9: the residual, attributed.
    if not clamp_ok or not gate:
        ok.append(leg("D9", None, "gate or counter missing"))
    else:
        worst = max(r["clamp_worst_full"] for r in B)
        ok.append(leg("D9", worst <= 2,
                      "worst fully-unlocked window across arm B's runs clamps "
                      "%d times (need <= 2; what is left is the host stall "
                      "tail, whose max lateness is %.1fx a period)"
                      % (worst, max(r["lmax"] for r in B) / float(period))))

    held = sum(1 for v in ok if v is True)
    failed = sum(1 for v in ok if v is False)
    void = sum(1 for v in ok if v is None)
    print("\n%d hold, %d FAIL, %d void" % (held, failed, void))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
