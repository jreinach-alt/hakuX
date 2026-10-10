#!/usr/bin/env python3
"""Draw census reader (#433, lane.drawrec1010).

    censusread.py <result dir | logcat.txt> [...] [--window LO,HI] [--all] [--per-mark]

Reads the `census*` lines a HAKUX_DRAWCENSUS=1 build prints on hakuX-stall
once per 60 frames (draw.c, drawcensus_frame()). Each set of lines covers
the 60 frames before its print time. A set is kept when its print time is
in [mark+LO, mark+HI] for some `hakuX-route: mark gameplay|goN`; the default
-2,13 is the race start the route measures, from ~2 s before GO to ~11 s
past it, plus a window's length so the last set still overlaps it. --all
keeps every set, menus and load included.

Every draw is one consecutive pair (this draw against the previous drawn
one). Its class is the first that applies, from the top:

  surf    colour or zeta surface changed
  shader  shader binding changed
  pipe    pipeline binding, vertex attribute layout or primitive changed
  tex     a bound texture, a direct surface view or a texture register
  reg     a key-feeding register (combiner, CSV, blend/depth static bits,
          window clip, any other) with shader and pipeline kept
  uni     uniforms only: c[], lighting, the uploaded bytes, registers read
          as uniforms (combine factors, fog, bump, eye vector)
  dyn     dynamic-state register bits only
  same    nothing tracked: vertex data only

The brief's decision: same+dyn+uni >= 50% -> reuse (step 2); otherwise
same >= 40% -> batching; otherwise stop.
"""
import argparse
import os
import re
import sys
from collections import Counter, defaultdict

TS = re.compile(r'^(\d+)-(\d+) (\d+):(\d+):([\d.]+) ')
CENSUS = re.compile(r'hakuX-stall\(\s*\d+\): (census(?:-[a-z]+)?) w=(\d+) (.*)$')
MARK = re.compile(r'hakuX-route.*mark (gameplay|go\d+)')
INIT = re.compile(r'\[drawrec1010\] census=(\d)')
KV = re.compile(r'([a-z_0-9+\-]+)=(\d+)')
HEXKV = re.compile(r' ([0-9a-f]+):(\d+)')

BITS = ['sb', 'pb', 'va', 'tx', 'sf', 'pm', 'uc', 'ul', 'ub', 'rc', 'rt', 'rl', 'rb', 'rd', 'rf', 'rw', 'ro']
BIT_DOC = {
    'sb': 'shader binding', 'pb': 'pipeline binding', 'va': 'vertex attribute layout',
    'tx': 'bound texture / direct view', 'sf': 'surface', 'pm': 'primitive mode',
    'uc': 'c[] constants', 'ul': 'lighting / material', 'ub': 'uploaded uniform bytes',
    'rc': 'reg: combiners, shader prog, clip mode', 'rt': 'reg: texture', 'rl': 'reg: CSV0/1, point size',
    'rb': 'reg: blend/depth/raster static bits', 'rd': 'reg: dynamic-state bits only',
    'rf': 'reg: factors, fog, bump, eye (uniform-fed)', 'rw': 'reg: window clip', 'ro': 'reg: other',
}
CLASSES = ['same', 'dyn', 'uni', 'reg', 'tex', 'pipe', 'shader', 'surf']
PATHS = ['sfp', 'mfp', 'full']
CPS = ['none', 'early', 'notdirty', 'samekey', 'lru', 'pend', 'miss', 'lrufull']
COSTS = ['shc_in', 'shc_stale', 'shc_stale_full', 'ubo_sets', 'ubo_sets_samesb', 'uploads', 'uploads_same',
         'reuse_full', 'same_notsfp']
ROWS = ['0', '1-4', '5-8', '9-16', '17-32', '33+']

# Register names for the census-ro table (nv2a_regs.h), by byte address
REGNAMES = {
    0x0FB4: 'CSV0_D', 0x0FB8: 'CSV0_C', 0x0FBC: 'CSV1_B', 0x0FC0: 'CSV1_A',
}


def secs(m):
    return int(m.group(3)) * 3600 + int(m.group(4)) * 60 + float(m.group(5))


def logcat_of(p):
    return os.path.join(p, 'logcat.txt') if os.path.isdir(p) else p


