#!/usr/bin/env python3
"""Read lane.gpuclock's `[gpuclk433]` lines (NOTES section 2) out of soak
result dirs and answer NOTES section 3's questions.

    gpuclock.py RUN [RUN ...]                     one block per run
    gpuclock.py --pair LOW_RUN HIGH_RUN [...]     + the registered verdicts,
                                                  LOW/HIGH pairs in order
    gpuclock.py --blocks PF_DIR [...]             one held session switched by
                                                  capture_simpsons_gpuclock.sh: the
                                                  windows split by `gpuclock pm=`,
                                                  pm 0 as LOW and pm 2 as HIGH; pm 1
                                                  (floor 550), if switched to, joins
                                                  a three-level ladder fit
    [--skip S]  ignore the first S seconds after `mark gameplay`, and after
                each block switch (default 10)
    [--tsv F]   one row per window

Per window (one [gpuclk433] line, 60 guest frames): fps = frames / the wall
time since the previous line (logcat stamps), F = 1000 / fps, gms / grn the
GPU and render-pass ms per frame, MHz and busy the means of the window's
100 ms samples.

Per run: medians over the gameplay windows, the clock's time at each step,
mean busy, `hot` = share of samples at busy >= 90 with the clock under the
ceiling, and the step response: after a sample at busy >= 90 under the
ceiling, the 100 ms samples until the clock first rises (censored at the
next line's end). Thermal from thermal.jsonl: hottest zone and xo at the
first and last sample in the window, the C/min between them, pauses, the
lowest ceiling, battery status, and the vCPU core's (cpu7) clock range.

The verdict (pair): e = ln(gms_low/gms_high) / ln(MHz_high/MHz_low) on
window medians; clock-limited e >= 0.6, not <= 0.2. fps follows the GPU if
F_low - F_high >= 0.6 (gms_low - gms_high). The control: low arm MHz <= 450,
high arm >= 600, or the pair is inert. Fit gms = c + k/MHz over every window
of the pair (least squares), with its RMS residual and R^2.
"""
import argparse, ast, json, math, os, re, statistics, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'testing'))
try:
    import thermal_state
except Exception:
    thermal_state = None

ap = argparse.ArgumentParser()
ap.add_argument('runs', nargs='+')
ap.add_argument('--pair', action='store_true')
ap.add_argument('--blocks', action='store_true')
ap.add_argument('--skip', type=float, default=10.0)
ap.add_argument('--tsv')
a = ap.parse_args()

TS = re.compile(r'^\d+-\d+ (\d+):(\d+):([\d.]+) ')


def secs(h, m, s):
    return int(h) * 3600 + int(m) * 60 + float(s)


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def lit(v):
    if isinstance(v, str):
        try:
            return ast.literal_eval(v)
        except Exception:
            return None
    return v


def f(x, p=1):
    return '-' if x is None else ('%.' + str(p) + 'f') % x


