#!/usr/bin/env python3
"""Judge a VBLANK-timing A/B against its registered prediction.

    vblank_ab.py --a A/logcat.txt --b B/logcat.txt --expect predictions/x.json
    vblank_ab.py --a A1/logcat.txt --a A2/logcat.txt \
                 --b B1/logcat.txt --b B2/logcat.txt --expect predictions/x.json
    vblank_ab.py --selftest

`ab_compare.py` cannot score this. It compares captures, and no golden capture
can see VBLANK timing -- that blindness is the reason the guest-timing stream
exists at all. So this does the same job on the `vbl` lines instead: per
regime, never pooled, and against a prediction file whose commit date is the
binding that `--expect`'s content hash would otherwise provide.

The regimes are the split that matters: the adaptive deferral only runs while
the guest is mid-frame, so any title alternates between windows it touches and
windows it does not. The no-deferral windows are the **within-run control** --
the change under test cannot reach them, so if they move, something else did.

WHAT WAS WRONG WITH THIS FILE UNTIL 2026-09-19, because it is the defect the
whole no-oracle stream was exposed to and not a tidy-up. `--expect` opened the
prediction to print its header and then judged five thresholds that lived HERE,
in code. The registered `expect` block was read by nothing. It is also read by
nothing at queue time -- `request.sh`'s soak path says so in its own comment,
"there is no queue-time oracle for that key space ... put it in `expect` as a
named rule YOUR OWN READER CHECKS" -- so for a soak the block was inert on both
ends, and a misspelt or invented leg could not fail in either direction.

It was not a theoretical gap. Against `predictions/vblank-grid-deferral.json`,
the prediction this judge was written for, the five legs it reported as held
line up with the block it never read like this:

    B1  code: def>20 mean FALLS by >= 1,000,000 ns
        registered: `def_gt20/mean_interval_ns` 18,100,000 -- an ABSOLUTE bar
    B2  code: whole-soak rate > 58.000 Hz
        registered: `whole_soak/delivered_millihertz` 58,000,000  -- agrees
    B3  code: def==0 mean moves by <= 50,000 ns
        registered: `def_eq0/mean_interval_ns` 16,712,711 -- arm A's own value,
        with NO tolerance anywhere in the file. The 50,000 is this judge's.
    B4  code: median gfps falls by <= 2
        registered: `gfps_median_drop_max` 2  -- agrees
    B5  code: defers per window rise
        registered: nothing at all

So two of the five had no registered key, one was judged against a tolerance
that was never registered, and one was judged in a different SHAPE (a delta
against a bar). All five held either way, which is why nobody noticed: the
arm's conclusion is unaffected and is NOT withdrawn. What was unsound was the
binding, and the next prediction on this stream would have been judged by
#65's legs no matter what it said.

So this judge now does three things it did not:

  * **Registered legs are judged from the file.** Every key in `expect` is
    looked up in KEYS below. An unknown key is a REFUSAL, not a shrug --
    that is the misspelt-leg trap the queue-time gate says it cannot catch.
    A key that needs a tolerance and does not have one is UNJUDGEABLE, and
    prints why, rather than quietly falling back to a constant in here.

  * **The built-in B1-B5 are scoped to the arm they were written for.** They
    are kept verbatim so #65's cited verdict still reproduces byte for byte,
    but they are scored only when `--expect` names that prediction. For any
    other file they print NOT APPLICABLE and count towards nothing.

  * **A regime with no windows makes its leg VOID, never HOLDS.** B3 is the
    within-run control, and on an arm pair with no `def==0` window the old
    code compared 0 against 0, moved 0 ns, and printed HOLDS. A control that
    cannot fail is not a control.

And it takes repeated `--a`/`--b`, because this project's rule is runs >= 2 and
#65's own headline arm is one run each. Runs are never pooled: every leg is
judged on every (A run, B run) pair and reported WORST CASE, with each pair
printed. A single-run arm is judged and then said to be a single-run arm, on
the verdict line, where it cannot be read as more than it is.

`--selftest` builds synthetic logcats and mutant predictions and asserts that
each gate above trips. It needs no device and no results on disk.
"""
import argparse
import json
import os
import re
import statistics
import sys
import tempfile

VBL = re.compile(
    r"vbl n=(?P<n>\d+) win=(?P<win>\d+)ms want=(?P<want>\d+) got=(?P<got>\d+) "
    r"drift=(?P<drift>[-+]?\d+) rate=(?P<rate>[\d.]+)Hz "
    r"p1=(?P<p1>\d+) p50=(?P<p50>\d+) p90=(?P<p90>\d+) p99=(?P<p99>\d+) "
    r"min=(?P<min>\d+) max=(?P<max>\d+) "
    r"src\(tmr=(?P<tmr>\d+) smp=(?P<smp>\d+) gfx=(?P<gfx>\d+)\) "
    r"coal=(?P<coal>\d+) def=(?P<def>\d+) rast=(?P<rast>\d+)/(?P<rastmax>\d+)")
