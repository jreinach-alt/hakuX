#!/usr/bin/env python3
"""The natural experiment on disk: every title soak of a title, its regimen,
its GPU clock samples and its frame rate after `mark gameplay`.

    survey.py <title substring> [--dir RESULTS] [--tsv out.tsv]

Per run: device, ref, regimen and the performance_mode it ran at (the GPU
floor: 0 -> 401 MHz, 1 -> 550, 2 -> 615; perfregimen NOTES 5a/5d), whether it
is a perflog build (hakuX-phase lines), the gfps median over the gameplay
window, the phase GPU ms median (perflog only), and the gpuclk samples
thermal.jsonl took inside the window (every 30 s: a distribution, not a
trace), with the battery's charge state.

Read with care: the builds, routes and lanes differ between runs. A clock
effect read from this table is a hypothesis for the controlled ladder, never
its result.
"""
import argparse, json, os, re, statistics

ap = argparse.ArgumentParser()
ap.add_argument('title')
ap.add_argument('--dir', default='/home/justin/hakux-work/dispatch/results')
ap.add_argument('--tsv')
a = ap.parse_args()

TS = re.compile(r'^\d+-\d+ (\d+):(\d+):([\d.]+) ')


def secs(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def lit(v):
    # thermal.jsonl stores some fields as Python reprs.
    if isinstance(v, str):
        try:
            import ast
            return ast.literal_eval(v)
        except Exception:
            return None
    return v


rows = []
for d in sorted(os.listdir(a.dir)):
    p = os.path.join(a.dir, d)
    try:
        r = json.load(open(os.path.join(p, 'result.json')))
    except Exception:
        continue
    if a.title.lower() not in str(r.get('title') or '').lower():
        continue
    try:
        runlog = open(os.path.join(p, 'run.log'), errors='replace').read()
    except OSError:
        continue
    mk = re.search(r'ROUTE (\d+):(\d+):([\d.]+) mark gameplay', runlog)
    reg = pm = None
    try:
        pr = json.load(open(os.path.join(p, 'perf_regimen.json')))
        reg, pm = pr.get('regimen'), pr.get('perf_mode')
    except Exception:
        pass
    mark = secs(*mk.groups()) if mk else None
    gf, ph = [], []
    t_last = None
    try:
        for line in open(os.path.join(p, 'logcat.txt'), errors='replace'):
            m = TS.match(line)
            if not m:
                continue
            t = secs(*m.groups())
            t_last = t
            if mark is None or t < mark:
                continue
            if 'gfps=' in line:
                g = re.search(r'gfps=(\d+)', line)
                gf.append(float(g.group(1)))
            elif 'hakuX-phase' in line:
                g = re.search(r'GPU:([\d.]+)', line)
                if g:
                    ph.append(float(g.group(1)))
    except OSError:
        pass
    clk, batt, hot = [], set(), []
    try:
        for l in open(os.path.join(p, 'thermal.jsonl')):
            s = json.loads(l)
            dt = s.get('dev_time')
            if not dt or mark is None:
                continue
            t = secs(*re.match(r'\d+-\d+ (\d+):(\d+):(\d+)', dt).groups())
            if t < mark:
                continue
            c = lit(s.get('clk')) or {}
            g = (c.get('gpu') or {}).get('gpuclk')
            if isinstance(g, int):
                clk.append(g // 1000000)
            pw = lit(s.get('pw')) or {}
            st = (pw.get('battery') or {}).get('status')
            if st:
                batt.add(st)
    except OSError:
        pass
    rows.append(dict(run=d, dev=r.get('device_label'), ref=r.get('ref'), reg=reg, pm=pm,
                     perflog=bool(ph), mark=mark is not None, n_gf=len(gf), gfps=med(gf),
                     gpu_ms=med(ph), clk=clk, batt='/'.join(sorted(batt)), env=','.join(r.get('env') or [])))

fmt = '%-48s %-5s %-10s %-8s %-3s %-4s %5s %6s %6s  %-14s %s'
print(fmt % ('run', 'dev', 'ref', 'regimen', 'pm', 'plog', 'n_gf', 'gfps', 'GPUms', 'battery', 'gpuclk MHz samples in gameplay'))
for x in rows:
    print(fmt % (x['run'][:48], x['dev'], (x['ref'] or '')[:10], x['reg'], x['pm'], 'Y' if x['perflog'] else '-',
                 x['n_gf'], '%.1f' % x['gfps'] if x['gfps'] is not None else '-',
                 '%.1f' % x['gpu_ms'] if x['gpu_ms'] is not None else '-', x['batt'][:14],
                 ' '.join(str(c) for c in x['clk']) if x['mark'] else 'NO MARK'))
if a.tsv:
    with open(a.tsv, 'w') as f:
        f.write('run\tdev\tref\tregimen\tpm\tperflog\tgfps\tgpu_ms\tclk\tbattery\tenv\n')
        for x in rows:
            f.write('\t'.join(str(v) for v in (x['run'], x['dev'], x['ref'], x['reg'], x['pm'], x['perflog'],
                                               x['gfps'], x['gpu_ms'], ' '.join(map(str, x['clk'])), x['batt'], x['env'])) + '\n')
