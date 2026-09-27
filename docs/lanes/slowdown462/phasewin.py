#!/usr/bin/env python3
"""The hakuX-phase and hakuX-cpu lines inside a held session's profile window.

    phasewin.py <session dir> [--gpu-scale 1.573]

Means, over the phase lines between `prof start` and `prof end`, of every
`Name:value` field (wall ms per frame, a running average of ~5 frames), plus
the hakuX-cpu puller fields (Pull, Lk, Mth). GPU, R and X are also printed
times --gpu-scale: the Nova's GPU timestamps tick at 19.2 MHz while hakuX
converts them at 30.2 (lane.flip474, #474 section 3), so its GPU figures read
0.636 of true. Pass 1.0 on a device whose clock is right.
"""
import argparse
import re
from collections import defaultdict
from datetime import datetime

ap = argparse.ArgumentParser()
ap.add_argument("dir")
ap.add_argument("--gpu-scale", type=float, default=1.573)
a = ap.parse_args()
ts = lambda l: datetime.strptime(l[:18], "%m-%d %H:%M:%S.%f")
start = end = None
lines = []
for l in open(f"{a.dir}/logcat.txt", errors="replace"):
    if "hakuX-route" in l and "prof start" in l:
        start = ts(l)
    elif "hakuX-route" in l and "prof end" in l:
        end = ts(l)
    elif "hakuX-phase" in l or ("hakuX-cpu" in l and "Pull:" in l):
        lines.append((ts(l), "phase" if "hakuX-phase" in l else "cpu", l))
vals = defaultdict(list)
n = defaultdict(int)
for t, kind, l in lines:
    if not (start and end and start <= t <= end):
        continue
    n[kind] += 1
    body = l.split("): ", 1)[1]
    for k, v in re.findall(r"([A-Za-z]+):([0-9.]+)", body):
        vals[(kind, k)].append(float(v))
print(f"window {start:%H:%M:%S}-{end:%H:%M:%S}: {n['phase']} phase lines, {n['cpu']} cpu lines")
for kind in ("phase", "cpu"):
    keys = [k for (kk, k) in vals if kk == kind]
    out = []
    for k in keys:
        v = vals[(kind, k)]
        m = sum(v) / len(v)
        s = f"{k} {m:.1f}"
        if kind == "phase" and k in ("GPU", "R", "X"):
            s += f" (x{a.gpu_scale}: {m * a.gpu_scale:.1f})"
        out.append(s)
    print(f"{kind}: " + ", ".join(out))
