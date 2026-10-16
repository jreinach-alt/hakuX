#!/usr/bin/env python3
"""Gain from each GP mixbin to the DSP output, with the title's own program.

  dsp_gain_matrix.py HARNESS DUMPDIR WORKDIR [--bins 0,1,2] [--frames 256]
                     [--freq 997]

Feeds a 997 Hz (--freq) sine at -20 dBFS into one mixbin at a time (dsp_harness
--route BIN:0:0) and fits the 997 Hz amplitude in each output channel over
the second half of the run. Prints, per bin, the gain in dB from the bin to
the EP's output FIFO 0 (the AC97 stream: what use_dsp = true plays) and to
the MON_GP tap (X:0x1400 and X:0x1420 after the GP frame), L and R. "-" is
below -80 dB, i.e. the bin does not reach that output.
"""
import math
import os
import subprocess
import sys

import numpy as np

RATE = 48000
F = 997.0
AMP = 0.1          # -20 dBFS


def fit_amp(x, f=None):
    f = F if f is None else f
    n = np.arange(len(x))
    s = np.sin(2 * math.pi * f * n / RATE)
    c = np.cos(2 * math.pi * f * n / RATE)
    a = np.vstack([s, c, np.ones_like(s)]).T
    coef, *_ = np.linalg.lstsq(a, x, rcond=None)
    return math.hypot(coef[0], coef[1])


def db(r):
    return f"{20 * math.log10(r):6.1f}" if r > 1e-4 else "     -"


def read(path):
    x = np.fromfile(path, dtype="<i2").astype(np.float64) / 32768.0
    x = x[: len(x) // 2 * 2].reshape(-1, 2)
    return x[len(x) // 2:]


def main():
    harness, dump, work = sys.argv[1:4]
    a = sys.argv[4:]
    bins = list(range(32))
    frames = 256
    while a:
        k = a.pop(0)
        if k == "--bins":
            bins = [int(b) for b in a.pop(0).split(",")]
        elif k == "--frames":
            frames = int(a.pop(0))
        elif k == "--freq":
            global F
            F = float(a.pop(0))
    os.makedirs(work, exist_ok=True)
    n = frames * 32
    t = np.arange(n)
    sig = np.zeros((n, 2))
    sig[:, 0] = AMP * np.sin(2 * math.pi * F * t / RATE)
    src = os.path.join(work, "sine997.s16le")
    (sig * 32768).round().astype("<i2").tofile(src)
    print("bin   EP_L   EP_R   GP_L   GP_R   (dB from bin to output)")
    for b in bins:
        out = os.path.join(work, f"bin{b:02d}")
        subprocess.run([harness, dump, "--in", src, "--frames", str(frames),
                        "--route", f"{b}:0:0", "--out", out], check=True,
                       stdout=subprocess.DEVNULL)
        ep = read(out + ".ep0.s16le")
        gp = read(out + ".gp.s16le")
        g = [fit_amp(ep[:, 0]) / AMP, fit_amp(ep[:, 1]) / AMP,
             fit_amp(gp[:, 0]) / AMP, fit_amp(gp[:, 1]) / AMP]
        print(f"{b:3d} " + " ".join(db(x) for x in g))


if __name__ == "__main__":
    main()
