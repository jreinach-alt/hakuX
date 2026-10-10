#!/usr/bin/env python3
"""Judge Addendum 1's recorder probes at the NFS MW race start (#433, lane.drawrec1010).

    proberead.py <result dir> [...] [--expect docs/testing/predictions/drawrec1010-probe.json]
                 [--window -2,1.5] [--vwindow -4,1.5] [--no-ft]

Each run's arm comes from its request.json env: HAKUX_PROBE_NULLREC=1 is
`nullrec` (the floor), HAKUX_PROBE_SNAPQ=1 `snapq` (the handoff's upper bound),
HAKUX_PROBE_SNAPQ=2 `snapq2` (its lower bound), anything else `base`.

Everything is read over the WARM countdown: the restarts go2..go12, lines
printed inside [mark+LO, mark+HI] (default -2,1.5, as drawread.py). The cold
start (`gameplay`) is printed apart and not judged.

  pace       drawread.pace_stats over hakuX-pace lines: ms per frame, v2 share
  vCPU       vcpuread.read's [rr425w] 2 s windows lying wholly inside
             [mark+VLO, mark+VHI] (default -4,1.5, vcpuread's own; a 2 s window
             rarely fits the 3.5 s countdown): busy and idle ms per frame
  [probe1010] hakuX-stall, one line per >= 60 flips (draw.c probe_tick):
             mid = GPU waits on the PFIFO thread at any finish but FLIP_STALL /
             PRESENTING (a non-deferred finish, or a rotation fence wait
             >= 100 us), per frame and ms each; flip = the same at the flip;
             hist = frames with 0/1/2/3/4+ mid waits; nd = non-deferred
             finishes by reason; rot = rotation fence waits; draws, null
             (NULLREC-skipped) draws; snap KB per draw, copy and enqueue us
  frametrace ftwin's per-frame table (P, crit, cls, v_run, p_run, pidle, waits)
             over the same warm frames, unless --no-ft

Verdict (the keys in the prediction's `expect`):
  BUILD       floor <= BUILD_floor_max, snapq - base <= BUILD_snapq_d_max and
              base mid waits per frame <= BUILD_mid_max
  DO NOT BUILD floor > NOBUILD_floor_min, or snapq2 - base >
              NOBUILD_snapq2_frac * (base - floor)
  OTHERWISE   the numbers; the deciding measurement is named in PR.md
  P_*         the registration's point ranges, each reported in or out
V: every run 12 marks, no fatal, the probe line matching its env, drawrec=1,
   a frametrace CSV; >= V_min_pace warm pace lines per arm.
"""
import argparse
import glob
import io
import json
import os
import re
import sys
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'nfs30plan1010'))
import drawread  # noqa: E402
import vcpuread  # noqa: E402

TS = drawread.TS
CFG = re.compile(r'\[probe1010\] waits=(\d) nullrec=(\d) snapq=(\d)')
PROBE = re.compile(
    r'\[probe1010\] f=(\d+) nullrec=(\d) snapq=(\d) mid=([\d.]+)/f ([\d.]+)ms/f each=([\d.]+)ms '
    r'flip=([\d.]+)/f ([\d.]+)ms/f hist=(\d+)/(\d+)/(\d+)/(\d+)/(\d+) max=(\d+) '
    r'\| nd n/f ms/f:(.*?) \| rot=([\d.]+)/f blk=([\d.]+)/f ([\d.]+)ms/f '
    r'\| draws=([\d.]+)/f null=([\d.]+)/f \| snap=([\d.]+)/f KB=([\d.]+) copy_us=([\d.]+) enq_us=([\d.]+)')
ND = re.compile(r'(\w+)=([\d.]+)/([\d.]+)')
ARMS = ('base', 'nullrec', 'snapq', 'snapq2')


def arm_of(env):
    if 'HAKUX_PROBE_NULLREC=1' in env:
        return 'nullrec'
    if 'HAKUX_PROBE_SNAPQ=2' in env:
        return 'snapq2'
    if 'HAKUX_PROBE_SNAPQ=1' in env:
        return 'snapq'
    return 'base'