GFPS = re.compile(r"gfps=(\d+)")
UL = re.compile(r"Ul:([YN])")
# Only the one field this judge needs off the phase line. vblank_report.py and
# vblank_phase_ab.py parse the whole thing; duplicating it here would be a
# second copy to keep in step with nv2a.c for one counter.
NEG = re.compile(r"vblphase n=\d+ .*? neg=(\d+) ")

# The prediction the built-in B legs were written against, and the only one
# they may be scored for. b_ref is a pair because the registered sha is the
# commit BEFORE the prediction file itself; the dispatcher ran the commit that
# adds the file, and the two trees are identical outside
# docs/testing/predictions/.
BUILTIN_PREDICTION = "vblank-grid-deferral"
BUILTIN_REFS = {"a": ("19f52510d9",), "b": ("ed5df55ccc", "bace14275d")}


def load(path):
    """Load one run. `path` is a logcat, or a dispatch result DIRECTORY.

    Prefer the directory. A bare logcat records neither which binary produced
    it nor which handheld ran it, so an arm assembled out of bare logcats can
    be pointed at the wrong ref and say nothing about it -- #64's cost leg lost
    a control to four soaks across two handhelds with nothing recording which.
    """
    meta = {}
    if os.path.isdir(path):
        rj = os.path.join(path, "result.json")
        if os.path.exists(rj):
            meta = json.load(open(rj))
        path = os.path.join(path, "logcat.txt")
    rows, gfps, ul, neg = [], [], [], []
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
            m = NEG.search(line)
            if m:
                neg.append(int(m.group(1)))
    if not rows:
        sys.exit("no vbl lines in %s" % path)
    return {"path": path, "rows": rows, "gfps": gfps, "ul": ul, "neg": neg,
            "ref": meta.get("ref"), "device": meta.get("device_label"),
            "title": meta.get("title")}


def regime(rows, lo, hi):
    return [r for r in rows if lo <= r["def"] <= hi]


REGIMES = {"def==0": (0, 0), "def 1-20": (1, 20),
           "def>20": (21, 10 ** 9), "all": (0, 10 ** 9)}


def mean_interval(rows):
    return sum(r["got"] for r in rows) // len(rows) if rows else 0


def rate_hz(rows):
    span = sum(r["win"] for r in rows)
    n = sum(r["n"] for r in rows)
    return n * 1000.0 / span if span else 0.0


def coal_rate(rows):
    n = sum(r["n"] for r in rows)
    return sum(r["coal"] for r in rows) / float(n) if n else 0.0


def defers_per_window(rows):
    return sum(r["def"] for r in rows) / len(rows) if rows else 0.0


# ---------------------------------------------------------------- the legs

class Leg(object):
    """One judged leg. `verdict` is True/False/None, None meaning unmeasured.

    A leg that could not be evaluated because the data it needs is absent is
    VOID -- it carries verdict None and is reported separately from the legs
    that held. It is never folded into "holds", which is the bug this class
    exists to make structurally hard: the old B3 compared an empty regime
    against an empty regime and called the control good.
    """

    def __init__(self, name, verdict, detail, void_reason=None):
        self.name, self.verdict = name, verdict
        self.detail, self.void_reason = detail, void_reason

    def show(self, indent="  "):
        mark = {True: "HOLDS", False: "FAILS", None: "VOID"}[self.verdict]
        print("%s%-30s %-6s %s" % (indent, self.name, mark, self.detail))


def void(name, why):
    return Leg(name, None, why, why)


def need_regime(pair, label, name):
    """Return (rows_a, rows_b) or a VOID leg if either side has no window."""
    lo, hi = REGIMES[label]
    ra, rb = regime(pair[0]["rows"], lo, hi), regime(pair[1]["rows"], lo, hi)
    if not ra or not rb:
        return None, void(name, "no `%s` window in %s -- the regime this leg "
                                "reads is absent, so it is VOID and not held"
                          % (label, "arm A" if not ra else "arm B"))
    return (ra, rb), None


def k_def_gt20_max(pair, name, val):
    got, bad = need_regime(pair, "def>20", name)
    if bad:
        return bad
    b = mean_interval(got[1])
    return Leg(name, b <= val, "arm B def>20 mean %d ns against a bar of %d"
               % (b, val))


