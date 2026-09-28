#!/usr/bin/env python3
"""Read what one tlb_reset_dirty() walk scans, and price walking less (#548).

    walk_read.py RUN [RUN...] [--window 90,240]
    walk_read.py --pair A_RUN B_RUN [--window 90,240]
    walk_read.py --selftest

RUN is a soak's result directory or a logcat file. The window is rdc_read.py's
(docs/testing/phase_read_split.py's THE WINDOW).

WHY. [rdc] names the callers; this reads the walk itself. accel/tcg/cputlb.c's
[tlb68] line (tag hakuX, one per 2 s, written by the vCPU thread) carries, for
the walks of its window:
  rd, rdc, rde, rdm, rdh, rdus   on the vCPU thread: walks, of which code
                                 arming, entries scanned, modes scanned,
                                 entries set TLB_NOTDIRTY, us
  rdo, rdoe, rdous               off the vCPU thread: walks, entries, us
  sd                             tlb_set_dirty (a notdirty store re-enabling
                                 its page)
  cpu                            the vCPU thread's CPU ms
  dm, sz                         the modes that can hold a live entry now, and
                                 each one's fast-table size ("5:4096,6:64")
  fx=rdN...                      rd1 when the walk covers only dm's modes
                                 (HAKUX_TCG68_RD), rd0 when it covers all

THE FIGURES, per run:
  entries, modes and us per walk, vCPU and off-vCPU
  live      the entries a walk over dm's modes alone would scan: the sum over
            sz of (table + 8 victim entries), the mean over the lines
  per flip  walks and us, both threads, and sd; flips are hakuX-pace's
            v0..v4 over the window, as pair461_read.py counts them
  share     the vCPU thread's walk us over its CPU ms
  price     on an rd0 run, (1 - live / entries) x us per flip on each thread:
            what walking only dm's modes would save IF a walk's time is
            proportional to the entries it scans. That is the model leg T and
            U of dirtytlb-rd.json test; it is not a measurement.

THE LEGS (--pair, dirtytlb-rd.json; A walks every mode, B only dm's):
  V   each arm has at least 20 [tlb68] and 20 [rdc] lines in the window
  W   every A line reads fx=rd0 and every B line fx=rd1
  E   B's entries per off-vCPU walk are within 15% of B's live entries (live
      is sampled once per line and the tables resize between samples: the two
      rd0 Crimson runs read 4% and 7% apart), and at most 0.6 x A's entries
      per walk
  X   the walks still do the same work: per walk, the entries B's walks
      re-arm are within 15% of A's, for the vertex sync ([rdc] vtx hits over
      calls) and for the vCPU thread (rdh over rd); sd per flip within 15%
  T   us per off-vCPU walk: B at most 0.75 x A
  U   us per vCPU walk: B at most 0.75 x A
  C   render-thread CPU per flip ([rdc] tcpu): B at most A - 1.0 ms
  F   gfps median: B at least A - 1
  K2  hakuX-cpu M median: the larger within 10% of the smaller
K1 (thermal parity) is docs/lanes/remote/pair461_read.py's, and j_per_frame
(leg J) is docs/lanes/dirtytlb/jpf.py's; neither is read here.
"""
import argparse
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing"))
sys.path.insert(0, HERE)
import phase_read_split as prs  # noqa: E402
import rdc_read  # noqa: E402

VTLB = 8   # CPU_VTLB_SIZE, include/hw/core/cpu.h
KEYS = ("dt", "cpu", "rd", "rdc", "rde", "rdm", "rdh", "rdus",
        "rdo", "rdoe", "rdous", "sd")
RE_KEY = {k: re.compile(r"(?<![A-Za-z0-9])%s=(\d+)" % k) for k in KEYS}
RE_SZ = re.compile(r"(?<![A-Za-z0-9])sz=(\S+)")
RE_FX = re.compile(r"(?<![A-Za-z0-9])fx=rd(\d)")
RE_PACE = re.compile(r"f=(\d+) v0=(\d+) v1=(\d+) v2=(\d+) v3=(\d+) v4=(\d+) vb=(\d+)")


