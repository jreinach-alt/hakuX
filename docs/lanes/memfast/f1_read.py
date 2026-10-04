#!/usr/bin/env python3
"""Read lane.memfast's F0a and F1 lines from one or more result dirs (#507).

    f1_read.py <result dir> [...]

[f0a] lines (HAKUX_F0A=<s>): printed as they are, one block per pass, with
the cold-refault price per 1,000 pages and the walk price per 8,192 pages.

[fm] lines (HAKUX_FASTMEM=1): rates per wall second over the windows from the
route's last `mark gameplay|play` (f0a_rates.mark), or the whole run if there
is no mark, and the last line's gauges. A run with
no [fm] line and no "[fm] on" line did not arm fastmem.

[tlb68] cpu= is the vCPU thread's CPU ms per window; it is printed over the
same span so an F1 run and its control can be compared on one line each.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from f0a_rates import clock, mark  # noqa: E402  the same span as f0a_rates

KV = re.compile(r'(\w+)=(-?[\w./>-]+)')


def span_lines(run, path):
    lines = open(path, errors='replace').read().splitlines()
    t = mark(run)
    if not t:
        return lines, False
    return [l for l in lines if (clock(l) or '') >= t], True


def read(d):
    path = d.rstrip('/') + '/logcat.txt'
    try:
        lines, marked = span_lines(d, path)
    except OSError as e:
        print(f'== {d}: {e}')
        return
    allf = open(path, errors='replace').read().splitlines()
    print(f'== {d}  ({"from the mark" if marked else "whole run, no mark"})')
    for l in allf:
        if '[f0a]' in l or '[fm] on' in l or '[fm] OFF' in l or '[fm] RAM' in l \
                or '[fm] mode' in l or '[fm] memfd' in l:
            print('  ', l[l.index('['):])
            if '[f0a] pass=' in l:
                kv = dict(KV.findall(l))
                cold = int(kv['cold'].split('/')[0])
                wps = int(kv['walkbatch_ps'])
                print(f'     cold refault {cold} ns p50 -> {cold / 1000:.1f} ms per '
                      f'1,000 pages; walk {wps / 1000:.1f} ns -> '
                      f'{wps * 8192 / 1e9:.3f} ms per 8,192-page revalidation')
    fm = [dict(KV.findall(l[l.index('[fm] dt='):])) for l in lines if '[fm] dt=' in l]
    tl = [dict(KV.findall(l[l.index('[tlb68]'):])) for l in lines if '[tlb68] w=' in l]
    if tl:
        wall = sum(int(t['dt']) for t in tl) / 1000.0
        cpu = sum(int(t['cpu']) for t in tl) / 1000.0
        print(f'   [tlb68] windows={len(tl)} wall={wall:.0f}s vCPU={100 * cpu / wall:.1f}% of wall')
    if fm:
        wall = sum(int(f['dt']) for f in fm) / 1000.0
        keys = ['map', 'mapf', 'unmap', 'drop', 'dropus', 'rv', 'rvw', 'rvk',
                'rvus', 'flt', 'pat', 'shit', 'cap', 'inv', 'ram', 'sadd']
        rates = {k: sum(int(f.get(k, 0)) for f in fm) / wall for k in keys}
        print(f'   [fm] windows={len(fm)} wall={wall:.0f}s')
        print('   per s: ' + '  '.join(f'{k}={rates[k]:.1f}' for k in keys))
        last = fm[-1]
        print('   last: ' + '  '.join(f'{k}={last.get(k)}' for k in
                                      ('on', 'mapped', 'listed', 'sites', 'patched', 'vmas')))
        vm = [int(f['vmas']) for f in fm if f.get('vmas', '0') != '0']
        if vm:
            print(f'   vmas: min {min(vm)} max {max(vm)} over {len(vm)} reads')
        tus = rates['dropus'] + rates['rvus']
        print(f'   shadow upkeep (drops + revalidations): {tus / 1000:.2f} ms per wall second')


if __name__ == '__main__':
    for a in sys.argv[1:]:
        read(a)
