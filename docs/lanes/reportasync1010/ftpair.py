#!/usr/bin/env python3
"""Frametrace pair at the NFS race start: where the period goes (#433, lane.reportasync1010).

    ftpair.py <A dir> <B dir> [--expect docs/testing/predictions/reportasync1010-ftpair.json]

A is `HAKUX_FRAMETRACE=1` alone, B adds `HAKUX_REPORT_ASYNC=1 HAKUX_TEXSCAN=1`; both perflog
builds, route nfs-mw-quickrace, `--pull 'frametrace_*'`. Frames come from ftwin.py
(docs/lanes/nfs30plan1010): a frame belongs to a window when its END falls in it. Windows:
cold = mark gameplay, -2 .. +1.5 s; warm = go2..go12, -2 .. +1.5 s; post = go2..go12, +1.5 .. +12 s.
A start whose route input hung or failed (raread.bad_starts) is left out. `heavy` = frames of
3+ VBLANKs (vb >= 3): the ones that missed 30 fps.

The PFIFO thread paces the frame, and its schedstat row sums to the period:

    P = p_run + p_rq + p_blk,  p_blk = pidle + hooked waits (p_<site>) + unhooked

  p_run      on CPU: recording (phase `Draw`, phaseread.py) + method parsing, finishes, the rest
  pidle      waiting for the guest's next frame (the VBLANK grid line, plus guest work)
  p_c_rep    hooked waits under pgraph_process_pending_reports (the #804 report fence)
  p_oth_hk   the other hooked waits (fences, submits, downloads) outside that context
  unhooked   blocked at no hooked site: the sd finishes' finish_event wait (cube faces),
             wait_frame_submitted, and the async path's rule-3 gate
  o_fence    fence waits on unregistered threads: the render thread's process_finish and,
             on B, the report reader `nv2a.vk.reports` (off the pacing thread)
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'nfs30plan1010'))
sys.path.insert(0, HERE)
import ftwin  # noqa: E402
import raread  # noqa: E402

P_SITES = ['p_bql', 'p_pfl', 'p_pgl', 'p_halt', 'p_idle', 'p_fence', 'p_submit', 'p_rthr', 'p_dl', 'p_oth']
WINDOWS = [('cold', 'cold', -2.0, 1.5), ('warm', 'warm', -2.0, 1.5), ('post', 'warm', 1.5, 12.0)]
ROWS = ['P', 'p_run', 'p_rq', 'p_blk', 'pidle', 'p_c_rep', 'p_oth_hk', 'unhooked', 'o_fence', 'gpu', 'vb']


def env_of(d):
    try:
        req = json.load(open(os.path.join(d, 'request.json')))
    except (OSError, ValueError):
        return [], ''
    return req.get('env') or [], str(req.get('perflog') or '')


def load(d):
    marks, anchors = ftwin.read_log(os.path.join(d, 'logcat.txt'))
    if not marks or not anchors:
        return None
    path, rows = ftwin.pick_csv(d, anchors)
    if not rows:
        return None
    ftwin.wall_of(rows, anchors)
    bad = raread.bad_starts(d)
    out = {'marks': len(marks), 'bad': bad, 'csv': os.path.basename(path)}
    for name, which, lo, hi in WINDOWS:
        sel = []
        for mt, mk in marks:
            if mk in bad:
                continue
            if (which == 'cold') != (mk == 'gameplay'):
                continue
            sel += [r for r in rows if mt + lo <= r['wall'] <= mt + hi]
        out[name] = sel
    return out


def mean_ms(fr, c):
    vals = [r[c] for r in fr if r.get(c) is not None]
    return sum(vals) / len(vals) / 1000.0 if vals else float('nan')


def account(fr):
    """The PFIFO row's buckets, ms per frame, over the frames given."""
    if not fr:
        return None
    a = {c: mean_ms(fr, c) for c in ['P', 'p_run', 'p_rq', 'p_blk', 'pidle', 'p_c_rep', 'o_fence', 'gpu']}
    hooked = sum(mean_ms(fr, c) for c in P_SITES)
    a['p_oth_hk'] = hooked - a['p_c_rep']
    a['unhooked'] = a['p_blk'] - a['pidle'] - hooked
    vb = [r['vb'] for r in fr if r.get('vb') is not None]
    a['vb'] = sum(vb) / len(vb) if vb else float('nan')
    for k in (2, 3, 4):
        a[f'v{k}'] = 100.0 * sum(1 for v in vb if (v == k if k < 4 else v >= 4)) / len(vb) if vb else 0.0
    a['n'] = len(fr)
    return a