def parse_tlb(line):
    d = {}
    for k in KEYS:
        m = RE_KEY[k].search(line)
        if not m:
            return None
        d[k] = int(m.group(1))
    sz, fx = RE_SZ.search(line), RE_FX.search(line)
    if not sz or not fx:
        return None
    d["fx"] = int(fx.group(1))
    live = 0
    if sz.group(1) != "-":
        for part in sz.group(1).split(","):
            idx, _, n = part.partition(":")
            if not idx.isdigit() or not n.isdigit():
                return None
            live += int(n) + VTLB
    d["live"] = live
    return d


def ratio(a, b):
    return a / float(b) if b else None


def read_run(run, window):
    logcat = rdc_read.locate(run)
    lines = open(logcat, errors="replace").read().splitlines()
    win = prs.window_lines(lines, window) if window else lines
    r = {"name": os.path.basename(os.path.dirname(os.path.abspath(logcat)))}
    rows, bad = [], 0
    for l in win:
        if "[tlb68]" not in l:
            continue
        d = parse_tlb(l)
        if d is None:
            bad += 1
        else:
            rows.append(d)
    r["lines"], r["malformed"] = len(rows), bad
    flips = 0
    for l in win:
        m = RE_PACE.search(l) if "hakuX-pace" in l else None
        if m:
            flips += sum(int(x) for x in m.groups()[1:6])
    r["flips"] = flips
    r["fx"] = sorted(set(d["fx"] for d in rows))
    tot = {k: sum(d[k] for d in rows) for k in KEYS}
    r["tot"] = tot
    r["live"] = ratio(sum(d["live"] for d in rows), len(rows))
    r["o_entries"] = ratio(tot["rdoe"], tot["rdo"])
    r["o_us"] = ratio(tot["rdous"], tot["rdo"])
    r["v_entries"] = ratio(tot["rde"], tot["rd"])
    r["v_modes"] = ratio(tot["rdm"], tot["rd"])
    r["v_us"] = ratio(tot["rdus"], tot["rd"])
    r["v_hits"] = ratio(tot["rdh"], tot["rd"])
    r["v_arming"] = ratio(tot["rdc"], tot["rd"])
    r["share"] = ratio(tot["rdus"], tot["cpu"] * 1000.0)
    for k in ("rd", "rdus", "rdo", "rdous", "sd", "cpu"):
        r["pf_" + k] = ratio(tot[k], flips)
    r["rdc"] = rdc_read.read_run(run, window)
    return r


def fmt(x, f="%.1f"):
    return "-" if x is None else f % x


def report(r):
    c = r["rdc"]
    print("%s: %d [tlb68] lines (%d malformed), %d flips, fx rd%s, gfps %s, M %s"
          % (r["name"], r["lines"], r["malformed"], r["flips"],
             ",".join(str(x) for x in r["fx"]) or "?", c["gfps"], c["M"]))
    if not r["lines"]:
        return
    print("  live entries (dm's modes, tables + victims): %s" % fmt(r["live"], "%.0f"))
    print("  %-9s %9s %9s %9s %9s %9s %9s" % ("thread", "walks/fl", "us/flip",
                                             "entries", "us/walk", "hits", "modes"))
    print("  %-9s %9s %9s %9s %9s %9s %9s"
          % ("vCPU", fmt(r["pf_rd"]), fmt(r["pf_rdus"], "%.0f"),
             fmt(r["v_entries"], "%.0f"), fmt(r["v_us"], "%.2f"),
             fmt(r["v_hits"], "%.2f"), fmt(r["v_modes"])))
    print("  %-9s %9s %9s %9s %9s %9s %9s"
          % ("off-vCPU", fmt(r["pf_rdo"]), fmt(r["pf_rdous"], "%.0f"),
             fmt(r["o_entries"], "%.0f"), fmt(r["o_us"], "%.2f"), "-", "-"))
    print("  vCPU: %s of its walks are code arming; walks take %s of its CPU"
          " (%s of %s ms per flip); sd %s per flip"
          % (fmt(100 * r["v_arming"] if r["v_arming"] is not None else None, "%.0f%%"),
             fmt(100 * r["share"] if r["share"] is not None else None, "%.1f%%"),
             fmt(r["pf_rdus"] / 1000.0 if r["pf_rdus"] is not None else None, "%.2f"),
             fmt(r["pf_cpu"], "%.2f"), fmt(r["pf_sd"])))
    if r["fx"] == [0] and r["live"] and r["o_entries"] and r["v_entries"]:
        so = max(0.0, 1 - r["live"] / r["o_entries"])
        sv = max(0.0, 1 - r["live"] / r["v_entries"])
        print("  price, if time is proportional to entries: off-vCPU %.0f%% = %s ms"
              " per flip; vCPU %.0f%% = %s ms per flip"
              % (100 * so, fmt(so * (r["pf_rdous"] or 0) / 1000.0, "%.2f"),
                 100 * sv, fmt(sv * (r["pf_rdus"] or 0) / 1000.0, "%.2f")))