def k_def_gt20_fall(pair, name, val):
    got, bad = need_regime(pair, "def>20", name)
    if bad:
        return bad
    fall = mean_interval(got[0]) - mean_interval(got[1])
    return Leg(name, fall >= val, "def>20 mean %d -> %d, a fall of %+d ns "
                                  "against a bar of %d"
               % (mean_interval(got[0]), mean_interval(got[1]), fall, val))


# A VBLANK stream is a video refresh rate. Anything outside this in millihertz
# is not a bar somebody chose, it is a unit that slipped -- and on this stream
# nothing would ever have said so, because until 2026-09-19 no reader opened
# the key. `vblank-grid-deferral.json` registers 58,000,000, which as the key's
# own name spells it is a bar of 58 kHz and cannot be met by any arm.
RATE_SANE_MHZ = (1000, 1000000)


def k_whole_soak_mhz(pair, name, val):
    got = rate_hz(pair[1]["rows"]) * 1000.0
    note = ""
    if not RATE_SANE_MHZ[0] <= val <= RATE_SANE_MHZ[1]:
        note = ("  <- UNREACHABLE AS REGISTERED: %g millihertz is %g Hz. No "
                "VBLANK stream runs there;\n%sthis reads as a unit slip (%d "
                "is %.3f Hz read as MICROhertz), and it is a bar no arm can "
                "pass." % (val, val / 1000.0, " " * 39, val, val / 1e6))
    return Leg(name, got >= val,
               "arm B whole-soak %.3f mHz (%.3f Hz) against a bar of %d%s"
               % (got, got / 1000.0, val, note))


def k_def_eq0_tol(pair, name, val):
    got, bad = need_regime(pair, "def==0", name)
    if bad:
        return bad
    a, b = mean_interval(got[0]), mean_interval(got[1])
    return Leg(name, abs(b - a) <= val,
               "control def==0 mean %d -> %d, moved %d ns against a tolerance "
               "of %d" % (a, b, abs(b - a), val))


def k_gfps_drop(stat):
    def judge(pair, name, val):
        ga, gb = pair[0]["gfps"], pair[1]["gfps"]
        if not ga or not gb:
            return void(name, "no gfps lines in %s -- the cost leg has no "
                              "data and is VOID, not held"
                        % ("arm A" if not ga else "arm B"))
        f = statistics.median if stat == "median" else (
            lambda s: sorted(s)[min(len(s) - 1, int(0.9 * len(s)))])
        g0, g1 = f(ga), f(gb)
        return Leg(name, (g0 - g1) <= val,
                   "gfps %s %.1f -> %.1f (%+.1f) against a drop bar of %d"
                   % (stat, g0, g1, g1 - g0, val))
    return judge


def k_defers_rise(pair, name, val):
    if not val:
        return void(name, "registered false, so nothing is asserted")
    p0 = defers_per_window(pair[0]["rows"])
    p1 = defers_per_window(pair[1]["rows"])
    return Leg(name, p1 > p0, "defers per window %.1f -> %.1f" % (p0, p1))


def k_late_neg_max(pair, name, val):
    negs = pair[0]["neg"] + pair[1]["neg"]
    if not negs:
        return void(name, "neither arm emits a `vblphase` line, so `neg` is "
                          "ABSENT rather than zero -- this binary predates the "
                          "phase instrument and the leg is VOID")
    worst = max(negs)
    return Leg(name, worst <= val,
               "worst per-window neg %d over %d windows against a bar of %d"
               % (worst, len(negs), val))


def k_coal_frac_of_a(pair, name, val):
    ca, cb = coal_rate(pair[0]["rows"]), coal_rate(pair[1]["rows"])
    if ca <= 0:
        return void(name, "arm A coalesced nothing, so a fraction OF arm A is "
                          "undefined -- VOID rather than trivially held")
    return Leg(name, cb <= val * ca,
               "coalesced %.3f%% -> %.3f%% of assertions, ratio %.3f against "
               "a bar of %.3f" % (100 * ca, 100 * cb, cb / ca, val))


def k_src_alt_max(pair, name, val):
    worst = max(sum(r["smp"] + r["gfx"] for r in p["rows"]) for p in pair)
    return Leg(name, worst <= val,
               "non-timer VBLANK assertions (smp+gfx), worst arm %d against a "
               "bar of %d" % (worst, val))


