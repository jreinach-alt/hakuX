#!/usr/bin/env python3
"""Per-voice source features from hxs_voices.py --dump-dir output.

  voice_feat.py DUMPDIR

For each vNNN.<ch>ch.<rate>.s16le: duration, AC RMS dBFS, 10 ms envelope
spread (p90-p10 dB), fraction of 10 ms frames more than 20 dB under the
loudest frame (pauses), zero-crossing rate per sample, spectral centroid and
the fraction of energy in 300-3400 Hz (speech band) from one FFT over the
whole buffer, and a short content hash (identical buffers share it).
Channel 0 only for stereo; the hash covers the whole file.
"""
import hashlib
import math
import os
import re
import struct
import sys

try:
    import numpy as np
except ImportError:
    np = None

d = sys.argv[1]
print("%-5s %3s %6s %6s %7s %6s %6s %6s %7s %6s %s" % (
    "v", "ch", "Hz", "ms", "rms", "env", "pause", "zcr", "centHz", "band", "hash"))
for name in sorted(os.listdir(d)):
    m = re.match(r"v(\d+)\.(\d)ch\.(\d+)\.s16le$", name)
    if not m:
        continue
    v, ch, rate = int(m.group(1)), int(m.group(2)), int(m.group(3))
    raw = open(os.path.join(d, name), "rb").read()
    h = hashlib.sha1(raw).hexdigest()[:8]
    n = len(raw) // 2
    s = struct.unpack("<%dh" % n, raw[: n * 2])
    x = [s[i] / 32768.0 for i in range(0, n, ch)]
    if len(x) < 64:
        continue
    mean = sum(x) / len(x)
    x = [a - mean for a in x]
    e = sum(a * a for a in x) / len(x)
    rms = 10 * math.log10(e) if e > 0 else -200
    fl = max(1, rate // 100)
    env = []
    for i in range(0, len(x) - fl + 1, fl):
        fe = sum(a * a for a in x[i:i + fl]) / fl
        env.append(10 * math.log10(fe) if fe > 1e-12 else -120)
    env_s = sorted(env)
    p10 = env_s[len(env_s) // 10]
    p90 = env_s[(len(env_s) * 9) // 10]
    pause = sum(1 for a in env if a < max(env) - 20) / len(env)
    zc = sum(1 for i in range(1, len(x)) if (x[i] >= 0) != (x[i - 1] >= 0)) / len(x)
    cent = band = float("nan")
    if np is not None and e > 0:
        X = np.abs(np.fft.rfft(np.array(x))) ** 2
        f = np.fft.rfftfreq(len(x), 1.0 / rate)
        cent = float((X * f).sum() / X.sum())
        band = float(X[(f >= 300) & (f <= 3400)].sum() / X.sum())
    print("%-5d %3d %6d %6.0f %7.1f %6.1f %6.2f %6.3f %7.0f %6.2f %s" % (
        v, ch, rate, 1000.0 * len(x) / rate, rms, p90 - p10, pause, zc, cent, band, h))
