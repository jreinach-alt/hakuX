#!/usr/bin/env python3
"""Turn the cumulative hakuX-audio `level` meter into per-interval levels.

  level_windows.py LOGCAT [--from HH:MM:SS] [--to HH:MM:SS]

The meter's acrms is over the whole run so far. Energy is additive, so the
level of the interval between two consecutive lines is

  10*log10((T2*10^(a2/10) - T1*10^(a1/10)) / (T2 - T1))

(ignoring the change in DC, which the meter reports at ~0.4 %FS). Prints one
row per interval per channel: wall clock, interval s, interval acrms dBFS,
and whether the running peak rose during it.
"""
import math
import re
import sys

LINE = re.compile(
    r"^(\d\d-\d\d \d\d:\d\d:\d\d)\.\d+ .*hakuX-audio\(\s*\d+\): level ([LR]): "
    r"([\d.]+) s\s+peak (\d+) .*?acrms (-?[\d.]+|-inf) dBFS")


def main():
    path = sys.argv[1]
    lo = hi = None
    args = sys.argv[2:]
    while args:
        k = args.pop(0)
        if k == "--from":
            lo = args.pop(0)
        elif k == "--to":
            hi = args.pop(0)
    prev = {}
    rows = {}
    with open(path, errors="replace") as f:
        for line in f:
            m = LINE.match(line)
            if not m:
                continue
            ts, ch, t, peak, a = m.groups()
            t = float(t)
            peak = int(peak)
            e = 0.0 if a == "-inf" else t * 10 ** (float(a) / 10)
            if ch in prev:
                pt, pe, ppeak = prev[ch]
                dt = t - pt
                de = e - pe
                lvl = 10 * math.log10(de / dt) if dt > 0 and de > 0 else float("-inf")
                rows.setdefault(ts, {})[ch] = (dt, lvl, peak > ppeak, peak)
            prev[ch] = (t, e, peak)
    print(f"{'clock':14s} {'dt s':>6s} {'L dBFS':>8s} {'R dBFS':>8s}  peak")
    for ts in sorted(rows):
        hhmmss = ts.split()[1]
        if lo and hhmmss < lo:
            continue
        if hi and hhmmss > hi:
            continue
        r = rows[ts]
        if "L" not in r or "R" not in r:
            continue
        dt = r["L"][0]
        rose = "rose to %d" % r["L"][3] if r["L"][2] else ""
        print(f"{ts:14s} {dt:6.2f} {r['L'][1]:8.2f} {r['R'][1]:8.2f}  {rose}")


if __name__ == "__main__":
    main()
