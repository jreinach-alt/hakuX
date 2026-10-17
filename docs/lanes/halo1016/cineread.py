#!/usr/bin/env python3
"""lane.halo1016: judge of docs/testing/predictions/halo1016-cinesplit.json.

usage: cineread.py <A result dir> <B result dir> [--expect PREDICTION.json]

Written before either result was read. Each arm is a soak on the
halo-cinematic route: `mark cinematic` after LOADING, then the opening
cinematic of The Pillar of Autumn plays untouched.

Per arm it prints the per-window timeline (one row per hakuX-pace line:
60 guest frames) whatever the verdict, then the frametrace account of the
plateau's frames. The legs:

  V  validity, both arms: `mark cinematic` in logcat, >= V_min_cine_shots
     `cine` route-frames, [hakuX-ft1] and [probe1010] lines, B's hakuX-build
     render_mode line names TU_DEBUG=sysmem and A's does not, and A's
     plateau spans >= V_a_plateau_min_s. The route-frames booted, profile,
     level, difficulty and loading are listed for a read by eye: a run
     whose route did not reach LOADING is void, not a miss.
  S  A's PFIFO thread over the plateau frames: mean p_run in
     [S_prun_min_ms, S_prun_max_ms]; sum p_blk / sum P >= S_blk_share_min;
     of p_blk, GPU waits (p_fence + p_submit + p_rthr + the unhooked
     remainder p_blk - pidle - the named non-idle waits) >=
     S_gpuwait_share_of_blk_min, lock waits (p_bql + p_pfl + p_pgl) <=
     S_lock_share_of_blk_max; sum p_rq / sum P <= S_rq_share_max.
  G  A: median of gpu / P over the plateau frames >= G_gpu50_share_min.
  W  A: probe1010's non-deferred finishes per frame over the plateau
     windows, mid-frame reasons only (every reason but flip and present:
     F2 is a synchronous finish inside the frame; the flip's own finish is
     ~1 per frame in every scene and decides nothing) >= W_finish_per_frame_min.
  P  B's mean frametrace period over A's plateau span, matched by seconds
     after `mark cinematic`, / A's mean period there <= P_ratio_max.
     Printed beside it, not judged: the same ratio over the whole
     [mark+40, mark+260] window, which does not depend on the slow shots
     falling at the same second in both arms.

The plateau span: the hakuX-pace windows (each covers the time since the
previous pace line) with ms per guest frame >= 50 whose end lies in
[mark+40 s, mark+260 s]. A frame is in the span if its wall time falls in
one of those windows.

Frame wall times come from the [hakuX-ft1] anchors (t_ms against the logcat
clock), as docs/lanes/frametrace/ftread.py does; the CSV is in microseconds.
"""
import argparse
import glob
import json
import os
import re
import statistics
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'frametrace'))
from ftread import read_frames  # noqa: E402

W = ['bql', 'pfl', 'pgl', 'halt', 'idle', 'fence', 'submit', 'rthr', 'dl', 'oth']
LOCKS = ['bql', 'pfl', 'pgl']
TS = re.compile(r'^(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d\.\d+)')
FLIPLIKE = ('flip', 'present')
PLATEAU = [50.0]         # --plateau-ms, likewise
SPAN = (40.0, 260.0)
MARK = ['cinematic']     # --mark, for reading other routes' results (not the judge)


def ts(line):
    m = TS.match(line)
    if not m:
        return None
    mo, dd, hh, mi, ss = m.groups()
    return datetime.strptime('2026-%s-%s %s:%s:%s' % (mo, dd, hh, mi, ss),
                             '%Y-%m-%d %H:%M:%S.%f').timestamp()


def hms(t):
    return datetime.fromtimestamp(t).strftime('%H:%M:%S')


def num(pat, s, cast=float, default=None):
    m = re.search(pat, s)
    return cast(m.group(1)) if m else default


def mean(v):
    return sum(v) / len(v) if v else float('nan')


def pct(v, p):
    if not v:
        return float('nan')
    v = sorted(v)
    return v[min(len(v) - 1, int(round((len(v) - 1) * p / 100.0)))]


