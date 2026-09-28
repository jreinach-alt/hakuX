#!/usr/bin/env python3
"""Flip gaps at DOA Ultimate's compile stalls, one soak at a time (#413).

    asyncwin.py <result dir | logcat.txt> [--json]
    asyncwin.py --selftest

Joins each [shd413] window (hakuX-perf: dt_ms, the wall time of 60 flips, and
the shader-module miss delta dsm) with the hakuX-pace line of the same frame
count (max=, the longest single flip gap in those 60 flips), and locates the
three stalls lane.pipeline413 found on the survey route:

  T  title-screen stage load. sm0 = the running shader-module miss total at
     the last window <= 50 s after the first line; T is the first window whose
     total reaches sm0 + 15. The stall is read over windows T-1 .. T+3, because
     in async mode the miss is counted when the draw is skipped and the wait
     for the pipeline lands in a later frame.
  FL menu -> first fight. From the first window after `mark play` with
     dsm >= 5, up to the steady fight: the first run of 3 windows with dsm 0
     and dt_ms >= 4000.
  H  mid-fight hitch: any window after the steady fight starts with dsm >= 3.

dsm, not dpm, locates them: sm is counted before the async branch in
shaders.c, and pm is not counted on an async enqueue (pipeline413 NOTES s.1).
Per stall it prints the longest flip gap (max of pace max=), frozen_ms (the
sum of the windows' longest gaps that are >= 1 s: a lower bound on the time
the screen stood still), the longest window (max dt_ms) and the span. F is the steady fight's median dt_ms over its
dsm-0 windows, as fps = 60000 / dt.
"""
import json
import os
import re
import statistics
import sys

TS = re.compile(r"^\d\d-\d\d (\d\d):(\d\d):(\d\d\.\d+) ")
SHD = re.compile(r"\[shd413\] f=(\d+) dt_ms=(\d+) .*? dpm=(\d+) sh=\d+ sm=(\d+) dsh=\d+ "
                 r"dsm=(\d+) vh=\d+ vm=\d+ dvh=\d+ dvm=(\d+)")
PACE = re.compile(r"hakuX-pace.*?: f=(\d+) .*max=([\d.]+) ms=([\d.]+)")
MARK = re.compile(r"hakuX-route.*: mark (\S+)")
ASYNC = re.compile(r"async compile: (ON|OFF)")


def secs(line):
    m = TS.match(line)
    if not m:
        return None
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def parse(lines):
    wins, marks, pace, asyncs = [], [], {}, []
    day, last = 0.0, None
    for line in lines:
        t = secs(line)
        if t is None:
            continue
        if last is not None and t + day < last - 43200:
            day += 86400
        t += day
        last = t
        m = ASYNC.search(line)
        if m:
            asyncs.append(m.group(1))
            continue
        m = MARK.search(line)
        if m:
            marks.append((t, m.group(1)))
            continue
        m = PACE.search(line)
        if m:
            pace[int(m.group(1))] = float(m.group(2))
            continue
        m = SHD.search(line)
        if m:
            f, dt, dpm, sm, dsm, dvm = (int(x) for x in m.groups())
            wins.append({"f": f, "dt": dt, "dpm": dpm, "sm": sm, "dsm": dsm,
                         "dvm": dvm, "t": t, "hms": line[6:18]})
    for w in wins:
        w["max"] = pace.get(w["f"])
    return wins, marks, asyncs


def span(wins, i, j):
    ws = wins[i:j + 1]
    gaps = [w["max"] for w in ws if w["max"] is not None]
    return {"from": ws[0]["hms"], "to": ws[-1]["hms"],
            "max_gap_ms": max(gaps) if gaps else None,
            "frozen_ms": round(sum(g for g in gaps if g >= 1000)),
            "max_dt_ms": max(w["dt"] for w in ws),
            "span_s": round(ws[-1]["t"] - ws[0]["t"] + ws[0]["dt"] / 1000.0, 1),
            "dsm": sum(w["dsm"] for w in ws), "dpm": sum(w["dpm"] for w in ws),
            "windows": ["%s dt=%d max=%s dsm=%d dpm=%d" % (
                w["hms"], w["dt"], "%.0f" % w["max"] if w["max"] is not None else "-",
                w["dsm"], w["dpm"]) for w in ws]}


