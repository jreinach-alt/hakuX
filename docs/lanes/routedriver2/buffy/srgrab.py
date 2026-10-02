#!/usr/bin/env python3
"""srgrab.py <serial> <seconds> <out dir> [WxH]: stream `screenrecord --output-format=frames`
(raw RGB888, a 20-byte header per frame: 5 x u32, the 2nd/3rd width/height) and keep every frame,
host-timestamped. Writes <out>/frames.raw and <out>/frames.tsv (index, host epoch s, header hex)."""
import os
import struct
import subprocess
import sys
import time

serial, secs, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
size = sys.argv[4] if len(sys.argv) > 4 else "320x240"
os.makedirs(out, exist_ok=True)
p = subprocess.Popen(["adb", "-s", serial, "exec-out", "screenrecord", "--output-format=frames",
                      "--size", size, "--time-limit", str(secs), "-"], stdout=subprocess.PIPE)
raw = open(os.path.join(out, "frames.raw"), "wb")
tsv = open(os.path.join(out, "frames.tsv"), "w")
n = 0


def readn(k):
    b = b""
    while len(b) < k:
        c = p.stdout.read(k - len(b))
        if not c:
            return None
        b += c
    return b


while True:
    h = readn(20)
    if h is None:
        break
    _, w, hh, stride, fmt = struct.unpack("<5I", h)
    body = readn(stride * hh)
    if body is None:
        break
    tsv.write("%d\t%.3f\t%s\t%d\t%d\t%d\n" % (n, time.time(), h[:4].hex(), w, hh, stride))
    raw.write(body)
    n += 1
p.wait()
print("frames", n)
