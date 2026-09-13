#!/usr/bin/env python3
"""The VBLANK timer's ROUND TRIP, read off a soak's own `vblphase` line.

WHY THIS EXISTS, and it is a correction rather than a new question.

#65's `defer_cap` 16 -> 15 landed and took unlock-mode loss from 11.005 to
0.798 s/min at zero measurable frame-rate cost. Its D9 leg FAILED: the worst
fully-unlocked window in arm B still clamped 5 times against a bar of 2. The
diagnosis was exact -- a deferral trips the grid's `<= now` clamp when the
timer round trip `L + L'` exceeds the margin the cap leaves -- and the value
12 was then chosen because `def_max - max_defer` reached **3,083,365 ns**, so
12's 4,170,938 ns of margin is "1.35x the observed maximum".

That justification does not survive being measured on more data, and this
tool is what measures it. 3,083,365 ns is a maximum over the ~32 fully-
unlocked windows two thor runs happened to contain. The SAME estimator, on
the SAME device, over the ~118 locked windows of each of those runs, reaches
**10.8 to 13.8 ms**. The quantity was not 1.35x covered; it was sampled too
few times to see its own tail. That is `AGENTS.md`'s "a within-ref floor is a
lower bound on the floor, never the floor", and "a bound is not a value".

THE ESTIMATOR. For a non-deferred assertion the recorded lateness is the
timer's own lateness `L`, because the callback fires at the grid slot and
asserts immediately. For a deferred one it is `L + hold + L'`, where
`hold = MIN(max_defer, remaining) <= max_defer`. So

    def_max - max_defer  <=  max(L + L')

is a LOWER BOUND on the round trip, and the bound is tight whenever the
deferral was cap-bound rather than window-bound. It is the estimator #65's
12 was derived from, so applying it elsewhere is like for like.

WHAT IT CANNOT SEE, stated before any number is read off it:

  - A HOST STALL is indistinguishable from a long round trip in a window
    aggregate. `--max-stall` drops windows whose non-deferred maximum exceeds
    a period, which is the only stall evidence a window line carries; it
    removes two windows in nine of the runs here and changes no conclusion,
    so it is reported rather than relied on.
  - `def_max` is a per-window maximum, so this measures the tail's DEPTH at
    two-second granularity and not the distribution.
  - A window whose deferrals were all `remaining`-bound rather than cap-bound
    under-reads, which is the safe direction for sizing a cap.

THE STATISTIC IS A WINDOW COUNT, not a rate or a mean, for the reason
`AGENTS.md` records three times: a rate over a window whose occupancy varies
measures the occupancy. #65's own D1/D5/D7 all failed that way. So the output
is "how many windows would clamp at cap X", which no amount of idle time can
dilute.

TWO CONTROLS ARE INSIDE THE TOOL, because a number with no control is a
number you have to trust:

  - `def_max >= def_mean` must hold in every window with a deferral. It is a
    property of the histogram, not of the host, so a non-zero count here is
    a parse defect and nothing else.
  - `nodef_n + def_n == n` must hold EXACTLY. Holding exactly says the three
    counters are read at one instant; holding to +-1 would say they are not,
    which is information about the instrument rather than noise.

  - and cap 16's margin is 6 ns, so EVERY window with a deferral must exceed
    it. A cap-16 column that is not the def-window count is the impossible
    row failing.
"""

import argparse
import json
import os
import re
import sys

LINE = re.compile(
    r"vblphase n=(?P<n>\d+) period=(?P<period>\d+) mean=(?P<mean>\d+) "
    r"p50=(?P<p50>\d+) p90=(?P<p90>\d+) p99=(?P<p99>\d+) max=(?P<max>\d+) "
    r"neg=(?P<neg>\d+) "
    r"nodef\(n=(?P<nodef_n>\d+) mean=(?P<nodef_mean>\d+) max=(?P<nodef_max>\d+)\) "
    r"def\(n=(?P<def_n>\d+) mean=(?P<def_mean>\d+) max=(?P<def_max>\d+)\) "
    r"unl=(?P<unl>\d+)")
CLAMP = re.compile(r"\bclamp=(\d+)")

# nv2a.c: `int defer_cap = unlocked ? 15 : 4;`
#         `int64_t poll_interval = unlocked ? period / 16 : period / 8;`
LOCKED_CAP, LOCKED_DIV = 4, 8
UNLOCK_DIV = 16

CAPS = list(range(16, 5, -1))