# The whole registered key space, and the ONLY keys this judge accepts. A key
# not here is refused rather than ignored: on the soak path nothing upstream
# can tell a good key from a typo, so this is where it has to be caught.
KEYS = {
    "def_gt20/mean_interval_max_ns": k_def_gt20_max,
    "def_gt20/mean_interval_fall_min_ns": k_def_gt20_fall,
    "whole_soak/delivered_millihertz": k_whole_soak_mhz,
    "def_eq0/mean_interval_tolerance_ns": k_def_eq0_tol,
    "gfps_median_drop_max": k_gfps_drop("median"),
    "gfps_p90_drop_max": k_gfps_drop("p90"),
    "defers_per_window/must_rise": k_defers_rise,
    "late_neg_max": k_late_neg_max,
    "coalesced/rate_max_frac_of_a": k_coal_frac_of_a,
    "src_non_timer_max": k_src_alt_max,
}

# Keys that were registered before this judge read any of them, and that name a
# quantity rather than a rule. They are reported as UNJUDGEABLE with the key
# that would make them judgeable, and they never count as held. Rewriting the
# registered file to add that key would be widening a prediction after its arm,
# which is the one thing the commit-date binding exists to prevent.
LEGACY = {
    "def_gt20/mean_interval_ns":
        ("an absolute bar whose direction is not registered; the judgeable "
         "spellings are `def_gt20/mean_interval_max_ns` (bar) or "
         "`def_gt20/mean_interval_fall_min_ns` (delta)"),
    "def_eq0/mean_interval_ns":
        ("arm A's own measured value, not a rule. The control needs "
         "`def_eq0/mean_interval_tolerance_ns` to be judgeable at all"),
}


# ------------------------------------------------------- the built-in legs

def builtin_legs(pair):
    """#65's grid-deferral legs, verbatim, so its cited verdict reproduces."""
    a, b = pair[0]["rows"], pair[1]["rows"]
    ma = {}
    for label, (lo, hi) in REGIMES.items():
        ma[label] = (mean_interval(regime(a, lo, hi)),
                     mean_interval(regime(b, lo, hi)))
    out = []
    d1 = ma["def>20"][0] - ma["def>20"][1]
    out.append(Leg("B1", d1 >= 1000000 if d1 >= 300000 else False,
                   "def>20 mean %d -> %d, a fall of %+d ns"
                   % (ma["def>20"][0], ma["def>20"][1], d1)))
    r2 = rate_hz(b)
    out.append(Leg("B2", r2 > 58.0, "whole-soak rate %.3f -> %.3f Hz"
                   % (rate_hz(a), r2)))
    # The control, with the empty-regime hole closed. Everything else about
    # this leg -- the 50,000 ns tolerance included -- is as it was.
    if not regime(a, 0, 0) or not regime(b, 0, 0):
        out.append(void("B3", "no def==0 window in one arm; the within-run "
                              "control is absent, so it is VOID not held"))
    else:
        d3 = abs(ma["def==0"][1] - ma["def==0"][0])
        out.append(Leg("B3", d3 <= 50000,
                       "def==0 mean %d -> %d, moved %d ns (control)"
                       % (ma["def==0"][0], ma["def==0"][1], d3)))
    if pair[0]["gfps"] and pair[1]["gfps"]:
        g0 = statistics.median(pair[0]["gfps"])
        g1 = statistics.median(pair[1]["gfps"])
        out.append(Leg("B4", (g0 - g1) <= 2,
                       "median gfps %.1f -> %.1f (%+.1f)" % (g0, g1, g1 - g0)))
    else:
        out.append(void("B4", "no gfps lines"))
    p0, p1 = defers_per_window(a), defers_per_window(b)
    out.append(Leg("B5", p1 > p0,
                   "defers per window %.1f -> %.1f" % (p0, p1)))
    return out


BUILTIN_COVERS = {
    "B1": "def_gt20/mean_interval_fall_min_ns",
    "B2": "whole_soak/delivered_millihertz",
    "B3": "def_eq0/mean_interval_tolerance_ns",
    "B4": "gfps_median_drop_max",
    "B5": "defers_per_window/must_rise",
}


# ------------------------------------------------------------------ report

def _sha_eq(x, y):
    if not x or not y:
        return False
    x, y = str(x), str(y)
    n = min(len(x), len(y))
    return n >= 7 and x[:n] == y[:n]