def read_probe(d):
    cfg, rows = None, []
    with open(os.path.join(d, 'logcat.txt'), errors='replace') as f:
        for ln in f:
            if '[probe1010]' not in ln:
                continue
            m = TS.match(ln)
            if not m:
                continue
            t = drawread.secs(m)
            q = PROBE.search(ln)
            if q:
                g = q.groups()
                f = int(g[0])
                nd = {k: (float(n) * f, float(ms) * f) for k, n, ms in ND.findall(g[14])}
                rows.append({'t': t, 'f': f, 'mid': float(g[3]) * f, 'mid_ms': float(g[4]) * f,
                             'flip': float(g[6]) * f, 'flip_ms': float(g[7]) * f,
                             'hist': [int(x) for x in g[8:13]], 'max': int(g[13]), 'nd': nd,
                             'rot': float(g[15]) * f, 'blk': float(g[16]) * f, 'rot_ms': float(g[17]) * f,
                             'draws': float(g[18]) * f, 'null': float(g[19]) * f,
                             'snap': float(g[20]) * f, 'kb': float(g[21]),
                             'copy_us': float(g[22]), 'enq_us': float(g[23])})
                continue
            q = CFG.search(ln)
            if q and cfg is None:
                cfg = tuple(int(x) for x in q.groups())
    return cfg, rows


def in_windows(items, marks, lo, hi, which, key=lambda e: e[0]):
    out = []
    for mt, name in marks:
        if (which == 'warm') == (name == 'gameplay'):
            continue
        out += [e for e in items if mt + lo <= key(e) <= mt + hi]
    return out


def probe_stats(rows):
    f = sum(r['f'] for r in rows)
    if not f:
        return None
    s = {k: sum(r[k] for r in rows) / f for k in
         ('mid', 'mid_ms', 'flip', 'flip_ms', 'rot', 'blk', 'rot_ms', 'draws', 'null', 'snap')}
    s['frames'] = f
    s['each'] = s['mid_ms'] / s['mid'] if s['mid'] else 0.0
    s['hist'] = [sum(r['hist'][i] for r in rows) for i in range(5)]
    s['max'] = max(r['max'] for r in rows)
    nd = {}
    for r in rows:
        for k, (n, ms) in r['nd'].items():
            a = nd.setdefault(k, [0.0, 0.0])
            a[0] += n
            a[1] += ms
    s['nd'] = {k: (n / f, ms / f) for k, (n, ms) in nd.items()}
    sn = sum(r['snap'] for r in rows)
    s['kb'] = sum(r['kb'] * r['snap'] for r in rows) / sn if sn else 0.0
    s['copy_us'] = sum(r['copy_us'] * r['snap'] for r in rows) / sn if sn else 0.0
    s['enq_us'] = sum(r['enq_us'] * r['snap'] for r in rows) / sn if sn else 0.0
    return s


def vcpu_stats(d, which, vlo, vhi):
    rrw, pace, marks = vcpuread.read(os.path.join(d, 'logcat.txt'))
    n, fr, busy, idle = 0, 0.0, 0.0, 0.0
    if not (rrw and pace and marks):
        return n, fr, busy, idle
    for mt, name in marks:
        if (which == 'warm') == (name == 'gameplay'):
            continue
        for t, i_us, b_us, _ in rrw:
            t0 = t - (i_us + b_us) / 1e6
            if t0 >= mt + vlo and t <= mt + vhi:
                f = vcpuread.frames_at(pace, t) - vcpuread.frames_at(pace, t0)
                if f > 0:
                    n += 1
                    fr += f
                    busy += b_us / 1e3
                    idle += i_us / 1e3
    return n, fr, busy, idle


