#!/usr/bin/env python3
"""Judge docs/testing/predictions/notify488-timing.json.

    python3 timing_judge.py <A result-id> <B result-id>
    python3 timing_judge.py --pilot <B result-id>

Reads each arm's Signal_timing::ST_*.txt (lane.xbox's suite, PR #486) from
the dispatcher result and prints every leg with its numbers and PASS/FAIL.
--pilot reads the B arm alone and prints the B-only legs (I1, N1, N2, H0).
Captures (ST_Done_*.png) are compared byte for byte, A against B, for P0.
"""
import hashlib
import os
import re
import sys
from statistics import median

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'
FRAME_US = 16683.3
DONE = ['ST_Done_Tiny', 'ST_Done_DOA', 'ST_Done_DOA_Read']


def load(run):
    caps = [c for c in sorted(os.listdir(R + run)) if c.startswith('captures')]
    if not caps:
        sys.exit(f'{run}: no captures dir')
    d = R + run + '/' + caps[0] + '/'
    out = {'dir': d}
    for f in os.listdir(d):
        m = re.match(r'Signal_timing::(ST_\w+)\.txt$', f)
        if not m:
            continue
        summ, raw, hdr = {}, [], None
        for line in open(d + f):
            line = line.rstrip('\n')
            if line.startswith('#'):
                continue
            if hdr is None and '\t' in line and not line[0].isdigit():
                hdr = line.split('\t')
                continue
            if hdr is not None:
                raw.append(dict(zip(hdr, (int(x) for x in line.split('\t')))))
                continue
            m2 = re.match(r'(\S+) n=(\d+)(?: median=([\d.]+))?', line)
            if m2:
                summ[m2.group(1)] = (int(m2.group(2)),
                                     float(m2.group(3)) if m2.group(3) else None)
                continue
            k, _, v = line.partition(' ')
            summ[k] = v
        out[m.group(1)] = (summ, raw)
    import json
    runs = json.load(open(R + run + '/result.json')).get('runs', [])
    out['completed'] = bool(runs) and all(r.get('progress_log_proof')
                                           for r in runs)
    out['fatal'] = 0
    for f in os.listdir(R + run):
        if f.startswith('logcat'):
            t = open(R + run + '/' + f, errors='replace').read()
            out['fatal'] += len(re.findall(r'Fatal signal|F DEBUG', t))
    return out


def med(arm, test, key):
    s = arm.get(test, ({}, []))[0].get(key)
    return s[1] if isinstance(s, tuple) else None


def num(arm, test, key):
    v = arm.get(test, ({}, []))[0].get(key)
    return int(v) if v is not None and str(v).isdigit() else None


def leg(name, ok, text):
    print(f'{"PASS" if ok else "FAIL"}  {name}: {text}')
    return ok


def ts_ratio(arm, freq):
    raw = arm['ST_Done_Tiny'][1]
    rs = []
    for a, b in zip(raw, raw[1:]):
        if a['notify_slot'] != 0 or b['notify_slot'] != 0:
            continue
        dts = ((b['ntf0_ts_hi'] << 32) | b['ntf0_ts_lo']) - \
              ((a['ntf0_ts_hi'] << 32) | a['ntf0_ts_lo'])
        dq = (b['kick'] - a['kick']) * 1e9 / freq
        if dq > 0:
            rs.append(dts / dq)
    return median(rs) if rs else None, len(rs)


def b_legs(B):
    cal = B.get('ST_Calibrate', ({}, []))[0]
    coi = float(cal.get('counter_over_interrupt', 'nan'))
    leg('I1 clock (B)', 0.995 <= coi <= 1.005, f'counter/interrupt {coi}')
    ok = True
    for t in DONE:
        reps, bt = num(B, t, 'reps'), num(B, t, 'busy_timeouts')
        ok &= reps == 300 and bt == 0
    leg('I1 reps (B)', ok, 'every Done test 300 reps, 0 busy timeouts')
    for t in DONE:
        nt, m = num(B, t, 'notify_timeouts'), med(B, t, 'kick_to_notify')
        leg(f'N1 {t}', nt == 0 and m is not None and m <= FRAME_US,
            f'notify_timeouts {nt}, kick_to_notify median {m} us')
    freq = float(B['ST_Done_Tiny'][0].get('freq_hz', 'nan'))
    r, n = ts_ratio(B, freq)
    leg('N2 timestamp is PTIMER ns', r is not None and 0.95 <= r <= 1.05,
        f'median dts/dkick {r} over {n} rep pairs')
    leg('H0 (B)', B['completed'] and not B['fatal'],
        f'completed {B["completed"]}, fatal lines {B["fatal"]}')


def main():
    a = sys.argv[1:]
    if a and a[0] == '--pilot':
        b_legs(load(a[1]))
        return
    A, B = load(a[0]), load(a[1])
    cal = A.get('ST_Calibrate', ({}, []))[0]
    coi = float(cal.get('counter_over_interrupt', 'nan'))
    leg('I1 clock (A)', 0.995 <= coi <= 1.005, f'counter/interrupt {coi}')
    b_legs(B)
    for t in DONE:
        nt = num(A, t, 'notify_timeouts')
        leg(f'M1 {t} (A never writes)', nt == 300, f'A notify_timeouts {nt}')
    sa, sb = med(A, 'ST_Done_DOA', 'kick_to_semaphore'), \
        med(B, 'ST_Done_DOA', 'kick_to_semaphore')
    leg('S1 DOA semaphore within a frame, halved',
        sb is not None and sa and sb <= FRAME_US and sb <= 0.5 * sa,
        f'A {sa} us, B {sb} us, B/A {sb / sa if sa and sb is not None else None}')
    leg('S2 guess: DOA <= 3 ms', sb is not None and sb <= 3000, f'B {sb} us')
    ta, tb = med(A, 'ST_Done_Tiny', 'kick_to_semaphore'), \
        med(B, 'ST_Done_Tiny', 'kick_to_semaphore')
    leg('S2 guess: Tiny halved', tb is not None and ta and tb <= 0.5 * ta,
        f'A {ta} us, B {tb} us')
    ra, rb = med(A, 'ST_Done_DOA_Read', 'cpu_read_back_buffer'), \
        med(B, 'ST_Done_DOA_Read', 'cpu_read_back_buffer')
    leg('S3 the download moved to the reader', rb is not None and ra and
        rb >= ra - 1000, f'A read {ra} us, B read {rb} us')
    for t in DONE:
        fa, fb = A['dir'] + f'Signal_timing::{t}.png', \
            B['dir'] + f'Signal_timing::{t}.png'
        if not (os.path.exists(fa) and os.path.exists(fb)):
            leg(f'P0 {t} capture', False, 'capture missing in an arm')
            continue
        ha = hashlib.sha256(open(fa, 'rb').read()).hexdigest()[:12]
        hb = hashlib.sha256(open(fb, 'rb').read()).hexdigest()[:12]
        leg(f'P0 {t} capture identical', ha == hb, f'A {ha} B {hb}')
    leg('H0 (A)', A['completed'] and not A['fatal'],
        f'completed {A["completed"]}, fatal lines {A["fatal"]}')


if __name__ == '__main__':
    main()