def parse_line(kind, rest):
    if kind in ('census-mask', 'census-ro'):
        d = {k: int(v) for k, v in KV.findall(rest) if k in ('other', 'rest')}
        # " other=N" is not hex:count, but drop it before the hex scan
        body = re.sub(r'\b(other|rest)=\d+', '', rest)
        d['_hex'] = [(int(k, 16), int(v)) for k, v in HEXKV.findall(' ' + body)]
        return d
    if kind == 'census-crow':
        m = re.match(r'rows (.*) by16 (.*)$', rest)
        rows = [int(v) for _, v in KV.findall(m.group(1))]
        by16 = [int(x) for x in m.group(2).split()]
        return {'_rows': rows, '_by16': by16}
    if kind == 'census-path':
        a, b = rest.split(' cp ', 1)
        d = {('path_' + k): int(v) for k, v in KV.findall(a)}
        d.update({('cp_' + k) if k not in ('bs', 'pbind') else k: int(v) for k, v in KV.findall(b)})
        return d
    if kind == 'census':
        a, b = rest.split(' cls ', 1)
        d = {k: int(v) for k, v in KV.findall(a)}
        d.update({('cls_' + k): int(v) for k, v in KV.findall(b)})
        return d
    return {k: int(v) for k, v in KV.findall(rest)}


def read(path):
    sets = defaultdict(dict)   # (pid-ish, w) -> {kind: (t, fields)}
    marks = []
    init = None
    with open(path, errors='replace') as f:
        for ln in f:
            m = TS.match(ln)
            if not m:
                continue
            t = secs(m)
            if 'hakuX-route' in ln:
                k = MARK.search(ln)
                if k:
                    marks.append((t, k.group(1)))
                continue
            q = INIT.search(ln)
            if q:
                init = int(q.group(1))
                continue
            q = CENSUS.search(ln)
            if q:
                kind, w, rest = q.group(1), int(q.group(2)), q.group(3)
                sets[w][kind] = (t, parse_line(kind, rest))
    out = []
    for w in sorted(sets):
        s = sets[w]
        if 'census' not in s:
            continue
        out.append((s['census'][0], w, {k: v[1] for k, v in s.items()}))
    return out, marks, init


def select(sets, marks, lo, hi, use_all):
    if use_all:
        return [(t, w, s, '-') for t, w, s in sets]
    keep = []
    for t, w, s in sets:
        for mt, name in marks:
            if mt + lo <= t <= mt + hi:
                keep.append((t, w, s, name))
                break
    return keep


def total(selected):
    tot = Counter()
    rows = [0] * 6
    by16 = [0] * 12
    masks = Counter()
    mask_other = 0
    ro = Counter()
    ro_other = 0
    for _, _, s, _ in selected:
        for kind in ('census', 'census-bits', 'census-path', 'census-cost'):
            for k, v in s.get(kind, {}).items():
                tot[k] += v
        cr = s.get('census-crow')
        if cr:
            rows = [a + b for a, b in zip(rows, cr['_rows'])]
            by16 = [a + b for a, b in zip(by16, cr['_by16'])]
        mk = s.get('census-mask')
        if mk:
            for k, v in mk['_hex']:
                masks[k] += v
            mask_other += mk.get('other', 0) + mk.get('rest', 0)
        r = s.get('census-ro')
        if r:
            for k, v in r['_hex']:
                ro[k] += v
            ro_other += r.get('other', 0)
    return tot, rows, by16, masks, mask_other, ro, ro_other


def pct(a, b):
    return 100.0 * a / b if b else 0.0


def mask_name(m):
    return '+'.join(b for i, b in enumerate(BITS) if m & (1 << i)) or '(none)'


