#!/usr/bin/env python3
"""GPU pass census reader for NFS Most Wanted's race start (#433, lane.gpupass1010).

    gpuread.py <result dir> [...] --arm off|on [--expect PRED.json] [--window LO,HI]

Each run is ONE fixed arm (the render-mode table row is a build-time choice, not a runtime
toggle): "off" is the default render mode (no kTitleRenderModes row for NFS, GMEM tiling),
"on" is sysmem (the row added by this lane). Pass `--arm` once per invocation and diff two
separate gpuread.py runs, or pass runs from both arms and the report splits them by apk
(a_ref/b_ref, from `[hakuX-lane] ref=` if present, else the run's build/apk string).

Reads logcat.txt for:
  hakuX-route  mark gameplay|go<N>          -- same convention as startread.py/phaseread.py:
                                                go1 is the first (cold) start, go2..go12 are warm.
  hakuX-pace   f= v0= v1= v2= v3= v4= vb= max= ms=     exact 60-flip histogram + wall span.
  hakuX-perf   gfps= G:(min-max)                       per-flip EMA period, for cross-check only.
  xemu-xfr XFR rp ...                        -- draw.c:xfr_emit(), independent of --perflog.
    in/out/nr_out/res_out each give med/mean/p90 ms per 60-frame window. `in` stamps the render
    span in full for a sysmem pass, only for a GMEM pass's LAST tile (draw.c:3706-3765), so
    in/out < 0.8 reads as GMEM still active -- the mode-confirmation falsifier for an "on" run.
    GPU busy ms/frame ~= out_mean (the full outer bracket); R ~= in_mean; X ~= out_mean - in_mean.
  xemu-xfr XFR rpc[ g] ...                   -- per-command-buffer census. The un-suffixed ("all"
    group) line's n is render passes per frame, counted over every pass; it is the all-passes
    count sysmem-vs-GMEM compares and the one texscan1010's HAKUX_TEXSCAN on/off compares.

A plain build (no --perflog) still prints hakuX-perf/hakuX-pace and the xemu-xfr lines; this
reader never looks for hakuX-phase.
"""
import argparse
import json
import os
import re
import statistics
import sys

TS = re.compile(r'^(\d+)-(\d+) (\d+):(\d+):([\d.]+) ')
MARK = re.compile(r'hakuX-route.*mark (gameplay|go\d+)')
PACE = re.compile(r'hakuX-pace\(\s*\d+\): f=(\d+) v0=(\d+) v1=(\d+) v2=(\d+) v3=(\d+) v4=(\d+) vb=(\d+) max=([\d.]+) ms=([\d.]+)')
PERF = re.compile(r'hakuX-perf\(\s*\d+\): gfps=(\d+) G:([\d.]+)\(([\d.]+)-([\d.]+)\)')
XFR_RP = re.compile(
    r'XFR rp in ([\d.]+) ([\d.]+) ([\d.]+) out ([\d.]+) ([\d.]+) ([\d.]+) '
    r'nr_out ([\d.]+) ([\d.]+) ([\d.]+) res_out ([\d.]+) ([\d.]+) ([\d.]+) '
    r'n([\d.]+) inrp(\d) dropped (\d+) dup (\d+) ([\d.]+)')
XFR_RPC = re.compile(r'XFR rpc( g)? all ([\d.]+) ([\d.]+) ([\d.]+) .* ldMB ([\d.]+) stMB ([\d.]+) in ([\d.]+) draws ([\d.]+)')
ROUTE_DONE = re.compile(r'hakuX-route.*route (done|finished)')
FATAL = re.compile(r'(FATAL EXCEPTION|hakuX-crash|hakuX-unhandled)')

GAMEPLAY_WINDOW = (1.5, 12.0)   # GO .. GO+10.5s, same convention as startread.py's start_rows
COUNTDOWN_WINDOW = (-2.0, 1.5)  # the countdown proper, same convention as phaseread.py's default


def secs(m):
    return int(m.group(3)) * 3600 + int(m.group(4)) * 60 + float(m.group(5))


def read(path):
    ev = {'pace': [], 'perf': [], 'rp': [], 'rpc': [], 'rpc_g': []}
    marks, fatal, route_done = [], 0, False
    with open(path, errors='replace') as f:
        for ln in f:
            m = TS.match(ln)
            if not m:
                continue
            t = secs(m)
            if FATAL.search(ln):
                fatal += 1
            if 'hakuX-route' in ln:
                k = MARK.search(ln)
                if k:
                    marks.append((t, k.group(1)))
                if ROUTE_DONE.search(ln):
                    route_done = True
                continue
            q = PACE.search(ln)
            if q:
                ev['pace'].append((t,) + tuple(int(x) for x in q.groups()[:7]) + (float(q.group(8)), float(q.group(9))))
                continue
            q = PERF.search(ln)
            if q:
                ev['perf'].append((t, int(q.group(1)), float(q.group(2))))
                continue
            q = XFR_RP.search(ln)
            if q:
                g = [float(x) for x in q.groups()[:12]] + [float(q.group(13)), int(q.group(14)), int(q.group(15)), int(q.group(16)), float(q.group(17))]
                ev['rp'].append((t,) + tuple(g))
                continue
            q = XFR_RPC.search(ln)
            if q:
                row = (t, float(q.group(2)), float(q.group(3)), float(q.group(4)), float(q.group(5)), float(q.group(6)), float(q.group(7)), float(q.group(8)))
                (ev['rpc_g'] if q.group(1) else ev['rpc']).append(row)
    return ev, marks, fatal, route_done


