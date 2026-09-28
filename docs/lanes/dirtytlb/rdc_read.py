#!/usr/bin/env python3
"""Read #548's [rdc] lines: who calls tlb_reset_dirty() off the vCPU thread.

    rdc_read.py RUN [RUN...] [--window 90,240]
    rdc_read.py --pair A_RUN B_RUN [--window 90,240]
    rdc_read.py --selftest

RUN is a soak's result directory (logcat.txt, thermal.jsonl, run.log) or a
logcat file. Every figure is taken over the window, 90 to 240 s after the
first hakuX-perf line unless --window says otherwise; the cut is
docs/testing/phase_read_split.py's THE WINDOW, as pair461_read.py's is.

THE LINE (system/physmem.c, tag hakuX-perf, one per 60+ guest flips):
  [rdc] f= dt= tid= tcpu= rdo= rdous= vtx=n/us/pg/h nv2a=.. tex=.. vga=..
        code=.. mig=.. snap=.. oth=.. v= dra= dx= tm= ovh=ns/n tk=
  Every field is the line's own window. <site>=calls/us/pages/hits.

THE FIGURES, per run, over the window's [rdc] lines:
  flips        the sum of f
  per flip     rdo, rdous, and each site's calls, us, pages and hits
  tcpu         render-thread CPU ms per flip: the sum of tcpu over lines that
               carry one, over those lines' flips
  ovh          the counter's own cost per flip: the timed ns per call times
               the window's calls, plus tk, over the flips
  sum          (sites' calls - rdo) and (sites' us - rdous), window totals
  gfps, M, Tq  medians of hakuX-perf's gfps and Tq and hakuX-cpu's M

THE LEGS, registered in docs/testing/predictions/dirtytlb-counter.json
before any [rdc] line existed. A leg whose inputs are missing reads UNREAD,
never PASS.
"""
import argparse
import os
import re
import shutil
import statistics
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing"))
import phase_read_split as prs  # noqa: E402

SITES = ["vtx", "nv2a", "tex", "vga", "code", "mig", "snap", "oth"]
RE_RDC = re.compile(
    r"\[rdc\] f=(\d+) dt=(-?\d+) tid=(-?\d+) tcpu=(-|[\d.]+) rdo=(\d+) rdous=(\d+) "
    + " ".join(r"%s=(\d+)/(\d+)/(\d+)/(\d+)" % s for s in SITES)
    + r" v=(\d+) dra=(-?\d+) dx=(\d+) tm=(\d+) ovh=(\d+)/(\d+) tk=(-?\d+)")
RE_GFPS = re.compile(r"gfps=(\d+)")
RE_TQ = re.compile(r"(?<![A-Za-z])Tq:(-?[\d.]+)")
RE_M = re.compile(r"(?<![A-Za-z])M:(-?[\d.]+)")


def parse_rdc(line):
    m = RE_RDC.search(line)
    if not m:
        return None
    g = m.groups()
    d = {"f": int(g[0]), "dt": int(g[1]), "tid": int(g[2]),
         "tcpu": None if g[3] == "-" else float(g[3]),
         "rdo": int(g[4]), "rdous": int(g[5])}
    for i, s in enumerate(SITES):
        d[s] = tuple(int(x) for x in g[6 + 4 * i: 10 + 4 * i])
    k = 6 + 4 * len(SITES)
    d["v"], d["dra"], d["dx"], d["tm"] = (int(x) for x in g[k:k + 4])
    d["ovns"], d["ovn"], d["tk"] = (int(x) for x in g[k + 4:k + 7])
    return d


def median(xs):
    return statistics.median(xs) if xs else None


def locate(run):
    if os.path.isdir(run):
        return os.path.join(run, "logcat.txt")
    return run


