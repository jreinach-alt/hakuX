#!/usr/bin/env python3
"""Read the HAKUX_APU_MIXLOG lines of a run: which voices MON_VP under-plays.

  mixlog_read.py LOGCAT [--min-frames 750]

LOGCAT is a run's logcat text (any file holding the "apumix" lines). For each
5 s window, prints every voice active for at least --min-frames APU frames
(750 = 0.5 s) with its speaker-bin slots, the gain MON_VP gives it today (the
largest slot gain, dB), and the per-side gains HAKUX_APU_MONVP_DOWNMIX gives
it (dB, and the excess over today's gain). An excess of 0 means the switch
leaves the voice alone; several dB means the voice is spread over several
speaker bins and today's mix under-plays it relative to single-bin voices.

The weights below are vp.c's monvp_downmix table (vp.c.patch); keep the two
the same.
"""
import math
import re
import sys

WEIGHTS = {0: (1, 0), 1: (0, 1), 2: (.70711, .70711), 3: (0, 0),
           4: (.70711, 0), 5: (0, .70711), 6: (1, 0), 7: (0, 1),
           8: (.70711, 0), 9: (0, .70711)}
NAMES = {0: "FL", 1: "FR", 2: "C", 3: "LFE", 4: "BL", 5: "BR", 6: "xFL",
         7: "xFR", 8: "xBL", 9: "xBR", 10: "I3DL2"}
LINE = re.compile(r"apumix w=(\d+) v=(\d+) n=(\d+) st=(\d) mp=(\d) bins=(\S+)")


def gain(vol):
    return 0.0 if vol >= 4095 else 10 ** (-vol / 64 / 20)


def db(g):
    return 20 * math.log10(g) if g > 0 else float("-inf")


def main():
    path = sys.argv[1]
    min_frames = 750
    if "--min-frames" in sys.argv:
        min_frames = int(sys.argv[sys.argv.index("--min-frames") + 1])
    print("w   v    n     st  slots (bin:dB)                                   "
          "max_dB  L_dB   R_dB   excess L/R")
    for line in open(path, errors="replace"):
        m = LINE.search(line)
        if not m:
            continue
        w, v, n, st, mp = (int(x) for x in m.groups()[:5])
        if n < min_frames:
            continue
        slots = [tuple(int(x) for x in s.split(":"))
                 for s in m.group(6).split(",")]
        gmax = max(gain(vol) for _, vol in slots)
        gl = sum(gain(vol) * WEIGHTS[b][0] for b, vol in slots if b in WEIGHTS)
        gr = sum(gain(vol) * WEIGHTS[b][1] for b, vol in slots if b in WEIGHTS)
        if gl == 0 and gr == 0:
            gl = gr = gmax
        desc = " ".join(f"{NAMES.get(b, b)}:{-vol / 64:.1f}"
                        for b, vol in slots if vol < 4095)
        print(f"{w:<3d} {v:<4d} {n:<5d} {st:<3d} {desc:48s} {db(gmax):6.1f} "
              f"{db(gl):6.1f} {db(gr):6.1f}  "
              f"{db(gl) - db(gmax):+5.1f} / {db(gr) - db(gmax):+5.1f}"
              + ("  mp" if mp else ""))


if __name__ == "__main__":
    main()