def inwin(seq, lo, hi):
    return [e for e in seq if lo <= e[0] <= hi]


def mean(xs):
    return sum(xs) / len(xs) if xs else float('nan')


def pct(a, b):
    return 100.0 * a / b if b else float('nan')


def windows(marks, labels, window):
    """[(t0, t1), ...] for every mark whose go-label is in `labels`."""
    return [(t + window[0], t + window[1]) for t, lab in marks if lab in labels]


def in_any(t, wins):
    return any(lo <= t <= hi for lo, hi in wins)


def collect_rp(rows, wins):
    return [r for r in rows if in_any(r[0], wins)]


def rp_pool(rows):
    """rows are (t, in_med, in_mean, in_p90, out_med, out_mean, out_p90, nrout_med, nrout_mean,
    nrout_p90, resout_med, resout_mean, resout_p90, n, inrp, dropped, dup, dup_ms)."""
    if not rows:
        return None
    in_m = mean([r[2] for r in rows])
    out_m = mean([r[5] for r in rows])
    nrout_m = mean([r[8] for r in rows])
    n = mean([r[13] for r in rows])
    inrp = mean([r[14] for r in rows])
    return dict(n=len(rows), in_ms=in_m, out_ms=out_m, nrout_ms=nrout_m, pass_pairs=n, inrp=inrp,
                gpu_busy=out_m + nrout_m, x_ms=out_m - in_m, xr=(out_m - in_m) / in_m if in_m else float('nan'),
                mode=in_m / out_m if out_m else float('nan'))


def rpc_pool(rows):
    """rows are (t, all_n, all_ms, all_kb, ldMB, stMB, in_ms, draws)."""
    if not rows:
        return None
    return dict(n=len(rows), passes=mean([r[1] for r in rows]), ms=mean([r[2] for r in rows]),
                kb=mean([r[3] for r in rows]), ldMB=mean([r[4] for r in rows]), stMB=mean([r[5] for r in rows]),
                in_ms=mean([r[6] for r in rows]), draws=mean([r[7] for r in rows]))


def pace_pool(rows):
    if not rows:
        return None
    v = [sum(r[2 + i] for r in rows) for i in range(5)]
    tot = sum(v)
    ms = sum(r[9] for r in rows)
    f = sum(r[1] for r in rows)
    return dict(n=len(rows), v=v, tot=tot, ms_per_frame=ms / f if f else float('nan'),
                v2=pct(v[2], tot), v3=pct(v[3], tot), v4=pct(v[4], tot))


