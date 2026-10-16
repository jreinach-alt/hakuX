#!/usr/bin/env python3
"""Per-window level of an s16le PCM file.

  pcm_windows.py PCM [--rate 48000] [--channels 2] [--win 1.0] [--to SECONDS]

Prints window start (s), AC RMS dBFS and peak dBFS per channel.
"""
import math
import sys

import numpy as np


def db(x):
    return 20 * math.log10(x / 32768.0) if x > 0 else float("-inf")


def main():
    path = sys.argv[1]
    rate, ch, win, to = 48000, 2, 1.0, None
    a = sys.argv[2:]
    while a:
        k = a.pop(0)
        v = a.pop(0)
        if k == "--rate":
            rate = int(v)
        elif k == "--channels":
            ch = int(v)
        elif k == "--win":
            win = float(v)
        elif k == "--to":
            to = float(v)
    x = np.fromfile(path, dtype="<i2").astype(np.float64)
    x = x[: len(x) // ch * ch].reshape(-1, ch)
    if to:
        x = x[: int(to * rate)]
    n = int(win * rate)
    print("start_s  " + "  ".join(f"ch{c}_rms ch{c}_pk" for c in range(ch)))
    for i in range(0, len(x) - n + 1, n):
        seg = x[i:i + n]
        cols = []
        for c in range(ch):
            s = seg[:, c]
            rms = math.sqrt(np.mean((s - s.mean()) ** 2))
            cols.append(f"{db(rms):7.2f} {db(np.abs(s).max()):6.2f}")
        print(f"{i / rate:7.2f}  " + "  ".join(cols))
    seg = x
    cols = []
    for c in range(ch):
        s = seg[:, c]
        rms = math.sqrt(np.mean((s - s.mean()) ** 2))
        cols.append(f"{db(rms):7.2f} {db(np.abs(s).max()):6.2f}")
    print("  whole  " + "  ".join(cols))


if __name__ == "__main__":
    main()