def read_run(d, block=None):
    try:
        runlog = open(os.path.join(d, 'run.log'), errors='replace').read()
    except OSError:
        runlog = ''
    mk = re.search(r'ROUTE (\d+):(\d+):([\d.]+) mark gameplay', runlog)
    if not mk:
        # a pathfind hold writes its mark to logcat (hakuX-route)
        for line in open(os.path.join(d, 'logcat.txt'), errors='replace'):
            if 'hakuX-route' in line and 'mark gameplay' in line:
                mk = TS.match(line)
                break
    end = None
    info = {'dir': d, 'name': os.path.basename(d.rstrip('/')), 'init': None, 'mark': bool(mk)}
    try:
        info['regimen'] = json.load(open(os.path.join(d, 'perf_regimen.json')))
    except Exception:
        info['regimen'] = {}
    try:
        info['result'] = json.load(open(os.path.join(d, 'result.json')))
    except Exception:
        info['result'] = {}
    mark = secs(*mk.groups()) if mk else None
    wins, prev_t = [], None
    pm, pm_t, state, state_t = None, None, None, None
    for line in open(os.path.join(d, 'logcat.txt'), errors='replace'):
        if 'hakuX-route' in line:
            m = TS.match(line)
            g = re.search(r'gpuclock pm=(\d+)', line)
            if m and g:
                pm, pm_t = int(g.group(1)), secs(*m.groups())
            elif m and ('gpuclock MISMATCH' in line or 'gpuclock end' in line or 'gpuclock blocks done' in line):
                pm, pm_t = None, secs(*m.groups())
            g = re.search(r'state=([a-z_]+)', line)
            if g and m:
                state, state_t = g.group(1), secs(*m.groups())
            continue
        if '[gpuclk433]' not in line:
            continue
        m = TS.match(line)
        if not m:
            continue
        t = secs(*m.groups())
        if ' init ' in line:
            info['init'] = line.split('[gpuclk433]', 1)[1].strip()
            continue
        g = dict(re.findall(r' (\w+)=(\S+)', line))
        w = {'t': t - mark if mark is not None else None, 'dt': t - prev_t if prev_t else None,
             'pm': pm, 'since_pm': t - pm_t if pm_t is not None else None, 'state': state,
             'since_state': t - state_t if state_t is not None else None}
        prev_t = t
        for k in ('frames', 'fr', 'ns', 'dr'):
            w[k] = int(g.get(k, 0))
        for k in ('gms', 'grn', 'floor', 'ceil'):
            w[k] = float(g[k]) if k in g else None
        seq = []
        if g.get('seq', '-') != '-':
            for s in g['seq'].split(','):
                mhz, busy = s.split('/')
                seq.append((int(mhz), int(busy)))
        w['seq'] = seq
        w['mhz'] = statistics.mean(s[0] for s in seq) if seq and all(s[0] > 0 for s in seq) else None
        w['busy'] = statistics.mean(s[1] for s in seq) if seq and all(s[1] >= 0 for s in seq) else None
        w['fps'] = w['frames'] / w['dt'] if w['dt'] and w['frames'] else None
        w['F'] = 1000.0 / w['fps'] if w['fps'] else None
        wins.append(w)
    info['all'] = wins
    info['win'] = [w for w in wins if w['t'] is not None and w['t'] >= a.skip and w['fps']]
    if block is not None:
        # this condition's windows only, a full window after the switch, in play
        info['name'] += ' pm=%d' % block
        info['win'] = [w for w in info['win'] if w['pm'] == block and w['since_pm'] is not None
                       and w['since_pm'] - (w['dt'] or 0) >= a.skip / 2 and w['state'] in (None, 'play', 'still')
                       and (w['since_state'] is None or w['since_state'] >= (w['dt'] or 0))]
    # thermal over the same window
    th = []
    try:
        for l in open(os.path.join(d, 'thermal.jsonl')):
            s = json.loads(l)
            dt = s.get('dev_time')
            if not dt or mark is None:
                continue
            t = secs(*re.match(r'\d+-\d+ (\d+):(\d+):(\d+)', dt).groups()) - mark
            if t < a.skip:
                continue
            tz = lit(s.get('tz')) or []
            temps = {z[1]: z[2] / 1000.0 for z in tz if isinstance(z[2], int) and z[2] > 0}
            clk = lit(s.get('clk')) or {}
            pw = lit(s.get('pw')) or {}
            th.append({'t': t, 'hot': max(temps.values()) if temps else None,
                       'xo': next((v for k, v in temps.items() if k.startswith('xo')), None),
                       'cpu7': (clk.get('cpu7') or {}).get('scaling_cur_freq'),
                       'gpu': (clk.get('gpu') or {}).get('gpuclk'),
                       'cap': (clk.get('gpu') or {}).get('max_gpuclk'),
                       'pause': s.get('pause'), 'batt': (pw.get('battery') or {}).get('status')})
    except OSError:
        pass
    if info['win']:
        t_end = info['win'][-1]['t']
        th = [x for x in th if x['t'] <= t_end + 30]
    info['th'] = th
    # power over the scored span (thermal_state.power_over, the soak summary's
    # own arithmetic); a blocks session interleaves conditions, so none there
    info['pw'] = None
    if block is None and info['win'] and mark is not None and thermal_state:
        try:
            recs = thermal_state.load(os.path.join(d, 'thermal.jsonl'))
            r0 = next(r for r in recs if r.get('dev_time'))
            base = thermal_state.dev_ts(r0) - secs(*re.match(r'\d+-\d+ (\d+):(\d+):(\d+)', r0['dev_time']).groups())
            w0, w1 = info['win'][0], info['win'][-1]
            info['pw'] = thermal_state.power_over(recs, base + mark + w0['t'] - (w0['dt'] or 0), base + mark + w1['t'])
        except Exception as ex:
            info['pw'] = {'measured': False, 'error': str(ex)}
    return info


