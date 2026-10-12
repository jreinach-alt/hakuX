#!/usr/bin/env python3
"""vCPU busy vs idle per guest frame at the NFS MW race start (#433, lane.nfs30plan1010).

    vcpuread.py <result dir> [...] [--window LO,HI] [--label countdown]

Reads two always-on lines from each run's logcat.txt:

  [rr425w] w=N idlepc=.. idle_us=A busy_us=B n=.. nb=.. drop=.. KEY:n:idle:busy:ih:bh:nb ...
      (accel/tcg/cpu-exec.c, one line per 2 s window, timestamped at the
      window's END; idle = the Xbox kernel idle loop at 0x8001b02e, busy =
      everything else the vCPU thread did, wall clock, so MMIO waits and
      page-watch downloads on the vCPU thread count as busy; idle + busy =
      wall time of the window). KEY is vec.units in hex: vec 0x30 = IRQ0
      (timer), 0x31 = IRQ1, 0x33 = IRQ3 (the NV2A). Each key's busy is the
      work the guest did after that wake, until it idled again.
  hakuX-pace f=F ...   (profile.c, every 60 guest flips; F = flip count)

For each route mark (`hakuX-route: mark gameplay|goN`) the window is
[mark+LO, mark+HI] (default -4,1.5: the countdown; GO is ~1.5 s after the
mark). A 2 s rr425w window counts when it lies wholly inside. Frames inside
it are read from f(t), piecewise-linear between pace lines. Prints per run
and pooled: windows, frames, busy ms per frame, idle ms per frame, busy
share, and busy per frame split by wake key (NV2A, timer, other).
"""
import argparse
import bisect
import os
import re
import sys

TS = re.compile(r'^(\d+)-(\d+) (\d+):(\d+):([\d.]+) ')
RRW = re.compile(r'\[rr425w\] w=(\d+) idlepc=\w+ idle_us=(\d+) busy_us=(\d+) n=(\d+) nb=(\d+) drop=(\d+)(.*)$')
KEY = re.compile(r'([0-9a-f]{2})\.([0-9a-f]{2}):(\d+):(\d+):(\d+):')
PACE = re.compile(r'hakuX-pace\(\s*\d+\): f=(\d+) ')
MARK = re.compile(r'hakuX-route.*mark (gameplay|go\d+)')


def secs(m):
    return int(m.group(3)) * 3600 + int(m.group(4)) * 60 + float(m.group(5))


def read(path):
    rrw, pace, marks = [], [], []
    with open(path, errors='replace') as f:
        for ln in f:
            m = TS.match(ln)
            if not m:
                continue
            t = secs(m)
            r = RRW.search(ln)
            if r:
                idle, busy = int(r.group(2)), int(r.group(3))
                keys = {}
                for k in KEY.finditer(r.group(7)):
                    vec = k.group(1)
                    cls = 'nv2a' if vec == '33' else ('timer' if vec == '30' else 'other')
                    keys[cls] = keys.get(cls, 0) + int(k.group(5))
                rrw.append((t, idle, busy, keys))
                continue
            p = PACE.search(ln)
            if p:
                pace.append((t, int(p.group(1))))
                continue
            k = MARK.search(ln)
            if k:
                marks.append((t, k.group(1)))
    return rrw, pace, marks


def frames_at(pace, t):
    ts = [p[0] for p in pace]
    i = bisect.bisect_left(ts, t)
    if i == 0:
        return pace[0][1]
    if i >= len(pace):
        return pace[-1][1]
    (t0, f0), (t1, f1) = pace[i - 1], pace[i]
    return f0 + (f1 - f0) * (t - t0) / (t1 - t0) if t1 > t0 else f0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--window', default='-4,1.5')
    ap.add_argument('--label', default='')
    a = ap.parse_args()
    lo, hi = (float(x) for x in a.window.split(','))
    print(f"window: mark{lo:+.1f} .. mark{hi:+.1f} s {a.label}")
    print(f"{'run':42s} {'win':>3s} {'frames':>6s} {'ms/f':>6s} {'busy/f':>6s} {'idle/f':>6s} {'busy%':>5s} "
          f"{'nv2a/f':>6s} {'timer/f':>7s} {'other/f':>7s}")
    pool = [0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    for d in a.dirs:
        rrw, pace, marks = read(os.path.join(d, 'logcat.txt'))
        if not rrw or not pace or not marks:
            print(f"{os.path.basename(d):42s} no rr425w/pace/marks ({len(rrw)}/{len(pace)}/{len(marks)})")
            continue
        n = 0
        fr = busy = idle = 0.0
        kb = {'nv2a': 0.0, 'timer': 0.0, 'other': 0.0}
        for mt, _ in marks:
            w0, w1 = mt + lo, mt + hi
            for t, i_us, b_us, keys in rrw:
                t0 = t - (i_us + b_us) / 1e6
                if t0 >= w0 and t <= w1:
                    f = frames_at(pace, t) - frames_at(pace, t0)
                    if f <= 0:
                        continue
                    n += 1
                    fr += f
                    busy += b_us / 1e3
                    idle += i_us / 1e3
                    for c in kb:
                        kb[c] += keys.get(c, 0) / 1e3
        if n == 0:
            print(f"{os.path.basename(d):42s} no pure rr425w window inside")
            continue
        span = busy + idle
        print(f"{os.path.basename(d):42s} {n:3d} {fr:6.0f} {span / fr:6.1f} {busy / fr:6.1f} {idle / fr:6.1f} "
              f"{100 * busy / span:4.0f}% {kb['nv2a'] / fr:6.1f} {kb['timer'] / fr:7.1f} {kb['other'] / fr:7.1f}")
        pool[0] += n
        pool[1] += fr
        pool[2] += busy
        pool[3] += idle
        pool[4] += kb['nv2a']
        pool[5] += kb['timer']
        pool[6] += kb['other']
    if pool[1]:
        n, fr, busy, idle, kn, kt, ko = pool
        span = busy + idle
        print(f"{'POOLED':42s} {n:3d} {fr:6.0f} {span / fr:6.1f} {busy / fr:6.1f} {idle / fr:6.1f} "
              f"{100 * busy / span:4.0f}% {kn / fr:6.1f} {kt / fr:7.1f} {ko / fr:7.1f}")


if __name__ == '__main__':
    sys.exit(main())