def summarise(rows):
    """Window totals and per-flip figures from parsed [rdc] rows."""
    r = {"lines": len(rows)}
    flips = sum(d["f"] for d in rows)
    r["flips"] = flips
    if not rows or not flips:
        return r
    calls = sum(d[s][0] for d in rows for s in SITES)
    us = sum(d[s][1] for d in rows for s in SITES)
    rdo = sum(d["rdo"] for d in rows)
    rdous = sum(d["rdous"] for d in rows)
    r["rdo"], r["rdous"] = rdo / flips, rdous / flips
    r["site"] = {s: tuple(sum(d[s][j] for d in rows) / flips for j in range(4))
                 for s in SITES}
    r["sum_calls"], r["sum_us"] = calls - rdo, us - rdous
    r["sum_calls_rel"] = (calls - rdo) / rdo if rdo else None
    r["sum_us_rel"] = (us - rdous) / rdous if rdous else None
    # per line: the calls identity, allowing the few walks that land between
    # the rdo read and the site reads in rdc_tick
    r["sum_line_bad"] = sum(1 for d in rows
                            if abs(sum(d[s][0] for s in SITES) - d["rdo"])
                            > max(3, 0.01 * d["rdo"]))
    t = [d for d in rows if d["tcpu"] is not None]
    r["tcpu_lines"] = len(t)
    r["tcpu"] = sum(d["tcpu"] for d in t) / sum(d["f"] for d in t) if t else None
    r["tids"] = sorted(set(d["tid"] for d in rows))
    ovn = sum(d["ovn"] for d in rows)
    r["ovh_ns_call"] = sum(d["ovns"] for d in rows) / ovn if ovn else None
    r["ovh_us_flip"] = (None if r["ovh_ns_call"] is None else
                        (r["ovh_ns_call"] * calls / 1000.0
                         + sum(max(d["tk"], 0) for d in rows)) / flips)
    r["oth"] = sum(d["oth"][0] for d in rows)
    r["dx"] = sum(d["dx"] for d in rows)
    r["dra"] = sorted(set(d["dra"] for d in rows))
    r["tm"] = sum(d["tm"] for d in rows) / flips
    r["v"] = sum(d["v"] for d in rows) / flips
    return r


def read_run(run, window):
    logcat = locate(run)
    lines = open(logcat, errors="replace").read().splitlines()
    win = prs.window_lines(lines, window) if window else lines
    rows, bad = [], 0
    for l in win:
        if "[rdc]" not in l:
            continue
        d = parse_rdc(l)
        if d is None:
            bad += 1
        else:
            rows.append(d)
    r = summarise(rows)
    r["name"] = os.path.basename(os.path.dirname(os.path.abspath(logcat)))
    r["malformed"] = bad
    perf = [l for l in win if "hakuX-perf" in l and RE_GFPS.search(l)]
    r["gfps"] = median([int(RE_GFPS.search(l).group(1)) for l in perf])
    r["Tq"] = median([float(m.group(1)) for l in perf for m in [RE_TQ.search(l)] if m])
    r["M"] = median([float(m.group(1)) for l in win if "hakuX-cpu" in l
                     for m in [RE_M.search(l)] if m])
    return r


def verdict(ok):
    return "PASS" if ok else "FAIL"