class Arm:
    def __init__(self, d):
        self.d = d
        self.name = os.path.basename(os.path.normpath(d))
        self.req = {}
        rq = os.path.join(d, 'request.json')
        if os.path.exists(rq):
            self.req = json.load(open(rq))
        self.mark = None
        self.render_mode = None
        self.pace = []       # (wall, f, ms, max)
        self.anchors = []    # (t_ms, wall)
        self.probe = []      # (wall, nframes, mid_n, mid_ms, {reason: (n, ms)}, draws)
        self.rr = {}         # wall -> dict of rr425 counters
        self.rrw = []        # (wall, idle_us, busy_us, n)
        self.gfps = []       # (wall, gfps, G mean)
        self.first = None    # the logcat's first timestamp
        lc = os.path.join(d, 'logcat.txt')
        if os.path.exists(lc):
            self.read_log(lc)
        self.frames = []
        self.csvs = self.run_csvs(d)
        for p in self.csvs:
            self.frames += read_frames(p)
        self.clock = None
        if self.frames and self.anchors:
            off = statistics.median(w - t / 1000.0 for t, w in self.anchors)
            for f in self.frames:
                f['wall'] = f['t_ns'] / 1e9 + off
            self.clock = 'ft1 anchors (%d)' % len(self.anchors)
        elif self.frames and self.pace:
            by_f = {f['f']: f['t_ns'] for f in self.frames}
            offs = [w - by_f[g - 1] / 1e9 for w, g, _, _ in self.pace if (g - 1) in by_f]
            if offs:
                off = statistics.median(offs)
                for f in self.frames:
                    f['wall'] = f['t_ns'] / 1e9 + off
                self.clock = 'hakuX-pace frame counter (%d)' % len(offs)
        if self.clock is None:
            self.frames = [f for f in self.frames if 'wall' in f]
        shots = os.path.join(d, 'route-frames')
        self.shots = sorted(os.listdir(shots)) if os.path.isdir(shots) else []

    def run_csvs(self, d):
        """This run's frametrace CSVs. --pull 'frametrace_*' also brings back
        every older CSV still on the device (the files are named by their
        device-local open time, frametrace_YYYYMMDD-HHMMSS.csv), so keep the
        ones opened no earlier than 120 s before the logcat's first line."""
        out = []
        for p in sorted(glob.glob(os.path.join(d, 'pulled', 'frametrace_*.csv'))):
            m = re.search(r'frametrace_(\d{8}-\d{6})\.csv$', p)
            if m and self.first is not None:
                opened = datetime.strptime(m.group(1), '%Y%m%d-%H%M%S').timestamp()
                if opened < self.first - 120:
                    continue
            out.append(p)
        return out

    def read_log(self, path):
        self.first = None
        for line in open(path, errors='replace'):
            if self.first is None:
                self.first = ts(line)
            if 'hakuX-route' in line and 'mark ' + MARK[0] in line and self.mark is None:
                self.mark = ts(line)
            elif 'render_mode:' in line and 'hakuX-build' in line and self.render_mode is None:
                self.render_mode = line.split('render_mode:', 1)[1].strip()
            elif 'hakuX-pace' in line and ' ms=' in line:
                t = ts(line)
                f = num(r' f=(\d+)', line, int)
                if t is not None and f is not None:
                    self.pace.append((t, f, num(r' ms=([\d.]+)', line),
                                      num(r' max=([\d.]+)', line)))
            elif '[hakuX-ft1] n=' in line:
                t, tm = ts(line), num(r' t_ms=([\d.]+)', line)
                if t is not None and tm is not None:
                    self.anchors.append((tm, t))
            elif '[probe1010] f=' in line:
                t = ts(line)
                nd = {}
                seg = line.split('| nd n/f ms/f:', 1)
                if len(seg) == 2:
                    for r, n, m in re.findall(r' (\w+)=([\d.]+)/([\d.]+)',
                                              seg[1].split('|', 1)[0]):
                        nd[r] = (float(n), float(m))
                self.probe.append((t, num(r'\] f=(\d+)', line, int, 0),
                                   num(r' mid=([\d.]+)/f', line, float, 0.0),
                                   num(r'/f ([\d.]+)ms/f each', line, float, 0.0),
                                   nd, num(r' draws=([\d.]+)/f', line, float, 0.0)))
            elif '[rr425w] ' in line:
                t = ts(line)
                self.rrw.append((t, num(r' idle_us=(\d+)', line, int, 0),
                                 num(r' busy_us=(\d+)', line, int, 0),
                                 num(r' n=(\d+)', line, int, 0)))
            elif '[rr425] w=' in line:
                t = ts(line)
                self.rr[t] = {k: num(r' %s=(\d+)' % k, line, int, 0)
                              for k in ('e', 'es', 'eo', 'ip', 'iq', 'dt')}
            elif re.search(r'gfps=\d+ G:', line):
                t = ts(line)
                m = re.search(r'gfps=(\d+) G:([\d.]+)', line)
                self.gfps.append((t, int(m.group(1)), float(m.group(2))))

    def windows(self):
        """Pace windows: (start wall, end wall, ms per frame, max ms)."""
        out = []
        for i, (t, f, ms, mx) in enumerate(self.pace):
            if i == 0 or ms is None:
                continue
            df = f - self.pace[i - 1][1]
            if df <= 0:
                continue
            out.append((t - ms / 1000.0, t, ms / df, mx))
        return out

    def plateau(self):
        if self.mark is None:
            return []
        return [w for w in self.windows()
                if w[2] >= PLATEAU[0] and SPAN[0] <= w[1] - self.mark <= SPAN[1]]

    def frames_in(self, spans):
        return [f for f in self.frames
                if any(a < f['wall'] <= b for a, b in spans)]

    def probe_in(self, spans):
        return [p for p in self.probe
                if p[0] is not None and any(a < p[0] <= b + 2.0 for a, b in spans)]


