#!/usr/bin/env python3
"""Read the [lock474] lines (and gfps) of one or more soaks over a window.

    python3 lockread.py [--from S] [--to S] <result-id> [...]

Seconds are from logcat line 1, as in docs/lanes/ghoul311/gfps.py. Per run:
the vCPU's PGRAPH read/write lock wait as a share of wall time, its split by
the puller's phase (fs = FLIP_STALL's surface_update, fo = its flip_stall op,
ot = anything else), the registers read, and the gfps median. PGRAPH register
offsets are named where hw/xbox/nv2a/nv2a_regs.h names them.
"""
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from statistics import median

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'
REGS_H = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      '../../../hw/xbox/nv2a/nv2a_regs.h')


def ts(l):
    return datetime.strptime('2026-' + l[:18], '%Y-%m-%d %H:%M:%S.%f')


def reg_names():
    # 0x700 is PGRAPH_STATUS in nouveau's nv04+ map; nv2a_regs.h does not name
    # it and nothing in hw/xbox/nv2a writes it, so it always reads 0 (idle).
    names = {0x700: 'STATUS (nouveau name; never written)'}
    try:
        for l in open(REGS_H):
            m = re.match(r'#define\s+(NV_PGRAPH_\w+)\s+0x([0-9A-Fa-f]+)\s*$', l)
            if m:
                names.setdefault(int(m.group(2), 16), m.group(1)[3:])
    except OSError:
        pass
    return names


def read(run, lo, hi):
    L = open(R + run + '/logcat.txt', errors='replace').read().splitlines()
    t0 = ts(L[1])
    rows, gfps = [], []
    for l in L:
        if 'hakuX-perf' not in l:
            continue
        try:
            s = (ts(l) - t0).total_seconds()
        except ValueError:
            continue
        if not lo <= s <= hi:
            continue
        if '[lock474]' in l:
            kv = dict(re.findall(r'(\w+)=([0-9.]+)\b', l))
            regs = re.findall(r'r\d=0x([0-9a-f]+):(\d+):([0-9.]+)', l)
            rows.append((s, {k: float(v) for k, v in kv.items()}, regs))
            continue
        m = re.search(r'gfps[= ]([\d.]+)', l)
        if m:
            gfps.append(float(m.group(1)))
    return rows, gfps


def main():
    args = sys.argv[1:]
    lo, hi = 151.0, 288.0
    while args and args[0].startswith('--'):
        k, v = args.pop(0), float(args.pop(0))
        if k == '--from':
            lo = v
        elif k == '--to':
            hi = v
    names = reg_names()
    for run in args:
        rows, gfps = read(run, lo, hi)
        print(f'{run}  window {lo:.0f}-{hi:.0f} s: {len(rows)} [lock474] '
              f'lines, {len(gfps)} gfps lines')
        if gfps:
            print(f'  gfps median {median(gfps):.1f} (min {min(gfps):.1f}, '
                  f'max {max(gfps):.1f}, n={len(gfps)})')
        if not rows:
            continue
        tot = defaultdict(float)
        for _, kv, _ in rows:
            for k, v in kv.items():
                tot[k] += v
        wall = tot['dt_ms']
        rd = tot['rd_wait_ms']
        wr = tot['wr_wait_ms']
        print(f'  wall {wall / 1000:.1f} s; reads {tot["rd"]:.0f} '
              f'({tot["rd"] / wall * 1000:.0f}/s), writes {tot["wr"]:.0f}')
        print(f'  read wait  {rd / 1000:.2f} s = {rd / wall:.3f} of wall; '
              f'fs {tot["rd_fs"] / max(rd, 1e-9):.2f} fo '
              f'{tot["rd_fo"] / max(rd, 1e-9):.2f} ot '
              f'{tot["rd_ot"] / max(rd, 1e-9):.2f}; slow (>=1 ms) '
              f'{tot["rd_slow"]:.0f}')
        print(f'  write wait {wr / 1000:.2f} s = {wr / wall:.3f} of wall; '
              f'fs {tot["wr_fs"] / max(wr, 1e-9):.2f} fo '
              f'{tot["wr_fo"] / max(wr, 1e-9):.2f} ot '
              f'{tot["wr_ot"] / max(wr, 1e-9):.2f}')
        if tot['flips']:
            print(f'  flips {tot["flips"]:.0f} ({tot["flips"] / wall * 1000:.1f}/s); '
                  f'per flip surface_update {tot["flip_surf_ms"] / tot["flips"]:.1f} ms, '
                  f'flip_stall op {tot["flip_op_ms"] / tot["flips"]:.1f} ms')
        if 'rd_unl' in tot:
            # Present from the counter's second version on; zero on any build
            # that never releases the lock across a fence wait.
            print(f'  served inside a lock-released fence wait: reads '
                  f'{tot["rd_unl"]:.0f}, writes {tot["wr_unl"]:.0f}')
        reg_n, reg_w = defaultdict(float), defaultdict(float)
        for _, _, regs in rows:
            for a, n, w in regs:
                reg_n[int(a, 16)] += float(n)
                reg_w[int(a, 16)] += float(w)
        print(f'  registers (top {max(len(r) for _, _, r in rows)} per line, summed):')
        for a in sorted(reg_n, key=lambda a: -reg_w[a])[:8]:
            print(f'    0x{a:04x} {names.get(a, "?"):32s} n={reg_n[a]:.0f} '
                  f'wait {reg_w[a] / 1000:.2f} s = {reg_w[a] / max(rd, 1e-9):.2f} of read wait')


if __name__ == '__main__':
    main()