def check_provenance(exp, A, B):
    """Refuse an arm built from the wrong binary, and say what is unrecorded.

    A logcat carries no ref. Pass dispatch result DIRECTORIES and this becomes
    a check; pass bare logcats and it can only report that it is not one, which
    it does rather than staying silent.
    """
    unrecorded = []
    for tag, runs, want in (("A", A, exp.get("a_ref")), ("B", B, exp.get("b_ref"))):
        for i, r in enumerate(runs):
            if not r["ref"]:
                unrecorded.append("%s%d" % (tag, i + 1))
                continue
            allow = BUILTIN_REFS["b"] if (tag == "B" and _sha_eq(
                want, BUILTIN_REFS["b"][0])) else (want,)
            if not any(_sha_eq(r["ref"], w) for w in allow):
                sys.exit(
                    "REFUSED: arm %s run %d was produced by ref %s, and the "
                    "prediction registers %s for arm %s.\n  A no-oracle arm "
                    "has no capture to disagree with, so the ref is the only\n"
                    "  thing that says which binary this measures. Re-register "
                    "on the ref that ran,\n  or point this at the runs the "
                    "prediction names." % (tag, i + 1, r["ref"], want, tag))
    # A device label that is MISSING on one arm is not the same as agreement.
    # #65's own arm A recorded none, and the investigation reports both arms as
    # "Thor" -- true of arm B's result.json and unrecorded for arm A.
    noname = ["%s%d" % (tag, i + 1)
              for tag, runs in (("A", A), ("B", B))
              for i, r in enumerate(runs) if r["ref"] and not r["device"]]
    if noname:
        print("  WARNING: %s record%s no device_label, so 'both arms ran on "
              "one handheld' is\n    an assumption here and not a reading."
              % (", ".join(noname), "s" if len(noname) == 1 else ""))
    devs = set(r["device"] for r in A + B if r["device"])
    if len(devs) > 1:
        print("  WARNING: runs span %s. A VBLANK rate is a property of the "
              "HOST's timer as\n    much as of the guest; two handhelds in one "
              "arm pair is not one measurement." % ", ".join(sorted(devs)))
    elif devs:
        print("  device      %s%s" % (devs.pop(),
                                      " (on the runs that recorded one)"
                                      if noname else ""))
    if unrecorded:
        print("  WARNING: %s carr%s no result.json, so neither the ref nor the "
              "handheld is\n    checked for %s. Pass the dispatch result "
              "DIRECTORY rather than its logcat."
              % (", ".join(unrecorded), "ies" if len(unrecorded) == 1 else "y",
                 "it" if len(unrecorded) == 1 else "them"))


def judge_pair(pair, exp, builtin_ok):
    expect = exp.get("expect") or {}
    registered, legacy = [], []
    for key in sorted(expect):
        if key in KEYS:
            registered.append(KEYS[key](pair, key, expect[key]))
        elif key in LEGACY:
            legacy.append(void(key, "UNJUDGEABLE AS REGISTERED: " + LEGACY[key]))
        else:
            sys.exit("REFUSED: `expect` key %r is not a rule this judge "
                     "knows.\n  A soak has no queue-time oracle for this key "
                     "space (see request.sh), so a key nothing here\n  "
                     "recognises would pass and fail in neither direction. "
                     "The known keys are:\n%s"
                     % (key, "".join("    %s\n" % k for k in sorted(KEYS))))
    built = builtin_legs(pair) if builtin_ok else []
    return registered, legacy, built


def pair_label(pa, pb, na, nb):
    return "A%d x B%d" % (pa + 1, pb + 1) if (na > 1 or nb > 1) else "A x B"


def worst(per_pair):
    """Fold a leg across run pairs: any FAILS wins, then any VOID."""
    out = {}
    for legs in per_pair:
        for leg in legs:
            cur = out.get(leg.name)
            if cur is None:
                out[leg.name] = leg
            elif leg.verdict is False and cur.verdict is not False:
                out[leg.name] = leg
            elif leg.verdict is None and cur.verdict is True:
                out[leg.name] = leg
    return [out[k] for k in sorted(out)]


