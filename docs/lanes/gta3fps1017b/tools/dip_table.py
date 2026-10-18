#!/usr/bin/env python3
"""Dip windows against good windows from a release logcat (#1049, #670, #702).

usage: dip_table.py LOGCAT --pid P [--from HH:MM:SS[.mmm]] [--to ...]
                    [--dip FPS] [--good FPS] [--bar FPS]

A pace window is one hakuX-pace line (f=<flips so far> ... ms=<window ms>):
fps = flips in the window * 1000 / ms. Its hakuX-perf "gfps=" line carries
the same timestamp and gives G (mean game frame time, ms), D, S, Df
(deferred flushes), Vpf, Ri (renderer idle, ms) and Tq (texture-dirty
queries). Every line is parsed whole and joined on (pid, timestamp), never
by position. [rdc] (system/physmem.c rdc_tick) prints tcpu, the CPU ms of
the printing thread over its own window of f frames and dt wall ms; tid
names that thread, and it is the one printing hakuX-pace (the flip side of
PGRAPH). From each [rdc] line: tc = tcpu / f, CPU ms per guest frame, and
busy = tcpu / dt in percent; a pace window takes the mean over the [rdc]
lines whose timestamp falls inside its span (end - ms, end], and only lines
whose tid is the pace line's thread ("-" lines are skipped).

Prints the window count, the time-weighted share at or above --bar, the
median and 5th percentile of window fps, the time share under 22, and per
class (dip: fps < --dip; good: fps >= --good) the mean of each field.
"""
import re
import statistics
import sys
from datetime import datetime, timedelta

HEAD = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d\d\d)\s+(\d+)\s+(\d+) \w "
                  r"(\S+?)\s*: (.*)$")
KV = re.compile(r"(\w+)[=:](-?[\d.]+)")
FIELDS = ["G", "D", "S", "Df", "Vpf", "Ri", "Tq", "tc", "busy"]


def ts(s):
    return datetime.strptime("2026-" + s, "%Y-%m-%d %H:%M:%S.%f")


def main():
    a = sys.argv[1:]
    path = a.pop(0)
    pid, t_from, t_to = None, None, None
    dip, good, bar = 26.0, 29.0, 28.5
    while a:
        k = a.pop(0)
        v = a.pop(0)
        if k == "--pid":
            pid = v
        elif k == "--from":
            t_from = v
        elif k == "--to":
            t_to = v
        elif k == "--dip":
            dip = float(v)
        elif k == "--good":
            good = float(v)
        elif k == "--bar":
            bar = float(v)
        else:
            sys.exit(f"unknown argument {k}")
    pace, gfps, rdc = [], {}, []
    pace_tid = None
    for line in open(path, errors="replace"):
        m = HEAD.match(line.rstrip("\n"))
        if not m or (pid and m.group(2) != pid):
            continue
        stamp, tid, tag, msg = m.group(1), m.group(3), m.group(4), m.group(5)
        clock = stamp.split()[1]
        if (t_from and clock < t_from) or (t_to and clock > t_to):
            continue
        if tag == "hakuX-pace" and msg.startswith("f="):
            kv = dict(KV.findall(msg))
            pace.append((stamp, int(kv["f"]), float(kv["ms"])))
            pace_tid = tid
        elif tag == "hakuX-perf" and msg.startswith("gfps="):
            # G:16.9(8.8-327.9): the value before the bracket
            msg = re.sub(r"\([^)]*\)", "", msg)
            gfps[stamp] = {k: float(v) for k, v in KV.findall(msg)}
        elif tag == "hakuX-perf" and msg.startswith("[rdc]"):
            kv = dict(KV.findall(msg))
            if "tcpu" not in kv or int(kv["f"]) <= 0 or int(kv["dt"]) <= 0:
                continue
            rdc.append((ts(stamp), kv["tid"], float(kv["tcpu"]) / int(kv["f"]),
                        100.0 * float(kv["tcpu"]) / int(kv["dt"])))
    wins = []
    prev_f = None
    for stamp, f, ms in pace:
        n = f - prev_f if prev_f is not None and f > prev_f else 60
        prev_f = f
        if ms <= 0:
            continue
        w = {"fps": n * 1000.0 / ms, "ms": ms}
        w.update({k: v for k, v in gfps.get(stamp, {}).items() if k in FIELDS})
        end = ts(stamp)
        start = end - timedelta(milliseconds=ms)
        tc = [(c, b) for t, td, c, b in rdc
              if start < t <= end and td == pace_tid]
        if tc:
            w["tc"] = sum(c for c, _ in tc) / len(tc)
            w["busy"] = sum(b for _, b in tc) / len(tc)
        wins.append(w)
    if not wins:
        sys.exit("no pace windows")
    total = sum(w["ms"] for w in wins)
    fps = sorted(w["fps"] for w in wins)
    at_bar = sum(w["ms"] for w in wins if w["fps"] >= bar) / total
    under22 = sum(w["ms"] for w in wins if w["fps"] < 22) / total
    p5 = fps[max(0, int(0.05 * len(fps)) - 1)] if len(fps) >= 20 else fps[0]
    print(f"windows {len(wins)}  span {total / 1000:.1f} s  "
          f"time >= {bar}: {100 * at_bar:.1f}%  median {statistics.median(fps):.1f}"
          f"  p5 {p5:.1f}  min {fps[0]:.1f}  time < 22: {100 * under22:.1f}%")
    for name, sel in (("dip", lambda w: w["fps"] < dip),
                      ("good", lambda w: w["fps"] >= good)):
        cls = [w for w in wins if sel(w)]
        parts = []
        for k in FIELDS:
            vals = [w[k] for w in cls if k in w]
            parts.append(f"{k} {sum(vals) / len(vals):.1f}" if vals else f"{k} -")
        label = f"< {dip}" if name == "dip" else f">= {good}"
        print(f"{name:4} ({label}, n={len(cls)}): " + "  ".join(parts))


if __name__ == "__main__":
    main()
