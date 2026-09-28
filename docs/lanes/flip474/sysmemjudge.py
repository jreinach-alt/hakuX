#!/usr/bin/env python3
"""Every number the flip474-sysmem-*.json legs name, for each run, one window.

    python3 sysmemjudge.py --from S --to S <result id> [...]

Seconds are from logcat line 1, as in phaseread.py. Per run:

  dev/apk/env  result.json's device_label, apk_sha and env (the pin is read
               back from the result, not from the prediction)
  tu           the app's TU_DEBUG lines ('env:' from the env_vars pref,
               'init:' from instance.c's default), or none
  phase        hakuX-phase lines in the window, and those with GPU > 0 (M0)
  GPU R X Tot  medians over the lines with GPU > 0, as printed
  X/R          the median of each line's X/R, not the ratio of the medians
  gfps         median, smallest, and smallest/median (T0 wants >= 0.6)
  gap          the longest gap between hakuX-perf gfps lines in the window (H0)
  last         seconds of the last gfps line and of the last logcat line
  crash        crash markers in the whole logcat
"""
import argparse
import json
import os
import re
from datetime import datetime
from statistics import median

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'


def ts(l):
    return datetime.strptime('2026-' + l[:18], '%Y-%m-%d %H:%M:%S.%f')


def num(k, l):
    m = re.search(r'(?<![A-Za-z])' + k + r':([0-9.]+)', l)
    return float(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='lo', type=float, required=True)
    ap.add_argument('--to', dest='hi', type=float, required=True)
    ap.add_argument('runs', nargs='+')
    a = ap.parse_args()
    for run in a.runs:
        text = open(R + run + '/logcat.txt', errors='replace').read()
        L = text.splitlines()
        res = json.load(open(R + run + '/result.json'))
        t0 = ts(L[1])
        tu = [l.split('): ', 1)[1] for l in L if 'TU_DEBUG' in l and '): ' in l]
        n = 0
        v = {'GPU': [], 'R': [], 'X': [], 'Tot': [], 'XR': []}
        gf = []
        last_any = last_g = None
        for l in L:
            try:
                s = (ts(l) - t0).total_seconds()
            except ValueError:
                continue
            last_any = s
            m = re.search(r'hakuX-perf\(\s*\d+\): gfps=([0-9.]+)', l)
            if m:
                last_g = s
                if a.lo <= s <= a.hi:
                    gf.append((s, float(m.group(1))))
                continue
            if 'hakuX-phase' not in l or not a.lo <= s <= a.hi:
                continue
            n += 1
            g, r, x, t = (num(k, l) for k in ('GPU', 'R', 'X', 'Tot'))
            if not g:
                continue
            v['GPU'].append(g)
            v['Tot'].append(t)
            v['R'].append(r)
            v['X'].append(x)
            if r:
                v['XR'].append(x / r)
        crash = len(re.findall(
            r'FATAL|beginning of crash|Tombstone|SIGSEGV|SIGABRT', text))
        print(run)
        print('  dev=%s apk=%s ref=%s env=%s' % (
            res.get('device_label'), res.get('apk_sha'),
            str(res.get('ref'))[:10], res.get('env')))
        print('  tu=%s' % (tu or 'none'))
        print('  phase=%d with GPU>0=%d' % (n, len(v['GPU'])))
        if v['GPU']:
            print('  GPU=%.1f R=%.1f X=%.1f Tot=%.1f X/R=%.2f' % (
                median(v['GPU']), median(v['R']), median(v['X']),
                median(v['Tot']), median(v['XR']) if v['XR'] else -1))
        if gf:
            g = [x for _s, x in gf]
            gaps = [b[0] - a_[0] for a_, b in zip(gf, gf[1:])]
            lo = min(gf, key=lambda p: p[1])
            print('  gfps median=%.1f n=%d min=%.1f at %.0f s (%.2f x median) '
                  'gap=%.1f s' % (median(g), len(g), lo[1], lo[0],
                                  lo[1] / median(g) if median(g) else 0,
                                  max(gaps) if gaps else -1))
        print('  last gfps line %.1f s, last logcat line %.1f s, crash=%d' % (
            last_g or -1, last_any or -1, crash))


if __name__ == '__main__':
    main()
