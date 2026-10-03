#!/usr/bin/env python3
"""F0a, the offline half: the event rates fastmem would pay for, per title,
from the [tlb68] (and [mf0]) lines a soak already printed (#507, lane.memfast).

    f0a_rates.py <result dir | logcat.txt> [--from HH:MM:SS] [--to HH:MM:SS] ...

The span defaults to the route's last `mark gameplay` or `mark play` (route.txt
or soak.log in the result dir) through the last line; with no mark it is the
whole run, and the output says so. Per run, per second of wall time:

  ff        full flushes, and their split by cause (cr3n new CR3 value, cr3s the
            same value reloaded, cr0, cr4, a20, fo other; fo holds the
            watch-insert flushes)
  watch     NV2A surface-watch inserts ([watch311] inserts=, a running total),
            to read against fo
  pf        INVLPG page flushes
  rd / rdo  tlb_reset_dirty calls on the vCPU thread / on any other thread
  rdh       entries a vCPU-thread call flagged TLB_NOTDIRTY (pages downgraded)
  sd        tlb_set_dirty: a notdirty store re-enabled a page. Under fastmem
            with stores (F2) each one is a protection fault plus an mprotect
  inst      TLB installs inside the census windows ([mf0] li+ln+lo+vi+vn+vo);
            absent on a build without the census

and the budget: with the inline compare at --compare percent of the vCPU
thread and the kill line at a third of it, the microseconds each sd event may
cost before sd alone reaches the kill line.

A run with no [tlb68] line is VOID. Rates are over wall time, so a run that
idles reads low; `cpu` is the vCPU thread's share of the wall, printed beside.
Offline; reads files only.
"""
import argparse
import os
import re

KV = re.compile(r"(\w+)=(-?\d+)\b")
CAUSES = ("cr3n", "cr3s", "cr0", "cr4", "a20", "fo")


def clock(line):
    m = re.match(r"\d\d-\d\d (\d\d:\d\d:\d\d)", line)
    return m.group(1) if m else None


def mark(run):
    """The route's last `mark gameplay|play` clock time, or None."""
    if not os.path.isdir(run):
        return None
    t = None
    for name in ("run.log", "soak.log", "route.txt"):
        p = os.path.join(run, name)
        if not os.path.isfile(p):
            continue
        with open(p, errors="replace") as f:
            for ln in f:
                m = re.search(r"(\d\d:\d\d:\d\d)\.\d+ mark (gameplay|play)\b", ln)
                if m:
                    t = m.group(1)
        if t:
            return t
    return None


def read(path, t_from, t_to):
    if os.path.isdir(path):
        path = os.path.join(path, "logcat.txt")
    tlb, mf0, watch = [], [], []
    with open(path, errors="replace") as f:
        for ln in f:
            for tag, rows in (("[tlb68] w=", tlb), ("[mf0] w=", mf0),
                              ("[watch311] live=", watch)):
                i = ln.find(tag)
                if i < 0:
                    continue
                t = clock(ln)
                if t is None or (t_from and t < t_from) or (t_to and t > t_to):
                    continue
                row = {k: int(v) for k, v in KV.findall(ln[i:])}
                row["_t"] = t
                rows.append(row)
    return path, tlb, mf0, watch


def secs(t):
    h, m, s = (int(x) for x in t.split(":"))
    return 3600 * h + 60 * m + s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--from", dest="t_from")
    ap.add_argument("--to", dest="t_to")
    ap.add_argument("--compare", type=float, default=17.4,
                    help="the inline compare's share of the vCPU thread, percent")
    a = ap.parse_args()
    for run in a.runs:
        t_from = a.t_from or mark(run)
        path, tlb, mf0, watch = read(run, t_from, a.t_to)
        print("== %s" % path)
        print("  span: from %s to %s"
              % (t_from or "the first line", a.t_to or "the last line")
              + ("" if a.t_from or not t_from else " (the route's mark)")
              + ("" if t_from else "; NO MARK, so boot and menus are in the rates"))
        if not tlb:
            print("  VOID: no [tlb68] line in the span")
            continue
        wall = sum(r["dt"] for r in tlb) / 1e3

        def rate(k, rows=tlb, w=wall):
            return sum(r.get(k, 0) for r in rows) / w

        print("  windows=%d wall=%.1fs vCPU cpu=%.1f%% of wall"
              % (len(tlb), wall, 100 * rate("cpu") / 1e3))
        ff = rate("ff")
        print("  ff=%.1f/s  by cause: %s"
              % (ff, "  ".join("%s=%.1f" % (c, rate(c)) for c in CAUSES)))
        if ff:
            print("     share: %s"
                  % "  ".join("%s=%.0f%%" % (c, 100 * rate(c) / ff) for c in CAUSES))
        if len(watch) >= 2:
            ws = (secs(watch[-1]["_t"]) - secs(watch[0]["_t"])) % 86400
            wi = (watch[-1]["inserts"] - watch[0]["inserts"]) / ws if ws else 0.0
            print("  watch inserts=%.1f/s over %d s (each insert and each remove is "
                  "one `fo` flush); live %d..%d"
                  % (wi, ws, min(r["live"] for r in watch), max(r["live"] for r in watch)))
        else:
            print("  watch inserts: fewer than two [watch311] lines in the span")
        print("  pf=%.1f/s  rd=%.1f/s  rdh=%.1f/s  rdo=%.1f/s  sd=%.1f/s"
              % (rate("pf"), rate("rd"), rate("rdh"), rate("rdo"), rate("sd")))
        if mf0:
            mw = sum(r["dt"] for r in mf0) / 1e3
            inst = sum(rate(k, mf0, mw) for k in ("li", "ln", "lo", "vi", "vn", "vo"))
            print("  inst=%.0f/s (census windows only)  per full flush=%.0f"
                  % (inst, inst / ff if ff else 0))
        else:
            print("  inst: no [mf0] line (a build without the census)")
        kill_ms = 10.0 * a.compare / 3.0 * rate("cpu") / 1e3
        sd = rate("sd")
        print("  kill line %.1f ms per wall second (a third of %.1f%% of the vCPU's %.0f ms)"
              % (kill_ms, a.compare, rate("cpu")))
        if sd:
            print("  sd alone reaches it at %.1f us per event" % (1e3 * kill_ms / sd))


if __name__ == "__main__":
    main()
