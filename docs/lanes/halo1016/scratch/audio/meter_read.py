#!/usr/bin/env python3
"""Read HAKUX_APU_METER=1 lines (meter_plus_norm.diff) from one leg's logcat.

  meter_read.py LOGCAT [--speech 65] [--music 85,86,88] [--skip 2]

Per 5 s window (apumeter w=N), with S = the speech voice's level, M = the
music voices' summed level, B = the 3D sum (3d=), and R = everything but the
speech voice:
    S-M, S-B, S-R  in dB; windows where S is absent are speech-free and are
    counted, not used. Medians over the windows that have S follow.
--skip drops the first N windows (a leg started from a save state plays its
3D voices through all-zero HRIRs until the guest rebinds them: REPORT.md 1.4).

apuhrtf lines: per 3D voice, the median l1, dc and l2 of what the guest bound,
and the LF gain each norm gives: l1 -> 20log(|dc|/l1), raw -> 20log(|dc|),
cap -> raw where l1 < 1 else l1. Left ear / right ear.

The hrtf_norm and apu_meter lines are echoed so the leg's switch is on record.
"""
import math
import re
import statistics
import sys


def db_sum(levels):
    e = sum(10 ** (x / 10.0) for x in levels if x > -199)
    return 10 * math.log10(e) if e > 0 else -200.0


def db_minus(total, part):
    e = 10 ** (total / 10.0) - 10 ** (part / 10.0)
    return 10 * math.log10(e) if e > 1e-20 else -200.0


def main():
    args = sys.argv[1:]
    path = args.pop(0)
    speech, music, skip = 65, [85, 86, 88], 0
    while args:
        k = args.pop(0)
        if k == "--speech":
            speech = int(args.pop(0))
        elif k == "--music":
            music = [int(x) for x in args.pop(0).split(",")]
        elif k == "--skip":
            skip = int(args.pop(0))
    rows, hr, nosp = [], {}, 0
    for line in open(path, errors="replace"):
        if "hrtf_norm:" in line or "apu_meter:" in line:
            print(line.strip())
        m = re.search(r"apumeter w=(\d+) 3d=(\S+) 2d=(\S+) top=(\S*) pause=(\S+)",
                      line)
        if m:
            w = int(m.group(1))
            if w < skip:
                continue
            d3, d2 = float(m.group(2)), float(m.group(3))
            top = {}
            for t in m.group(4).split(","):
                if ":" in t:
                    v, x = t.split(":")
                    top[int(v)] = float(x)
            if speech not in top:
                nosp += 1
                continue
            s = top[speech]
            mus = db_sum([top[v] for v in music if v in top])
            rest = db_minus(db_sum([d3, d2]), s)
            rows.append((w, d3, d2, s, mus, s - mus, s - d3, s - rest,
                         m.group(5)))
            continue
        m = re.search(r"apuhrtf v=(\d+) h=\d+ l1=(\S+)/(\S+) l2=(\S+)/(\S+) "
                      r"dc=(\S+)/(\S+)", line)
        if m:
            v = int(m.group(1))
            hr.setdefault(v, []).append([float(x) for x in m.groups()[1:]])
    print("%4s %6s %6s %6s %6s %6s %6s %6s  %s" % (
        "w", "3d", "2d", "S", "M", "S-M", "S-B", "S-R", "pause"))
    for r in rows:
        print("%4d %6.1f %6.1f %6.1f %6.1f %6.1f %6.1f %6.1f  %s" % r)
    if rows:
        med = [statistics.median(r[i] for r in rows) for i in (5, 6, 7)]
        print("median over %d speech windows: S-M %.1f  S-B %.1f  S-R %.1f "
              "(%d windows without v%d)" % (len(rows), med[0], med[1], med[2],
                                            nosp, speech))
    else:
        print("no window carries v%d (%d windows read)" % (speech, nosp))

    def g(x):
        return 20 * math.log10(abs(x)) if abs(x) > 1e-9 else -200.0

    if hr:
        print("%4s %3s %13s %13s %13s %13s %13s" % (
            "v", "n", "l1 L/R", "dc L/R", "LF@l1 dB", "LF@raw dB", "LF@cap dB"))
    for v in sorted(hr):
        col = list(zip(*hr[v]))
        l1 = [statistics.median(col[0]), statistics.median(col[1])]
        dc = [statistics.median(col[4]), statistics.median(col[5])]
        at_l1 = [g(dc[i] / l1[i]) if l1[i] > 0 else -200.0 for i in (0, 1)]
        at_raw = [g(dc[i]) for i in (0, 1)]
        at_cap = [at_raw[i] if l1[i] < 1 else at_l1[i] for i in (0, 1)]
        print("%4d %3d %6.3f/%6.3f %6.3f/%6.3f %6.1f/%6.1f %6.1f/%6.1f "
              "%6.1f/%6.1f" % (v, len(hr[v]), l1[0], l1[1], dc[0], dc[1],
                               at_l1[0], at_l1[1], at_raw[0], at_raw[1],
                               at_cap[0], at_cap[1]))


main()