def ft_table(dirs, lo, hi, which):
    """ftwin's table over the warm (or cold) frames of these runs, as text."""
    try:
        import ftwin
    except ImportError as e:
        return f"  (ftwin unavailable: {e})\n"
    pooled = []
    for d in dirs:
        marks, anchors = ftwin.read_log(os.path.join(d, 'logcat.txt'))
        if not anchors or not marks or not glob.glob(os.path.join(d, 'pulled', 'frametrace_*.csv')):
            continue
        _, rows = ftwin.pick_csv(d, anchors)
        if not rows:
            continue
        ftwin.wall_of(rows, anchors)
        for mt, name in marks:
            if (which == 'warm') == (name == 'gameplay'):
                continue
            pooled += [r for r in rows if mt + lo <= r['wall'] <= mt + hi]
    buf = io.StringIO()
    with redirect_stdout(buf):
        ftwin.table(f'{which} frames', pooled, False)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--expect')
    ap.add_argument('--window', default='-2,1.5')
    ap.add_argument('--vwindow', default='-4,1.5')
    ap.add_argument('--no-ft', action='store_true')
    a = ap.parse_args()
    lo, hi = (float(x) for x in a.window.split(','))
    vlo, vhi = (float(x) for x in a.vwindow.split(','))
    exp = json.load(open(a.expect)).get('expect', {}) if a.expect else {}

    runs = []
    print(f"window: print time in mark{lo:+.1f} .. mark{hi:+.1f} s (vCPU: windows inside mark{vlo:+.1f} .. mark{vhi:+.1f})")
    print(f"{'run':42s} {'arm':8s} {'apk':12s} marks fatal probe-cfg drawrec ftcsv")
    v_ok = True
    for d in a.dirs:
        r = drawread.read_run(d)
        env = json.load(open(os.path.join(d, 'request.json'))).get('env') or []
        r['arm'] = arm_of(env)
        r['cfg'], r['probe'] = read_probe(d)
        r['ft'] = len(glob.glob(os.path.join(d, 'pulled', 'frametrace_*.csv')))
        want = (1, int(r['arm'] == 'nullrec'), {'snapq': 1, 'snapq2': 2}.get(r['arm'], 0))
        ok = (len(r['marks']) >= exp.get('V_marks', 12) and r['fatal'] == 0 and r['cfg'] == want
              and r['switch'] is not None and r['switch'][0] == 1 and r['ft'] > 0)
        v_ok &= ok
        print(f"{r['name']:42s} {r['arm']:8s} {r['apk']:12s} {len(r['marks']):5d} {r['fatal']:5d} "
              f"{r['cfg']} {r['switch']} {r['ft']}  {'ok' if ok else 'VOID'}")
        runs.append(r)

    res = {}
    for which in ('cold', 'warm'):
        print(f"\n== {which} countdown, pooled per arm")
        for arm in ARMS:
            sel = [r for r in runs if r['arm'] == arm]
            if not sel:
                continue
            pace = []
            prows = []
            vn = vf = vb = vi = 0.0
            for r in sel:
                pace += in_windows(r['pace'], r['marks'], lo, hi, which)
                prows += in_windows(r['probe'], r['marks'], lo, hi, which, key=lambda e: e['t'])
                n, fr, busy, idle = vcpu_stats(r['dir'], which, vlo, vhi)
                vn += n
                vf += fr
                vb += busy
                vi += idle
            ps = drawread.pace_stats(pace)
            pr = probe_stats(prows)
            res[(arm, which)] = (ps, pr, (vn, vf, vb, vi))
            print(f"  {arm:8s} runs {len(sel)}: pace lines {ps['n']}: {ps['ms']:.1f} ms/frame, "
                  f"v2 {ps['v2']:.1f}% v3 {ps['v3']:.1f}% v4+ {ps['v4+']:.1f}%")
            if vf:
                print(f"           vCPU ({int(vn)} rr425w windows, {vf:.0f} frames): {(vb + vi) / vf:.1f} ms/frame, "
                      f"busy {vb / vf:.1f}, idle {vi / vf:.1f} ({100 * vb / (vb + vi):.0f}% busy)")
            else:
                print("           vCPU: no rr425w window inside")
            if pr:
                hist = '/'.join(str(x) for x in pr['hist'])
                nd = ' '.join(f"{k}={n:.2f}/{ms:.2f}" for k, (n, ms) in sorted(pr['nd'].items())) or 'none'
                print(f"           [probe1010] {pr['frames']} frames: mid {pr['mid']:.2f}/f {pr['mid_ms']:.2f} ms/f "
                      f"(each {pr['each']:.2f} ms), flip {pr['flip']:.2f}/f {pr['flip_ms']:.2f} ms/f, "
                      f"hist {hist}, max {pr['max']}")
                print(f"           nd n/f ms/f: {nd} | rot {pr['rot']:.2f}/f, >=100us {pr['blk']:.2f}/f, "
                      f"{pr['rot_ms']:.2f} ms/f | draws {pr['draws']:.0f}/f, null {pr['null']:.0f}/f"
                      + (f" | snap {pr['snap']:.0f}/f, {pr['kb']:.1f} KB, copy {pr['copy_us']:.2f} us, "
                         f"enq {pr['enq_us']:.2f} us = {pr['snap'] * (pr['copy_us'] + pr['enq_us']) / 1000:.2f} ms/f"
                         if pr['snap'] else ''))
            else:
                print("           [probe1010]: no line inside")
            if not a.no_ft:
                sys.stdout.write(ft_table([r['dir'] for r in sel], lo, hi, which))

    def warm(arm):
        return res.get((arm, 'warm'), ({'ms': float('nan'), 'n': 0}, None, None))

    base, floor = warm('base')[0]['ms'], warm('nullrec')[0]['ms']
    sq, sq2 = warm('snapq')[0]['ms'], warm('snapq2')[0]['ms']
    bpr = warm('base')[1]
    mid = bpr['mid'] if bpr else float('nan')
    d1, d2 = sq - base, sq2 - base
    pace_ok = all(warm(arm)[0]['n'] >= exp.get('V_min_pace', 15) for arm in ARMS)
    v_ok &= pace_ok

    print("\n== Verdict (warm countdown)")
    print(f"  base {base:.1f}, floor (NULLREC) {floor:.1f}, base - floor {base - floor:.1f} ms/frame")
    print(f"  SNAPQ=1 {sq:.1f} (delta {d1:+.1f}), SNAPQ=2 {sq2:.1f} (delta {d2:+.1f}) ms/frame")
    print(f"  base mid-frame GPU waits on the PFIFO thread: {mid:.2f}/frame"
          + (f", {bpr['each']:.2f} ms each, {bpr['mid_ms']:.2f} ms/frame" if bpr else ''))
    print(f"  V: {'PASS' if v_ok else 'FAIL'} (pace lines per arm: "
          + ', '.join(f"{arm} {warm(arm)[0]['n']}" for arm in ARMS) + ')')
    build = (floor <= exp.get('BUILD_floor_max', 28) and d1 <= exp.get('BUILD_snapq_d_max', 2)
             and mid <= exp.get('BUILD_mid_max', 1))
    nobuild = (floor > exp.get('NOBUILD_floor_min', 33)
               or d2 > exp.get('NOBUILD_snapq2_frac', 0.5) * (base - floor))
    verdict = 'VOID' if not v_ok else 'BUILD' if build else 'DO NOT BUILD' if nobuild else 'OTHERWISE'
    print(f"  BUILD rule: floor {floor:.1f} <= {exp.get('BUILD_floor_max', 28)}: {floor <= exp.get('BUILD_floor_max', 28)}; "
          f"SNAPQ=1 delta {d1:+.1f} <= {exp.get('BUILD_snapq_d_max', 2)}: {d1 <= exp.get('BUILD_snapq_d_max', 2)}; "
          f"mid {mid:.2f} <= {exp.get('BUILD_mid_max', 1)}: {mid <= exp.get('BUILD_mid_max', 1)}")
    print(f"  DO NOT BUILD rule: floor {floor:.1f} > {exp.get('NOBUILD_floor_min', 33)}: "
          f"{floor > exp.get('NOBUILD_floor_min', 33)}; SNAPQ=2 delta {d2:+.1f} > "
          f"{exp.get('NOBUILD_snapq2_frac', 0.5)} x {base - floor:.1f}: "
          f"{d2 > exp.get('NOBUILD_snapq2_frac', 0.5) * (base - floor)}")
    for key, val in (('base', base), ('floor', floor), ('snapq_d', d1), ('snapq2_d', d2), ('mid', mid)):
        lo_, hi_ = exp.get(f'P_{key}_lo'), exp.get(f'P_{key}_hi')
        if lo_ is not None:
            print(f"  P_{key}: {val:.2f} in [{lo_}, {hi_}]: {'in' if lo_ <= val <= hi_ else 'OUT'}")
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