def run(a_paths, b_paths, expect_path):
    exp = json.load(open(expect_path))
    stem = os.path.basename(expect_path)[:-5] \
        if expect_path.endswith(".json") else os.path.basename(expect_path)

    print("prediction %s" % expect_path)
    print("  registered %s by %s, issue #%s"
          % (exp.get("registered_utc"), exp.get("who"), exp.get("issue")))
    print("  a_ref %s  b_ref %s" % (exp.get("a_ref"), exp.get("b_ref")))
    judge = exp.get("judge")
    if judge and os.path.basename(judge) != os.path.basename(__file__):
        sys.exit("REFUSED: this prediction names %s as its judge, and this is "
                 "%s.\n  Two judges on this stream carry different legs; "
                 "running the wrong one\n  reports a verdict about a "
                 "hypothesis nobody registered."
                 % (judge, os.path.basename(__file__)))

    builtin_ok = (stem == BUILTIN_PREDICTION
                  and str(exp.get("a_ref")) in BUILTIN_REFS["a"]
                  and str(exp.get("b_ref")) in BUILTIN_REFS["b"])

    A = [load(p) for p in a_paths]
    B = [load(p) for p in b_paths]
    print("  runs        A %d   B %d" % (len(A), len(B)))
    check_provenance(exp, A, B)
    print()

    print("%-10s %-9s %10s %9s %8s %8s" % ("", "regime", "mean ns", "rate Hz",
                                           "windows", "unlockY"))
    for tag, runs in (("A", A), ("B", B)):
        for i, r in enumerate(runs):
            for label, (lo, hi) in REGIMES.items():
                rows = regime(r["rows"], lo, hi)
                print("%-10s %-9s %10d %9.3f %8d %8s"
                      % ("%s%d" % (tag, i + 1) if len(runs) > 1 else tag,
                         label, mean_interval(rows), rate_hz(rows), len(rows),
                         r["ul"].count("Y") if label == "all" else ""))
    print()

    per_reg, per_leg, per_built = [], [], []
    for ia, ra in enumerate(A):
        for ib, rb in enumerate(B):
            reg, leg, built = judge_pair((ra, rb), exp, builtin_ok)
            per_reg.append(reg)
            per_leg.append(leg)
            per_built.append(built)
            if len(A) * len(B) > 1:
                print("  %s" % pair_label(ia, ib, len(A), len(B)))
                for x in reg + built:
                    x.show("    ")
    if len(A) * len(B) > 1:
        print()

    reg = worst(per_reg)
    legacy = per_leg[0]
    built = worst(per_built)

    print("legs, as registered in the prediction%s"
          % (" (worst case over %d run pairs)" % (len(A) * len(B))
             if len(A) * len(B) > 1 else ""))
    if not reg and not legacy:
        print("  (none: the prediction registers no `expect` key this judge "
              "can read)")
    for leg in reg + legacy:
        leg.show()

    print()
    print("legs, built in to this judge -- #65's grid-deferral arm")
    if builtin_ok:
        for leg in built:
            leg.show()
    else:
        print("  NOT APPLICABLE: these five legs were written for prediction "
              "%r\n  at a_ref %s / b_ref %s. This run names %r, so scoring "
              "them here\n  would report #65's hypothesis against somebody "
              "else's arm."
              % (BUILTIN_PREDICTION, BUILTIN_REFS["a"][0],
                 "/".join(BUILTIN_REFS["b"]), stem))

    print()
    print("binding report")
    expect = exp.get("expect") or {}
    if builtin_ok:
        missing = [(n, k) for n, k in sorted(BUILTIN_COVERS.items())
                   if k not in expect]
        for n, k in missing:
            print("  %s is judged from code and has NO registered key (%s)"
                  % (n, k))
        if not missing:
            print("  every built-in leg has a registered key")
    for f in ("must_not_move", "must_not_regress", "expect_counts"):
        v = exp.get(f)
        if v:
            print("  `%s` has %d entr%s: prose for a reader, judged by nothing "
                  "here" % (f, len(v), "y" if len(v) == 1 else "ies"))

    allb = A + B
    coal = sum(sum(r["coal"] for r in x["rows"]) for x in allb)
    n = sum(sum(r["n"] for r in x["rows"]) for x in allb)
    print()
    print("coalesced   %d of %d assertions over all runs (%.2f%%)"
          % (coal, n, 100.0 * coal / n))
    print("p99 median  A %s   B %s"
          % (" ".join("%d" % statistics.median(r["p99"] for r in x["rows"])
                      for x in A),
             " ".join("%d" % statistics.median(r["p99"] for r in x["rows"])
                      for x in B)))

    scored = reg + legacy + (built if builtin_ok else [])
    held = [x for x in scored if x.verdict is True]
    failed = [x for x in scored if x.verdict is False]
    voided = [x for x in scored if x.verdict is None]
    print()
    print("VERDICT: %d of %d legs hold, %d fail, %d void"
          % (len(held), len(scored), len(failed), len(voided)))
    if len(A) < 2 or len(B) < 2:
        print("RUNS: %d per arm A, %d per arm B. This project's rule is "
              "runs >= 2 for a\n  no-oracle measurement, because the replicate "
              "is the RUN and not the window.\n  Read every number above as "
              "one run's worth of evidence." % (len(A), len(B)))
    return 1 if failed else 0


# ---------------------------------------------------------------- selftest

