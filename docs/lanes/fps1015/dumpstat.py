#!/usr/bin/env python3
"""Per-frame draw census of a frame dump (framedump_*.jsonl, schema 4+):
draws, submits (command-buffer finishes), colour-target switches, and the
blended draws (NV_PGRAPH_BLEND_EN, bit 3 of "rs.blend") by kind, blend
factors, vertex count and colour target. With --by-target, blended draws a
frame per colour target and its size.

A dump carries no vertex positions unless armed with `vtxNN`, so it cannot
give pixel area; the colour target size and the vertex count are the proxies.
Usage:

    dumpstat.py FRAMEDUMP.jsonl [--by-target] [--top N]
"""
import argparse
import collections
import json
import sys

PRIM = {0: 'end', 1: 'points', 2: 'lines', 3: 'line_loop', 4: 'line_strip',
        5: 'tris', 6: 'tri_strip', 7: 'tri_fan', 8: 'quads', 9: 'quad_strip',
        10: 'polygon'}
FACT = ['0', '1', 'sc', '1-sc', 'sa', '1-sa', 'da', '1-da', 'dc', '1-dc',
        'sat', '?11', 'cc', '1-cc', 'ca', '1-ca']


def blend_name(b):
    return '%s+%s' % (FACT[(b >> 4) & 0xF], FACT[(b >> 8) & 0xF])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dump')
    ap.add_argument('--by-target', action='store_true')
    ap.add_argument('--top', type=int, default=8)
    a = ap.parse_args()

    fr = collections.defaultdict(collections.Counter)
    sub = {}
    modes = collections.Counter()
    targets = collections.Counter()
    last_color = {}
    with open(a.dump, errors='replace') as f:
        for line in f:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get('t') != 'draw':
                continue
            n = o['f']
            c = fr[n]
            c['draws'] += 1
            s = o.get('submits')
            if s is not None:
                lo, hi = sub.get(n, (s, s))
                sub[n] = (min(lo, s), max(hi, s))
            col = o.get('color') or {}
            key = (col.get('addr'), col.get('w'), col.get('h'))
            if last_color.get(n) != key:
                c['target_switches'] += 1
                last_color[n] = key
            b = int((o.get('rs') or {}).get('blend', '0x0'), 16)
            verts = o.get('count', 0)
            c['verts'] += verts
            if b & 0x8:
                c['blended'] += 1
                c['blended_verts'] += verts
                c['blended_' + o['kind']] += 1
                modes[(o['kind'], blend_name(b), PRIM.get(o['prim'], o['prim']))] += 1
                tk = '%sx%s @%s' % (col.get('w'), col.get('h'), col.get('addr'))
                targets[tk] += 1
                if col.get('w') and col.get('h'):
                    c['blended_target_px'] += col['w'] * col['h']

    frames = sorted(fr)
    nf = len(frames) or 1
    for n in frames:
        lo, hi = sub.get(n, (0, 0))
        fr[n]['submits'] = hi - lo
    # a frame's submits are the span between its first and its last draw;
    # the finish that ends the frame shows up in the next frame's first draw
    span = [sub[frames[i + 1]][0] - sub[frames[i]][0]
            for i in range(len(frames) - 1) if frames[i] in sub
            and frames[i + 1] in sub and frames[i + 1] == frames[i] + 1]

    keys = ['draws', 'verts', 'target_switches', 'blended', 'blended_verts',
            'blended_inline_array', 'blended_inline_elements',
            'blended_draw_arrays', 'blended_inline_buffer',
            'blended_target_px']
    print('%d frames' % len(frames))
    for k in keys:
        vals = [fr[n][k] for n in frames]
        if not any(vals):
            continue
        print('  %-24s mean %10.1f  min %9d  max %9d'
              % (k, sum(vals) / nf, min(vals), max(vals)))
    if span:
        print('  %-24s mean %10.1f  min %9d  max %9d'
              % ('submits frame-to-frame', sum(span) / len(span), min(span),
                 max(span)))
    print('blended draws a frame by kind, blend (src+dst), primitive:')
    for k, v in modes.most_common(a.top):
        print('  %7.1f  %s' % (v / nf, ' '.join(str(x) for x in k)))
    if a.by_target:
        print('blended draws a frame by colour target:')
        for k, v in targets.most_common(a.top):
            print('  %7.1f  %s' % (v / nf, k))
    return 0


if __name__ == '__main__':
    sys.exit(main())