def show(acc_a, acc_b, title):
    print(f"\n{title}")
    if not acc_a or not acc_b:
        print("  (no frames)")
        return
    print(f"  {'ms/frame':10s} {'A':>8s} {'B':>8s} {'B-A':>8s}   {'B share of P':>12s}")
    for r in ROWS:
        a, b = acc_a[r], acc_b[r]
        share = f"{100 * b / acc_b['P']:.0f} %" if r not in ('P', 'vb', 'gpu', 'o_fence') else ''
        print(f"  {r:10s} {a:8.2f} {b:8.2f} {b - a:+8.2f}   {share:>12s}")
    print(f"  {'v2/v3/v4+':10s} {acc_a['v2']:.0f}/{acc_a['v3']:.0f}/{acc_a['v4']:.0f} %   "
          f"{acc_b['v2']:.0f}/{acc_b['v3']:.0f}/{acc_b['v4']:.0f} %   frames {acc_a['n']} / {acc_b['n']}")


def judge(da, db, ra, rb, exp):
    e = exp['expect']
    res = []
    env_a, pl_a = env_of(da)
    env_b, pl_b = env_of(db)
    v = (ra['marks'] >= e['V_min_marks'] and rb['marks'] >= e['V_min_marks']
         and 12 - len(ra['bad']) >= e['V_min_valid_starts'] and 12 - len(rb['bad']) >= e['V_min_valid_starts']
         and len(ra['warm']) >= e['V_min_warm_frames'] and len(rb['warm']) >= e['V_min_warm_frames']
         and 'HAKUX_FRAMETRACE=1' in env_a and 'HAKUX_FRAMETRACE=1' in env_b
         and 'HAKUX_REPORT_ASYNC=1' not in env_a and 'HAKUX_TEXSCAN=1' not in env_a
         and 'HAKUX_REPORT_ASYNC=1' in env_b and 'HAKUX_TEXSCAN=1' in env_b
         and pl_a == 'true' and pl_b == 'true')
    res.append(('V', v, f"marks {ra['marks']}/{rb['marks']}, bad starts {len(ra['bad'])}/{len(rb['bad'])}, "
                        f"warm frames {len(ra['warm'])}/{len(rb['warm'])}, env A {env_a} B {env_b}, perflog {pl_a}/{pl_b}"))
    wa, wb = account(ra['warm']), account(rb['warm'])
    res.append(('F', wa['p_c_rep'] >= e['F_a_min'] and wb['p_c_rep'] <= e['F_b_max'],
                f"warm p_c_rep A {wa['p_c_rep']:.2f} (>= {e['F_a_min']}), B {wb['p_c_rep']:.2f} (<= {e['F_b_max']})"))
    res.append(('U', wa['unhooked'] - wb['unhooked'] >= e['U_d_min'],
                f"warm unhooked A {wa['unhooked']:.2f} - B {wb['unhooked']:.2f} = {wa['unhooked'] - wb['unhooked']:.2f} (>= {e['U_d_min']})"))
    res.append(('P', wb['P'] - wa['P'] <= e['P_d_max'],
                f"warm period A {wa['P']:.2f} B {wb['P']:.2f}, B-A {wb['P'] - wa['P']:+.2f} (<= {e['P_d_max']})"))
    sh = wb['p_run'] / wb['P']
    res.append(('R', sh >= e['R_prun_share_min'],
                f"B warm p_run {wb['p_run']:.2f} of P {wb['P']:.2f} = {100 * sh:.0f} % (>= {100 * e['R_prun_share_min']:.0f} %)"))
    print('\nJUDGE (' + exp.get('registered_utc', '?') + ')')
    for k, ok, why in res:
        print(f"  {k} {'PASS' if ok else 'FAIL'}  {why}")
    n = sum(1 for _, ok, _ in res if ok)
    print(f"VERDICT: {'PASS' if n == len(res) else 'FAIL'} -- {n} of {len(res)} checks hold")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('--expect')
    o = ap.parse_args()
    ra, rb = load(o.a), load(o.b)
    if not ra or not rb:
        print(f"missing frametrace or marks: A {bool(ra)} B {bool(rb)}")
        return 2
    print(f"A {os.path.basename(o.a)} ({ra['csv']}, {ra['marks']} marks, bad {sorted(ra['bad'])})")
    print(f"B {os.path.basename(o.b)} ({rb['csv']}, {rb['marks']} marks, bad {sorted(rb['bad'])})")
    for name, _, lo, hi in WINDOWS:
        show(account(ra[name]), account(rb[name]), f"{name}: frame end in mark{lo:+.1f} .. mark{hi:+.1f} s, all frames")
        ha = [r for r in ra[name] if (r.get('vb') or 0) >= 3]
        hb = [r for r in rb[name] if (r.get('vb') or 0) >= 3]
        show(account(ha), account(hb), f"{name}: heavy frames (vb >= 3)")
    if o.expect:
        judge(o.a, o.b, ra, rb, json.load(open(o.expect)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