def _synth(path, windows, defers, got, gfps=29, coal=0, neg=None, smp=0):
    """Write a logcat whose `vbl` lines say exactly what the caller asked."""
    with open(path, "w") as fh:
        for i in range(windows):
            if neg is not None:
                fh.write("vblphase n=120 period=16683750 mean=1 p50=1 p90=1 "
                         "p99=1 max=1 neg=%d nodef(n=1 mean=1 max=1) "
                         "def(n=1 mean=1 max=1) unl=0 coal=0 coal_en=0 "
                         "coal_short=0 coal_gap=0 en=1 clamp=0\n" % neg)
            fh.write("gfps=%d Ul:N\n" % gfps)
            fh.write("vbl n=120 win=2000ms want=16683750 got=%d drift=+0 "
                     "rate=59.900Hz p1=1 p50=1 p90=1 p99=25050000 min=1 "
                     "max=1 src(tmr=120 smp=%d gfx=0) coal=%d def=%d "
                     "rast=0/0\n" % (got, smp, coal, defers))


def _pred(path, expect, **kw):
    doc = {"registered_utc": "2026-09-19T00:00:00Z", "who": "selftest",
           "issue": "65", "a_ref": "0" * 10, "b_ref": "1" * 10,
           "expect": expect}
    doc.update(kw)
    json.dump(doc, open(path, "w"))


def _capture(fn):
    """Run fn, returning (exit code, stdout). SystemExit(str) is code 2."""
    import io
    import contextlib
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = fn()
    except SystemExit as e:
        code = 2 if isinstance(e.code, str) else (e.code or 0)
        buf.write(str(e.code))
    return code, buf.getvalue()


