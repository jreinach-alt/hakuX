#!/usr/bin/env python3
"""Judge #787's measurement run: is the guest-late stall the TLB flush?

Reads one soak result directory (logcat.txt) and prints, for every frame
stall (a hakuX-pace line whose worst flip is >= --stall ms) that overlaps a
[tlb68] flush burst (ff >= --burst), the [tcg787] costs summed over the
[tlb68] windows that overlap the stall's 60-flip span:

  gus   tb_gen_code time (the brief's re-translation question)
  tfus  TLB refill time (the flush's real fallout: TBs survive a TLB flush)
  ffus  full-flush work, pfus INVLPG work
  F     gus + tfus + ffus + pfus, everything a flush can cost the vCPU

and the [tpc787] entry pcs that hold the time in those windows. Legs and
bands are the registered prediction's (predictions/flushstall787-kabuki.json).

usage: fs_judge.py <result_dir> [--stall 400] [--burst 50] [--skip 30]
                   [--all] [--json out]

--skip drops stalls whose span starts in the first S seconds of the log (the
boot translation burst). --all judges the legs over every stall, not only
those that overlap a flush burst.
"""
import json
import os
import re
import sys


def kv(line):
    return dict(re.findall(r' (\w+)=(-?[\w.:,/]+)', line))


def ts(line):
    m = re.match(r'(\d\d-\d\d) (\d\d):(\d\d):(\d\d\.\d+)', line)
    if not m:
        return None
    return int(m.group(2)) * 3600 + int(m.group(3)) * 60 + float(m.group(4))


def num(d, k, default=0):
    try:
        return int(d[k])
    except (KeyError, ValueError):
        return default


def load(path):
    win = {}        # w -> dict (tlb68 t_end, dt, ff, pf; tcg787; rr425; tpc)
    pages = []      # (t, gen, calls)
    pace = []       # (t, max_ms, span_ms)
    for line in open(path, errors='replace'):
        t = ts(line)
        if t is None:
            continue
        if '[tlb68]' in line:
            d = kv(line)
            w = win.setdefault(int(d['w']), {})
            w.update(t=t, dt=num(d, 'dt'), ff=num(d, 'ff'), pf=num(d, 'pf'),
                     cr3s=num(d, 'cr3s'), cr3n=num(d, 'cr3n'))
        elif '[tcg787]' in line:
            d = kv(line)
            w = win.setdefault(int(d['w']), {})
            w['tcg'] = {k: num(d, k) for k in
                        ('gc', 'cg', 'gus', 'cgus', 'gmax', 'disc', 'tbf',
                         'ffus', 'pfus', 'tf', 'tfx', 'tfus', 'pl')}
        elif '[rr425]' in line:
            d = kv(line)
            w = win.setdefault(int(d['w']), {})
            w['rr'] = {k: num(d, k) for k in ('it', 'gapus', 'tbus')}
        elif '[tpc787]' in line:
            d = kv(line)
            w = win.setdefault(int(d['w']), {})
            w['tpc'] = re.findall(r' ([0-9a-f]{8}):([0-9a-f]{6}):(\d+):(\d+)',
                                  line)
            w['tpc_us'] = num(d, 'us')
        elif 'hakuX-pages' in line and 'generated' in line:
            g = re.search(r'generated (\d+) of (\d+) calls', line)
            pages.append((t, int(g.group(1)), int(g.group(2))))
        elif 'hakuX-pace' in line:
            mx = re.search(r' max=([\d.]+)', line)
            ms = re.search(r' ms=([\d.]+)', line)
            if mx and ms:
                pace.append((t, float(mx.group(1)), float(ms.group(1))))
    return win, pages, pace


def overlapping(win, t0, t1):
    out = []
    for w, r in sorted(win.items()):
        if 't' not in r:
            continue
        a, b = r['t'] - r['dt'] / 1000.0, r['t']
        if a < t1 and b > t0:
            out.append(w)
    return out


def band(v, lo, hi):
    return 'PASS' if v < lo else 'FAIL' if v >= hi else 'BETWEEN'


