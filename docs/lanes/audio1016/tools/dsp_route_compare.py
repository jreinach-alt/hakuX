#!/usr/bin/env python3
"""One voice's level through the title's DSP program vs the MON_VP mix.

  dsp_route_compare.py HARNESS DUMPDIR VOICE.s16le WORKDIR \
      --slots BIN:VOL_DB,BIN:VOL_DB,... [--headroom-db -6.02] [--frames N]

VOICE.s16le is the voice's stereo source (hxs_voices.py --dump-dir writes
it). --slots lists the voice's eight bin slots in order with their volume
in dB (attenuate(vol[b]) times the envelope); "off" slots are left out but
keep their position, e.g. 6:-11.2,8:-11.2,7:-11.2,9:-11.2,2:-11.2,11:off.

Prints AC RMS dBFS, L and R, of the second half of the output for:

  monvp      the MON_VP mix in vp.c: max slot gain times the source, no
             headroom divisor (computed here, no DSP)
  dsp_b%2    the GP/EP output with slot b fed from channel b % 2, which is
             what voice_process() does today
  dsp_b>>1   the same with slot b fed from channel (b >> 1) & 1
  ref_0/1    the source at the max slot gain into bins 0 (L) and 1 (R) only:
             what a plain front-left/front-right voice at the same volume
             gives through the same program

The headroom divisor (default -6.02 dB: submix_headroom 1) is applied to
every DSP route, as voice_process() does.
"""
import math
import os
import subprocess
import sys

import numpy as np


def acrms(x):
    x = x - x.mean()
    r = math.sqrt(float(np.mean(x * x)))
    return 20 * math.log10(r) if r > 0 else float("-inf")


def levels(x):
    h = x[len(x) // 2:]
    return acrms(h[:, 0]), acrms(h[:, 1])


def read(path):
    x = np.fromfile(path, dtype="<i2").astype(np.float64) / 32768.0
    return x[: len(x) // 2 * 2].reshape(-1, 2)


def main():
    harness, dump, voice, work = sys.argv[1:5]
    a = sys.argv[5:]
    slots, hr, frames = None, -6.02, None
    while a:
        k = a.pop(0)
        if k == "--slots":
            slots = []
            for s in a.pop(0).split(","):
                b, v = s.split(":")
                slots.append((int(b), None if v == "off" else float(v)))
        elif k == "--headroom-db":
            hr = float(a.pop(0))
        elif k == "--frames":
            frames = int(a.pop(0))
    os.makedirs(work, exist_ok=True)
    src = read(voice)
    if frames is None:
        frames = len(src) // 32
    gmax = max(v for _, v in slots if v is not None)
    mon = src[: frames * 32] * 10 ** (gmax / 20)
    print(f"source        L {acrms(src[:, 0]):7.2f}  R {acrms(src[:, 1]):7.2f}"
          f"  (L/R correlation "
          f"{np.corrcoef(src[:, 0], src[:, 1])[0, 1]:.3f})")
    l, r = levels(mon)
    print(f"monvp         L {l:7.2f}  R {r:7.2f}")
    runs = {
        "dsp_b%2": [(b, i % 2, v) for i, (b, v) in enumerate(slots)
                    if v is not None],
        "dsp_b>>1": [(b, (i >> 1) & 1, v) for i, (b, v) in enumerate(slots)
                     if v is not None],
        "ref_0/1": [(0, 0, gmax), (1, 1, gmax)],
    }
    for name, routes in runs.items():
        out = os.path.join(work, name.replace("%", "mod").replace(">>", "shr")
                           .replace("/", "_"))
        cmd = [harness, dump, "--in", voice, "--frames", str(frames),
               "--out", out]
        for b, ch, v in routes:
            cmd += ["--route", f"{b}:{ch}:{v + hr}"]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        l, r = levels(read(out + ".ep0.s16le"))
        print(f"{name:12s}  L {l:7.2f}  R {r:7.2f}   routes "
              + " ".join(f"{b}<{'LR'[c]}" for b, c, _ in routes))


if __name__ == "__main__":
    main()