def run_report(label, ev, marks, cold_wins, warm_wins, cd_wins):
    out = {}
    for name, wins in (('cold', cold_wins), ('warm', warm_wins)):
        out[name] = dict(rp=rp_pool(collect_rp(ev['rp'], wins)), rpc=rpc_pool(collect_rp(ev['rpc'], wins)),
                          rpc_g=rpc_pool(collect_rp(ev['rpc_g'], wins)), pace=pace_pool(collect_rp(ev['pace'], wins)))
    out['countdown'] = dict(pace=pace_pool(collect_rp(ev['pace'], cd_wins)),
                             G=mean([r[2] for r in collect_rp(ev['perf'], cd_wins)]))
    print(f"\n{label}: {len(marks)} go marks")
    for name in ('cold', 'warm'):
        rp, rpc, rpc_g, pace = out[name]['rp'], out[name]['rpc'], out[name]['rpc_g'], out[name]['pace']
        if rp:
            print(f"  {name:5s} XFR rp   n={rp['n']:2d} GPU busy {rp['gpu_busy']:5.2f} ms  R(in) {rp['in_ms']:5.2f}  "
                  f"X(out-in) {rp['x_ms']:5.2f}  X/R {rp['xr']:5.2f}  mode(in/out) {rp['mode']:4.2f}  "
                  f"pass_pairs/frame {rp['pass_pairs']:5.1f}  inrp {rp['inrp']:4.2f}")
        if rpc:
            print(f"  {name:5s} XFR rpc  n={rpc['n']:2d} passes/frame {rpc['passes']:5.1f}  ms {rpc['ms']:6.2f}  "
                  f"ldMB {rpc['ldMB']:5.2f} stMB {rpc['stMB']:5.2f}  draws/frame {rpc['draws']:6.0f}" +
                  (f"   [g-only: passes {rpc_g['passes']:4.1f} ldMB {rpc_g['ldMB']:4.2f} stMB {rpc_g['stMB']:4.2f}]" if rpc_g else ""))
        if pace:
            print(f"  {name:5s} pace     n={pace['n']:2d} ms/frame {pace['ms_per_frame']:5.2f}  "
                  f"v2 {pace['v2']:4.1f}% v3 {pace['v3']:4.1f}% v4 {pace['v4']:4.1f}%  (of {pace['tot']} flips)")
    cd = out['countdown']
    if cd['pace']:
        print(f"  countdown pace n={cd['pace']['n']:2d} ms/frame {cd['pace']['ms_per_frame']:5.2f}  "
              f"v2 {cd['pace']['v2']:4.1f}% v3 {cd['pace']['v3']:4.1f}% v4 {cd['pace']['v4']:4.1f}%  G {cd['G']:.1f}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--arm', choices=['off', 'on'], required=True, help='render mode arm this batch of runs used')
    ap.add_argument('--expect', help='prediction json with an "expect" dict of named leg thresholds')
    args = ap.parse_args()

    exp = json.load(open(args.expect)).get('expect', {}) if args.expect else {}
    e = lambda k, d: exp.get(k, d)
    legs = []

    def leg(name, ok, text):
        legs.append((name, ok))
        print("%-3s %s  %s" % (name, "PASS" if ok else "FAIL", text))

    all_marks, all_rp, all_rpc, all_rpc_g, all_pace, all_perf = [], [], [], [], [], []
    bad = []
    pooled_cold = pooled_warm = None
    for d in args.dirs:
        p = os.path.join(d, 'logcat.txt')
        ev, marks, fatal, route_done = read(p)
        n_go = len(marks)
        if n_go < e('V_min_starts', 12):
            bad.append("%s: only %d go marks" % (d, n_go))
        if fatal:
            bad.append("%s: %d fatal lines" % (d, fatal))
        cold_wins = windows(marks, {'go1'}, GAMEPLAY_WINDOW)
        warm_labels = {'go%d' % i for i in range(2, 13)}
        warm_wins = windows(marks, warm_labels, GAMEPLAY_WINDOW)
        cd_wins = windows(marks, {'go1'} | warm_labels, COUNTDOWN_WINDOW)
        out = run_report("%s (arm=%s)" % (os.path.basename(d), args.arm), ev, marks, cold_wins, warm_wins, cd_wins)
        all_marks += marks
        all_rp += ev['rp']
        all_rpc += ev['rpc']
        all_rpc_g += ev['rpc_g']
        all_pace += ev['pace']
        all_perf += ev['perf']

    cold_wins = windows(all_marks, {'go1'}, GAMEPLAY_WINDOW)
    warm_wins = windows(all_marks, {'go%d' % i for i in range(2, 13)}, GAMEPLAY_WINDOW)
    cd_wins = windows(all_marks, {'go%d' % i for i in range(1, 13)}, COUNTDOWN_WINDOW)
    pooled = {'rp': all_rp, 'rpc': all_rpc, 'rpc_g': all_rpc_g, 'pace': all_pace, 'perf': all_perf}
    pool_out = run_report("POOLED (%d runs, arm=%s)" % (len(args.dirs), args.arm), pooled, all_marks, cold_wins, warm_wins, cd_wins)

    leg('V', not bad, "; ".join(bad) or "every run has >= %d go marks, no fatal lines" % e('V_min_starts', 12))

    cold_rp = pool_out['cold']['rp']
    if cold_rp:
        # draw.c:3706-3765: in/out < 0.8 reads as GMEM (only the last tile is stamped in full);
        # the off arm (table default, GMEM) is expected BELOW that line, the on arm (sysmem,
        # this lane's row) AT or above it.
        lo, hi = (e('M_mode_min', 0.0), e('M_mode_max', 0.8)) if args.arm == 'off' else (e('M_mode_min', 0.8), e('M_mode_max', 1.5))
        leg('M', lo <= cold_rp['mode'] <= hi,
            "cold in/out (mode-confirmation) %.2f, expected in [%.2f, %.2f] for arm=%s (in/out < 0.8 reads as GMEM still active)"
            % (cold_rp['mode'], lo, hi, args.arm))
        g_hi = e('G_cold_max', 14.0 if args.arm == 'on' else 99.0)
        leg('G', cold_rp['gpu_busy'] <= g_hi,
            "cold GPU busy %.2f ms/frame, predicted <= %.1f for arm=%s" % (cold_rp['gpu_busy'], g_hi, args.arm))
        x_hi = e('X_cold_max', 0.3 if args.arm == 'on' else 99.0)
        leg('X', cold_rp['xr'] <= x_hi,
            "cold X/R %.2f, predicted <= %.1f for arm=%s" % (cold_rp['xr'], x_hi, args.arm))
    else:
        leg('M', False, "no XFR rp lines landed in the cold window")

    cold_rpc = pool_out['cold']['rpc']
    if cold_rpc:
        lo, hi = e('P_cold_passes_min', 0.0), e('P_cold_passes_max', 99.0)
        leg('P', lo <= cold_rpc['passes'] <= hi,
            "cold render passes/frame %.1f, predicted in [%.1f, %.1f]" % (cold_rpc['passes'], lo, hi))

    print("\nlegs: %s" % " ".join("%s=%s" % (nm, "PASS" if ok else "FAIL") for nm, ok in legs))


if __name__ == '__main__':
    sys.exit(main())