def analyse(wins, marks):
    out = {"T": None, "FL": None, "H": [], "F": None}
    if not wins:
        return out
    t0 = wins[0]["t"]
    early = [w for w in wins if w["t"] - t0 <= 50]
    sm0 = early[-1]["sm"] if early else wins[0]["sm"]
    ti = next((i for i, w in enumerate(wins) if w["t"] - t0 > 50 and w["sm"] >= sm0 + 15), None)
    if ti is not None:
        out["T"] = span(wins, max(ti - 1, 0), min(ti + 3, len(wins) - 1))
        out["T"]["at_s"] = round(wins[ti]["t"] - t0)
    play = next((t for t, n in marks if n == "play"), None)
    if play is None:
        return out
    fi = next((i for i, w in enumerate(wins) if w["t"] > play and w["dsm"] >= 5), None)
    if fi is None:
        return out
    si = None
    for i in range(fi + 1, len(wins) - 2):
        if all(w["dsm"] == 0 and w["dt"] >= 4000 for w in wins[i:i + 3]):
            si = i
            break
    if si is None:
        out["FL"] = span(wins, fi, len(wins) - 1)
        out["FL"]["open"] = True
        return out
    out["FL"] = span(wins, fi, si - 1)
    out["FL"]["at_s"] = round(wins[fi]["t"] - t0)
    for i in range(si, len(wins)):
        if wins[i]["dsm"] >= 3:
            h = span(wins, i, i)
            h["at_s"] = round(wins[i]["t"] - t0)
            out["H"].append(h)
    steady = [w["dt"] for w in wins[si:] if w["dsm"] == 0]
    if steady:
        med = statistics.median(steady)
        out["F"] = {"windows": len(steady), "median_dt_ms": med,
                    "fps": round(60000.0 / med, 2) if med else None,
                    "from": wins[si]["hms"]}
    return out


def load(path):
    res = {}
    if os.path.isdir(path):
        rj = os.path.join(path, "result.json")
        if os.path.exists(rj):
            r = json.load(open(rj))
            res = {"shader_cache": r.get("shader_cache"),
                   "device": r.get("device_label"), "apk": r.get("apk_sha"),
                   "ref": r.get("ref"), "seconds": r.get("seconds")}
        path = os.path.join(path, "logcat.txt")
    return res, path


def main():
    if "--selftest" in sys.argv:
        return selftest()
    res, path = load(sys.argv[1])
    wins, marks, asyncs = parse(open(path, errors="replace"))
    a = analyse(wins, marks)
    a["result"] = res
    a["async_compile"] = asyncs
    a["lines"] = len(wins)
    a["marks"] = ["%s@%.0fs" % (n, t - wins[0]["t"]) for t, n in marks] if wins else []
    if "--json" in sys.argv:
        print(json.dumps(a, indent=1))
        return 0
    print("result: %s" % res)
    print("async compile: %s; %d [shd413] lines; marks %s" % (
        ",".join(asyncs) or "no line", len(wins), " ".join(a["marks"])))
    for k in ("T", "FL"):
        s = a[k]
        if not s:
            print("%-2s not found" % k)
            continue
        print("%-2s at %ss %s..%s  longest flip gap %s ms  longest window %d ms  frozen %d ms  span %.1f s  dsm %d dpm %d%s" % (
            k, s.get("at_s", "?"), s["from"], s["to"], s["max_gap_ms"], s["max_dt_ms"], s["frozen_ms"],
            s["span_s"], s["dsm"], s["dpm"], "  (OPEN: no steady fight)" if s.get("open") else ""))
        for line in s["windows"]:
            print("     " + line)
    for h in a["H"]:
        print("H  at %ss %s  longest flip gap %s ms  window %d ms  dsm %d dpm %d" % (
            h["at_s"], h["from"], h["max_gap_ms"], h["max_dt_ms"], h["dsm"], h["dpm"]))
    if not a["H"]:
        print("H  none")
    print("F  %s" % a["F"])
    return 0