def nearest(rows, t, before=2.6):
    best = None
    for r in rows:
        if r[0] is not None and t - before <= r[0] <= t + 0.5:
            best = r
    return best


def timeline(arm):
    print('### timeline: %s (mark cinematic %s)\n' %
          (arm.name, hms(arm.mark) if arm.mark else 'MISSING'))
    print('| t-mark s | ms/f | max | idle share | e M | eo k | ip | iq | '
          'p_run | p_blk | pidle | gpu | P | mid nd/f | draws/f |')
    print('|' + '---|' * 15)
    rrk = sorted(arm.rr)
    for a, b, msf, mx in arm.windows():
        rel = b - arm.mark if arm.mark else b
        w = nearest(arm.rrw, b)
        share = ('%.2f' % (w[1] / float(w[1] + w[2]))) if w and (w[1] + w[2]) else '-'
        rk = [k for k in rrk if b - 2.6 <= k <= b + 0.5]
        r = arm.rr[rk[-1]] if rk else None
        fr = [f for f in arm.frames if a < f['wall'] <= b]

        def mf(k):
            v = [f[k] for f in fr if f.get(k) is not None]
            return '%.1f' % (mean(v) / 1000.0) if v else '-'
        pr = [p for p in arm.probe if p[0] is not None and a < p[0] <= b + 2.0]
        if pr:
            p = pr[0]
            mid = sum(n for k, (n, _) in p[4].items() if k not in FLIPLIKE)
            ps, dr = '%.2f' % mid, '%.0f' % p[5]
        else:
            ps = dr = '-'
        print('| %.0f | %.1f | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
            rel, msf, '%.0f' % mx if mx is not None else '-', share,
            '%.1f' % (r['e'] / 1e6) if r else '-', '%.0f' % (r['eo'] / 1e3) if r else '-',
            r['ip'] if r else '-', r['iq'] if r else '-',
            mf('p_run'), mf('p_blk'), mf('pidle'), mf('gpu'), mf('P'), ps, dr))
    print()


def account(arm, fr, label):
    """The frametrace account over a frame set, ms per frame."""
    print('### frametrace account: %s, %s (%d frames)\n' % (arm.name, label, len(fr)))
    if not fr:
        print('no frames\n')
        return None
    sP = float(sum(f['P'] for f in fr))

    def s(k):
        return float(sum(f[k] for f in fr if isinstance(f.get(k), int) and f[k] > 0))
    named = sum(s('p_' + w) for w in W if w != 'idle')
    punn = sum(max(0, f['p_blk'] - f['pidle'] -
                   sum(f.get('p_' + w) or 0 for w in W if w != 'idle')) for f in fr)
    acc = dict(P=sP / len(fr) / 1000.0, prun=s('p_run') / len(fr) / 1000.0,
               blk_share=s('p_blk') / sP, rq_share=s('p_rq') / sP,
               gpuwait=(s('p_fence') + s('p_submit') + s('p_rthr') + punn) / max(1.0, s('p_blk')),
               locks=sum(s('p_' + w) for w in LOCKS) / max(1.0, s('p_blk')),
               pidle_share=s('pidle') / max(1.0, s('p_blk')),
               dl_share=s('p_dl') / max(1.0, s('p_blk')),
               gpu50=pct([f['gpu'] / float(max(1, f['P'])) for f in fr], 50))
    rows = [('period P', s('P')), ('PFIFO on-CPU p_run', s('p_run')),
            ('PFIFO run queue p_rq', s('p_rq')), ('PFIFO blocked p_blk', s('p_blk')),
            ('  of it, waiting for work (pidle)', s('pidle'))]
    rows += [('  of it, p_' + w, s('p_' + w)) for w in W if w != 'idle' and s('p_' + w)]
    rows += [('  of it, unhooked remainder', punn),
             ('DMA_PUT pfifo.lock wait (lockw)', s('lockw')),
             ('vCPU on-CPU v_run', s('v_run')), ('vCPU blocked v_blk', s('v_blk')),
             ('guest idle (gidle)', s('gidle')),
             ('GPU execution (raw ts)', s('gpu')),
             ('main loop on-CPU m_run', s('m_run')), ('render on-CPU r_run', s('r_run'))]
    rows += [('vCPU wait v_' + w, s('v_' + w)) for w in W if s('v_' + w)]
    print('| | ms/frame | share of P |')
    print('|---|---|---|')
    for k, v in rows:
        print('| %s | %.2f | %.0f%% |' % (k, v / len(fr) / 1000.0, 100.0 * v / sP))
    print('\nnamed non-idle PFIFO waits %.2f ms/f; gpu/P p50 %.2f; mhz p50 %s\n' % (
        named / len(fr) / 1000.0, acc['gpu50'],
        pct([f['mhz'] for f in fr if f.get('mhz')], 50)))
    return acc