def summarize(r):
    W = r['win']
    out = {'n': len(W)}
    for k in ('fps', 'F', 'gms', 'grn', 'mhz', 'busy'):
        out[k] = med([w[k] for w in W])
    seq = [s for w in W for s in w['seq']]
    out['samples'] = len(seq)
    ceil = min([w['ceil'] for w in W if w['ceil']] or [680])
    out['ceil'] = ceil
    out['floor'] = sorted(set(w['floor'] for w in W if w['floor'] is not None))
    hist = {}
    for m_, b in seq:
        hist[m_] = hist.get(m_, 0) + 1
    out['hist'] = {k: v / len(seq) for k, v in sorted(hist.items())} if seq else {}
    hot = [1 for m_, b in seq if b >= 90 and m_ < ceil]
    out['hot'] = len(hot) / len(seq) if seq else None
    out['busy90'] = sum(1 for m_, b in seq if b >= 90) / len(seq) if seq else None
    # step response, within each window's sequence
    lags, cens = [], 0
    for w in W:
        s = w['seq']
        i = 0
        while i < len(s):
            if s[i][1] >= 90 and s[i][0] < ceil:
                j = i + 1
                while j < len(s) and s[j][0] <= s[i][0]:
                    j += 1
                if j < len(s):
                    lags.append(j - i)
                else:
                    cens += 1
                i = j
            else:
                i += 1
    out['lag'] = (med(lags), len(lags), cens)
    span = sum(w['dt'] for w in W if w['dt'])
    out['fps_mean'] = sum(w['frames'] for w in W if w['dt']) / span if span else None
    pw = r.get('pw') or {}
    out['pw'] = pw
    out['jpf'] = pw['net_w'] / out['fps_mean'] if pw.get('net_w') and out['fps_mean'] else None
    th = r['th']
    if th:
        out['hot0'], out['hot1'] = th[0]['hot'], th[-1]['hot']
        out['xo0'], out['xo1'] = th[0]['xo'], th[-1]['xo']
        span = (th[-1]['t'] - th[0]['t']) / 60.0
        out['rate'] = (th[-1]['hot'] - th[0]['hot']) / span if span > 0 and th[0]['hot'] and th[-1]['hot'] else None
        out['pause'] = any(x['pause'] for x in th)
        caps = [x['cap'] for x in th if x['cap']]
        out['mincap'] = min(caps) // 1000000 if caps else None
        c7 = [x['cpu7'] for x in th if x['cpu7']]
        out['cpu7'] = (min(c7) // 1000, max(c7) // 1000) if c7 else None
        gs = [x['gpu'] // 1000000 for x in th if x['gpu']]
        out['th_gpu'] = gs
        out['batt'] = sorted(set(x['batt'] for x in th if x['batt']))
    return out


def show(r, s):
    reg = r['regimen']
    res = r['result']
    print('== %s  %s ref %s  regimen=%s perf_mode=%s fan=%s  env=%s' % (
        r['name'], res.get('device_label'), res.get('ref'), reg.get('regimen'), reg.get('perf_mode'),
        reg.get('fan_mode'), ','.join(res.get('env') or [])))
    print('   init: %s' % r['init'])
    if not r['mark']:
        print('   NO mark gameplay: no window')
        return
    print('   windows %d (skip %.0f s)  fps %s  F %s ms  gms %s  grn %s  MHz %s  busy %s  floor %s ceil %s' % (
        s['n'], a.skip, f(s['fps']), f(s['F']), f(s['gms'], 2), f(s['grn'], 2), f(s['mhz'], 0), f(s['busy'], 0),
        s['floor'], s['ceil']))
    print('   clock time-at-step (%d samples): %s' % (s['samples'], ' '.join('%d:%.1f%%' % (k, 100 * v) for k, v in s['hist'].items())))
    print('   busy>=90 %s of samples; busy>=90 under the ceiling (hot) %s; step response after hot: median %s samples (n=%d, censored %d)' % (
        f(100 * s['busy90'] if s['busy90'] is not None else None) + '%', f(100 * s['hot'] if s['hot'] is not None else None) + '%',
        s['lag'][0], s['lag'][1], s['lag'][2]))
    if 'hot0' in s:
        print('   thermal: hottest %s -> %s C (%s C/min), xo %s -> %s, pause %s, lowest ceiling %s MHz, cpu7 %s MHz, battery %s, thermal.jsonl gpuclk %s' % (
            f(s['hot0']), f(s['hot1']), f(s['rate'], 2), f(s['xo0']), f(s['xo1']), s['pause'], s['mincap'], s['cpu7'], s['batt'], s['th_gpu']))
    if s.get('pw', {}).get('measured'):
        p = s['pw']
        print('   power over the window (%d samples): battery %+.2f W, usb %s W, net %s W; fps (frames/time) %s -> %s J/frame' % (
            p['samples'], p['battery_w'], f(p['usb_w'], 2), f(p['net_w'], 2), f(s['fps_mean']), f(s['jpf'], 3)))


def fit(ws):
    pts = [(1.0 / w['mhz'], w['gms']) for w in ws if w['mhz'] and w['gms'] is not None]
    if len(pts) < 3:
        return None
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    if sxx == 0:
        return None
    k = sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx
    c = my - k * mx
    res = [p[1] - (c + k * p[0]) for p in pts]
    sst = sum((p[1] - my) ** 2 for p in pts)
    rms = math.sqrt(sum(x * x for x in res) / n)
    return {'n': n, 'c': c, 'k': k, 'rms': rms, 'r2': 1 - sum(x * x for x in res) / sst if sst else None,
            'clock_share_at_401': (k / 401.0) / (c + k / 401.0) if c + k / 401.0 else None}


mids = []
if a.blocks:
    runs = [r for d in a.runs for r in (read_run(d, 0), read_run(d, 2))]
    mids = [read_run(d, 1) for d in a.runs]
    a.pair = True
else:
    runs = [read_run(d) for d in a.runs]
sums = [summarize(r) for r in runs]
for r, s in zip(runs, sums):
    show(r, s)
if a.tsv:
    with open(a.tsv, 'w') as fh:
        fh.write('run\tt\tfps\tF\tgms\tgrn\tmhz\tbusy\tfloor\tceil\tns\n')
        for r in runs:
            for w in r['win']:
                fh.write('\t'.join(str(x) for x in (r['name'], f(w['t']), f(w['fps'], 2), f(w['F'], 2), w['gms'], w['grn'],
                                                     f(w['mhz'], 0), f(w['busy'], 0), w['floor'], w['ceil'], w['ns'])) + '\n')
if a.pair:
    for i in range(0, len(runs) - 1, 2):
        lo, hi = sums[i], sums[i + 1]
        print('\n## pair %s (low) / %s (high)' % (runs[i]['name'], runs[i + 1]['name']))
        ok_ctl = lo['mhz'] is not None and hi['mhz'] is not None and lo['mhz'] <= 450 and hi['mhz'] >= 600
        print('   control: low %s MHz, high %s MHz -> %s' % (f(lo['mhz'], 0), f(hi['mhz'], 0),
              'the clock moved' if ok_ctl else 'INERT (the pair says nothing about the clock)'))
        if None in (lo['gms'], hi['gms'], lo['mhz'], hi['mhz'], lo['F'], hi['F']):
            print('   incomplete')
            continue
        e = math.log(lo['gms'] / hi['gms']) / math.log(hi['mhz'] / lo['mhz'])
        verdict = 'CLOCK-LIMITED' if e >= 0.6 else ('NOT clock-bound' if e <= 0.2 else 'PARTLY clock-bound')
        print('   a. gms %.2f -> %.2f ms (x%.3f) for MHz x%.3f: e = %.2f -> %s' % (
            lo['gms'], hi['gms'], hi['gms'] / lo['gms'], hi['mhz'] / lo['mhz'], e, verdict))
        dF, dG = lo['F'] - hi['F'], lo['gms'] - hi['gms']
        print('   b. F %.1f -> %.1f ms (fps %.1f -> %.1f): dF %.1f against dGPU %.1f -> %s' % (
            lo['F'], hi['F'], lo['fps'], hi['fps'], dF, dG,
            'fps FOLLOWS the GPU' if dG > 0 and dF >= 0.6 * dG else 'fps does NOT follow the GPU (something else paces)'))
        if 'hot0' in lo and 'hot0' in hi:
            bad = []
            if lo['hot0'] and hi['hot0'] and abs(lo['hot0'] - hi['hot0']) > 5:
                bad.append('start %.1f vs %.1f C' % (lo['hot0'], hi['hot0']))
            if lo.get('rate') is not None and hi.get('rate') is not None and abs(lo['rate'] - hi['rate']) > 0.5:
                bad.append('heating %.2f vs %.2f C/min' % (lo['rate'], hi['rate']))
            if lo['pause'] or hi['pause']:
                bad.append('thermal pause')
            if (lo['mincap'] or 680) < 680 or (hi['mincap'] or 680) < 680:
                bad.append('ceiling under 680')
            print('   validity: %s' % ('; '.join(bad) + ' -> fps VOID' if bad else 'ok'))
        if lo.get('jpf') and hi.get('jpf'):
            print('   cost: net %.2f -> %.2f W, %.3f -> %.3f J/frame (x%.2f)' % (
                lo['pw']['net_w'], hi['pw']['net_w'], lo['jpf'], hi['jpf'], hi['jpf'] / lo['jpf']))
        ft = fit(runs[i]['win'] + runs[i + 1]['win'])
        if ft:
            print('   fit gms = c + k/MHz over %d windows: c %.2f ms, k %.0f ms*MHz, RMS residual %.2f ms, R^2 %s; clock-scaled share at 401 MHz %.0f%%' % (
                ft['n'], ft['c'], ft['k'], ft['rms'], f(ft['r2'], 2), 100 * ft['clock_share_at_401']))

# The ladder (blocks with a pm 1 level): the three levels' window medians, the
# elasticity of each step, and gms = c + k/MHz fitted on the three medians
# (two parameters, three points: the residual is the curvature 1/MHz misses).
for i, mid in enumerate(mids):
    if not mid['win']:
        continue
    lo, hi = sums[2 * i], sums[2 * i + 1]
    md = summarize(mid)
    show(mid, md)
    lv = sorted([x for x in (lo, md, hi) if x['gms'] is not None and x['mhz']], key=lambda x: x['mhz'])
    print('\n## ladder %s: %s' % (mid['name'].rsplit(' ', 1)[0], '  '.join(
        '%s MHz gms %.2f F %.1f (n %d)' % (f(x['mhz'], 0), x['gms'], x['F'], x['n']) for x in lv)))
    for p, q in zip(lv, lv[1:]):
        if q['mhz'] > p['mhz'] and q['gms'] > 0:
            print('   step %s -> %s MHz: e = %.2f, dF %.1f against dGPU %.1f' % (
                f(p['mhz'], 0), f(q['mhz'], 0), math.log(p['gms'] / q['gms']) / math.log(q['mhz'] / p['mhz']),
                p['F'] - q['F'], p['gms'] - q['gms']))
    ft = fit([{'mhz': x['mhz'], 'gms': x['gms']} for x in lv])
    if ft:
        print('   fit on the level medians: c %.2f ms, k %.0f ms*MHz, RMS residual %.3f ms, R^2 %s' % (
            ft['c'], ft['k'], ft['rms'], f(ft['r2'], 3)))
