#!/usr/bin/env python3
"""Join [rr425w] guest-idle windows to frametrace frames (the G1 gap, in-row).

    idlejoin.py <result dir> [--delay 20]

Without the guest-idle hook (G1) the frame record books the guest's idle loop
as vCPU on-CPU time, so a title that idles by spinning reads `run`. The
always-on [rr425w] line has the idle loop's wall time per 2-s window
(`idle_us`, from STI at the idle pc to the interrupt that ends it, booked
whole in the window it ends in) and which interrupt ended it. This spreads
each window's idle over its frames and re-asks rule step 2 (guest work +
run queue > deadline) with guest work = vCPU on-CPU - idle.

Per window: frames, late share, vCPU on-CPU ms/frame, idle ms/frame, guest
work ms/frame, and the idle by waking vector (30 = PIT timer, 33 = NV2A).
Then the late frames re-read: how many still exceed the deadline on guest
work alone, using (a) the window's mean idle per frame, (b) the bound where
all the window's idle sits in its late frames (the most favourable to "not
run"). A window-mean split is not a frame record: it is the bracket the
frame record would fall in, and the G1 hook is what replaces it.
"""
import argparse
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ftread  # noqa: E402

TS = re.compile(r'^\d+-\d+ (\d+):(\d+):([\d.]+) ')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('d')
    ap.add_argument('--delay', type=float, default=20.0)
    ap.add_argument('--capture', help='archived capture dir for the frames')
    a = ap.parse_args()
    csvs, logs = ftread.find_files(a.capture or a.d, False)
    frames = []
    for c in csvs:
        frames += ftread.read_frames(c)
    anchors, pace, mark = ftread.read_logs(logs, a.capture or a.d)[:3]
    if mark is None:
        mk = re.search(r'ROUTE (\d+):(\d+):([\d.]+) mark gameplay',
                       open(os.path.join(a.d, 'run.log'), errors='replace').read())
        mark = ftread.secs(*mk.groups())
    ftread.wall_of(frames, anchors, pace)
    t0 = mark + a.delay
    frames = [f for f in frames if f['wall'] >= t0]
    win = []
    for l in open(os.path.join(a.d, 'logcat.txt'), errors='replace'):
        if '[rr425w]' not in l:
            continue
        m = TS.match(l)
        t = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
        if t - 2.0 < t0:
            continue
        idle = int(re.search(r'idle_us=(\d+)', l)[1])
        byv = {}
        for vec, n, iu in re.findall(r' ([0-9a-f]{2})\.[0-9a-f]{2}:(\d+):(\d+):', l):
            byv[vec] = byv.get(vec, 0) + int(iu)
        win.append((t - 2.0, t, idle, byv))
    if not win:
        print('VOID: no [rr425w] lines in the window')
        return
    rows = []
    still_a = still_b = late_n = 0
    for a0, a1, idle, byv in win:
        fr = [f for f in frames if a0 < f['wall'] <= a1]
        if len(fr) < 5:
            continue
        D = max(f['ireq'] or 1 for f in fr) * statistics.median(f['vbp'] for f in fr) / 1000.0
        # period-late (profile.h since session 4): the CSV's `late` of an
        # older capture misses frames whose VBLANK the deferral held
        late = [f for f in fr if f['late'] or f['P'] * 20 > D * 1000 * 21]
        vrun = statistics.mean(f['v_run'] for f in fr) / 1000.0
        ipf = idle / 1000.0 / len(fr)
        rows.append((a1, len(fr), len(late) / len(fr), vrun, ipf, vrun - ipf,
                     byv.get('30', 0) / 1000.0 / len(fr),
                     byv.get('33', 0) / 1000.0 / len(fr)))
        for f in late:
            late_n += 1
            w = (f['v_run'] + f['v_rq']) / 1000.0
            if w - ipf > D:
                still_a += 1
            if w - idle / 1000.0 / len(late) > D:
                still_b += 1
    print('windows %d, frames %d, late %d' % (len(rows), sum(r[1] for r in rows), late_n))
    print()
    print('| | mean | p10 | p90 |')
    print('|---|---|---|---|')
    for i, name in ((3, 'vCPU on-CPU ms/frame'), (4, 'guest idle ms/frame'),
                    (5, 'guest work ms/frame (on-CPU - idle)'),
                    (6, 'idle ended by the timer (vec 30), ms/frame'),
                    (7, 'idle ended by the NV2A (vec 33), ms/frame'),
                    (2, 'late share')):
        v = sorted(r[i] for r in rows)
        print('| %s | %.2f | %.2f | %.2f |' % (
            name, statistics.mean(v), v[len(v) // 10], v[(9 * len(v)) // 10]))
    print()
    print('late frames whose guest work alone exceeds the deadline:')
    print('  (a) window-mean idle per frame: %d of %d (%.1f%%)' % (
        still_a, late_n, 100.0 * still_a / late_n if late_n else 0))
    print('  (b) all the window idle in its late frames: %d of %d (%.1f%%)' % (
        still_b, late_n, 100.0 * still_b / late_n if late_n else 0))
    # windows binned by late share: does guest work per frame cross the
    # deadline where the frames are late?
    print()
    print('| late share of the window | windows | guest work ms/frame | idle ms/frame | vCPU on-CPU ms/frame |')
    print('|---|---|---|---|---|')
    for lo, hi in ((0, .2), (.2, .5), (.5, .8), (.8, 1.01)):
        b = [r for r in rows if lo <= r[2] < hi]
        if b:
            print('| %.1f-%.1f | %d | %.2f | %.2f | %.2f |' % (
                lo, min(hi, 1), len(b), statistics.mean(r[5] for r in b),
                statistics.mean(r[4] for r in b), statistics.mean(r[3] for r in b)))
    # does lateness track guest work or idle across windows?
    if len(rows) > 3:
        def corr(x, y):
            mx, my = statistics.mean(x), statistics.mean(y)
            sx = sum((a - mx) ** 2 for a in x) ** .5
            sy = sum((b - my) ** 2 for b in y) ** .5
            return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy) if sx and sy else 0
        ls = [r[2] for r in rows]
        print('across windows, corr(late share, guest work/frame) %.2f; '
              'corr(late share, idle/frame) %.2f' % (
                  corr(ls, [r[5] for r in rows]), corr(ls, [r[4] for r in rows])))


if __name__ == '__main__':
    main()
