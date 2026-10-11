#!/usr/bin/env python3
"""Copy a capture's raw frame data into the lane dir, for later lanes.

    archive.py <result dir> [...]

Writes docs/lanes/frametrace/captures/<result id>/:
  frames.csv.gz   every frame row of the frametrace CSV(s) whose flip time
                  falls inside the run (other sessions' CSVs, pulled because
                  the env outlived their run, are left out: their t_ns is
                  outside this run's [hakuX-ft1] clock range)
  ft.log.gz       the [hakuX-ft1] summaries and [hakuX-ft] hitch blocks
  meta.md         title, device, ref, env, the mark line, file sources
"""
import glob
import gzip
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    for d in sys.argv[1:]:
        d = d.rstrip('/')
        rid = os.path.basename(d)
        out = os.path.join(HERE, 'captures', rid)
        os.makedirs(out, exist_ok=True)
        res = json.load(open(os.path.join(d, 'result.json')))
        ft, tms = [], []
        for l in open(os.path.join(d, 'logcat.txt'), errors='replace'):
            if '[hakuX-ft1]' in l or '[hakuX-ft]' in l:
                ft.append(l)
                m = re.search(r' t_ms=([\d.]+)', l)
                if m:
                    tms.append(float(m[1]))
        lo = (min(tms) - 5000) * 1e6 if tms else None
        hi = (max(tms) + 5000) * 1e6 if tms else None
        with gzip.open(os.path.join(out, 'ft.log.gz'), 'wt') as f:
            f.writelines(ft)
        kept, srcs, hdr = 0, [], None
        with gzip.open(os.path.join(out, 'frames.csv.gz'), 'wt') as g:
            for c in sorted(glob.glob(os.path.join(d, 'pulled',
                                                   'frametrace_*.csv'))):
                n = 0
                with open(c) as f:
                    h = f.readline()
                    if hdr is None:
                        hdr = h
                        g.write(h)
                    for row in f:
                        t = row.split(',', 2)[1]
                        if lo is None or lo <= int(t) <= hi:
                            g.write(row)
                            n += 1
                srcs.append('%s: %d rows kept' % (os.path.basename(c), n))
                kept += n
        mark = ''
        for l in open(os.path.join(d, 'run.log'), errors='replace'):
            if 'mark gameplay' in l:
                mark = l.strip()
                break
        with open(os.path.join(out, 'meta.md'), 'w') as f:
            f.write('result %s\ntitle %s\ndevice %s\nref %s\nenv %s\n'
                    'mark %s\n%s\n' % (rid, res.get('title'),
                                       res.get('device_label'), res.get('ref'),
                                       ' '.join(res.get('env') or []), mark,
                                       '\n'.join(srcs)))
        print('%s: %d frames, %d ft lines -> %s' % (rid, kept, len(ft), out))


if __name__ == '__main__':
    main()