def legs_b(b):
    """The legs read on the counter arm alone."""
    out = {}
    if not b.get("lines") or b["lines"] < 20:
        out["V"] = ("VOID", "%s [rdc] lines in the window, 20 needed" % b.get("lines"))
        return out
    tl = b["tcpu_lines"] / float(b["lines"])
    out["V"] = (verdict(tl >= 0.8 and not b["malformed"]),
                "%d lines, %d malformed, tcpu on %.0f%% (tids %s)"
                % (b["lines"], b["malformed"], 100 * tl, b["tids"]))
    out["C1"] = (verdict(b["sum_line_bad"] <= 0.05 * b["lines"]
                         and abs(b["sum_calls_rel"] or 0) <= 0.01
                         and abs(b["sum_us_rel"] or 0) <= 0.02),
                 "sites - rdo: %+d calls (%+.2f%%), %+d us (%+.2f%%); %d lines off"
                 % (b["sum_calls"], 100 * (b["sum_calls_rel"] or 0), b["sum_us"],
                    100 * (b["sum_us_rel"] or 0), b["sum_line_bad"]))
    out["C2"] = (verdict(b["oth"] == 0 and b["dx"] == 0),
                 "oth %d, dx %d, dra %s" % (b["oth"], b["dx"], b["dra"]))
    if b["ovh_us_flip"] is None or not b["rdous"]:
        out["H"] = ("UNREAD", "no timed calls")
    else:
        out["H"] = (verdict(b["ovh_us_flip"] <= 0.01 * b["rdous"]
                            and b["ovh_ns_call"] <= 500),
                    "%.0f ns/call, %.1f us/flip = %.2f%% of rdous/flip %.0f"
                    % (b["ovh_ns_call"], b["ovh_us_flip"],
                       100 * b["ovh_us_flip"] / b["rdous"], b["rdous"]))
    s = b["site"]
    vt = s["vtx"][0] + s["tex"][0]
    out["N1"] = (verdict(b["rdo"] and vt >= 0.95 * b["rdo"]),
                 "vtx+tex %.1f of rdo %.1f per flip (%.1f%%)"
                 % (vt, b["rdo"], 100 * vt / b["rdo"] if b["rdo"] else 0))
    out["N2"] = (verdict(s["vtx"][0] > s["tex"][0]),
                 "vtx %.1f vs tex %.1f calls per flip" % (s["vtx"][0], s["tex"][0]))
    if b["Tq"] is None:
        out["X"] = ("UNREAD", "no Tq")
    else:
        out["X"] = (verdict(s["tex"][0] <= 1.2 * b["Tq"] + 1),
                    "tex walks %.1f per flip vs Tq median %.1f" % (s["tex"][0], b["Tq"]))
    return out


def legs_pair(a, b):
    out = legs_b(b)
    if a["gfps"] is None or b["gfps"] is None:
        out["F"] = ("UNREAD", "no gfps")
    else:
        out["F"] = (verdict(b["gfps"] >= a["gfps"] - 1),
                    "gfps median A %s / B %s" % (a["gfps"], b["gfps"]))
    if a["M"] is None or b["M"] is None:
        out["K2"] = ("UNREAD", "no hakuX-cpu M")
    else:
        hi, lo = max(a["M"], b["M"]), min(a["M"], b["M"])
        out["K2"] = (verdict(lo > 0 and hi / lo <= 1.1),
                     "M median A %.0f / B %.0f" % (a["M"], b["M"]))
    return out


def fmt(x, f="%.1f"):
    return "-" if x is None else f % x


