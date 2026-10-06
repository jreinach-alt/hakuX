#!/usr/bin/env python3
"""Align the [ide425] window lines with the hakuX-pace hitches in one logcat.

    python3 ide425_windows.py <logcat> [--min-ms 100]

For each pace line whose worst frame is at least --min-ms, print the [ide425]
window that closed from 2.5 s before to 0.5 s after it, with that window's
fields. Then the totals over all windows: how many carry PIO read sectors, and
the median IRQ count and per-sector latency where they do. stdlib only.
"""
import re
import statistics
import sys

STAMP = re.compile(r"^(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d\.\d+)")
FIELD = re.compile(r"(\w+)=(-?\d+)")
PACE = re.compile(r"hakuX-pace.*\bmax=([0-9.]+)")


def secs(line):
    m = STAMP.match(line)
    if not m:
        return None
    _, d, hh, mm, ss = m.groups()
    return ((int(d) * 24 + int(hh)) * 60 + int(mm)) * 60 + float(ss)


def clock(t):
    t = int(t)
    return "%02d:%02d:%02d" % (t // 3600 % 24, t // 60 % 60, t % 60)


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    min_ms = 100.0
    if "--min-ms" in argv:
        min_ms = float(argv[argv.index("--min-ms") + 1])
    lines = open(argv[1], errors="replace").read().splitlines()

    wins = []
    paces = []
    for line in lines:
        t = secs(line)
        if t is None:
            continue
        if "[ide425]" in line:
            f = {k: int(v) for k, v in FIELD.findall(line.split("[ide425]", 1)[1])}
            f["t"] = t
            wins.append(f)
        else:
            m = PACE.search(line)
            if m:
                paces.append((t, float(m.group(1))))

    print("ide425 windows: %d   pace lines: %d" % (len(wins), len(paces)))
    print()
    print("hitch   max_ms  win_s  irq  rd_sec  ends  lat_us/sec(mean,max)  "
          "w_us/word(mean)  wr_w  rest%")
    for t, mx in paces:
        if mx < min_ms:
            continue
        near = [w for w in wins if t - 2.5 <= w["t"] <= t + 0.5]
        if not near:
            print("%s  %6.0f  (no window)" % (clock(t), mx))
            continue
        for w in near:
            win = max(w["win_us"], 1)
            lat_n = w["lat_n"]
            lat_mean = w["lat_us_sum"] / lat_n if lat_n else 0.0
            w_n = w["w"]
            w_mean = w["w_us_sum"] / w_n if w_n else 0.0
            print("%s  %6.0f  %5.1f  %4d  %6d  %4d  %8.0f, %6d  %15.1f  %4d  %5.1f"
                  % (clock(t), mx, win / 1e6, w["irq"], w["rd_sec"], w["ends"],
                     lat_mean, w["lat_us_max"], w_mean, w["wr_w"],
                     100.0 * w["rest_us"] / win))
    print()
    if not wins:
        return
    pio = [w for w in wins if w["rd_sec"] > 0]
    noio = [w for w in wins if w["irq"] >= 100 and w["rd_sec"] == 0]
    print("windows with PIO read sectors: %d of %d" % (len(pio), len(wins)))
    print("windows with >=100 IRQs and no PIO read sectors: %d" % len(noio))
    if pio:
        print("PIO windows: median irq %d, median rd_sec %d, median lat_us/sec "
              "%.0f, median w_us/word %.1f" % (
                  statistics.median(w["irq"] for w in pio),
                  statistics.median(w["rd_sec"] for w in pio),
                  statistics.median(w["lat_us_sum"] / w["lat_n"]
                                    for w in pio if w["lat_n"]),
                  statistics.median(w["w_us_sum"] / w["w"]
                                    for w in pio if w["w"])))
    if wins:
        print("all windows: median irq %d, median ends %d, max lat_us_max %d, "
              "max w_us_max %d" % (
                  statistics.median(w["irq"] for w in wins),
                  statistics.median(w["ends"] for w in wins),
                  max(w["lat_us_max"] for w in wins),
                  max(w["w_us_max"] for w in wins)))


if __name__ == "__main__":
    main(sys.argv)
