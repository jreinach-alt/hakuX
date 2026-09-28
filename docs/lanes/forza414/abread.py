#!/usr/bin/env python3
"""Race-window figures from a perflog Forza soak logcat (lane.forza414, #414).

    abread.py <logcat.txt> [<logcat.txt> ...] [--from 243] [--to 414] [--bucket 0]

t = 0 is the first `hakuX-route: soak start`. Every figure is taken over the
lines whose t falls in [--from, --to], the window forza414-coalesce-soak.json
names. One column per logcat, so an A/B is `abread.py A/logcat.txt B/logcat.txt`.

  fps      60 / (pace ms / 1000) per hakuX-pace line (60 flips per line)
  vpf      VBLANKs per flip, from the pace line's v0..v4 histogram
  Tot, Draw, Pipe, Fin, Sub, Fen, Idle, GPU, R   hakuX-phase, ms per frame
  Finish, sd, cDef, cDefC, pDl   hakuX-stall, per 60 flips
  ev.dl, unshelve, stale   hakuX-stall evict[], per 60 flips
  s413.*   [surf413] ms per frame inside pgraph_vk_surface_update: cdef is
           the completion, fin the pgraph_vk_finish time inside the update;
           realupl is the upload_pending uploads per 60 frames
  dfF, dfR   xemu-surf: the completion's wait and its staged copy, ms/frame
  cpu      vCPU thread ms per 2 s ([tlb68])
  Push, Mth   hakuX-cpu, ms per frame
  <caller>.fin/.fence/.pre/.dl/.ms   [sdcall], summed over the window and
           divided by the guest frames it covers (per frame)
  su_upl, su_deferred   the same, per frame
  why.*    [sdcall] why=: su_upl's bindings by the setter of upload_pending
           (new, inv, stale, hoff, cpuw, gap, oth), per frame
  clr, clrfull   of those, the ones on a clearing update, and the ones that
           clear then covered whole (SurfaceBinding.cleared), per frame

Medians are over lines; [sdcall] is a sum over frames, because a caller that
is absent from a line prints nothing rather than a zero.
--bucket N also prints fps, Sub and cDef per N seconds across the whole run.
"""
import re
import statistics
import sys

TS = re.compile(r'^\d\d-\d\d (\d\d):(\d\d):(\d\d)\.(\d\d\d) ')
CALL = re.compile(r'(\w+)=fin(\d+)/fence(\d+)/pre(\d+)/dl(\d+)/([\d.]+)ms')
WHY = ('new', 'inv', 'stale', 'hoff', 'cpuw', 'gap', 'oth')
WHY_RE = re.compile(r'why=' + '/'.join(w + r'(\d+)' for w in WHY))


def secs(line):
    m = TS.match(line)
    if not m:
        return None
    h, mi, s, ms = (int(x) for x in m.groups())
    return h * 3600 + mi * 60 + s + ms / 1000.0


def num(pat, line):
    m = re.search(pat, line)
    return float(m.group(1)) if m else None


