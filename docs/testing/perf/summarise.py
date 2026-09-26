#!/usr/bin/env python3
"""Summarise one perf run: guest pacing from the log, load from the sampler."""
import re, sys, os, statistics as st

def pacing(path):
    rows = []
    for line in open(path, errors='ignore'):
        m = re.search(r'gfps=(\d+) G:([\d.]+)\(([\d.]+)-([\d.]+)\) '
                      r'D:([\d.]+)\(([\d.]+)-([\d.]+)\) S:([\d.]+) J:([\d.]+) Df:(\d+)', line)
        if m:
            rows.append([float(x) for x in m.groups()])
    return rows

def load(path):
    samples, cur = [], None
    for line in open(path, errors='ignore'):
        line = line.strip()
        if line.startswith('---'):
            if cur: samples.append(cur)
            cur = {'t': int(line.split()[1]), 'threads': {}, 'gpu': {}}
        elif cur is None:
            continue
        elif line.startswith('thread '):
            p = line.split()
            if len(p) >= 5:
                try: cur['threads'][p[2] + '/' + p[1]] = int(p[3]) + int(p[4])
                except ValueError: pass
        else:
            p = line.split(None, 1)
            if len(p) == 2: cur['gpu'][p[0]] = p[1]
    if cur: samples.append(cur)
    return samples

def report(tag, d='/home/justin/hakux-work/perf'):
    plog, llog = f'{d}/{tag}.log', f'{d}/{tag}-load.txt'
    if not os.path.exists(plog):
        print(f'{tag}: no log'); return
    rows = pacing(plog)
    if not rows:
        print(f'{tag}: no pacing samples'); return
    g = [r[0] for r in rows]; gm = [r[1] for r in rows]
    dm = [r[4] for r in rows]; sw = [r[7] for r in rows]; df = [r[9] for r in rows]
    out = [f'guest fps med {st.median(g):.0f} (min {min(g):.0f} max {max(g):.0f})',
           f'game ms med {st.median(gm):.1f} (min {min(gm):.1f})',
           f'display ms med {st.median(dm):.2f}',
           f'swap ms med {st.median(sw):.1f}',
           f'defers med {st.median(df):.0f}']
    gpu = cpu = ''
    if os.path.exists(llog):
        s = load(llog)
        if len(s) >= 2:
            pct = [int(x['gpu'].get('gpu_pct', 0)) for x in s if x['gpu'].get('gpu_pct', '').isdigit()]
            clk = {int(x['gpu'].get('gpu_clk', 0)) // 1000000 for x in s if x['gpu'].get('gpu_clk', '').isdigit()}
            a, b = s[0], s[-1]; dt = (b['t'] - a['t']) / 1000.0
            th = sorted((((b['threads'][k] - a['threads'][k]) / 100.0) / dt * 100, k)
                        for k in b['threads'] if k in a['threads'])[::-1]
            th = [x for x in th if x[0] > 0.5]
            gpu = (f'GPU busy med {st.median(pct):.0f}% at {sorted(clk)} MHz' if pct else '')
            cpu = (f'hottest thread {th[0][0]:.0f}% ({th[0][1].split("/")[0]}), '
                   f'all threads {sum(x[0] for x in th):.0f}% of one core' if th else '')
    print(f'== {tag}')
    print('   ' + ' | '.join(out))
    if gpu: print(f'   {gpu}')
    if cpu: print(f'   {cpu}')

if __name__ == '__main__':
    for t in sys.argv[1:]:
        report(t)
