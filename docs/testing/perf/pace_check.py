#!/usr/bin/env python3
"""Read the hakuX-pace lines in a logcat and judge them, and summarise a run.

    pace_check.py LOGCAT [--nominal 2] [--judge]

The line (profile.c, one per 60 flips, right after hakuX-perf):

    f=<frame_count> v0= v1= v2= v3= v4= vb=<VBLANKs> max=<ms> ms=<window ms>

vK counts the flips in the window that consumed K VBLANKs (v4 is 4 or more).
Late frames for a title with nominal N VBLANKs per flip are the flips with
K > N.

With --judge, the legs of docs/testing/predictions/perfbase-pace.json are
checked and the exit code is 1 if any fails:

  P1  consecutive lines are exactly 60 frames apart (f % 60 == 0 and no step
      other than 60 between the lines of one process), ignoring the first line
  P2  v0+v1+v2+v3+v4 == 60 on every line
  P3  run mean of vb/60 is within 5% of the run mean of hakuX-perf's Vpf
      (Vpf is an EMA of the same per-flip count, so this checks the window
      and the printing, not an independent measurement)
  P4  THE IMPOSSIBLE ROW: no window has more VBLANKs than its wall time can
      hold, i.e. vb * 16.667 ms <= 1.05 * ms. VBLANKs come from the timer and
      ms from the flip clock, so these are two independent sources
  P5  run mean of the window fps (60 / (ms / 1000)) is within 5% of the run
      mean of hakuX-perf's gfps (the per-second flip counter)

The first line of a process is excluded from every leg: its window starts at
boot, where the first flip interval has no predecessor and the VBLANK delta is
taken from zero.
"""
import argparse
import re
import statistics
import sys

VBLANK_MS = 1000.0 / 60.0

PACE = re.compile(r"hakuX-pace.*?f=(\d+) v0=(\d+) v1=(\d+) v2=(\d+) v3=(\d+) "
                  r"v4=(\d+) vb=(\d+) max=([\d.]+) ms=([\d.]+)")
PERF = re.compile(r"hakuX-perf.*?gfps=(\d+) .*?Vpf:([\d.]+)")


def parse(path):
    pace, perf = [], []
    with open(path, errors="replace") as fh:
        for ln in fh:
            m = PACE.search(ln)
            if m:
                g = m.groups()
                pace.append(dict(f=int(g[0]), v=[int(x) for x in g[1:6]],
                                 vb=int(g[6]), max=float(g[7]),
                                 ms=float(g[8])))
                continue
            m = PERF.search(ln)
            if m:
                perf.append(dict(gfps=int(m.group(1)),
                                 vpf=float(m.group(2))))
    return pace, perf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logcat")
    ap.add_argument("--nominal", type=int, default=2,
                    help="VBLANKs per flip at the title's target (2 = 30 fps)")
    ap.add_argument("--judge", action="store_true")
    a = ap.parse_args()

    pace, perf = parse(a.logcat)
    print("lines     hakuX-pace %d  hakuX-perf %d" % (len(pace), len(perf)))
    if len(pace) < 3:
        print("FAIL      fewer than three hakuX-pace lines: nothing to judge")
        return 1
    # A frame count that goes down is a new process; drop each first line.
    body, steps = [], []
    for i, p in enumerate(pace):
        if i == 0 or p["f"] < pace[i - 1]["f"]:
            continue
        steps.append(p["f"] - pace[i - 1]["f"])
        body.append(p)

    n = len(body)
    late = [sum(p["v"][a.nominal + 1:]) for p in body]
    fps = [60.0 / (p["ms"] / 1000.0) for p in body if p["ms"] > 0]
    print("windows   %d (first line of each process excluded)" % n)
    print("late      %d of %d flips (%.1f%%) above %d VBLANKs; windows with "
          "none late: %d of %d (%.0f%%)"
          % (sum(late), 60 * n, 100.0 * sum(late) / (60 * n), a.nominal,
             sum(1 for x in late if x == 0), n,
             100.0 * sum(1 for x in late if x == 0) / n))
    for k in range(5):
        print("v%d%s       %d" % (k, "+" if k == 4 else " ",
                                 sum(p["v"][k] for p in body)))
    mx = sorted(p["max"] for p in body)
    print("max ms    median %.1f  p90 %.1f  worst %.1f"
          % (statistics.median(mx), mx[int(0.9 * (len(mx) - 1))], mx[-1]))
    print("win fps   median %.1f  min %.1f  max %.1f"
          % (statistics.median(fps), min(fps), max(fps)))
    if not a.judge:
        return 0

    fails = []
    bad = [s for s in steps if s != 60] + [p["f"] for p in body
                                           if p["f"] % 60]
    print("P1 every 60 flips   %s  (%d steps, %d bad)"
          % ("PASS" if not bad else "FAIL", len(steps), len(bad)))
    if bad:
        fails.append("P1")
    bad = [p for p in body if sum(p["v"]) != 60]
    print("P2 counts sum to 60 %s  (%d of %d windows off)"
          % ("PASS" if not bad else "FAIL", len(bad), n))
    if bad:
        fails.append("P2")
    if perf:
        mvb = statistics.mean(p["vb"] / 60.0 for p in body)
        mvpf = statistics.mean(p["vpf"] for p in perf[1:] or perf)
        rel = abs(mvb - mvpf) / mvpf if mvpf else float("inf")
        ok = rel <= 0.05
        print("P3 vb/60 vs Vpf     %s  (%.3f vs %.3f, %.1f%%)"
              % ("PASS" if ok else "FAIL", mvb, mvpf, 100 * rel))
        if not ok:
            fails.append("P3")
        mg = statistics.mean(p["gfps"] for p in perf[1:] or perf)
        mf = statistics.mean(fps)
        rel = abs(mf - mg) / mg if mg else float("inf")
        ok = rel <= 0.05
        print("P5 win fps vs gfps  %s  (%.2f vs %.2f, %.1f%%)"
              % ("PASS" if ok else "FAIL", mf, mg, 100 * rel))
        if not ok:
            fails.append("P5")
    else:
        print("P3/P5               FAIL  (no hakuX-perf lines to compare)")
        fails += ["P3", "P5"]
    bad = [p for p in body if p["vb"] * VBLANK_MS > 1.05 * p["ms"]]
    print("P4 vb fits in ms    %s  (%d of %d windows exceed)"
          % ("PASS" if not bad else "FAIL", len(bad), n))
    if bad:
        fails.append("P4")
    print("verdict   %s" % ("PASS" if not fails else "FAIL " + " ".join(fails)))
    return 1 if fails else 0