def selftest():
    """One mutant per gate. Each must TRIP; a gate nothing trips is decoration."""
    d = tempfile.mkdtemp(prefix="vblank_ab_selftest")
    j = lambda n: os.path.join(d, n)
    fails = []

    def check(name, cond, detail=""):
        print("  %-52s %s" % (name, "ok" if cond else "FAILED"))
        if not cond:
            fails.append("%s %s" % (name, detail))

    # Baseline: a healthy pair, every leg registered and judgeable.
    _synth(j("a.txt"), 20, 30, 19000000, gfps=29, coal=10, neg=0)
    _synth(j("b.txt"), 20, 40, 16700000, gfps=29, coal=1, neg=0)
    # ... plus def==0 windows, so the control has something to read.
    with open(j("a.txt"), "a") as fh:
        fh.write(open(j("a.txt")).read().replace("def=30", "def=0")
                 .replace("got=19000000", "got=16700000"))
    with open(j("b.txt"), "a") as fh:
        fh.write(open(j("b.txt")).read().replace("def=40", "def=0")
                 .replace("got=16700000", "got=16710000"))
    good = {"def_gt20/mean_interval_fall_min_ns": 1000000,
            "whole_soak/delivered_millihertz": 58000,
            "def_eq0/mean_interval_tolerance_ns": 50000,
            "gfps_median_drop_max": 2,
            "defers_per_window/must_rise": True,
            "late_neg_max": 0}
    _pred(j("good.json"), good)
    code, out = _capture(lambda: run([j("a.txt")], [j("b.txt")], j("good.json")))
    check("baseline: every registered leg holds", code == 0 and "FAILS" not in out)
    check("baseline: one run per arm is said out loud", "RUNS: 1 per arm" in out)
    check("baseline: built-ins are not scored for a foreign prediction",
          "NOT APPLICABLE" in out)

    # GATE 1: an unknown `expect` key is refused, not ignored.
    bad = dict(good)
    bad["def_gt20/mean_interval_fall_min_nx"] = 1000000   # one-character typo
    _pred(j("typo.json"), bad)
    code, out = _capture(lambda: run([j("a.txt")], [j("b.txt")], j("typo.json")))
    check("mutant: a misspelt expect key REFUSES", code == 2 and "REFUSED" in out)

    # GATE 2: a prediction naming another judge is refused.
    _pred(j("other.json"), good, judge="docs/testing/vblank_phase_ab.py")
    code, out = _capture(lambda: run([j("a.txt")], [j("b.txt")], j("other.json")))
    check("mutant: a prediction naming another judge REFUSES",
          code == 2 and "REFUSED" in out)

    # GATE 3: an absent regime makes the control VOID, never HOLDS. This is the
    # old B3 bug: 0 against 0 moved 0 ns and printed HOLDS.
    _synth(j("a0.txt"), 20, 30, 19000000, gfps=29, neg=0)
    _synth(j("b0.txt"), 20, 40, 16700000, gfps=29, neg=0)
    code, out = _capture(lambda: run([j("a0.txt")], [j("b0.txt")], j("good.json")))
    ctl = [l for l in out.splitlines() if "def_eq0/mean_interval_tol" in l]
    check("mutant: control with no def==0 window is VOID",
          len(ctl) == 1 and "VOID" in ctl[0], ctl)

    # GATE 4: `neg` absent is VOID, not zero. A binary older than the phase
    # instrument emits no vblphase line at all, and summing an empty list is 0.
    _synth(j("aold.txt"), 20, 30, 19000000, gfps=29)
    _synth(j("bold.txt"), 20, 40, 16700000, gfps=29)
    code, out = _capture(
        lambda: run([j("aold.txt")], [j("bold.txt")], j("good.json")))
    ln = [l for l in out.splitlines() if "late_neg_max" in l]
    check("mutant: absent `neg` is VOID, not a passing zero",
          len(ln) == 1 and "VOID" in ln[0], ln)

    # GATE 5: a leg that should fail, does. Without this the four gates above
    # could all be passing because nothing is ever judged.
    _synth(j("bslow.txt"), 20, 40, 19100000, gfps=29, neg=0)
    with open(j("bslow.txt"), "a") as fh:
        fh.write(open(j("bslow.txt")).read().replace("def=40", "def=0"))
    code, out = _capture(
        lambda: run([j("a.txt")], [j("bslow.txt")], j("good.json")))
    check("mutant: an arm B that did not improve FAILS",
          code == 1 and "FAILS" in out)

    # GATE 6: a legacy value-only key is UNJUDGEABLE and never counts as held.
    _pred(j("legacy.json"), {"def_eq0/mean_interval_ns": 16712711})
    code, out = _capture(
        lambda: run([j("a.txt")], [j("b.txt")], j("legacy.json")))
    check("mutant: a value-only key is UNJUDGEABLE, 0 legs hold",
          "UNJUDGEABLE" in out and "0 of 1 legs hold" in out)

    # GATE 7: a bar outside any video refresh rate is named as unreachable
    # rather than silently failed. This is the state the ONE registered
    # prediction on this stream is actually in.
    _pred(j("units.json"), {"whole_soak/delivered_millihertz": 58000000})
    code, out = _capture(
        lambda: run([j("a.txt")], [j("b.txt")], j("units.json")))
    check("mutant: an out-of-range rate bar is named UNREACHABLE",
          code == 1 and "UNREACHABLE AS REGISTERED" in out)

    # GATE 8: a run directory whose result.json names a ref the prediction did
    # not register is REFUSED. Without this the judge happily scores the wrong
    # binary, because a logcat does not say which one made it.
    os.makedirs(j("rundir"))
    os.rename(j("a.txt"), j("rundir/logcat.txt"))
    json.dump({"ref": "deadbeef99", "device_label": "thor"},
              open(j("rundir/result.json"), "w"))
    code, out = _capture(
        lambda: run([j("rundir")], [j("b.txt")], j("good.json")))
    check("mutant: a run from an unregistered ref REFUSES",
          code == 2 and "REFUSED" in out)
    json.dump({"ref": "0" * 10, "device_label": "thor"},
              open(j("rundir/result.json"), "w"))
    code, out = _capture(
        lambda: run([j("rundir")], [j("b.txt")], j("good.json")))
    check("baseline: the registered ref is accepted and reported",
          code == 0 and "device      thor" in out)
    check("baseline: the bare-logcat arm says its ref is unchecked",
          "carries no result.json" in out or "carry no result.json" in out)
    os.rename(j("rundir/logcat.txt"), j("a.txt"))

    # GATE 9: two runs per arm are folded worst-case, and the runs>=2 warning
    # goes away only when both arms have two.
    code, out = _capture(lambda: run([j("a.txt"), j("a.txt")],
                                     [j("b.txt"), j("bslow.txt")],
                                     j("good.json")))
    check("mutant: a bad second B run fails the folded verdict",
          code == 1 and "RUNS:" not in out)

    print()
    if fails:
        print("SELFTEST FAILED: %d" % len(fails))
        for f in fails:
            print("  %s" % f)
        return 1
    print("SELFTEST: all gates trip")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", action="append", default=[],
                    help="arm A logcat; repeat for runs >= 2")
    ap.add_argument("--b", action="append", default=[],
                    help="arm B logcat; repeat for runs >= 2")
    ap.add_argument("--expect")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.a or not args.b:
        ap.error("--a and --b are both required (repeat either for runs >= 2)")
    if not args.expect:
        ap.error("--expect is required. This judge scores a REGISTERED "
                 "prediction; without one\n  its legs would be whatever "
                 "happens to be in the file, which is the defect\n  its "
                 "docstring describes.")
    return run(args.a, args.b, args.expect)


if __name__ == "__main__":
    sys.exit(main())