def main():
    rd = sys.argv[1]
    stall = float(sys.argv[sys.argv.index('--stall') + 1]) \
        if '--stall' in sys.argv else 400.0
    burst = int(sys.argv[sys.argv.index('--burst') + 1]) \
        if '--burst' in sys.argv else 50
    skip = float(sys.argv[sys.argv.index('--skip') + 1]) \
        if '--skip' in sys.argv else 30.0
    judge_all = '--all' in sys.argv
    win, pages, pace = load(os.path.join(rd, 'logcat.txt'))
    t_first = min([r['t'] - r['dt'] / 1000.0 for r in win.values()
                   if 't' in r] or [0])
    rep = {'result': os.path.basename(rd.rstrip('/')), 'stalls': [],
           'validity': {}, 'legs': {}}

    tcg_w = [w for w, r in win.items() if 'tcg' in r]
    tlb_w = [w for w, r in win.items() if 't' in r]
    pl = sorted({win[w]['tcg']['pl'] for w in tcg_w})
    v = rep['validity']
    v['V1 tcg787 lines'] = {'tlb68': len(tlb_w), 'tcg787': len(tcg_w),
                            'pl': pl,
                            'ok': bool(tlb_w) and
                            len(tcg_w) >= 0.9 * len(tlb_w) and pl == [1]}
    # The timer moves with translation: the windows that generate the most
    # code carry the most gus; the windows that generate almost none read
    # near 0.
    heavy = [win[w]['tcg']['gus'] for w in tcg_w
             if win[w]['tcg']['cg'] >= 2000]
    quiet = sorted(win[w]['tcg']['gus'] for w in tcg_w
                   if win[w]['tcg']['cg'] <= 20)
    qmed = quiet[len(quiet) // 2] if quiet else None
    v['V2 moves with translation'] = {
        'heavy_windows': len(heavy), 'heavy_max_gus': max(heavy or [0]),
        'quiet_windows': len(quiet), 'quiet_median_gus': qmed,
        'ok': bool(heavy) and max(heavy) >= 50000 and
        qmed is not None and qmed <= 20000}
    # An independent instrument: tb_gen_code runs between TBs, so it is
    # inside [rr425]'s sampled gap time.
    sg = sum(win[w]['tcg']['gus'] for w in tcg_w)
    sgap = sum(win[w]['rr']['gapus'] for w in tcg_w if 'rr' in win[w])
    v['V3 inside the loop gap'] = {'sum_gus': sg, 'sum_gapus': sgap,
                                   'ok': sgap > 0 and sg <= 1.5 * sgap}
    # Every call is wrapped: gc tracks hakuX-pages' calls over the span both
    # cover (gc can only fall short by calls that longjmp out).
    if pages and tcg_w:
        t_lo, t_hi = pages[0][0], pages[-1][0]
        calls = sum(c for t, g, c in pages[1:])
        gc = sum(win[w]['tcg']['gc'] for w in tcg_w
                 if t_lo < win[w].get('t', 0) <= t_hi)
        v['V4 gc vs pages calls'] = {'gc': gc, 'calls': calls,
                                     'ratio': round(gc / calls, 3)
                                     if calls else None,
                                     'ok': calls > 0 and
                                     0.85 <= gc / calls <= 1.10}
    else:
        v['V4 gc vs pages calls'] = {'ok': False, 'why': 'no lines'}

    for t, mx, ms in pace:
        if mx < stall or t - ms / 1000.0 < t_first + skip:
            continue
        ws = overlapping(win, t - ms / 1000.0, t)
        ff = sum(win[w].get('ff', 0) for w in ws)
        s = {'t': round(t, 1), 'max_ms': mx, 'span_ms': ms, 'windows': ws,
             'ff': ff, 'pf': sum(win[w].get('pf', 0) for w in ws),
             'burst': any(win[w].get('ff', 0) >= burst for w in ws)}
        if all('tcg' in win[w] for w in ws) and ws:
            for k in ('gc', 'cg', 'gus', 'cgus', 'disc', 'tbf', 'ffus',
                      'pfus', 'tf', 'tfx', 'tfus'):
                s[k] = sum(win[w]['tcg'][k] for w in ws)
            s['gmax'] = max(win[w]['tcg']['gmax'] for w in ws)
            s['F_us'] = s['gus'] + max(s['tfus'], 0) + s['ffus'] + s['pfus']
        tpc = {}
        tot = 0
        for w in ws:
            tot += win[w].get('tpc_us', 0)
            for pc, b, us, n in win[w].get('tpc', []):
                tpc.setdefault((pc, b), [0, 0])
                tpc[(pc, b)][0] += int(us)
                tpc[(pc, b)][1] += int(n)
        s['tpc_us'] = tot
        s['tpc_top'] = ['%s:%s:%dus:%d' % (pc, b, us, n) for (pc, b), (us, n)
                        in sorted(tpc.items(), key=lambda x: -x[1][0])[:10]]
        s['rr_tbus'] = sum(win[w].get('rr', {}).get('tbus', 0) for w in ws)
        s['rr_gapus'] = sum(win[w].get('rr', {}).get('gapus', 0) for w in ws)
        rep['stalls'].append(s)

    burst_stalls = [s for s in rep['stalls']
                    if (judge_all or s['burst']) and 'gus' in s]
    v['V5 a stall to judge'] = {'n': len(burst_stalls),
                                'all': judge_all,
                                'ok': len(burst_stalls) > 0}
    valid = all(x['ok'] for x in v.values())
    L = rep['legs']
    if not burst_stalls:
        L['G'] = L['F'] = 'BLIND: no stall >= %g ms to judge' % stall
    else:
        gw = max(s['gus'] for s in burst_stalls) / 1000.0
        fw = max(s['F_us'] for s in burst_stalls) / 1000.0
        L['G'] = '%s: worst stall span gus %.1f ms (PASS < 100, FAIL >= 400)' \
            % (band(gw, 100, 400), gw)
        L['F'] = '%s: worst stall span F %.1f ms (PASS < 250, FAIL >= 400)' \
            % (band(fw, 250, 400), fw)
    L['valid'] = valid

    print(json.dumps(rep, indent=1))
    if '--json' in sys.argv:
        json.dump(rep, open(sys.argv[sys.argv.index('--json') + 1], 'w'),
                  indent=1)


if __name__ == '__main__':
    main()