def verdict(ok):
    return "PASS" if ok else "FAIL"


def within(a, b, tol):
    return a is not None and b is not None and b > 0 and abs(a - b) <= tol * b


def vtx_hits(c):
    n, _, _, h = c["site"]["vtx"] if c.get("flips") else (0, 0, 0, 0)
    return ratio(h, n)


def legs(a, b):
    out = {}
    ca, cb = a["rdc"], b["rdc"]
    ok = all(r["lines"] >= 20 and (r["rdc"].get("lines") or 0) >= 20 for r in (a, b))
    if not ok:
        out["V"] = ("VOID", "[tlb68]/[rdc] lines A %s/%s, B %s/%s; 20 of each needed"
                    % (a["lines"], ca.get("lines"), b["lines"], cb.get("lines")))
        return out
    out["V"] = ("PASS", "[tlb68]/[rdc] lines A %d/%d, B %d/%d"
                % (a["lines"], ca["lines"], b["lines"], cb["lines"]))
    sw = a["fx"] == [0] and b["fx"] == [1]
    out["W"] = (verdict(sw), "fx A rd%s, B rd%s" % (a["fx"], b["fx"]))
    if not sw:
        # the arms did not run what they name: nothing below is about the fix
        return out
    out["E"] = (verdict(within(b["o_entries"], b["live"], 0.15)
                        and b["o_entries"] <= 0.6 * a["o_entries"]),
                "entries per off-vCPU walk A %.0f, B %.0f; B live %.0f"
                % (a["o_entries"], b["o_entries"], b["live"]))
    ha, hb = vtx_hits(ca), vtx_hits(cb)
    out["X"] = (verdict(within(hb, ha, 0.15) and within(b["v_hits"], a["v_hits"], 0.15)
                        and within(b["pf_sd"], a["pf_sd"], 0.15)),
                "hits per walk: vtx A %s / B %s, vCPU A %s / B %s; sd per flip A %s / B %s"
                % (fmt(ha, "%.2f"), fmt(hb, "%.2f"), fmt(a["v_hits"], "%.2f"),
                   fmt(b["v_hits"], "%.2f"), fmt(a["pf_sd"]), fmt(b["pf_sd"])))
    out["T"] = (verdict(b["o_us"] <= 0.75 * a["o_us"]),
                "us per off-vCPU walk A %.2f / B %.2f (x%.2f, bar 0.75)"
                % (a["o_us"], b["o_us"], b["o_us"] / a["o_us"]))
    out["U"] = (verdict(b["v_us"] <= 0.75 * a["v_us"]),
                "us per vCPU walk A %.2f / B %.2f (x%.2f, bar 0.75)"
                % (a["v_us"], b["v_us"], b["v_us"] / a["v_us"]))
    if ca["tcpu"] is None or cb["tcpu"] is None:
        out["C"] = ("UNREAD", "no tcpu")
    else:
        out["C"] = (verdict(cb["tcpu"] <= ca["tcpu"] - 1.0),
                    "render-thread CPU per flip A %.2f / B %.2f ms (%+.2f, bar -1.0)"
                    % (ca["tcpu"], cb["tcpu"], cb["tcpu"] - ca["tcpu"]))
    pair = rdc_read.legs_pair(ca, cb)
    out["F"], out["K2"] = pair["F"], pair["K2"]
    return out


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
        for k, (v, why) in sorted(legs(ra, rb).items()):
            print("  %-3s %-6s %s" % (k, v, why))
        return 0
    for run in a.runs:
        report(read_run(run, window))
    return 0


