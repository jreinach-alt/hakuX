#!/usr/bin/env python3
"""The [shd413] windows of a soak logcat, and the stalls among them (#413).

    shdwin.py <result dir | logcat.txt> [--stall-ms 5000] [--warm-ms 3100]
    shdwin.py --selftest

Each [shd413] line (hakuX-perf, pgraph/profile.c) closes a window of 60 flips
and carries the pipeline (p), shader-module (s) and SPIR-V (v) cache hits and
misses with their deltas over that window, and dt_ms, the window's wall time.
A window with dt_ms >= --stall-ms holds a stall; its dpm is the pipelines
created inside it. Prints every window, then per stall: dpm, dsm, the miss
rate against the median non-stall rate (after the first 60 s), and
(dt_ms - warm_ms) / dpm, the ms per missed pipeline once doa413c's warm cost
of the same load is taken out. The route marks are shown where they fall.
"""
import json
import os
import re
import statistics
import sys

TS = re.compile(r"^\d\d-\d\d (\d\d):(\d\d):(\d\d\.\d+) ")
SHD = re.compile(
    r"\[shd413\] f=(\d+) dt_ms=(\d+) ph=(\d+) pm=(\d+) dph=(\d+) dpm=(\d+) "
    r"sh=(\d+) sm=(\d+) dsh=(\d+) dsm=(\d+) vh=(\d+) vm=(\d+) dvh=(\d+) dvm=(\d+) "
    r"L=([YN]) W=(\d+)")
FIELDS = ("f", "dt_ms", "ph", "pm", "dph", "dpm", "sh", "sm", "dsh", "dsm",
          "vh", "vm", "dvh", "dvm")
MARK = re.compile(r"hakuX-route.*: mark (\S+)")


def secs(line):
    m = TS.match(line)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def parse(lines):
    # The stamp has no year and secs() drops the date, so a soak that crosses
    # 00:00 on the device clock would jump back 86400 s; carry a day offset
    # whenever the clock goes backwards by more than half a day.
    wins, marks, bad = [], [], 0
    day, last = 0.0, None
    for line in lines:
        t = secs(line)
        if t is None:
            continue
        if last is not None and t + day < last - 43200:
            day += 86400
        t += day
        last = t
        m = MARK.search(line)
        if m:
            marks.append((t, m.group(1)))
            continue
        if "[shd413]" not in line:
            continue
        m = SHD.search(line)
        if not m:
            bad += 1
            continue
        w = dict(zip(FIELDS, (int(x) for x in m.groups()[:14])))
        w["L"], w["W"], w["t"] = m.group(15), int(m.group(16)), t
        w["hms"] = line[6:18]
        wins.append(w)
    return wins, marks, bad


def analyse(wins, stall_ms, warm_ms):
    out = {"stalls": [], "monotonic": True}
    for a, b in zip(wins, wins[1:]):
        for k in ("ph", "pm", "sh", "sm", "vh", "vm"):
            if b[k] < a[k]:
                out["monotonic"] = False
    if not wins:
        return out
    t0 = wins[0]["t"]
    rates = [w["dpm"] / (w["dt_ms"] / 1000.0) for w in wins
             if 0 < w["dt_ms"] < stall_ms and w["t"] - t0 >= 60]
    base = statistics.median(rates) if rates else 0.0
    out["base_rate"] = base
    for w in wins:
        if w["dt_ms"] < stall_ms:
            continue
        rate = w["dpm"] / (w["dt_ms"] / 1000.0)
        s = dict(w)
        s["rate"] = rate
        s["x_base"] = rate / base if base > 0 else float("inf")
        s["ms_per_pm"] = (w["dt_ms"] - warm_ms) / w["dpm"] if w["dpm"] else None
        s["ms_per_pm_raw"] = w["dt_ms"] / w["dpm"] if w["dpm"] else None
        out["stalls"].append(s)
    return out


def logcat_of(path):
    if os.path.isdir(path):
        rj = os.path.join(path, "result.json")
        if os.path.exists(rj):
            r = json.load(open(rj))
            print("result: shader_cache=%s device=%s apk=%s" % (
                r.get("shader_cache"), r.get("device_label") or r.get("device"),
                r.get("apk_sha") or r.get("ref")))
        return os.path.join(path, "logcat.txt")
    return path


