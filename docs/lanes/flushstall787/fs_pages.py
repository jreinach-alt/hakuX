#!/usr/bin/env python3
"""Time series of translation counts and frame stalls from a soak's logcat.

Prints, in log order: every hakuX-pages line (120 frames each: blocks
discarded, generated, calls), every [tlb68] window with a flush, every
[tcg787] window (when the build carries it), and every hakuX-pace line whose
worst frame is >= --stall ms. Time is seconds from the first line.

usage: fs_pages.py <logcat.txt> [--stall MS]
"""
import re
import sys


def main():
    path = sys.argv[1]
    stall = 300.0
    if '--stall' in sys.argv:
        stall = float(sys.argv[sys.argv.index('--stall') + 1])
    t0 = None
    for line in open(path, errors='replace'):
        m = re.match(r'(\d\d-\d\d) (\d\d):(\d\d):(\d\d\.\d+)', line)
        if not m:
            continue
        t = int(m.group(2)) * 3600 + int(m.group(3)) * 60 + float(m.group(4))
        if t0 is None:
            t0 = t
        ts = '%7.1f' % (t - t0)
        if 'hakuX-pages' in line and 'generated' in line:
            g = re.search(r'blocks discarded (\d+) of (\d+) visited, '
                          r'generated (\d+) of (\d+) calls', line)
            print(ts, 'pages  disc=%s gen=%s calls=%s' %
                  (g.group(1), g.group(3), g.group(4)))
        elif '[tlb68]' in line:
            ff = int(re.search(r' ff=(\d+)', line).group(1))
            pf = int(re.search(r' pf=(\d+)', line).group(1))
            if ff or pf:
                print(ts, 'tlb68  ff=%d pf=%d' % (ff, pf))
        elif '[tcg787]' in line:
            print(ts, 'tcg787', line.split('[tcg787]', 1)[1].strip())
        elif 'hakuX-pace' in line:
            mx = re.search(r' max=([\d.]+)', line)
            if mx and float(mx.group(1)) >= stall:
                print(ts, 'PACE  ', line.split(':', 3)[-1].strip())


if __name__ == '__main__':
    main()
