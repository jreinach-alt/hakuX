#!/usr/bin/env python3
"""Does the PFIFO thread's unhooked wait track the render thread's fence wait?

    rtjoin.py <result dir or captures/<id>> [--site 0x536104] [--delay 20] [--until HH:MM:SS]

Why: from f2763fe4c0 the Vulkan interposer books every fence wait by call
site. On Forza and Nightfire the PFIFO row keeps 8-12 ms a frame of blocked
time that no hook books, and the render thread (row `o`, unregistered) waits
about as long at render_thread.c:157 -- process_finish's fence wait for a
non-deferred finish, whose PFIFO side is draw.c:4319,
qemu_event_wait(&finish_event): an event wait, which the interposer cannot
see. Equal means are not a join. If that event wait is the PFIFO's unbooked
time, the two move together second by second with a slope near 1; a mutex
(pfifo.c 1713/1727/1784/1808, NOTES section 10's alternative) would not
follow the render thread's fence.

Per [hakuX-ft1] summary line (about 1 s): the site's ms/frame from `fw=`
(since the previous line), against the mean over the frames since the
previous line of the PFIFO's unbooked blocked time
(p_blk - pidle - the PFIFO's named waits), and of its idle. Prints the
means, the correlation, and the least-squares slope and intercept.
The window is ftread.py's (mark + delay, to --until).
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ftread  # noqa: E402
from chain import corr  # noqa: E402


def site_slots(sites, pc):
    return {s for s, desc in sites.items() if ' pc=%s ' % pc in desc + ' '}


def fit(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    if not sxx:
        return float('nan'), float('nan')
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sxx
    return b, my - b * mx


def punbooked(f):
    named = sum(f['p_' + w] for w in ftread.W if w != 'idle')
    u = f['p_blk'] - f['pidle'] - named
    return u if u > 0 else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('d')
    ap.add_argument('--site', default='0x536104')
    ap.add_argument('--delay', type=int, default=20)
    ap.add_argument('--until')
    a = ap.parse_args()
    csvs, logs = ftread.find_files(a.d, [])
    frames = []
    for p in csvs:
        frames += ftread.read_frames(p)
    anchors, pace, mark, summ, _, sites = ftread.read_logs(logs, a.d)
    if mark is None or not ftread.wall_of(frames, anchors, pace):
        print('VOID: no window')
        return 1
    t0 = mark + a.delay
    t1 = ftread.secs(*a.until.split(':')) if a.until else float('inf')
    slots = site_slots(sites, a.site)
    if not slots:
        print('VOID: no site line names pc=%s' % a.site)
        return 1
    rows = []
    prev = None
    fi = 0
    frames.sort(key=lambda f: f['wall'])
    for wall, line in summ:
        if prev is None or wall < t0 or wall > t1:
            prev = wall
            continue
        fw = re.search(r' fw=(\S*)', line)
        if fw is None:
            prev = wall
            continue
        site_ms = 0.0
        for ent in fw.group(1).split(','):
            m = re.match(r'[^#]+#(\d+):([\d.]+)/', ent)
            if m and int(m.group(1)) in slots:
                site_ms += float(m.group(2))
        while fi < len(frames) and frames[fi]['wall'] <= prev:
            fi += 1
        seg = []
        j = fi
        while j < len(frames) and frames[j]['wall'] <= wall:
            seg.append(frames[j])
            j += 1
        prev = wall
        if len(seg) < 5:
            continue
        rows.append((site_ms, sum(punbooked(f) for f in seg) / len(seg) / 1000.0,
                     sum(f['pidle'] for f in seg) / len(seg) / 1000.0))
    if len(rows) < 10:
        print('VOID: %d seconds in the window' % len(rows))
        return 1
    x = [r[0] for r in rows]
    y = [r[1] for r in rows]
    z = [r[2] for r in rows]
    b, c = fit(x, y)
    print('site pc=%s (slots %s): %d one-second lines' % (a.site, sorted(slots), len(rows)))
    print('  render-thread fence wait at the site, ms/frame: mean %.2f' % (sum(x) / len(x)))
    print('  PFIFO unbooked blocked, ms/frame:               mean %.2f' % (sum(y) / len(y)))
    print('  corr(site, PFIFO unbooked) = %.2f; slope %.2f, intercept %.2f ms' % (corr(x, y), b, c))
    print('  corr(site, PFIFO idle)     = %.2f  (control: a wait the PFIFO is not in)' % corr(x, z))
    return 0


if __name__ == '__main__':
    sys.exit(main())