def report(r):
    print("%s: %s [rdc] lines, %s flips, gfps %s, Tq %s, M %s"
          % (r["name"], r.get("lines"), r.get("flips"), r["gfps"], r["Tq"], r["M"]))
    if not r.get("flips"):
        return
    print("  per flip: rdo %.1f  rdous %.0f  tcpu %s ms  vCPU walks %.1f  tail-miss pages %.2f"
          % (r["rdo"], r["rdous"], fmt(r["tcpu"], "%.2f"), r["v"], r["tm"]))
    print("  %-5s %8s %8s %8s %8s %8s" % ("site", "calls", "us", "pages", "hits", "us/call"))
    for s in SITES:
        n, us, pg, h = r["site"][s]
        if n:
            print("  %-5s %8.1f %8.0f %8.1f %8.1f %8.1f" % (s, n, us, pg, h, us / n))
    print("  overhead %s ns/call, %s us/flip; oth %d dx %d dra %s"
          % (fmt(r["ovh_ns_call"], "%.0f"), fmt(r["ovh_us_flip"]), r["oth"], r["dx"], r["dra"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="*")
    ap.add_argument("--pair", nargs=2, metavar=("A", "B"))
    ap.add_argument("--window", default="90,240")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    window = tuple(float(x) for x in a.window.split(",")) if a.window else None
    if a.pair:
        ra, rb = (read_run(x, window) for x in a.pair)
        report(ra)
        report(rb)
        for k, (v, why) in sorted(legs_pair(ra, rb).items()):
            print("  %-3s %-6s %s" % (k, v, why))
        return 0
    for run in a.runs:
        r = read_run(run, window)
        report(r)
        for k, (v, why) in sorted(legs_b(r).items()):
            print("  %-3s %-6s %s" % (k, v, why))
    return 0


def fake_line(t, f=60, rdo=10500, vtx=6000, tex=4500, oth=0, dx=0, tcpu="210.5", us=27):
    sites = {"vtx": vtx, "tex": tex, "oth": oth}
    parts = " ".join("%s=%d/%d/%d/%d" % (s, sites.get(s, 0), sites.get(s, 0) * us,
                                         sites.get(s, 0), sites.get(s, 0) // 2)
                     for s in SITES)
    return ("09-28 10:%02d:%02d.000  1234  1300 I hakuX-perf: [rdc] f=%d dt=2000 tid=1300 "
            "tcpu=%s rdo=%d rdous=%d %s v=3 dra=-1234 dx=%d tm=0 ovh=6000/40 tk=30"
            % (t // 60, t % 60, f, tcpu, rdo, rdo * us, parts, dx))


def selftest():
    ok = True
    tmp = tempfile.mkdtemp()
    try:
        def run(name, body):
            d = os.path.join(tmp, name)
            os.makedirs(d)
            lines = ["09-28 10:00:00.000  1234  1300 I hakuX-perf: gfps=30 G:33.3"]
            for t in range(100, 230, 5):
                lines.append("09-28 10:%02d:%02d.000  1234  1300 I hakuX-perf: gfps=30 G:33.3 Tq:80"
                             % (t // 60, t % 60))
                lines.append("09-28 10:%02d:%02d.500  1234  1301 I hakuX-cpu( 1): M:20000"
                             % (t // 60, t % 60))
                lines.append(body(t))
            open(os.path.join(d, "logcat.txt"), "w").write("\n".join(lines) + "\n")
            return read_run(d, (90, 240))

        good = run("good", lambda t: fake_line(t))
        L = legs_b(good)
        for k in ("V", "C1", "C2", "H", "N1", "N2", "X"):
            if L[k][0] != "PASS":
                print("FAIL selftest: good run leg %s %s" % (k, L[k]))
                ok = False
        # 26 lines of 60 flips: rdo 175 per flip
        ok &= abs(good["rdo"] - 175) < 1e-9 and good["lines"] == 26
        ok &= abs(good["tcpu"] - 210.5 / 60) < 1e-9
        # the impossible row: an untagged walk fails C2, and C1 on rdo mismatch
        bad = run("bad", lambda t: fake_line(t, vtx=5400, oth=600))
        Lb = legs_b(bad)
        ok &= Lb["C2"][0] == "FAIL" and Lb["C1"][0] == "PASS" and Lb["N1"][0] == "FAIL"
        miss = run("miss", lambda t: fake_line(t, rdo=12000))
        ok &= legs_b(miss)["C1"][0] == "FAIL"
        # the middle element: tex largest, vtx second, so N2 must fail
        mid = run("mid", lambda t: fake_line(t, vtx=3600, tex=6900))
        ok &= legs_b(mid)["N2"][0] == "FAIL" and legs_b(mid)["X"][0] == "FAIL"
        # X: more texture walks than texture dirty tests is impossible
        xb = dict(mid, Tq=0.5)
        ok &= legs_b(xb)["X"][0] == "FAIL"
        # tcpu from a changing thread reads '-', so V fails on share
        void = run("void", lambda t: fake_line(t, tcpu="-"))
        ok &= legs_b(void)["V"][0] == "FAIL"
        # no lines: VOID, never PASS
        none = run("none", lambda t: "09-28 10:00:01.000  1 1 I hakuX: nothing")
        ok &= legs_b(none)["V"][0] == "VOID" and "C1" not in legs_b(none)
        # a truncated line counts as malformed
        ok &= parse_rdc(fake_line(100)[:-20]) is None
        P = legs_pair(good, good)
        ok &= P["F"][0] == "PASS" and P["K2"][0] == "PASS"
    finally:
        shutil.rmtree(tmp)
    print("selftest %s" % ("ok" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
