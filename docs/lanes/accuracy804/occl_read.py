#!/usr/bin/env python3
"""Summarise the [occl804] lines (HAKUX_OCCL_LOG, reports.c) of one or more logcats.

usage: occl_read.py LOGCAT [LOGCAT ...] [--from HH:MM:SS] [--to HH:MM:SS]

Per logcat: logged guest frames, frames with any query, frames with pend > 0
(submitted frames still on the GPU at the read), queries read and the share
nonzero, reports handed to the guest and the share nonzero, and frames whose
reports were ALL zero while queries were read. Then, for the frames with the
large (> 2) query batches, how often report slot k flips between zero and
nonzero from one batch to the next (a period-2 flip is what a stale read of
the previous command buffer's slot gives a visibility-gated draw).
"""
import re
import sys

LINE = re.compile(r'^\S+ (\S+) .*\[occl804\] f=(\d+) wait=(\d) procs=(\d+) q=(\d+) '
                  r'qnz=(\d+) pend=(\d+) rep=(\d+) repnz=(\d+) repmax=(\d+) v=(\S+)')


def read(path, t_from, t_to):
    rows = []
    with open(path, errors='replace') as f:
        for ln in f:
            m = LINE.match(ln)
            if not m:
                continue
            t = m.group(1)[:8]
            if (t_from and t < t_from) or (t_to and t > t_to):
                continue
            g = m.groups()
            vals = [] if g[10] == '-' else [int(x) for x in g[10].split(',')]
            rows.append(dict(t=m.group(1), f=int(g[1]), wait=int(g[2]), procs=int(g[3]),
                             q=int(g[4]), qnz=int(g[5]), pend=int(g[6]), rep=int(g[7]),
                             repnz=int(g[8]), repmax=int(g[9]), v=vals))
    return rows


def summarise(path, rows):
    print(f'== {path}')
    if not rows:
        print('  no [occl804] frame lines: a void capture, not a pass')
        return
    wait = {r['wait'] for r in rows}
    withq = [r for r in rows if r['q']]
    big = [r for r in rows if r['q'] > 2]
    q = sum(r['q'] for r in rows)
    qnz = sum(r['qnz'] for r in rows)
    rep = sum(r['rep'] for r in rows)
    repnz = sum(r['repnz'] for r in rows)
    print(f'  wait={sorted(wait)} frames={len(rows)} ({rows[0]["t"]} .. {rows[-1]["t"]})'
          f' frames_with_queries={len(withq)} big_batches(q>2)={len(big)}')
    print(f'  pend>0 frames={sum(1 for r in rows if r["pend"])}  pend max={max(r["pend"] for r in rows)}')
    print(f'  queries={q} nonzero={qnz} ({100.0 * qnz / max(q, 1):.1f}%)'
          f'  reports={rep} nonzero={repnz} ({100.0 * repnz / max(rep, 1):.1f}%)')
    allzero_big = sum(1 for r in big if r['repnz'] == 0)
    print(f'  big batches with every report 0: {allzero_big} of {len(big)}')
    # slot-wise zero/nonzero flips between successive big batches
    flips = same = 0
    for a, b in zip(big, big[1:]):
        for x, y in zip(a['v'], b['v']):
            if (x == 0) != (y == 0):
                flips += 1
            else:
                same += 1
    print(f'  slot zero<->nonzero flips between successive big batches: {flips} of {flips + same}'
          f' ({100.0 * flips / max(flips + same, 1):.1f}%)')


def main():
    args = sys.argv[1:]
    t_from = t_to = None
    if '--from' in args:
        i = args.index('--from'); t_from = args[i + 1]; del args[i:i + 2]
    if '--to' in args:
        i = args.index('--to'); t_to = args[i + 1]; del args[i:i + 2]
    for p in args:
        summarise(p, read(p, t_from, t_to))


if __name__ == '__main__':
    main()