def report(label, selected, nruns):
    tot, rows, by16, masks, mask_other, ro, ro_other = total(selected)
    n = tot['draws']
    frames = 60 * len(selected)
    print(f'== {label}: {len(selected)} windows ({frames} frames), {n} draws ({n / frames if frames else 0:.0f}/frame), '
          f'clears {tot["clr"]}, skipped {tot["skip"]}')
    if not n:
        return None
    print('\nclass (first that applies)      draws      %   cum %')
    cum = 0
    for c in CLASSES:
        v = tot['cls_' + c]
        cum += v
        print(f'  {c:28s} {v:9d} {pct(v, n):6.1f} {pct(cum, n):6.1f}')
    reuse = tot['cls_same'] + tot['cls_dyn'] + tot['cls_uni']
    same = tot['cls_same']
    print(f'\n  reuse criterion   same+dyn+uni = {pct(reuse, n):5.1f}%  (>= 50% -> step 2, reuse)')
    print(f'  batch criterion   same         = {pct(same, n):5.1f}%  (>= 40% -> batching); '
          f'same+dyn = {pct(same + tot["cls_dyn"], n):5.1f}%')

    print('\ninput changed vs previous draw   draws      %')
    for b in BITS:
        print(f'  {b} {BIT_DOC[b]:40s} {tot[b]:9d} {pct(tot[b], n):6.1f}')

    print('\npath                             draws      %')
    for p in PATHS:
        print(f'  {p:30s} {tot["path_" + p]:9d} {pct(tot["path_" + p], n):6.1f}')
    print('create_pipeline outcome')
    for c in CPS:
        print(f'  {c:30s} {tot["cp_" + c]:9d} {pct(tot["cp_" + c], n):6.1f}')
    print(f'  {"bind_shaders called":30s} {tot["bs"]:9d} {pct(tot["bs"], n):6.1f}')
    print(f'  {"pipeline rebound":30s} {tot["pbind"]:9d} {pct(tot["pbind"], n):6.1f}')

    print('\ncost signals                     draws      %')
    doc = {
        'shc_in': 'entered with shader_bindings_changed',
        'shc_stale': '... shader binding unchanged',
        'shc_stale_full': '... and took the full path',
        'ubo_sets': 'UBO descriptor set written',
        'ubo_sets_samesb': '... shader binding unchanged',
        'uploads': 'uniform bytes uploaded',
        'uploads_same': '... same bytes, same binding',
        'reuse_full': 'same/dyn/uni draw on full path',
        'same_notsfp': 'same draw that missed SFP',
    }
    for c in COSTS:
        print(f'  {doc[c]:38s} {tot[c]:9d} {pct(tot[c], n):6.1f}')

    print('\nc[] rows changed per draw        draws      %')
    for name, v in zip(ROWS, rows):
        print(f'  {name:30s} {v:9d} {pct(v, n):6.1f}')
    print('c[] row block changed (16 rows each), % of draws:')
    print('  ' + ' '.join(f'c{16 * i}-{16 * i + 15}:{pct(v, n):.0f}' for i, v in enumerate(by16)))

    print('\ncommonest change masks           draws      %')
    for m, v in masks.most_common(20):
        print(f'  {mask_name(m):30s} {v:9d} {pct(v, n):6.1f}')
    print(f'  {"(outside the per-window top 24)":30s} {mask_other:9d} {pct(mask_other, n):6.1f}')

    if ro or ro_other:
        print('\nreg: other, by address (first 8 seen per window)')
        for a, v in ro.most_common(12):
            print(f'  0x{a:04X} {REGNAMES.get(a, ""):10s} {v:9d} {pct(v, n):6.1f}')
        print(f'  {"other":17s} {ro_other:9d}')

    if pct(reuse, n) >= 50:
        verdict = 'REUSE (step 2)'
    elif pct(same, n) >= 40:
        verdict = 'BATCHING'
    else:
        verdict = 'NEITHER (stop; recommend the recorder thread)'
    print(f'\nverdict: {verdict}\n')
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='+')
    ap.add_argument('--window', default='-2,13')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--per-mark', action='store_true')
    a = ap.parse_args()
    lo, hi = (float(x) for x in a.window.split(','))
    pooled = []
    for p in a.paths:
        sets, marks, init = read(logcat_of(p))
        sel = select(sets, marks, lo, hi, a.all)
        name = os.path.basename(os.path.normpath(p))
        print(f'# {name}: census={init} sets={len(sets)} marks={len(marks)} kept={len(sel)}')
        if a.per_mark:
            for _, mname in marks:
                report(f'{name} {mname}', [s for s in sel if s[3] == mname], 1)
        report(name, sel, 1)
        pooled += sel
    if len(a.paths) > 1:
        report('pooled', pooled, len(a.paths))


if __name__ == '__main__':
    sys.exit(main())
