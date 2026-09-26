#!/usr/bin/env python3
"""Per-run gfps and [watch311] curves, seconds from the first hakuX-perf line."""
import datetime, glob, json, os, re, sys
R = '/home/justin/hakux-work/dispatch/results'
TS = r'(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)'
def t(s): return datetime.datetime.strptime('2026-' + s, '%Y-%m-%d %H:%M:%S.%f')
for i in sys.argv[1:]:
    d = [os.path.join(R, n) for n in os.listdir(R) if n.endswith(i)][0]
    req = json.load(open(os.path.join(d, 'request.json')))
    res = json.load(open(os.path.join(d, 'result.json'))) if os.path.exists(os.path.join(d, 'result.json')) else {}
    lc = sorted(glob.glob(os.path.join(d, 'logcat*.txt')))
    print('==', os.path.basename(d), req.get('device'), req.get('ref'), req.get('title', '')[:30], req.get('seconds'))
    print('   result keys:', {k: res[k] for k in list(res)[:12] if not isinstance(res[k], (dict, list))})
    perf, watch, crash = [], [], []
    for f in lc:
        for l in open(f, errors='replace'):
            m = re.match(TS + r'.*?hakuX-perf.*?gfps=(\d+) G:', l)
            if m: perf.append((t(m.group(1)), int(m.group(2))))
            m = re.match(TS + r'.*?\[watch311\] (.*)', l)
            if m: watch.append((t(m.group(1)), m.group(2).strip()))
            if re.search(r'FATAL|SIGSEGV|SIGABRT|Abort message|assertion', l): crash.append(l.strip()[:160])
    t0 = perf[0][0] if perf else (watch[0][0] if watch else None)
    if t0 is None:
        print('   no perf or watch lines'); continue
    print('   gfps:', ' '.join('%d:%d' % ((a - t0).total_seconds(), g) for a, g in perf))
    win = sorted(g for a, g in perf if 90 <= (a - t0).total_seconds() <= 240)
    if win: print('   gfps 90-240 s: n=%d median=%d min=%d' % (len(win), win[len(win) // 2], win[0]))
    for a, w in watch[::max(1, len(watch) // 25)] + watch[-1:]:
        print('   watch %+5ds %s' % ((a - t0).total_seconds(), w))
    print('   crash-ish lines:', len(crash), crash[:3])
    fr = sorted(glob.glob(os.path.join(d, 'frames', '*.png')))
    print('   frames:', len(fr))
