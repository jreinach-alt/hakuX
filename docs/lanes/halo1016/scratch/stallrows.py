#!/usr/bin/env python3
"""Print one row per perflog hakuX-stall block: time, Finish total, sd, flip,
pres, sd[dl ...], dif[...], txr dl/scdl/s2tc, txdl reasons, and the nearest
gfps. A reading aid for an existing result, not a judge.

usage: stallrows.py LOGCAT [--from HH:MM:SS] [--to HH:MM:SS]
"""
import re
import sys

FIN = re.compile(r'Finish:(\d+)\(vtx(\d+) sc(\d+) sd(\d+) buf(\d+) fb(\d+) pres(\d+) flip(\d+)')
SDX = re.compile(r' sd\[ev(\d+) noCb(\d+) dl(\d+) cDef(\d+) cDefC(\d+) pDl(\d+) dDl(\d+)\]')
DIF = re.compile(r'dif\[ovl(\d+) ovlSh(\d+) exp(\d+) expSh(\d+) blt(\d+) flu(\d+) dds(\d+) oth(\d+)\]')
TXR = re.compile(r'txr\[ct(\d+) bt(\d+)/(\d+) dl(\d+)/(\d+)K sc(\d+) scdl(\d+) img(\d+) pool(\d+) '
                 r's2tc(\d+) s2td(\d+)\](?: txdl\[lv(\d+) dim(\d+) cube(\d+) pitch(\d+) swz(\d+) '
                 r'cvt(\d+) bpp(\d+) upl(\d+) oth(\d+)\])?')
GF = re.compile(r'gfps=(\d+) G:([\d.]+)')
T = re.compile(r'^\d\d-\d\d (\d\d:\d\d:\d\d)\.\d+')


def main():
    a = sys.argv[1:]
    path = a[0]
    lo = a[a.index('--from') + 1] if '--from' in a else '00:00:00'
    hi = a[a.index('--to') + 1] if '--to' in a else '99:99:99'
    gf = '-'
    row = None
    print('time | fin | sd | flip | pres | vtx | sd[dl] | dif ovl/exp/blt/oth | txr dl | scdl | s2tc | s2td | txdl lv/dim/cube/pitch/swz/cvt/bpp/upl/oth | gfps')
    for line in open(path, errors='replace'):
        m = T.match(line)
        if not m:
            continue
        t = m.group(1)
        if not (lo <= t <= hi):
            continue
        g = GF.search(line)
        if g and 'hakuX-perf' in line:
            gf = g.group(1)
        f = FIN.search(line)
        if f and 'hakuX-stall' in line:
            s = SDX.search(line)
            d = DIF.search(line)
            row = [t, f.group(1), f.group(4), f.group(8), f.group(7), f.group(2),
                   s.group(3) if s else '-',
                   '/'.join(d.group(i) for i in (1, 3, 5, 8)) if d else '-']
            continue
        x = TXR.search(line)
        if x and row:
            why = '/'.join(x.group(i) for i in range(12, 21)) if x.group(12) else '-'
            print(' | '.join(row + [x.group(4), x.group(7), x.group(10), x.group(11), why, gf]))
            row = None


if __name__ == '__main__':
    main()
