#!/usr/bin/env python3
"""The PFIFO thread's fence wait and what drives it, per window (#433).

Written AFTER the pilots' data arrived (drive_split.py, committed before it,
does not parse pw=/vw=/pm= or txw[]). It asks one question of a result dir:
in each 60-flip window, how much of the frame is the PFIFO thread asleep in
vkWaitForFences, and does that track the #474 drain (`txw faf`) ahead of the
surface-to-texture copies (`txw cp`)?

Per hakuX-pace window after `mark gameplay` (or all, with --all):

  fps        60 / (pace ms / 1000)
  Ri         hakuX-perf Ri (PFIFO park ms/flip, EWMA)
  faf_ms/n   txw[] faf: flush_all_frames ahead of a copy or upload,
             ms/flip and calls/flip (perflog only)
  cp_n       txw[] cp calls/flip (copy_surface_to_texture)
  up_n       txw[] up calls/flip (upload_texture_image)
  bt_ms      txw[] bt: pgraph_vk_bind_textures wall ms/flip
  s2t_n      GPUXFR s2t copies per frame (HAKUX_GPUXFR=1)
  prun pblk  [hakuX-ft1] PFIFO run / blocked ms per frame (HAKUX_FRAMETRACE=1)
  p_fence    [hakuX-ft1] pw[5]: PFIFO ms/frame in vkWaitForFences
  v_lock     [hakuX-ft1] vw[2]: vCPU ms/frame waiting for pgraph.lock
  vgw vgi    [hakuX-ft1] vCPU guest work / guest idle ms per frame
  gpu50      [hakuX-ft1] GPU ms per frame, median
  pm_run pm_bgpu pm_pgraph   [hakuX-ft1] frame classes, share of frames

Usage: ft_waits.py <result dir> [--all]
"""
import os
import re
import statistics
import sys
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drive_split import ts, kv, pid_of, over  # noqa: E402

# profile.h: wait index 2 = PGRAPH_LOCK, 5 = FENCE
W_PGRAPH_LOCK, W_FENCE = 2, 5


def main():
    rdir = sys.argv[1]
    include_all = '--all' in sys.argv
    lines = open(os.path.join(rdir, 'logcat.txt'), errors='replace').read().splitlines()
    pids = Counter(pid_of(l) for l in lines if 'hakuX-pace' in l)
    pid = pids.most_common(1)[0][0] if pids else None
    turnip = [l for l in lines if 'GPU: PurpleVK' in l or 'Loading custom Vulkan driver' in l
              or ('[gpl569]' in l and 'mode=' in l)]
    print('# turnip check: %s' % (turnip[0].strip() if turnip else 'NONE FOUND -- run does not count'))

    mark = None
    pace, perf, txw, xfr, ft1 = [], [], [], [], []
    for l in lines:
        t = ts(l)
        if t is None:
            continue
        if 'hakuX-route' in l and 'mark gameplay' in l and mark is None:
            mark = t
        if pid and '(' + pid + ')' not in l and '( ' + pid + ')' not in l:
            continue
        if 'hakuX-pace' in l and ' f=' in l:
            pace.append((t, kv(l.split('hakuX-pace', 1)[1])))
        elif 'hakuX-perf' in l and 'gfps=' in l:
            m = re.search(r'Ri:([\d.]+)', l)
            if m:
                perf.append((t, {'Ri': float(m.group(1))}))
        elif 'txw[' in l:
            m = re.search(r'bt([\d.]+)/[\d.]+ .* faf([\d.]+)/([\d.]+) .* cp([\d.]+)/([\d.]+) '
                          r'up([\d.]+)/([\d.]+)\]', l)
            if m:
                txw.append((t, {'bt_ms': float(m.group(1)), 'faf_ms': float(m.group(2)),
                                'faf_n': float(m.group(3)), 'cp_n': float(m.group(5)),
                                'up_n': float(m.group(7))}))
        elif 'xemu-xfr XFR nr ' in l:
            m = re.search(r' s2t [\d.]+ [\d.]+ [\d.]+ n([\d.]+)', l)
            if m:
                xfr.append((t, {'s2t_n': float(m.group(1))}))
        elif '[hakuX-ft1]' in l and ' pw=' in l:
            body = l.split('[hakuX-ft1]', 1)[1]
            d = {k: v for k, v in kv(body).items()
                 if k in ('prun', 'pblk', 'gpu50', 'vgw', 'vgi', 'n')}
            pw = re.search(r' pw=([\d.,]+)', body)
            vw = re.search(r' vw=([\d.,]+)', body)
            if pw:
                d['p_fence'] = float(pw.group(1).split(',')[W_FENCE])
            if vw:
                d['v_lock'] = float(vw.group(1).split(',')[W_PGRAPH_LOCK])
            pm = re.search(r' pm=([\w:,]+)', body)
            if pm:
                cls = dict((a, int(b)) for a, b in (x.split(':') for x in pm.group(1).split(',')))
                tot = sum(cls.values()) or 1
                for k in ('run', 'bgpu', 'pgraph'):
                    d['pm_' + k] = cls.get(k, 0) / tot
            ft1.append((t, d))

    print('# pid %s, mark gameplay %s, pace %d, txw %d, xfr %d, ft1 %d'
          % (pid, datetime.fromtimestamp(mark).strftime('%H:%M:%S') if mark else 'NONE',
             len(pace), len(txw), len(xfr), len(ft1)))
    cols = ['t', 'fps', 'Ri', 'faf_ms', 'faf_n', 'cp_n', 'up_n', 'bt_ms', 's2t_n', 'prun',
            'pblk', 'p_fence', 'v_lock', 'vgw', 'vgi', 'gpu50', 'pm_run', 'pm_bgpu', 'pm_pgraph']
    print('\t'.join(cols))
    rows = []
    prev_f = None
    for t, p in pace:
        f, ms = p.get('f'), p.get('ms', 0)
        nf = (f - prev_f) if prev_f is not None and f is not None else 60
        prev_f = f
        if ms <= 0 or nf <= 0:
            continue
        w0 = t - ms / 1e3
        if mark and not include_all and w0 < mark:
            continue
        r = {'t': datetime.fromtimestamp(t).strftime('%H:%M:%S'), 'fps': 1000.0 * nf / ms}
        for src in (perf, txw, xfr, ft1):
            r.update(over(src, w0 - 0.5, t + 0.5))
        rows.append(r)
        print('\t'.join('-' if r.get(c) is None else
                        ('%.2f' % r[c] if c.startswith('pm_') else '%.1f' % r[c])
                        if isinstance(r[c], float) else str(r[c]) for c in cols))

    bands = [('>=28.5', lambda x: x >= 28.5), ('26-28.5', lambda x: 26 <= x < 28.5),
             ('<26', lambda x: x < 26)]
    num = cols[1:]
    sys.stderr.write('band\tn\t' + '\t'.join(num) + '\n')
    for name, pred in bands:
        sel = [r for r in rows if pred(r['fps'])]
        meds = []
        for k in num:
            vals = [r[k] for r in sel if isinstance(r.get(k), (int, float))]
            meds.append(('%.2f' if k.startswith('pm_') else '%.1f') % statistics.median(vals)
                        if vals else '-')
        sys.stderr.write('%s\t%d\t%s\n' % (name, len(sel), '\t'.join(meds)))


if __name__ == '__main__':
    main()
