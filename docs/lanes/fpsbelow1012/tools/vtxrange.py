#!/usr/bin/env python3
"""Which runs on disk carry a `range` download that is not the texture scan (lane.fpsbelow1012, NOTES.md section 10).

`[sdcall] range=` counts every caller of pgraph_vk_download_surfaces_in_range_if_dirty() under one name:
create_texture's scan (texture.c), the vertex-RAM sync (vertex.c, via draw.c's gpu_stale test), image blits and
lines (blit.c). `txr[... scdl<n>]` (hakuX-stall) is the scan's own share, so a window whose `range` downloads come
with `scdl` near 0 is the vertex sync or a blit (NOSCAN). The census cannot split those two; HAKUX_RANGELOG's
[sdrange] line can (surface.c). The vtx column is `[rdc] vtx=<calls>`: DIRECT TLB walks, one per dirty vertex sync
without HAKUX_DRAWREC, one per run of owed pages with it. It says vertex syncs ran, not how many.

Usage: vtxrange.py [results dir] [--since <id prefix>]   Prints one row per run: title, windows, medians per
60 frames of range dl, range fin, range wait ms, scan dl, vtx walks; and the class guess.
"""
import json, os, re, statistics, sys

RES = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else '/home/justin/hakux-work/dispatch/results'

def med(xs):
    return statistics.median(xs) if xs else None

def scan(d):
    p = os.path.join(d, 'logcat.txt')
    try:
        f = open(p, errors='replace')
    except OSError:
        return None
    rng, scdl, vtx = [], [], []
    for l in f:
        if '[sdcall]' in l:
            fr = re.search(r'frames=(\d+)', l)
            m = re.search(r'range=fin(\d+)/fence\d+/pre\d+/dl(\d+)/([\d.]+)ms', l)
            n = int(fr.group(1)) if fr else 60
            if m and n:
                rng.append((int(m.group(2)) * 60 / n, int(m.group(1)) * 60 / n, float(m.group(3)) * 60 / n))
            elif n:
                rng.append((0, 0, 0))
        elif 'txr[' in l:
            m = re.search(r'scdl(\d+)', l)
            if m:
                scdl.append(int(m.group(1)))
        elif '[rdc]' in l:
            m = re.search(r'f=(\d+) .* vtx=(\d+)/', l)
            if m and int(m.group(1)):
                vtx.append(int(m.group(2)) * 60 / int(m.group(1)))
    f.close()
    if len(rng) < 20:
        return None
    # the busy half: windows past the median of range downloads, so menus do not dilute a play window
    r = sorted(rng)[len(rng) // 2:]
    return dict(n=len(rng), dl=med([x[0] for x in r]), fin=med([x[1] for x in r]), ms=med([x[2] for x in r]),
                scdl=med(sorted(scdl)[len(scdl) // 2:]) if scdl else None,
                vtx=med(sorted(vtx)[len(vtx) // 2:]) if vtx else None)

def main():
    since = None
    if '--since' in sys.argv:
        since = sys.argv[sys.argv.index('--since') + 1]
    rows = []
    for e in sorted(os.listdir(RES)):
        d = os.path.join(RES, e)
        rq = os.path.join(d, 'request.json')
        if not os.path.isfile(rq):
            continue
        if since and os.path.getmtime(rq) < os.path.getmtime(os.path.join(RES, since, 'request.json')):
            continue
        try:
            j = json.load(open(rq))
        except Exception:
            continue
        if j.get('kind', 'soak') not in ('soak', None) and not j.get('title'):
            continue
        s = scan(d)
        if not s or not s['dl'] or s['dl'] < 60:
            continue
        cls = '?'
        if s['scdl'] is not None and s['vtx'] is not None:
            if s['scdl'] < 0.1 * s['dl']:
                cls = 'NOSCAN'
            elif s['scdl'] >= 0.5 * s['dl']:
                cls = 'SCAN'
            else:
                cls = 'MIXED'
        rows.append((j.get('title', '?')[:40], e, s, cls))
    for t, e, s, cls in rows:
        f = lambda v: '-' if v is None else '%.0f' % v
        print('%-40s %-44s n%-4d dl%-5s fin%-5s %5sms scdl%-5s vtx%-5s %s' % (
            t, e, s['n'], f(s['dl']), f(s['fin']), f(s['ms']), f(s['scdl']), f(s['vtx']), cls))

if __name__ == '__main__':
    main()
