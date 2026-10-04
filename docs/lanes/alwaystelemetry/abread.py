#!/usr/bin/env python3
"""Read the alwaystelemetry perflog-overhead A/B pair (#433).

usage: abread.py <plain result dir> <perflog result dir>

Both arms run the same returning route, then a `repeat forever` walk loop
timed on the wall clock, so the guest's path after the mark diverges between
arms and a later scene is not the same scene. The read therefore uses three
windows, all offsets from `mark gameplay` in run.log:

  same    +30..+180 s, both arms on the same walk before either reaches new
          content (no dpm after +30 in either arm before +187)
  steady  every gameplay second whose [shd413] window compiled nothing
          (dpm=0), the whole run
  all     every gameplay second

Headroom, not fps, is the measure: Castlevania sits at the 60 fps vsync cap,
so an fps tie only bounds the cost. The headroom readers present in BOTH
builds are:
  tcpu      [rdc] render-thread CPU ms per ~1 s window (CLOCK_THREAD_CPUTIME_ID)
  Ri        gfps line, renderer idle ms per flip
  run%      [idlehalt] vCPU run_us / span_us
  idle_us   [rr425w] guest idle-loop us per 2 s window
"""
import datetime
import json
import os
import re
import statistics
import sys

TS = re.compile(r"^(\d\d-\d\d) (\d\d:\d\d:\d\d\.\d+) ")


def stamp(line):
    m = TS.match(line)
    if not m:
        return None
    return datetime.datetime.strptime("2026-" + m.group(1) + " " + m.group(2),
                                      "%Y-%m-%d %H:%M:%S.%f")


def mark_time(run_log, day):
    for line in open(run_log, errors="replace"):
        m = re.match(r"ROUTE (\d\d:\d\d:\d\d\.\d+) mark gameplay", line)
        if m:
            return datetime.datetime.strptime(day + " " + m.group(1),
                                              "%Y-%m-%d %H:%M:%S.%f")
    raise SystemExit("no mark gameplay in " + run_log)


def read(d):
    lc = os.path.join(d, "logcat.txt")
    first = next(l for l in open(lc, errors="replace") if TS.match(l))
    mark = mark_time(os.path.join(d, "run.log"),
                     stamp(first).strftime("%Y-%m-%d"))
    rows = []      # (off, key, value)
    compile_s = []  # offsets of [shd413] windows with dpm > 0
    for line in open(lc, errors="replace"):
        t = stamp(line)
        if t is None:
            continue
        off = (t - mark).total_seconds()
        if off < 0:
            continue
        if "[rdc] f=" in line:
            m = re.search(r"tcpu=([\d.]+)", line)
            dt = re.search(r" dt=(\d+)", line)
            if m and dt and int(dt.group(1)) > 0:
                rows.append((off, "tcpu_ms_per_s",
                             float(m.group(1)) * 1000.0 / int(dt.group(1))))
        elif "hakuX-perf" in line and "gfps=" in line:
            m = re.search(r"gfps=(\d+) .*?Ri:([\d.]+)", line)
            if m:
                rows.append((off, "gfps", int(m.group(1))))
                rows.append((off, "Ri_ms", float(m.group(2))))
        elif "[idlehalt] w=" in line:
            m = re.search(r"span_us=(\d+) run_us=(\d+)", line)
            if m and int(m.group(1)) > 0:
                rows.append((off, "vcpu_run_pct",
                             100.0 * int(m.group(2)) / int(m.group(1))))
        elif "[rr425w] w=" in line:
            m = re.search(r"idle_us=(\d+) busy_us=(\d+)", line)
            if m:
                tot = int(m.group(1)) + int(m.group(2))
                if tot:
                    rows.append((off, "guest_idle_pct",
                                 100.0 * int(m.group(1)) / tot))
        elif "hakuX-pace" in line:
            m = re.search(r"max=([\d.]+)", line)
            if m:
                rows.append((off, "pace_max_ms", float(m.group(1))))
        if "[shd413]" in line:
            m = re.search(r"dpm=(\d+)", line)
            if m and int(m.group(1)) > 0:
                compile_s.append(off)
    v = json.load(open(os.path.join(d, "verdict.json")))
    return rows, compile_s, v


def near(off, marks, pad=3.0):
    return any(abs(off - c) <= pad for c in marks)


def summarise(rows, compile_s, lo, hi, steady):
    out = {}
    for key in ("gfps", "Ri_ms", "tcpu_ms_per_s", "vcpu_run_pct",
                "guest_idle_pct", "pace_max_ms"):
        xs = [x for off, k, x in rows if k == key and lo <= off < hi
              and not (steady and near(off, compile_s))]
        if xs:
            out[key] = (len(xs), statistics.median(xs), statistics.mean(xs))
    return out


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    arms = [("plain", sys.argv[1]), ("perflog", sys.argv[2])]
    data = {name: read(d) for name, d in arms}
    windows = [("same +30..+180 s", 30, 180, False),
               ("steady (no compile within 3 s)", 30, 1e9, True),
               ("all gameplay", 0, 1e9, False)]
    for title, lo, hi, steady in windows:
        print("== %s" % title)
        s = {n: summarise(*data[n][:2], lo, hi, steady) for n, _ in arms}
        print("%-16s %22s %22s %9s" % ("", "plain n/med/mean",
                                        "perflog n/med/mean", "d(mean)"))
        for key in s["plain"]:
            a = s["plain"][key]
            b = s["perflog"].get(key)
            if not b:
                continue
            print("%-16s %5d %7.2f %7.2f   %5d %7.2f %7.2f %+9.2f"
                  % (key, a[0], a[1], a[2], b[0], b[1], b[2], b[2] - a[2]))
        print()
    print("== compile windows after the mark (offset s)")
    for n, _ in arms:
        print("%-8s %s" % (n, [round(c) for c in data[n][1]]))
    print()
    print("== verdict")
    for key in ("fps_ok_share", "fps_window_median",
                "g_fps_mean_reported_not_judged", "gameplay_s", "pass",
                "failing"):
        print("%-32s %-14s %s" % (key, data["plain"][2].get(key),
                                  data["perflog"][2].get(key)))
    for key in ("net_w", "j_per_frame", "flips"):
        print("%-32s %-14s %s" % ("power." + key,
                                  data["plain"][2]["power"].get(key),
                                  data["perflog"][2]["power"].get(key)))


if __name__ == "__main__":
    main()