def main():
    if "--selftest" in sys.argv:
        return selftest()
    path = logcat_of(sys.argv[1])
    stall_ms = int(sys.argv[sys.argv.index("--stall-ms") + 1]) if "--stall-ms" in sys.argv else 5000
    warm_ms = int(sys.argv[sys.argv.index("--warm-ms") + 1]) if "--warm-ms" in sys.argv else 3100
    wins, marks, bad = parse(open(path, errors="replace"))
    print("%d [shd413] lines, %d unparsed; marks: %s" % (
        len(wins), bad, ", ".join("%s@%.0fs" % (n, t - wins[0]["t"]) for t, n in marks) if wins else marks))
    mi = 0
    for w in wins:
        while mi < len(marks) and marks[mi][0] <= w["t"]:
            print("   -- mark %s" % marks[mi][1])
            mi += 1
        print("%s f=%6d dt=%6d ms  p %5d/%-5d +%d/+%d  s %4d/%-4d +%d/+%d  v %4d/%-4d +%d/+%d  L=%s W=%d" % (
            w["hms"], w["f"], w["dt_ms"], w["ph"], w["pm"], w["dph"], w["dpm"],
            w["sh"], w["sm"], w["dsh"], w["dsm"], w["vh"], w["vm"], w["dvh"], w["dvm"],
            w["L"], w["W"]))
    a = analyse(wins, stall_ms, warm_ms)
    print("\nmonotonic totals: %s; non-stall median pipeline-miss rate (after 60 s): %.2f /s"
          % (a["monotonic"], a.get("base_rate", 0.0)))
    print("stalls (dt_ms >= %d):" % stall_ms)
    for s in a["stalls"]:
        after = [n for t, n in marks if t <= s["t"]]
        print("  %s dt %6d ms  dpm %4d dsm %4d dvm %4d  rate %.1f/s (%.1fx base)  "
              "ms/pm raw %s, minus warm %s  [after mark %s]" % (
                  s["hms"], s["dt_ms"], s["dpm"], s["dsm"], s["dvm"], s["rate"], s["x_base"],
                  "%.0f" % s["ms_per_pm_raw"] if s["ms_per_pm_raw"] else "-",
                  "%.0f" % s["ms_per_pm"] if s["ms_per_pm"] is not None else "-",
                  after[-1] if after else "none"))


def selftest():
    lines = []

    def L(h, f, dt, pm, dpm, sm=0, dsm=0):
        lines.append("09-28 %s I/hakuX-perf( 1): [shd413] f=%d dt_ms=%d ph=10 pm=%d dph=1 dpm=%d "
                     "sh=5 sm=%d dsh=0 dsm=%d vh=1 vm=2 dvh=0 dvm=0 L=N W=0" % (h, f, dt, pm, dpm, sm, dsm))
    L("05:00:00.000", 60, 0, 5, 5)
    L("05:01:02.000", 120, 1000, 6, 1)
    L("05:01:03.000", 180, 1000, 8, 2)
    lines.append("09-28 05:01:04.000 I/hakuX-route( 2): mark booted")
    L("05:01:17.000", 240, 13000, 108, 100, 40, 40)
    L("05:01:18.000", 300, 1000, 108, 0, 40, 0)
    lines.append("09-28 05:01:19.000 I/hakuX-perf( 1): [shd413] f=garbage")
    wins, marks, bad = parse(lines)
    ok = True

    def check(c, msg):
        nonlocal ok
        print(("ok   " if c else "FAIL ") + msg)
        ok = ok and c
    check(len(wins) == 5 and bad == 1, "5 windows, 1 unparsed line")
    check(marks == [(5 * 3600 + 64.0, "booted")], "the route mark is read")
    a = analyse(wins, 5000, 3100)
    check(a["monotonic"], "totals monotonic")
    check(len(a["stalls"]) == 1 and a["stalls"][0]["dpm"] == 100, "one stall, dpm 100")
    # base = median of [1, 2, 0] per s over non-stall windows after 60 s = 1.0
    check(abs(a["base_rate"] - 1.0) < 1e-9, "base rate is the median, 1.0/s")
    s = a["stalls"][0]
    check(abs(s["ms_per_pm"] - 99.0) < 1e-9, "ms/pm = (13000-3100)/100 = 99")
    check(abs(s["x_base"] - 100 / 13.0) < 1e-9, "stall rate 7.7/s = 7.7x base")
    wins2, _, _ = parse(lines[:3] + [lines[0].replace("pm=5", "pm=1")])
    check(not analyse(wins2, 5000, 3100)["monotonic"], "a decreasing total is caught")
    # The same soak shifted to start at 23:59:00: every window after 00:00
    # keeps its offset from t0, so the base rate and the stall are unchanged
    # and the mark still falls after the first window.
    def shift(line):
        h, m, sec = line[6:18].split(":")
        t = (int(h) * 3600 + int(m) * 60 + float(sec) - 5 * 3600 + 23 * 3600 + 59 * 60) % 86400
        return line[:6] + "%02d:%02d:%06.3f" % (t // 3600, t % 3600 // 60, t % 60) + line[18:]
    wins3, marks3, _ = parse([shift(x) for x in lines])
    check(wins3[1]["hms"].startswith("00:00") and wins3[0]["hms"].startswith("23:59"),
          "the shifted soak crosses midnight")
    a3 = analyse(wins3, 5000, 3100)
    check(abs(a3["base_rate"] - 1.0) < 1e-9 and len(a3["stalls"]) == 1,
          "across midnight: base rate 1.0/s, one stall")
    check(marks3[0][0] - wins3[0]["t"] == 64.0, "across midnight: the mark stays 64 s after t0")
    print("selftest %s" % ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