def leg(name, ok, text):
    print('- %s: %s  %s' % (name, 'HIT' if ok else 'MISS', text))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('--expect')
    ap.add_argument('--mark', default='cinematic', help='route mark (default cinematic)')
    ap.add_argument('--plateau-ms', type=float, default=50.0,
                    help='ms per frame a slow window reaches (default 50, the registered rule)')
    o = ap.parse_args()
    MARK[0], PLATEAU[0] = o.mark, o.plateau_ms
    ex = json.load(open(o.expect))['expect'] if o.expect else {}
    A, B = Arm(o.a), Arm(o.b)
    for arm, tag in ((A, 'A'), (B, 'B')):
        print('## %s: %s\n' % (tag, arm.name))
        print('request: ref %s env %s; frames %d (%s; from %s); pace lines %d; probe1010 %d; '
              'ft1 anchors %d; render_mode: %s\n' % (
                  arm.req.get('ref'), arm.req.get('env'), len(arm.frames), arm.clock,
                  ', '.join(os.path.basename(p) for p in arm.csvs) or 'no CSV',
                  len(arm.pace), len(arm.probe), len(arm.anchors), arm.render_mode))
        chk = [s for s in arm.shots if re.search(
            r'-(booted|profile|level|difficulty|loading)\.png$', s)]
        print('route-frames to read by eye: %s\n' % (', '.join(chk) or 'NONE'))
        timeline(arm)

    print('## Verdict\n')
    pl = A.plateau()
    spans = [(a, b) for a, b, _, _ in pl]
    plat_s = sum(b - a for a, b in spans)
    print('A plateau: %d windows, %.0f s, from mark+%.0f to mark+%.0f\n' % (
        len(pl), plat_s, (spans[0][0] - A.mark) if spans else 0,
        (spans[-1][1] - A.mark) if spans else 0))
    v = []
    for arm, tag in ((A, 'A'), (B, 'B')):
        n_cine = sum(1 for s in arm.shots if s.endswith('-cine.png'))
        v.append(arm.mark is not None)
        v.append(n_cine >= ex.get('V_min_cine_shots', 10))
        v.append(bool(arm.anchors) and bool(arm.probe) and bool(arm.frames))
        sysm = bool(arm.render_mode) and 'TU_DEBUG=sysmem' in arm.render_mode
        v.append(sysm if tag == 'B' else (arm.render_mode is not None and not sysm))
        print('- V %s: mark %s, cine shots %d, ft1/probe/frames %s/%s/%s, render_mode %s' % (
            tag, 'yes' if arm.mark else 'NO', n_cine, len(arm.anchors), len(arm.probe),
            len(arm.frames), arm.render_mode))
    v.append(plat_s >= ex.get('V_a_plateau_min_s', 20))
    valid = all(v)
    print('- V: %s (A plateau %.0f s)\n' % ('valid' if valid else 'VOID', plat_s))

    fa = A.frames_in(spans)
    acc = account(A, fa, 'A over its plateau span')
    if A.mark is not None:
        lo, hi = A.mark + SPAN[0], A.mark + SPAN[1]
        account(A, [f for f in A.frames if lo < f['wall'] <= hi],
                'A over [mark+40, mark+260]')
    if B.mark is not None and A.mark is not None:
        bspans = [(a - A.mark + B.mark, b - A.mark + B.mark) for a, b in spans]
        fb = B.frames_in(bspans)
        accb = account(B, fb, "B over A's plateau span (same seconds after mark)")
        lo, hi = B.mark + SPAN[0], B.mark + SPAN[1]
        fbw = [f for f in B.frames if lo < f['wall'] <= hi]
        account(B, fbw, 'B over [mark+40, mark+260]')
        bp = B.plateau()
        print('B by the same rule: %d windows, %.0f s\n' % (
            len(bp), sum(b - a for a, b, _, _ in bp)))
    else:
        accb, fbw = None, []

    pa = A.probe_in(spans)
    nf = sum(p[1] for p in pa)
    mid = (sum(p[1] * sum(n for k, (n, _) in p[4].items() if k not in FLIPLIKE)
               for p in pa) / nf) if nf else float('nan')
    allnd = (sum(p[1] * sum(n for n, _ in p[4].values()) for p in pa) / nf) if nf else float('nan')
    reasons = {}
    for p in pa:
        for k, (n, m) in p[4].items():
            r = reasons.setdefault(k, [0.0, 0.0])
            r[0] += p[1] * n
            r[1] += p[1] * m
    print('probe1010 over A plateau: %d lines, %d frames; mid-frame nd %.2f/f, all nd %.2f/f; '
          'by reason n/f ms/f: %s\n' % (
              len(pa), nf, mid, allnd,
              ' '.join('%s=%.2f/%.2f' % (k, r[0] / nf, r[1] / nf)
                       for k, r in sorted(reasons.items())) if nf else '-'))

    if acc:
        leg('S', ex['S_prun_min_ms'] <= acc['prun'] <= ex['S_prun_max_ms'] and
            acc['blk_share'] >= ex['S_blk_share_min'] and
            acc['gpuwait'] >= ex['S_gpuwait_share_of_blk_min'] and
            acc['locks'] <= ex['S_lock_share_of_blk_max'] and
            acc['rq_share'] <= ex['S_rq_share_max'],
            'p_run %.1f ms/f [%s, %s]; blk %.0f%% of P (>= %.0f%%); of blk: GPU waits %.0f%% '
            '(>= %.0f%%), locks %.0f%% (<= %.0f%%), pidle %.0f%%, dl %.0f%%; rq %.0f%% of P (<= %.0f%%)' % (
                acc['prun'], ex['S_prun_min_ms'], ex['S_prun_max_ms'],
                100 * acc['blk_share'], 100 * ex['S_blk_share_min'],
                100 * acc['gpuwait'], 100 * ex['S_gpuwait_share_of_blk_min'],
                100 * acc['locks'], 100 * ex['S_lock_share_of_blk_max'],
                100 * acc['pidle_share'], 100 * acc['dl_share'],
                100 * acc['rq_share'], 100 * ex['S_rq_share_max']))
        leg('G', acc['gpu50'] >= ex['G_gpu50_share_min'],
            'gpu/P p50 %.2f (>= %.2f; raw timestamps, x1/1.573 for true)' % (
                acc['gpu50'], ex['G_gpu50_share_min']))
    leg('W', mid == mid and mid >= ex['W_finish_per_frame_min'],
        'mid-frame non-deferred finishes %.2f/f (>= %.2f)' % (mid, ex['W_finish_per_frame_min']))
    if acc and accb:
        ratio = accb['P'] / acc['P']
        full = ''
        fa_w = [f for f in A.frames if A.mark + SPAN[0] < f['wall'] <= A.mark + SPAN[1]]
        if fa_w and fbw:
            full = '; over [mark+40, mark+260]: A %.1f, B %.1f ms, ratio %.2f (not judged)' % (
                mean([f['P'] for f in fa_w]) / 1000.0, mean([f['P'] for f in fbw]) / 1000.0,
                mean([f['P'] for f in fbw]) / mean([f['P'] for f in fa_w]))
        leg('P', ratio <= ex['P_ratio_max'],
            "B/A mean period over A's plateau span %.2f (<= %.2f; A %.1f, B %.1f ms)%s" % (
                ratio, ex['P_ratio_max'], acc['P'], accb['P'], full))
    if not valid:
        print('\nVOID: a V check failed; the legs above are printed, not scored.')


if __name__ == '__main__':
    main()