def max_defer(period, unlocked, unlock_cap):
    if unlocked:
        return (period // UNLOCK_DIV) * unlock_cap
    return (period // LOCKED_DIV) * LOCKED_CAP


def margin(period, cap):
    """Room the grid keeps at `cap`: the next slot is one period away."""
    return period - (period // UNLOCK_DIV) * cap


def parse(path):
    rows = []
    with open(path, errors="replace") as fh:
        for ln in fh:
            m = LINE.search(ln)
            if not m:
                continue
            r = {k: int(v) for k, v in m.groupdict().items()}
            c = CLAMP.search(ln)
            r["clamp"] = int(c.group(1)) if c else None
            rows.append(r)
    return rows


def analyse(rows, unlock_cap, drop_stalls):
    """Round trip per window, CONDITIONED ON REGIME rather than pooled.

    `max_defer` is `period/2` locked and `poll_interval * unlock_cap`
    unlocked, so a window that mixes the two regimes has two different holds
    inside one aggregate and `def_max` could belong to either. Assigning it
    one of them under-reads with the unlocked value and over-reads with the
    locked one, so a MIXED window is excluded instead. That is `AGENTS.md`'s
    "condition on the state, then compare within it" -- and it is the exact
    trap #65's U5 failed on, where a hold pooled across two caps measured the
    mixture rather than either regime.
    """
    period = rows[0]["period"]
    defw = [r for r in rows if r["def_n"] > 0]

    mixed = [r for r in defw if 0 < r["unl"] < r["n"]]
    defw = [r for r in defw if r["unl"] == 0 or r["unl"] == r["n"]]

    dropped = 0
    if drop_stalls:
        keep = [r for r in defw if r["nodef_max"] <= period]
        dropped = len(defw) - len(keep)
        defw = keep

    rt = []
    for r in defw:
        rt.append(r["def_max"] - max_defer(period, r["unl"] == r["n"], unlock_cap))

    bad_hist = sum(1 for r in rows if r["def_n"] > 0 and r["def_max"] < r["def_mean"])
    bad_ident = sum(1 for r in rows if r["nodef_n"] + r["def_n"] != r["n"])
    bad_neg = sum(1 for r in rows if r["neg"])

    return {
        "period": period,
        "windows": len(rows),
        "def_windows": len(defw),
        "mixed_regime_windows": len(mixed),
        "control_neg": bad_neg,
        "dropped_stall_windows": dropped,
        # `unl` is s_vbh.unlocked_n: the COUNT of assertions in the window
        # that were made in unlock mode, not a flag. A "fully unlocked"
        # window is unl == n, which is the population #65's D-legs judge on.
        "unlock_windows": sum(1 for r in rows if r["unl"]),
        "fully_unlocked_windows": sum(1 for r in rows if r["unl"] and r["unl"] == r["n"]),
        "rt_max": max(rt) if rt else 0,
        "rt_p90": sorted(rt)[int(0.9 * len(rt))] if rt else 0,
        "rt_median": sorted(rt)[len(rt) // 2] if rt else 0,
        "exceed": {c: sum(1 for x in rt if x > margin(period, c)) for c in CAPS},
        "clamp_total": sum(r["clamp"] for r in rows if r["clamp"] is not None),
        "control_def_max_lt_mean": bad_hist,
        "control_counter_identity": bad_ident,
    }


def selftest():
    """Check the regex against the format string nv2a.c actually prints.

    A reader that silently matches nothing reports a soak full of numbers as
    a soak that emitted none, which reads exactly like a failed run. That
    cost two falsifiers on 2026-09-12.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(here, "..", "..", "hw", "xbox", "nv2a", "nv2a.c")
    ok = True
    try:
        text = open(src, errors="replace").read()
    except OSError as exc:
        print("SELFTEST: cannot read nv2a.c: %s" % exc)
        return False

    for needle in ('"vblphase n=%u period=%lld', "nodef(n=%u mean=",
                   "def(n=%u mean=", "unl=%u", "clamp=%u"):
        if needle not in text:
            print("SELFTEST: nv2a.c no longer prints %r" % needle)
            ok = False

    sample = ("hakuX-perf: vblphase n=120 period=16683750 mean=3150012 p50=300000 "
              "p90=9500000 p99=14150000 max=15473593 neg=0 "
              "nodef(n=79 mean=417975 max=2803593) "
              "def(n=41 mean=8414183 max=15473593) unl=0 coal=1 coal_en=1 "
              "coal_short=1 coal_gap=16662083 en=1 clamp=0")
    m = LINE.search(sample)
    if not m:
        print("SELFTEST: the regex does not match a known-good line")
        return False
    if int(m.group("def_mean")) != 8414183:
        print("SELFTEST: field capture is wrong")
        ok = False
    if CLAMP.search(sample).group(1) != "0":
        print("SELFTEST: clamp capture is wrong")
        ok = False

    p = 16683750
    if max_defer(p, 1, 16) - p not in (0, -6, -1, -2, -3, -4, -5):
        print("SELFTEST: cap 16 is meant to be a period to the nanosecond, got %d"
              % max_defer(p, 1, 16))
        ok = False
    if margin(p, 12) != 4170942:
        print("SELFTEST: cap 12 margin %d" % margin(p, 12))
        ok = False

    print("selftest " + ("ok" if ok else "FAILED"))
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="*",
                    help="dispatch result directories, or logcat.txt paths")
    ap.add_argument("--unlock-cap", type=int, default=15,
                    help="the defer_cap the RUN was built with (default 15)")
    ap.add_argument("--keep-stall-windows", action="store_true",
                    help="do not drop windows whose non-deferred max exceeds a period")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return 0 if selftest() else 1
    if not args.results:
        ap.error("give at least one result directory")

    out = []
    for path in args.results:
        lg = path
        label = ref = title = "?"
        if os.path.isdir(path):
            lg = os.path.join(path, "logcat.txt")
            try:
                res = json.load(open(os.path.join(path, "result.json")))
                label = res.get("device_label", "?")
                ref = (res.get("ref") or "?")[:10]
                title = res.get("title") or res.get("disc_id") or "?"
            except Exception:
                pass
        if not os.path.exists(lg):
            print("MISSING: %s" % lg, file=sys.stderr)
            continue
        rows = parse(lg)
        if not rows:
            print("NO vblphase LINES: %s  (run --selftest)" % lg, file=sys.stderr)
            continue
        a = analyse(rows, args.unlock_cap, not args.keep_stall_windows)
        a.update(run=os.path.basename(path.rstrip("/")), device=label, ref=ref,
                 title=title)
        out.append(a)

    if args.json:
        print(json.dumps(out, indent=2))
        return 0

    if not out:
        return 1
    period = out[0]["period"]
    print("period %d ns   locked max_defer %d" % (period, max_defer(period, 0, 0)))
    print("estimator: def_max - max_defer, a LOWER bound on max(L + L')")
    print("statistic: windows that would clamp at each cap (occupancy-free)")
    print()
    print("%-36s %-5s %-10s %5s %4s %4s  %s" %
          ("run", "dev", "ref", "defw", "fuw", "mix",
           " ".join("c%-4d" % c for c in CAPS)))
    for a in out:
        print("%-36s %-5s %-10s %5d %4d %4d  %s" %
              (a["run"][:36], a["device"], a["ref"], a["def_windows"],
               a["fully_unlocked_windows"], a["mixed_regime_windows"],
               " ".join("%-5d" % a["exceed"][c] for c in CAPS)))
    print()
    print("%-36s %14s %14s %14s %7s" %
          ("run", "rt_max", "rt_p90", "rt_median", "clamps"))
    for a in out:
        print("%-36s %14d %14d %14d %7d" %
              (a["run"][:36], a["rt_max"], a["rt_p90"], a["rt_median"],
               a["clamp_total"]))
    print()
    print("margins: " + "  ".join("c%d=%d" % (c, margin(period, c)) for c in CAPS))
    print()
    bad = 0
    for a in out:
        if a["control_def_max_lt_mean"]:
            print("CONTROL FAILED %s: def_max < def_mean in %d windows"
                  % (a["run"], a["control_def_max_lt_mean"]))
            bad += 1
        if a["control_counter_identity"]:
            print("CONTROL: nodef_n + def_n != n in %d windows of %s"
                  % (a["control_counter_identity"], a["run"]))
            bad += 1
        if a["control_neg"]:
            print("IMPOSSIBLE ROW FAILED %s: neg != 0 in %d windows -- a QEMU "
                  "timer cannot fire early, so an assertion cannot be ahead "
                  "of its own grid slot" % (a["run"], a["control_neg"]))
            bad += 1
    if not bad:
        print("controls ok: neg == 0 (the impossible row: no assertion is "
              "early), def_max >= def_mean everywhere, nodef_n + def_n == n "
              "EXACTLY -- the three counters are read at one instant")
    print()
    print("cap-16 column is COVERAGE, not a control: it counts windows with "
          "at least one CAP-BOUND deferral (cap 16 leaves 6 ns, so a "
          "cap-bound hold must exceed it). A window below it was "
          "`remaining`-bound and under-reads the round trip.")
    if any(a["dropped_stall_windows"] for a in out):
        print("dropped as host-stall windows: " +
              ", ".join("%s=%d" % (a["run"][:20], a["dropped_stall_windows"])
                        for a in out if a["dropped_stall_windows"]))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