def selftest():
    """A passing fixture must pass and each broken leg must fail alone."""
    import os
    import subprocess
    import tempfile

    def log(mutate=None):
        out = []
        for i in range(1, 8):
            out.append("I/hakuX-perf( 1): gfps=30 G:33.3(33.0-34.0) D:16.7"
                       "(16.0-17.0) S:1.0 J:0.1 Df:0 Vd:0.1 Ul:N Vpf:2.05 "
                       "Ri:1.0 Tq:0")
            w = dict(f=60 * i, v=[0, 0, 57, 3, 0], ms=2050.0)
            if mutate:
                mutate(i, w)
            vb = sum(k * c for k, c in enumerate(w["v"]))
            out.append("I/hakuX-pace( 1): f=%d v0=%d v1=%d v2=%d v3=%d v4=%d "
                       "vb=%d max=50.1 ms=%.1f"
                       % ((w["f"],) + tuple(w["v"]) + (vb, w["ms"])))
        return "\n".join(out) + "\n"

    def gap(i, w):
        if i == 4:
            w["f"] = 250

    def short(i, w):
        if i == 4:
            w["v"] = [0, 0, 56, 3, 0]

    def crowded(i, w):
        if i == 4:
            w["ms"] = 1500.0

    def slow(i, w):
        w["ms"] = 2500.0

    cases = [("clean", None, "PASS"), ("gap", gap, "FAIL P1"),
             ("short", short, "FAIL P2"), ("crowded", crowded, "FAIL P4"),
             ("slow", slow, "FAIL P5")]
    bad = 0
    for name, mut, want in cases:
        with tempfile.NamedTemporaryFile("w", suffix=".txt",
                                         delete=False) as fh:
            fh.write(log(mut))
        r = subprocess.run([sys.executable, __file__, fh.name, "--judge"],
                           capture_output=True, text=True)
        os.unlink(fh.name)
        got = [ln for ln in r.stdout.splitlines()
               if ln.startswith("verdict")]
        got = got[0].split(None, 1)[1] if got else "(no verdict)"
        ok = got == want and (r.returncode == 0) == (want == "PASS")
        bad += not ok
        print("%-8s want %-11s got %-11s %s" % (name, want, got,
                                                 "ok" if ok else "WRONG"))
    return 1 if bad else 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    sys.exit(main())