def fake_tlb(t, fx=0, entries=9456, us=24, vus=18, hits=1, sd=29000):
    rd, rdo = 14400, 10500
    return ("09-28 10:%02d:%02d.700  1234  1299 W hakuX   : [tlb68] w=1 dt=2000 cpu=1850 "
            "ff=0 ffe=0 rd=%d rdc=%d rde=%d rdm=%d rdh=%d rdus=%d rdo=%d rdoe=%d "
            "rdous=%d sd=%d dm=0x60 sz=5:4096,6:64 tw=1 tn=4096 rs=0 ka=0 kafb=0 "
            "fx=rd%djc1ka0tb0 rt=0 cb=0 cbb=0"
            % (t // 60, t % 60, rd, rd, rd * entries, rd * (2 if fx else 22),
               rd * hits, rd * vus, rdo, rdo * entries, rdo * us, sd, fx))


def selftest():
    ok = True
    tmp = tempfile.mkdtemp()
    try:
        def run(name, tcpu="1290.0", **kw):
            d = os.path.join(tmp, name)
            os.makedirs(d)
            lines = ["09-28 10:00:00.000  1234  1300 I hakuX-perf: gfps=30 G:33.3"]
            for t in range(100, 230, 5):
                at = "09-28 10:%02d:%02d" % (t // 60, t % 60)
                lines.append("%s.000  1234  1300 I hakuX-perf: gfps=30 G:33.3 Tq:80" % at)
                lines.append("%s.200  1234  1300 I hakuX-pace: f=%d v0=0 v1=0 v2=60 v3=0 v4=0"
                             " vb=120 max=40.0 ms=2000.0" % (at, t * 12))
                lines.append("%s.500  1234  1301 I hakuX-cpu( 1): M:20000" % at)
                lines.append(rdc_read.fake_line(t, tcpu=tcpu))
                lines.append(fake_tlb(t, **kw))
            open(os.path.join(d, "logcat.txt"), "w").write("\n".join(lines) + "\n")
            return read_run(d, (90, 240))

        a = run("a")
        ok &= a["lines"] == 26 and a["flips"] == 26 * 60 and a["fx"] == [0]
        ok &= a["live"] == 4096 + 64 + 2 * VTLB
        ok &= abs(a["o_entries"] - 9456) < 1e-9 and abs(a["v_modes"] - 22) < 1e-9
        ok &= abs(a["pf_rdo"] - 175) < 1e-9 and abs(a["o_us"] - 24) < 1e-9
        b = run("b", tcpu="1200.0", fx=1, entries=4176, us=11, vus=8)
        L = legs(a, b)
        for k in ("V", "W", "E", "X", "T", "U", "C", "F", "K2"):
            if L[k][0] != "PASS":
                print("FAIL selftest: good pair leg %s %s" % (k, L[k]))
                ok = False
        # the switch did not take: W fails and no leg about the fix is read
        same = legs(a, run("same"))
        ok &= same["W"][0] == "FAIL" and "T" not in same
        # rd1 but the walk still scans every mode's table: E fails
        ok &= legs(a, run("wide", tcpu="1200.0", fx=1, us=11, vus=8))["E"][0] == "FAIL"
        # the walk got faster by skipping live entries: hits drop, X fails
        skip = legs(a, run("skip", tcpu="1200.0", fx=1, entries=4176, us=11, vus=8,
                           hits=0))
        ok &= skip["X"][0] == "FAIL" and skip["T"][0] == "PASS"
        # fewer entries, same time per walk: the model is wrong, T and U fail
        flat = legs(a, run("flat", tcpu="1200.0", fx=1, entries=4176))
        ok &= flat["T"][0] == "FAIL" and flat["U"][0] == "FAIL" and flat["E"][0] == "PASS"
        # the walks got cheaper and the render thread's CPU did not move
        ok &= legs(a, run("nocpu", fx=1, entries=4176, us=11, vus=8))["C"][0] == "FAIL"
        # no [tlb68] line: VOID, never a verdict
        d = os.path.join(tmp, "none")
        os.makedirs(d)
        open(os.path.join(d, "logcat.txt"), "w").write(
            "09-28 10:00:00.000  1234  1300 I hakuX-perf: gfps=30 G:33.3\n")
        none = legs(a, read_run(d, (90, 240)))
        ok &= none["V"][0] == "VOID" and "W" not in none
        # a truncated line is malformed, not a row of zeros
        ok &= parse_tlb(fake_tlb(100)[:-40]) is None
    finally:
        shutil.rmtree(tmp)
    print("selftest %s" % ("ok" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
