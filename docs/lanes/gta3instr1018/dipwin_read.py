#!/usr/bin/env python3
"""Read the perflog [dipwin] lines (hakuX-rpbrk, vk/draw.c) out of a logcat.

    dipwin_read.py LOGCAT [--from HH:MM:SS] [--to HH:MM:SS] [--max-pipe MS]

Times are the logcat's own clock (the device's). Each [dipwin] line is one
window of `fl` flips (60) on the PFIFO thread, `s` seconds long. The reader
prints:

  1. one row per window: flip interval, render passes and ends per flip, the
     share of ends the break counters attribute, and the larger timers in ms
     per flip;
  2. over the selected windows (sums, then divided by their flips): the break
     reasons per flip, every timer in calls and ms per flip, the finishes by
     reason, and the non-draw callers by library offset.

--max-pipe drops windows whose full-path pipeline time is above MS per flip,
which is how a cold pipeline compile shows in this line (the compile runs
inside `pipe`). The dropped windows are listed, not hidden.
"""
import argparse
import re
import sys
from collections import OrderedDict

BREAKS = ["bfbd", "bpd", "bqry", "bclr", "bclre", "bnd", "bsnb", "bsbd", "bsmd"]
LINE = re.compile(r"^(\d\d-\d\d) (\d\d:\d\d:\d\d\.\d+) .*\[dipwin\] (.*)$")


def parse(rest):
    w = OrderedDict()
    for tok in rest.split():
        if "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        if v == "-":
            v = ""
        if k in ("bfin", "nd"):
            d = OrderedDict()
            for part in filter(None, v.split(",")):
                name, n = part.rsplit(":", 1)
                d[name] = int(n)
            w[k] = d
        elif k == "fin":
            d = OrderedDict()
            for part in filter(None, v.split(",")):
                name, nm = part.split(":", 1)
                n, ms = nm.split("/")
                d[name] = (int(n), float(ms))
            w[k] = d
        elif "/" in v:
            n, ms = v.split("/")
            w[k] = (int(n), float(ms))
        elif "." in v:
            w[k] = float(v)
        else:
            w[k] = int(v)
    return w


def timers(w):
    return [k for k, v in w.items() if isinstance(v, tuple)]


def attributed(w):
    return sum(w.get("bfin", {}).values()) + sum(w.get(b, 0) for b in BREAKS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logcat")
    ap.add_argument("--from", dest="t0")
    ap.add_argument("--to", dest="t1")
    ap.add_argument("--max-pipe", type=float)
    a = ap.parse_args()

    wins = []
    for line in open(a.logcat, errors="replace"):
        m = LINE.match(line.rstrip("\n"))
        if not m:
            continue
        t = m.group(2)
        if a.t0 and t[:8] < a.t0:
            continue
        if a.t1 and t[:8] > a.t1:
            continue
        w = parse(m.group(3))
        w["_t"] = t
        wins.append(w)
    if not wins:
        sys.exit("no [dipwin] lines in the range")

    # Running totals only grow: a window whose cfl/crp/cbrk goes backwards
    # means a counter was lost or a second emitter ran.
    mono = all(b["cfl"] - a_["cfl"] == b["fl"] and b["crp"] >= a_["crp"] and
               b["cbrk"] >= a_["cbrk"] for a_, b in zip(wins, wins[1:])
               if b["tid"] == a_["tid"])
    tids = sorted({w["tid"] for w in wins})

    big = ["pipe", "bind", "key", "descf", "vsync", "vcopy", "sub", "fen", "stale", "dl", "fall"]
    print("windows %d (%s .. %s)  tids %s  running totals monotonic and flip-contiguous: %s" %
          (len(wins), wins[0]["_t"], wins[-1]["_t"], tids, "yes" if mono else "NO"))
    print()
    print("| time | ms/flip | rp/flip | attributed | " + " | ".join(big) + " | full/flip | staleMB/flip |")
    print("|---|" + "---|" * (len(big) + 5))
    keep, dropped = [], []
    for w in wins:
        fl = w["fl"]
        pipe = w["pipe"][1] / fl
        row = ["%s" % w["_t"][:8], "%.1f" % (1000 * w["s"] / fl), "%.1f" % (w["rp"] / fl),
               "%d/%d" % (attributed(w), w["brk"])]
        row += ["%.2f" % (w[k][1] / fl) if k in w else "-" for k in big]
        row += ["%.0f" % (w["full"] / fl), "%.1f" % (w["staleK"] / 1024 / fl)]
        cold = a.max_pipe is not None and pipe > a.max_pipe
        (dropped if cold else keep).append(w)
        print("| " + " | ".join(row) + (" | (dropped: pipe)" if cold else " |"))
    print()
    if dropped:
        print("dropped by --max-pipe %.1f: %s" % (a.max_pipe, ", ".join(w["_t"][:8] for w in dropped)))
        print()
    if not keep:
        sys.exit("every window dropped")

    fl = sum(w["fl"] for w in keep)
    s = sum(w["s"] for w in keep)
    print("selected: %d windows, %d flips, %.1f s, %.2f ms/flip (%.1f fps)" %
          (len(keep), fl, s, 1000 * s / fl, fl / s))
    rp = sum(w["rp"] for w in keep)
    brk = sum(w["brk"] for w in keep)
    print("render passes %.2f/flip, ends %.2f/flip" % (rp / fl, brk / fl))
    print()
    print("| end reason | per flip |")
    print("|---|---|")
    bfin = OrderedDict()
    for w in keep:
        for k, n in w.get("bfin", {}).items():
            bfin[k] = bfin.get(k, 0) + n
    for k, n in bfin.items():
        print("| finish (%s) | %.2f |" % (k, n / fl))
    for b in BREAKS:
        n = sum(w.get(b, 0) for w in keep)
        if n:
            print("| %s | %.2f |" % (b, n / fl))
    print("| unattributed | %.2f |" % ((brk - sum(attributed(w) for w in keep)) / fl))
    print()
    print("| timer | calls/flip | ms/flip |")
    print("|---|---|---|")
    for k in timers(keep[0]):
        n = sum(w[k][0] for w in keep)
        ms = sum(w[k][1] for w in keep)
        print("| %s | %.1f | %.2f |" % (k, n / fl, ms / fl))
    for k in ("full", "ubo"):
        print("| (%s count) | %.1f | |" % (k, sum(w[k] for w in keep) / fl))
    print("| (vcopy KB) | %.1f | |" % (sum(w["vcopyK"] for w in keep) / fl))
    print("| (stale KB) | %.1f | |" % (sum(w["staleK"] for w in keep) / fl))
    print()
    print("| finish | calls/flip | ms/flip |")
    print("|---|---|---|")
    fin = OrderedDict()
    for w in keep:
        for k, (n, ms) in w.get("fin", {}).items():
            c = fin.get(k, (0, 0.0))
            fin[k] = (c[0] + n, c[1] + ms)
    for k, (n, ms) in fin.items():
        print("| %s | %.2f | %.2f |" % (k, n / fl, ms / fl))
    print()
    nd = OrderedDict()
    for w in keep:
        for k, n in w.get("nd", {}).items():
            nd[k] = nd.get(k, 0) + n
    print("non-draw callers per flip: " + ", ".join("%s %.2f" % (k, n / fl) for k, n in
                                                   sorted(nd.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
