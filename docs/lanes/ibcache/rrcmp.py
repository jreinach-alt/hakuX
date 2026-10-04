#!/usr/bin/env python3
"""[rr425] and [rr425w] of two capture sessions, side by side (#507, lane.ibcache).

    rrcmp.py <session A> <session B> [--last 40]

Over the last N windows of each logcat.txt (the profile window sits at the
end of the s4 route): the loop's dispatch and return counters per second, and
the guest's idle share (the idle thread's HLT time, [rr425w] idle_us against
busy_us). A vCPU saving on a frame-capped title shows up as guest idle, not as
frames. Offline; reads files only.
"""
import argparse
import os
import re


def series(path, tag):
    out = []
    for line in open(path, errors="replace"):
        if tag in line:
            out.append({k: int(v)
                        for k, v in re.findall(r"(\w+)=(\d+)", line)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--last", type=int, default=40)
    a = ap.parse_args()
    rate, idle = [], []
    for d in (a.a, a.b):
        p = os.path.join(d, "logcat.txt")
        rr = series(p, "[rr425] ")[-a.last:]
        dt = sum(x["dt"] for x in rr) / 1000.0
        rate.append({k: sum(x.get(k, 0) for x in rr) / dt for k in rr[0]})
        w = series(p, "[rr425w] ")[-a.last:]
        i = sum(x["idle_us"] for x in w)
        b = sum(x["busy_us"] for x in w)
        idle.append((i, b, sum(1 for x in w if x["idle_us"]), len(w)))
    na = os.path.basename(os.path.normpath(a.a))
    nb = os.path.basename(os.path.normpath(a.b))
    print("last %d windows; A %s, B %s" % (a.last, na, nb))
    print("[rr425], per second of wall time")
    print("  %-6s %12s %12s %8s" % ("field", "A", "B", "B/A"))
    for k in ("it", "e", "m", "r", "g", "x", "hc", "hm", "ip", "iq"):
        x, y = rate[0][k], rate[1][k]
        print("  %-6s %12.0f %12.0f %8s"
              % (k, x, y, "%.3f" % (y / x) if x else "-"))
    print("[rr425w] guest idle")
    for n, (i, b, nz, tot) in zip("AB", idle):
        print("  %s idle %.2f s of %.2f s (%.2f%%), %d of %d windows with "
              "any idle" % (n, i / 1e6, (i + b) / 1e6,
                            100.0 * i / (i + b) if i + b else 0, nz, tot))


if __name__ == "__main__":
    main()
