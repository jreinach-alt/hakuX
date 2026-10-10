#!/usr/bin/env python3
"""lane.perdrawon1010: frame time against draws/frame at the race start, per switch state.
Unjudged; a reading aid beside startread.py, which is the registered judge.

    startfit.py RUN [RUN ...] [--window LO,HI] [--at D1,D2,...] [--step N]

Why: startread.py's matched-work number weights three wide bins (<1100, 1100-1400, 1400-1700). Within
one bin the two states can sit at different draws/frame (the fixed-state arms put off at 750 and on at
823 draws/frame in <1100), so the bin difference carries load as well as the switches. Here each state's
rows get a least-squares line, frame_ms = a + b * draws/frame (one point per perflog row, weighted by
its frames: a row is 60 guest frames). That line gives frame ms and fps at fixed draws/frame, e.g. the
owner's 1,374-1,658. The fit is done for all the given runs pooled, then per run, and the per-run spread
is the run-to-run band. The rows are startread.py's own (`start_rows`, the same window and pure-row
rule), loaded from that file, not re-implemented.
"""
import os, sys

here = os.path.dirname(os.path.abspath(__file__))
_sr = os.path.join(here, "startread.py")
S = {"__name__": "startread", "__file__": _sr}
exec(compile(open(_sr).read().rsplit("\nmain()", 1)[0], _sr, "exec"), S)


def fit(pts):
    """weighted least squares of y on x, pts = [(x, y, w)]; (a, b) or None."""
    sw = sum(w for _, _, w in pts)
    if len(pts) < 3 or not sw:
        return None
    mx = sum(x * w for x, _, w in pts) / sw
    my = sum(y * w for _, y, w in pts) / sw
    sxx = sum(w * (x - mx) ** 2 for x, _, w in pts)
    if not sxx:
        return None
    b = sum(w * (x - mx) * (y - my) for x, y, w in pts) / sxx
    return my - b * mx, b


def points(runs, state):
    return [(r["BE"], 1000.0 / r["gfps"], 1.0) for run in runs for _, p, r in run["srows"] if p == state]


def main():
    a = sys.argv[1:]
    dirs, window, at, step = [], S["WINDOW"], (800, 1000, 1300, 1500, 1650), 200
    while a:
        k = a.pop(0)
        if k == "--window":
            window = tuple(float(x) for x in a.pop(0).split(","))
        elif k == "--at":
            at = tuple(int(x) for x in a.pop(0).split(","))
        elif k == "--step":
            step = int(a.pop(0))
        else:
            dirs.append(S["rdir"](k))
    if not dirs:
        sys.exit(__doc__.split("\n\n")[1])
    R = [S["read_run"](d) for d in dirs]
    for r in R:
        S["read_toggle"](r)
        if r["toggle_ms"] == 0:
            S["read_arm"](r)
        r["go"] = S["go_marks"](r)
        r["srows"] = S["start_rows"](r, window)

    print("window mark %+.1f .. %+.1f s, %d runs" % (window[0], window[1], len(R)))
    print("\nrows by %d-draw bin: n, gfps, frame_ms, draws/f" % step)
    lo = min((r["BE"] for run in R for _, _, r in run["srows"]), default=0) // step * step
    hi = max((r["BE"] for run in R for _, _, r in run["srows"]), default=0)
    b = lo
    while b <= hi:
        cells = []
        for st in (0, 1):
            rows = [r for run in R for _, p, r in run["srows"] if p == st and b <= r["BE"] < b + step]
            s = S["summ"](rows)
            cells.append("%3d %5.1f %5.1f %5.0f" % (s["n"], s["gfps"], s["fms"], s["BE"]) if s else "  0" + " " * 18)
        print("  %4d-%-4d  off %s   on %s" % (b, b + step, cells[0], cells[1]))
        b += step

    F = {st: fit(points(R, st)) for st in (0, 1)}
    print("\npooled fit frame_ms = a + b * draws/frame")
    for st in (0, 1):
        f = F[st]
        print("  %-3s %s" % (("off", "on")[st], "a %.1f ms, b %.2f us/draw (n %d)" % (f[0], 1000 * f[1], len(points(R, st)))
                                if f else "too few rows"))
    if F[0] and F[1]:
        print("\n  draws/f   off fps (ms)    on fps (ms)    on-off ms   on-off fps")
        for d in at:
            o, n = F[0][0] + F[0][1] * d, F[1][0] + F[1][1] * d
            print("  %6d   %5.1f (%5.1f)   %5.1f (%5.1f)    %+6.1f      %+5.1f" % (d, 1000 / o, o, 1000 / n, n, n - o,
                                                                               1000 / n - 1000 / o))

    print("\nper run fit, fps at %s draws/frame" % ",".join(map(str, at)))
    for run in R:
        sts = sorted(set(p for _, p, _ in run["srows"]))
        for st in sts:
            f = fit(points([run], st))
            print("  %-40s %-3s %s" % (run["id"][:40], ("off", "on")[st],
                                       " ".join("%5.1f" % (1000 / (f[0] + f[1] * d)) for d in at) if f else "too few rows"))


main()