def selftest():
    lines = []

    def W(h, f, dt, sm, dsm, mx, dpm=0):
        lines.append("09-28 %s I/hakuX-pace( 1): f=%d v0=0 v1=60 v2=0 v3=0 v4=0 vb=60 max=%.1f ms=%d.0"
                     % (h, f, mx, dt))
        lines.append("09-28 %s I/hakuX-perf( 1): [shd413] f=%d dt_ms=%d ph=1 pm=1 dph=1 dpm=%d "
                     "sh=1 sm=%d dsh=1 dsm=%d vh=0 vm=1 dvh=0 dvm=0 L=N W=0" % (h, f, dt, dpm, sm, dsm))
    lines.append("09-28 00:59:59.000 I/hakuX   ( 1): async compile: ON")
    W("01:00:00.000", 60, 0, 10, 10, 4000.0)
    W("01:00:40.000", 120, 1000, 12, 2, 20.0)
    W("01:01:10.000", 180, 1000, 20, 8, 900.0)     # t=70: 20 < 12+15
    W("01:01:24.000", 240, 14000, 30, 10, 12000.0)  # T: 30 >= 27
    W("01:01:26.000", 300, 2000, 30, 0, 300.0)
    lines.append("09-28 01:02:00.000 I/hakuX-route( 2): mark play")
    W("01:02:10.000", 360, 2000, 31, 1, 20.0)
    W("01:02:19.000", 420, 9000, 42, 11, 7600.0)    # FL starts
    W("01:02:22.000", 480, 3000, 42, 0, 60.0)
    W("01:02:28.000", 540, 6000, 45, 3, 2200.0)
    W("01:02:33.000", 600, 5300, 45, 0, 100.0)      # steady fight
    W("01:02:38.000", 660, 5300, 45, 0, 100.0)
    W("01:02:43.000", 720, 5400, 45, 0, 100.0)
    W("01:02:58.000", 780, 15000, 53, 8, 4200.0)    # H
    W("01:03:03.000", 840, 5200, 53, 0, 100.0)
    wins, marks, asyncs = parse(lines)
    a = analyse(wins, marks)
    ok = True

    def check(c, msg):
        nonlocal ok
        print(("ok   " if c else "FAIL ") + msg)
        ok = ok and c
    check(asyncs == ["ON"] and len(wins) == 14, "14 windows, async ON read")
    check(all(w["max"] is not None for w in wins), "every window joined to its pace max")
    check(a["T"] and a["T"]["at_s"] == 84 and a["T"]["max_gap_ms"] == 12000.0,
          "T is the window crossing sm0+15 (not the earlier dsm-8 one), gap 12000")
    check(a["T"]["from"] == "01:01:10.000" and a["T"]["to"] == "01:02:19.000",
          "T spans T-1..T+3")
    check(a["FL"] and a["FL"]["from"] == "01:02:19.000" and a["FL"]["to"] == "01:02:28.000",
          "FL runs from the first dsm>=5 after play to the steady fight")
    check(a["FL"]["max_gap_ms"] == 7600.0 and a["FL"]["dsm"] == 14, "FL gap 7600, dsm 14")
    check(a["FL"]["frozen_ms"] == 9800, "FL frozen = 7600 + 2200 (the 60 ms gap is not >= 1 s)")
    check(len(a["H"]) == 1 and a["H"][0]["max_dt_ms"] == 15000, "one hitch, 15000 ms window")
    check(a["F"]["median_dt_ms"] == 5300 and a["F"]["windows"] == 4, "F median 5300 over 4 dsm-0 windows")
    b = analyse(wins[:10], marks)
    check(b["FL"].get("open") and b["F"] is None, "no steady fight: FL open, F absent")
    print("selftest %s" % ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