def read(path, lo, hi, bucket):
    lines = open(path, errors='replace').read().splitlines()
    t0 = None
    for l in lines:
        if 'soak start' in l:
            t0 = secs(l)
            break
    if t0 is None:
        raise SystemExit('%s: no soak start line' % path)
    med = {}
    calls = {}
    frames = 0
    su = {'su_upl': 0, 'su_deferred': 0, 'clr': 0, 'clrfull': 0}
    su_seen = set()
    per = {}

    def add(k, v, t):
        if v is None:
            return
        if lo <= t <= hi:
            med.setdefault(k, []).append(v)
        if bucket and k in ('fps', 'Sub', 'cDef'):
            per.setdefault(int(t // bucket), {}).setdefault(k, []).append(v)

    for l in lines:
        t = secs(l)
        if t is None:
            continue
        t -= t0
        if t < 0:
            continue
        if 'hakuX-pace' in l and ' ms=' in l:
            ms = num(r' ms=([\d.]+)', l)
            if ms:
                add('fps', 60000.0 / ms, t)
            v = [num(r' v%d=(\d+)' % i, l) for i in range(5)]
            if None not in v and sum(v):
                add('vpf', sum(i * n for i, n in enumerate(v)) / sum(v), t)
        elif 'hakuX-phase' in l:
            add('Tot', num(r'Tot:([\d.]+)', l), t)
            add('Surf', num(r'Surf:([\d.]+)', l), t)
            add('Draw', num(r'Draw:([\d.]+)', l), t)
            add('Pipe', num(r'Pipe:([\d.]+)', l), t)
            add('Fin', num(r'Fin:([\d.]+)', l), t)
            add('Sub', num(r'Sub:([\d.]+)', l), t)
            add('Fen', num(r'Fen:([\d.]+)', l), t)
            add('Idle', num(r'Idle:([\d.]+)', l), t)
            add('GPU', num(r'GPU:([\d.]+)', l), t)
            add('R', num(r'\(R:([\d.]+)', l), t)
        elif 'hakuX-stall' in l and 'Finish:' in l:
            add('Finish', num(r'Finish:(\d+)', l), t)
            add('sd', num(r' sd(\d+)', l), t)
            add('cDef', num(r'cDef(\d+)', l), t)
            add('cDefC', num(r'cDefC(\d+)', l), t)
            add('pDl', num(r'pDl(\d+)', l), t)
            add('PreDL', num(r'PreDL:(\d+)', l), t)
        elif '[surf413]' in l:
            for k in ('part', 'cdef', 'upl', 'exp', 'fin'):
                add('s413.' + k, num(r' %s=([\d.]+)' % k, l), t)
            add('realupl', num(r'realupl=(\d+)', l), t)
        elif 'xemu-surf' in l and 'dfF:' in l:
            add('dfF', num(r'dfF:([\d.]+)', l), t)
            add('dfR', num(r'dfR:([\d.]+)', l), t)
        elif 'hakuX-stall' in l and 'evict[' in l:
            add('ev.dl', num(r'evict\[dl:(\d+)', l), t)
            add('unshelve', num(r'unshelve:(\d+)', l), t)
            add('stale', num(r'stale:(\d+)', l), t)
        elif 'hakuX-cpu' in l:
            add('Push', num(r'Push:([\d.]+)', l), t)
            add('Mth', num(r'Mth:([\d.]+)', l), t)
        elif '[tlb68]' in l:
            add('cpu', num(r' cpu=(\d+)', l), t)
        elif '[sdcall]' in l and lo <= t <= hi:
            frames += int(num(r'frames=(\d+)', l))
            for name, fin, fence, pre, dl, ms in CALL.findall(l):
                c = calls.setdefault(name, [0, 0, 0, 0, 0.0])
                c[0] += int(fin)
                c[1] += int(fence)
                c[2] += int(pre)
                c[3] += int(dl)
                c[4] += float(ms)
            for k in ('su_upl', 'su_deferred', 'clr', 'clrfull'):
                v = num(r' %s=(\d+)' % k, l)
                if v is not None:
                    su[k] += int(v)
                    su_seen.add(k)
            m = WHY_RE.search(l)
            if m:
                for w, v in zip(WHY, m.groups()):
                    su['why.' + w] = su.get('why.' + w, 0) + int(v)
                    su_seen.add('why.' + w)
    out = {}
    for k, v in med.items():
        out[k] = (statistics.median(v), min(v), max(v), len(v))
    out['_frames'] = frames
    out['_calls'] = calls
    out['_su'] = {k: su[k] for k in su_seen}
    out['_per'] = per
    return out


def main(argv):
    lo, hi, bucket = 243.0, 414.0, 0.0
    paths = []
    i = 1
    while i < len(argv):
        if argv[i] == '--from':
            lo = float(argv[i + 1])
            i += 2
        elif argv[i] == '--to':
            hi = float(argv[i + 1])
            i += 2
        elif argv[i] == '--bucket':
            bucket = float(argv[i + 1])
            i += 2
        else:
            paths.append(argv[i])
            i += 1
    if not paths:
        raise SystemExit(__doc__)
    runs = [read(p, lo, hi, bucket) for p in paths]
    print('window t = %g-%g s; median (min-max, n lines)' % (lo, hi))
    keys = ['fps', 'vpf', 'Tot', 'Surf', 'Draw', 'Pipe', 'Fin', 'Sub', 'Fen',
            'Idle', 'GPU', 'R', 'Finish', 'sd', 'cDef', 'cDefC', 'pDl',
            'PreDL', 'ev.dl', 'unshelve', 'stale', 'realupl', 's413.part',
            's413.cdef', 's413.upl', 's413.exp', 's413.fin', 'dfF', 'dfR',
            'cpu', 'Push', 'Mth']
    for k in keys:
        row = []
        for r in runs:
            if k in r:
                m, a, b, n = r[k]
                row.append('%8.2f (%.1f-%.1f, %d)' % (m, a, b, n))
            else:
                row.append('       -')
        ratio = ''
        if len(runs) == 2 and k in runs[0] and k in runs[1] and runs[0][k][0]:
            ratio = '  B/A %.3f' % (runs[1][k][0] / runs[0][k][0])
        print('%-7s %s%s' % (k, '   '.join('%-28s' % x for x in row), ratio))
    print('[sdcall], per guest frame')
    names = []
    for r in runs:
        for n in r['_calls']:
            if n not in names:
                names.append(n)
    print('guest frames: ' + '   '.join(str(r['_frames']) for r in runs))
    for n in names + ['TOTAL']:
        row = []
        for r in runs:
            f = r['_frames'] or 1
            if n == 'TOTAL':
                c = [sum(x[j] for x in r['_calls'].values()) for j in range(5)]
            else:
                c = r['_calls'].get(n, [0, 0, 0, 0, 0.0])
            row.append('fin %.3f fence %.3f pre %.3f dl %.2f ms %.2f' % tuple(x / f for x in c))
        print('%-8s %s' % (n, '   |   '.join(row)))
    for k in ('su_upl', 'su_deferred') + tuple('why.' + w for w in WHY) + ('clr', 'clrfull'):
        row = []
        for r in runs:
            f = r['_frames'] or 1
            row.append('%.2f' % (r['_su'][k] / f) if k in r['_su'] else 'absent')
        print('%-12s %s' % (k, '   |   '.join(row)))
    if bucket:
        print('per %g s: fps / Sub / cDef medians' % bucket)
        bs = sorted(set(b for r in runs for b in r['_per']))
        for b in bs:
            row = []
            for r in runs:
                d = r['_per'].get(b, {})
                row.append(' '.join(
                    '%s %6.1f' % (k, statistics.median(d[k])) if k in d else '%s      -' % k
                    for k in ('fps', 'Sub', 'cDef')))
            print('t=%4d  %s' % (b * bucket, '   |   '.join(row)))


if __name__ == '__main__':
    main(sys.argv)
