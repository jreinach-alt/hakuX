#!/usr/bin/env python3
"""Per-second table from a plain (non-perflog) hakuX logcat: fps, worst frame,
texture uploads/converts, shader and pipeline cache misses, GPU ms, draws.

Answers "is a dip a texture upload/convert, a shader or pipeline compile, or a
surface readback?" for any second where fps falls.

    python3 dips433.py <logcat.txt>
"""
import re
import sys

KV = re.compile(r'(\w+)=([-\d.]+)')


def main(path):
    rows, cur = [], {}
    for line in open(path, errors='replace'):
        ts = line[6:18]
        if 'hakuX-pace:' in line:
            if cur:
                rows.append(cur)
            kv = dict(KV.findall(line))
            ms = float(kv['ms'])
            cur = {'t': ts, 'f': int(kv['f']), 'ms': ms, 'max': float(kv['max'])}
        elif not cur:
            continue
        elif '[shd413]' in line:
            kv = dict(KV.findall(line))
            cur.update(pm=int(kv['dpm']), sm=int(kv['dsm']), vm=int(kv['dvm']),
                       pc=float(kv['dpc_ms']), fb=int(kv['dfb']))
        elif 'hakuX-stall: txu[' in line:
            m = re.search(r'txu\[n(\d+)/(\d+)K new(\d+) rb(\d+)', line)
            cur.update(txn=int(m[1]), txk=int(m[2]), txnew=int(m[3]), txrb=int(m[4]))
        elif 'hakuX-stall: RPBreaks' in line:
            m = re.search(r'sd\[ev\d+ noCb\d+ dl(\d+)', line)
            cur['sdl'] = int(m[1]) if m else 0
        elif 'hakuX-phase:' in line:
            g = re.search(r'GPU:([\d.]+)', line)
            t = re.search(r'Tot:([\d.]+)', line)
            cur.update(gpu=float(g[1]), tot=float(t[1]))
        elif 'xemu-work:' in line:
            m = re.search(r'BE:(\d+)', line)
            cur['be'] = int(m[1])
    if cur:
        rows.append(cur)
    prev = None
    print('time         fps  max_ms  draws/f  GPUms  txu_n  txu_K  new  rb  sfc_dl  pipe_miss  shd_miss  pc_ms')
    for r in rows:
        if prev is None:
            prev = r
            continue
        frames = r['f'] - prev['f']
        fps = frames * 1000.0 / r['ms'] if r['ms'] else 0
        dpf = r.get('be', 0) / frames if frames else 0
        print('%s %5.1f %7.1f %8.1f %6.1f %6d %6d %4d %3d %7d %10d %9d %6.1f' % (
            r['t'], fps, r['max'], dpf, r.get('gpu', 0), r.get('txn', 0), r.get('txk', 0),
            r.get('txnew', 0), r.get('txrb', 0), r.get('sdl', 0), r.get('pm', 0),
            r.get('sm', 0), r.get('pc', 0)))
        prev = r


if __name__ == '__main__':
    main(sys.argv[1])
