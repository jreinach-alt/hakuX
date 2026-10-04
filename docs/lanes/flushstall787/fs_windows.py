#!/usr/bin/env python3
"""Per-window table of the vCPU counters in a soak's logcat.

One row per [tlb68] window: flushes (ff, pf, cr3s, fo), the [rr425] split of
the window's vCPU time (it dispatches, gapus = loop time between TBs, which
includes tb_gen_code, tbus = time inside TBs), [idlehalt] run_us, and the
[tcg787] translation counters when the build carries them.

usage: fs_windows.py <logcat.txt> [--min-ff N]
"""
import re
import sys


def kv(line):
    return dict(re.findall(r' (\w+)=([\-\w.:,/]+)', line))


def main():
    path = sys.argv[1]
    min_ff = 0
    if '--min-ff' in sys.argv:
        min_ff = int(sys.argv[sys.argv.index('--min-ff') + 1])
    rows = {}
    for line in open(path, errors='replace'):
        m = re.match(r'(\d\d-\d\d) (\d\d):(\d\d):(\d\d\.\d+)', line)
        if not m:
            continue
        t = int(m.group(2)) * 3600 + int(m.group(3)) * 60 + float(m.group(4))
        for tag, keys in (('[tlb68]', ['cpu', 'ff', 'pf', 'cr3s', 'cr3n',
                                       'fo', 'jcus', 'rd', 'rdus']),
                          ('[rr425]', ['it', 'gapus', 'tbus', 'm', 'x']),
                          ('[idlehalt]', ['run_us']),
                          ('[tcg787]', ['gc', 'cg', 'gus', 'gmax', 'inv',
                                        'invtb', 'tbf', 'tbfus'])):
            if tag in line:
                d = kv(line)
                w = int(d['w'])
                r = rows.setdefault(w, {})
                if tag == '[tlb68]':
                    r['t'] = t
                for k in keys:
                    if k in d:
                        r[k] = d[k]
    if 0 not in rows or 't' not in rows[0]:
        print('no [tlb68] w=0 line')
        return
    t0 = rows[0]['t']
    cols = ['cpu', 'ff', 'pf', 'cr3s', 'fo', 'it', 'gapus', 'tbus', 'm',
            'run_us', 'gc', 'cg', 'gus', 'gmax', 'invtb', 'tbf']
    print('w t ' + ' '.join(cols))
    for w in sorted(rows):
        r = rows[w]
        if 't' not in r or int(r.get('ff', 0)) < min_ff:
            continue
        print(w, round(r['t'] - t0, 1),
              ' '.join(str(r.get(k, '-')) for k in cols))


if __name__ == '__main__':
    main()
