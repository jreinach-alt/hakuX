#!/usr/bin/env python3
"""lane.defaulton1017: judge of docs/testing/predictions/defaulton1017-screen.json (#1018).

usage: screenread.py --row HON=<id or dir> [--row HNI=...] [--row HOFF=...] [--row MKSM=...] [--row TS=...]
                     [--row RS=...] [--row SHR=...] [--row CLR=...] [--row AMP=...] [--ref EIF=<id or dir>]
                     [--expect PREDICTION.json]

Written before any row ran. One build (ed2b1d3333), the Nova. The four switches read unset as on, so the ON
rows carry no switch env; HNI sets HAKUX_IBC=0, HOFF sets all four to 0. An id is looked up as
dispatch/results/*<id>. --ref EIF= (halo1016's arm EIF, 0-0-x-1792231794-halo1016-2208719) is printed beside
the Halo rows, not judged.

Per row, read from logcat.txt and run.log:
  switches  the first `[s2tcvt] on|off`, `[rearly1018] early=`, `[fldcw1018] chain=`, `[ibc507] on=` lines and
            the env value each names. `[s2tcvt]` logs only where the check is reached (the first surface
            download that could take the decode), so a title that never reaches it logs neither.
  report    the `[rearly1018] w` windows: early cold unarmed submit skip0 skipn full stale vis desync. Halo
            rows: the windows with mark+131 < t <= mark+191 (halo1016's span); other rows: every window.
            early share = early / (early + cold + skip0 + skipn + full); vis, stale, desync per early.
  fldcw     the last `[fldcw1018] n= flips=` line (cumulative; one every 2^20 FLDCW calls).
  end       valid end: no crash line (`hakuX-crash`, `Fatal signal`), hakuX-pace lines from launch to within
            15 s of the logcat's last line and covering >= seconds - 45 s, and the pace frame count still
            rising over the last 30 s of pace lines. Route end (`ROUTE ... end` in run.log) is reported.
  Halo      censusread's ms per guest frame over [mark+131, mark+191] and per 10-s window from mark+100 to
            mark+210 (the 12 windows halo1016 quoted as "33.4-34.7" for EIF); `[rtrace] w` windows and mode.
  MKSM      fps1015's s2tread.read_run with the arm set to `on` (s2tread names the arm from the env, and the
            ON row has none): s2tread's V for an on run, and `locked`, the first 30 windows (1800 guest
            frames) from shot s13, in frames a second: fps1015's on runs 54.2 and 54.4.
  TS        fps1015's tsread.read_run, arm `on`: tsread's V for an on run and the play span's median gfps:
            fps1015's on run 59.0.

V (a failure voids that row's legs):
  ON rows   `[rearly1018] early=1`, `[fldcw1018] chain=1`, `[ibc507] on=1 layout=ok`, each naming its
            variable `(unset)`; `[s2tcvt] on HAKUX_S2T_CVT=(unset)` if an `[s2tcvt]` line is logged
            (required in Halo, MKSM and TS, which reach it). A row whose request sets HAKUX_IBC=0 (HNI, and
            every title row queued after the pilot: NOTES, 05:25) wants `[ibc507] on=0` and `HAKUX_IBC=0`.
            HOFF: `[s2tcvt] off`, `early=0`, `chain=0`, `on=0`.
  Halo      `mark cinematic` and >= 20 `[rtrace] w` windows, all mode=async.
  every row a valid end, as above.

Legs (thresholds from the prediction's expect block):
  HG    HON ms/f over the span <= HG_msf_max and every 10-s window <= HG_window_max.
  HEA   HON early share over the span >= HEA_share_min.
  HVIS  HON vis / early over the span <= VIS_share_max.
  HDS   desync / early <= DS_share_max in every ON row (HON, HNI, MKSM, TS, RS, SHR, CLR, AMP) whose early > 0.
  HIBC  HNI ms/f >= HON ms/f + HIBC_delta_min (IBC is needed for Halo's bar; a MISS sends IBC back to off).
  HOFF  HOFF ms/f >= HOFF_msf_min.
  MKF   MKSM locked fps >= MKF_fps_min.
  MKE   MKSM early (every window) <= MKE_early_max.
  TSF   TS play median gfps >= TSF_fps_min.
  RV SV CV AV  RS, SHR, CLR, AMP each end valid; VIS:<row> in each whose early >= VIS_min_early: vis / early
        <= VIS_share_max.
  FL    flips <= FL_flips_max in every ON row that logs a `[fldcw1018] n=` line.
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LANES = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(LANES, 'halo1016'))
sys.path.insert(0, os.path.join(LANES, 'fps1015'))
from cineread import ts  # noqa: E402
from reportread import SPAN, read_trace  # noqa: E402
from vcpuread import VArm, leg, window_msf  # noqa: E402
import s2tread  # noqa: E402
import tsread  # noqa: E402

RESULTS = '/home/justin/hakux-work/dispatch/results'
ORDER = ('HON', 'HNI', 'HOFF', 'MKSM', 'TS', 'RS', 'SHR', 'CLR', 'AMP', 'EIF')
HALO = {'HON', 'HNI', 'HOFF', 'EIF'}
ON = ('HON', 'HNI', 'MKSM', 'TS', 'RS', 'SHR', 'CLR', 'AMP')
S2T_REACHED = {'HON', 'HNI', 'HOFF', 'MKSM', 'TS'}
TAIL = ('RV', 'RS'), ('SV', 'SHR'), ('CV', 'CLR'), ('AV', 'AMP')
RK = ('early', 'cold', 'unarmed', 'submit', 'skip0', 'skipn', 'full', 'stale', 'vis', 'desync')
CRASH = re.compile(r'hakuX-crash|Fatal signal')
VAR = re.compile(r'(HAKUX_\w+)=(\S+)')


def resolve(x):
    if os.path.isdir(x):
        return x
    hits = sorted(glob.glob(os.path.join(RESULTS, '*' + x)))
    if len(hits) != 1:
        sys.exit('%s: %d result dirs match' % (x, len(hits)))
    return hits[0]


class Row:
    def __init__(self, role, d):
        self.role, self.d = role, d
        self.name = os.path.basename(os.path.normpath(d))
        self.req = json.load(open(os.path.join(d, 'request.json')))
        self.sw = {}          # switch -> (state text, env value)
        self.win = []         # (t, {field: n})
        self.fld = None       # (n, flips)
        self.pace = []        # (t, f)
        self.crash = []
        self.last = None
        self.needs_async = False
        f_re = re.compile(r'hakuX-pace\(\s*\d+\): f=(\d+)')
        for line in open(os.path.join(d, 'logcat.txt'), errors='replace'):
            t = ts(line)
            if t is not None:
                self.last = t
            if CRASH.search(line):
                self.crash.append(line.strip()[:200])
            m = f_re.search(line)
            if m:
                self.pace.append((t, int(m.group(1))))
                continue
            if '[s2tcvt] on' in line or '[s2tcvt] off' in line:
                self.first('s2t', 'on' if '[s2tcvt] on' in line else 'off', line)
            elif '[rearly1018] needs' in line:
                self.needs_async = True
            elif '[rearly1018] early=' in line:
                self.first('early', re.search(r'early=(\d)', line).group(1), line)
            elif '[rearly1018] w ' in line:
                self.win.append((t, {k: int(v) for k, v in re.findall(r' (\w+)=(\d+)', line.split('] w', 1)[1])}))
            elif '[fldcw1018] chain=' in line:
                self.first('chain', re.search(r'chain=(\d)', line).group(1), line)
            elif '[fldcw1018] n=' in line:
                m = re.search(r'n=(\d+) flips=(\d+)', line)
                self.fld = (int(m.group(1)), int(m.group(2)))
            elif '[ibc507] on=' in line:
                m = re.search(r'on=(\d) layout=(\w+)', line)
                self.first('ibc', '%s %s' % (m.group(1), m.group(2)), line)
        self.route_end = False
        self.held = None
        rl = os.path.join(d, 'run.log')
        if os.path.exists(rl):
            for line in open(rl, errors='replace'):
                if re.match(r'^ROUTE \S+ end\b', line):
                    self.route_end = True
                m = re.match(r'^held .* for (\d+)s', line)
                if m:
                    self.held = int(m.group(1))
        self.halo = VArm(d) if role in HALO else None

    def first(self, k, state, line):
        if k not in self.sw:
            m = VAR.search(line)
            self.sw[k] = (state, m.group(2) if m else None)

    def report(self, lo=None, hi=None):
        tot = dict.fromkeys(RK, 0)
        n = 0
        for t, kv in self.win:
            if lo is not None and not (t is not None and lo < t <= hi):
                continue
            n += 1
            for k in RK:
                tot[k] += kv.get(k, 0)
        tot['windows'] = n
        den = tot['early'] + tot['cold'] + tot['skip0'] + tot['skipn'] + tot['full']
        e = tot['early']
        tot['share'] = e / den if den else float('nan')
        for k in ('vis', 'stale', 'desync'):
            tot[k + '_share'] = tot[k] / e if e else float('nan')
        return tot

    def end(self):
        why = []
        if self.crash:
            why.append('%d crash lines, first: %s' % (len(self.crash), self.crash[0]))
        p = [x for x in self.pace if x[0] is not None]
        secs = self.req.get('seconds') or 0
        if not p:
            why.append('no hakuX-pace lines')
            return why
        if self.last - p[-1][0] > 15:
            why.append('pace stops %.0f s before the log ends' % (self.last - p[-1][0]))
        if p[-1][0] - p[0][0] < secs - 45:
            why.append('pace covers %.0f s of %d' % (p[-1][0] - p[0][0], secs))
        back = [f for t, f in p if t <= p[-1][0] - 30]
        if back and p[-1][1] <= back[-1]:
            why.append('pace frame count flat over the last 30 s (f=%d)' % p[-1][1])
        return why


def want(role, env):
    """(state, env value) each switch line must show. IBC follows the request: rows queued after the pilot
    carry HAKUX_IBC=0, because HIBC missed and the registered rule sends IBC back to off (NOTES, 05:25)."""
    if role == 'HOFF':
        return {'s2t': ('off', '0'), 'early': ('0', '0'), 'chain': ('0', '0'), 'ibc': ('0 ok', '0')}
    w = {'s2t': ('on', '(unset)'), 'early': ('1', '(unset)'), 'chain': ('1', '(unset)'),
         'ibc': ('1 ok', '(unset)')}
    if 'HAKUX_IBC=0' in env:
        w['ibc'] = ('0 ok', '0')
    return w


def fmt(x, nd=1):
    return '-' if x is None or x != x else '%.*f' % (nd, x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--row', action='append', default=[])
    ap.add_argument('--ref', action='append', default=[])
    ap.add_argument('--expect')
    o = ap.parse_args()
    e = json.load(open(o.expect))['expect'] if o.expect else {}
    dirs = {k: resolve(v) for k, v in (a.split('=', 1) for a in o.row + o.ref)}
    rows = {r: Row(r, dirs[r]) for r in ORDER if r in dirs}
    bad, rep, halo, mk, tsr = {}, {}, {}, None, None

    for r, x in rows.items():
        why = []
        if r != 'EIF':
            for k, (st, ev) in want(r, x.req.get('env') or []).items():
                got = x.sw.get(k)
                if got is None:
                    if k != 's2t' or r in S2T_REACHED:
                        why.append('no %s line' % k)
                elif got != (st, ev):
                    why.append('%s %s %s=%s, want %s %s' % (k, got[0], k, got[1], st, ev))
            if x.needs_async:
                why.append('[rearly1018] needs HAKUX_REPORT_ASYNC=1')
            why += x.end()
        if x.halo is not None:
            if x.halo.mark is None:
                why.append('no mark cinematic')
            else:
                s0, s1 = x.halo.span(*SPAN)
                tr = read_trace(x.d, x.halo.mark)
                halo[r] = {'msf': x.halo.msf(s0, s1), 'w': window_msf(x.halo), 'tr': tr}
                if tr['windows'] < 20 or tr['modes'] != {'async'}:
                    why.append('%d [rtrace] w windows, modes %s' % (tr['windows'], sorted(tr['modes'])))
                rep[r] = x.report(s0, s1)
        else:
            rep[r] = x.report()
        if r == 'MKSM':
            mk = s2tread.read_run(x.d)
            mk['arm'] = 'on'
            if 'error' in mk:
                why.append('s2tread: %s' % mk['error'])
            else:
                cut = [w for w in mk['windows'] if w['span'] == 'cut']
                play = [w for w in mk['windows'] if w['span'] == 'play']
                sig = sum(1 for w in cut if s2tread.signature('on', w))
                lock = [w for w in mk['windows'] if w['t0'] >= mk['cut'][0]][:s2tread.CUTN]
                secs = lock[-1]['t'] - lock[0]['t0'] if lock else 0
                mk['locked'] = 60.0 * len(lock) / secs if secs else float('nan')
                mk['v'] = (len(cut), sig, len(play), mk['on_lines'], len(mk['first']), len(lock))
                if len(cut) < 15 or sig * 3 < len(cut) * 2 or len(play) < 8 or not mk['on_lines'] \
                        or not mk['first'] or len(lock) < s2tread.CUTN:
                    why.append('s2tread V: cut %d sig %d play %d on %d first %d locked windows %d' % mk['v'])
        if r == 'TS':
            tsr = tsread.read_run(x.d)
            tsr['arm'] = 'on'
            if 'error' in tsr:
                why.append('tsread: %s' % tsr['error'])
            else:
                intro = [w for w in tsr['windows'] if w['span'] == 'intro']
                play = [w for w in tsr['windows'] if w['span'] == 'play']
                sig = sum(1 for w in play if tsread.signature('on', w))
                tsr['gfps'] = s2tread.med(play, 'gfps')
                tsr['v'] = (len(intro), len(play), sig, tsr['on_lines'])
                if len(intro) < 10 or len(play) < 30 or sig * 3 < len(play) * 2 or not tsr['on_lines']:
                    why.append('tsread V: intro %d play %d sig %d on %d' % tsr['v'])
        if why and r != 'EIF':
            bad[r] = why

    print('### switches, as each row logged them (state, env value)\n')
    print('| row | dir | s2tcvt | rearly | fldcw chain | ibc | crash | pace s | route end | held s |')
    print('|---|---|---|---|---|---|---|---|---|---|')
    for r, x in rows.items():
        p = [t for t, _ in x.pace if t is not None]
        print('| %s | %s | %s | %s | %s | %s | %d | %s | %s | %s |' % (
            r, x.name, *(('%s %s' % x.sw[k]) if k in x.sw else '-' for k in ('s2t', 'early', 'chain', 'ibc')),
            len(x.crash), '%.0f' % (p[-1] - p[0]) if p else '-', 'yes' if x.route_end else 'no', x.held))
    print('\n### reports (Halo rows: windows in [mark+%d, mark+%d]; others: every window)\n' % SPAN)
    print('| row | windows | early | cold | unarmed | skip0 | skipn | full | early share | stale/early | '
          'vis/early | desync/early | fldcw n | flips |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for r, x in rows.items():
        t = rep.get(r)
        if t is None:
            continue
        print('| %s | %d | %d | %d | %d | %d | %d | %d | %s | %s | %s | %s | %s | %s |' % (
            r, t['windows'], t['early'], t['cold'], t['unarmed'], t['skip0'], t['skipn'], t['full'],
            fmt(t['share'], 4), fmt(t['stale_share'], 4), fmt(t['vis_share'], 4), fmt(t['desync_share'], 5),
            x.fld[0] if x.fld else '-', x.fld[1] if x.fld else '-'))
    if halo:
        print('\n### Halo: ms per guest frame over [mark+%d, mark+%d], and per 10-s window from mark+100\n' % SPAN)
        print('| row | span | ' + ' | '.join('+%d' % v for v in range(100, 220, 10)) + ' | rtrace windows |')
        print('|---' * 15 + '|')
        for r in ORDER:
            if r in halo:
                h = halo[r]
                print('| %s | %.1f | %s | %d %s |' % (r, h['msf'], ' | '.join('%.1f' % v for v in h['w']),
                                                    h['tr']['windows'], ','.join(sorted(h['tr']['modes']))))
    if mk and 'locked' in mk:
        print('\n- MKSM: locked %.1f fps over the first %d windows from s13; cutscene median gfps %s, '
              'gameplay median gfps %s; V cut/sig/play/on/first/locked %s'
              % (mk['locked'], mk['v'][5], fmt(s2tread.med([w for w in mk['windows'] if w['span'] == 'cut'], 'gfps')),
                 fmt(s2tread.med([w for w in mk['windows'] if w['span'] == 'play'], 'gfps')), mk['v']))
    if tsr and 'gfps' in tsr:
        print('- TS: play median gfps %s; V intro/play/sig/on %s' % (fmt(tsr['gfps']), tsr['v']))

    print('\n### verdict\n')
    for r, why in bad.items():
        print('- V: %s VOID  %s' % (r, '; '.join(why)))
    ok = lambda r: r in rows and r not in bad  # noqa: E731
    if ok('HON') and 'HON' in halo:
        h = halo['HON']
        leg('HG', h['msf'] <= e['HG_msf_max'] and max(h['w']) <= e['HG_window_max'],
            'HON %.1f ms/f (<= %.1f), windows %.1f-%.1f (<= %.1f)'
            % (h['msf'], e['HG_msf_max'], min(h['w']), max(h['w']), e['HG_window_max']))
        t = rep['HON']
        leg('HEA', t['share'] >= e['HEA_share_min'], 'HON early %d, share %.4f (>= %.2f)'
            % (t['early'], t['share'], e['HEA_share_min']))
        leg('HVIS', t['vis_share'] <= e['VIS_share_max'], 'HON vis %d of %d early, %.4f (<= %.2f)'
            % (t['vis'], t['early'], t['vis_share'], e['VIS_share_max']))
    else:
        for k in ('HG', 'HEA', 'HVIS'):
            leg(k, None, 'HON void or absent')
    ds = [(r, rep[r]) for r in ON if ok(r) and rep[r]['early'] > 0]
    leg('HDS', all(t['desync_share'] <= e['DS_share_max'] for _, t in ds) if ds else None,
        '; '.join('%s %d of %d' % (r, t['desync'], t['early']) for r, t in ds) or 'no ON row with early > 0')
    if ok('HON') and ok('HNI') and 'HON' in halo and 'HNI' in halo:
        dl = halo['HNI']['msf'] - halo['HON']['msf']
        leg('HIBC', dl >= e['HIBC_delta_min'], 'HNI %.1f - HON %.1f = %+.2f ms/f (>= +%.1f)'
            % (halo['HNI']['msf'], halo['HON']['msf'], dl, e['HIBC_delta_min']))
    else:
        leg('HIBC', None, 'HON or HNI void or absent')
    if ok('HOFF') and 'HOFF' in halo:
        leg('HOFF', halo['HOFF']['msf'] >= e['HOFF_msf_min'], 'HOFF %.1f ms/f (>= %.1f)'
            % (halo['HOFF']['msf'], e['HOFF_msf_min']))
    else:
        leg('HOFF', None, 'HOFF void or absent')
    if ok('MKSM'):
        leg('MKF', mk['locked'] >= e['MKF_fps_min'], 'MKSM locked %.1f fps (>= %.0f)'
            % (mk['locked'], e['MKF_fps_min']))
        leg('MKE', rep['MKSM']['early'] <= e['MKE_early_max'], 'MKSM early %d (<= %d)'
            % (rep['MKSM']['early'], e['MKE_early_max']))
    else:
        leg('MKF', None, 'MKSM void or absent')
        leg('MKE', None, 'MKSM void or absent')
    if ok('TS'):
        leg('TSF', tsr['gfps'] >= e['TSF_fps_min'], 'TS play median %.1f fps (>= %.0f)'
            % (tsr['gfps'], e['TSF_fps_min']))
    else:
        leg('TSF', None, 'TS void or absent')
    for k, r in TAIL:
        if r not in rows:
            leg(k, None, '%s absent' % r)
            continue
        leg(k, r not in bad, '%s %s' % (r, 'valid end' if r not in bad else '; '.join(bad[r])))
        t = rep[r]
        if r not in bad and t['early'] >= e['VIS_min_early']:
            leg('VIS:' + r, t['vis_share'] <= e['VIS_share_max'], '%s vis %d of %d early, %.4f (<= %.2f)'
                % (r, t['vis'], t['early'], t['vis_share'], e['VIS_share_max']))
        else:
            print('- VIS:%s: not judged, early %d (< %d) or row void' % (r, t['early'], e['VIS_min_early']))
    fl = [(r, rows[r].fld) for r in ON if ok(r) and rows[r].fld]
    leg('FL', all(f[1] <= e['FL_flips_max'] for _, f in fl) if fl else None,
        '; '.join('%s %d of %d' % (r, f[1], f[0]) for r, f in fl) or 'no ON row logs a flips line')
    return 0


if __name__ == '__main__':
    sys.exit(main())
