#!/usr/bin/env python3
"""level_windows.py's method (audio1016/tools) for `logcat -v threadtime` dumps.

  lvl_tt.py LOGCAT [PID]

The `level` meter's acrms is cumulative over the run; energy is additive, so the
interval level between consecutive lines is
  10*log10((T2*10^(a2/10) - T1*10^(a1/10)) / (T2 - T1)).
Also prints the voice_headroom window count / 7500 (= mean active voices in the
5 s window) at the nearest preceding line, and the running peak.
"""
import math
import re
import sys

TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+(\d+)\s+(\d+) . hakuX-audio: (.*)$")
LV = re.compile(r"level ([LR]): ([\d.]+) s\s+peak (\d+) .*?acrms (-?[\d.]+|-inf) dBFS")
VH = re.compile(r"voice_headroom: window (\d+) active voice-frames\s+hr0..7 = ([\d ]+?)\s+cumulative")

path = sys.argv[1]
pid = sys.argv[2] if len(sys.argv) > 2 else None
prev = {}
rows = []
voices = None
cur = {}
for line in open(path, errors="replace"):
    m = TS.match(line)
    if not m:
        continue
    ts, p, _tid, body = m.groups()
    if pid and p != pid:
        continue
    v = VH.match(body)
    if v:
        voices = int(v.group(1)) / 7500.0
        continue
    lm = LV.match(body)
    if not lm:
        continue
    ch, t, peak, a = lm.groups()
    t = float(t)
    e = 0.0 if a == "-inf" else t * 10 ** (float(a) / 10)
    if ch in prev:
        pt, pe = prev[ch]
        dt = t - pt
        de = e - pe
        lvl = 10 * math.log10(de / dt) if dt > 0 and de > 0 else float("-inf")
        cur[ch] = (dt, lvl, int(peak))
    prev[ch] = (t, e)
    if ch == "R" and "L" in cur and "R" in cur:
        rows.append((ts, t, cur["L"][0], cur["L"][1], cur["R"][1], cur["L"][2], voices))
        cur = {}

print("%-18s %8s %6s %8s %8s %6s %6s" % ("clock", "audio_s", "dt", "L dBFS", "R dBFS", "R-L", "voices"))
for ts, t, dt, l, r, pk, vo in rows:
    print("%-18s %8.1f %6.2f %8.2f %8.2f %6.2f %6s" % (
        ts, t, dt, l, r, r - l, "%.1f" % vo if vo is not None else "-"))
