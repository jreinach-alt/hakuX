#!/usr/bin/env python3
"""lane.halo1016: judge of docs/testing/predictions/halo1016-speech.json (#938).

usage: speechread.py --expect PRED.json A=<dir> R=<dir> [C=<dir>] [H=<dir>]

Written before any leg was read. Each leg is a soak on the halo-cinematic
route with HAKUX_APU_METER=1 (commit 8f70b1e9e0) and one HAKUX_APU_HRTF_NORM
value: A unset (l1, today's), R raw; C cap and H off are optional (cap is,
voice by voice, whichever of A and R is quieter, so A, R and the logged l1
already determine it). It reads, from each leg's logcat after
`mark cinematic`:

  apumeter w= 3d= 2d= top=v:dB,... pause=v:n,...   (one per 5 s)
  apuhrtf v= h= l1=L/R l2=L/R dc=L/R itd=          (HRIR scale as bound)
  apuvoice sslempty v=<speech>                      (HAKUX_APU_VOICELOG=1)
  hrtf_norm: <mode>, apu_meter: on                  (the switch reached the APU)

Per window with the speech voice in top=: S = its level, M = the music
voices' summed level, B = 3d=, R = everything but S (3d+2d minus S), all
dBFS. A window without the speech voice is speech-free: counted, not used.

Legs (names in the prediction's expect block):
  V  every leg: mark cinematic, >= V_min_cine_shots cine route-frames,
     `apu_meter: on`, the leg's hrtf_norm mode logged, >= V_min_speech_windows
     speech windows, the music voices in >= half of those.
  B  baseline (H2 vs a register error): A's median S-M is >= B_sm_min_db.
     S-M under it means hakuX plays speech under music against the
     title's own volume registers (+4.1 / +1.0 dB at the owner's slot0 /
     slot1, REPORT.md 1.2), and the account moves off the bed to the 2D path.
  L  H1's precondition: the median l1 over the 3D voices' apuhrtf lines in A
     is < L_l1_max (an HRIR whose taps sum under 1 is raised by today's
     division; one over 1 is cut, and then cap is l1 and raw is louder).
  N  H1 (the lever): for C and R, median(B) is >= N_bed_drop_db under A's
     and median(S-R) >= N_sr_gain_db over A's, and the run clips no more
     than A (level L/R `clipped`). Hit if either C or R hits.
  U  upper bound of the HRTF lever: H's median(S-R) minus A's (printed,
     not judged: `off` is not a candidate default, it drops the 3D cue).
  S  H3 (speech starves under the slow shots, #1018): in A, `sslempty` lines
     for the speech voice >= S_sslempty_min. Speech-voice pauses in meter
     windows under 25 fps (>= 40 ms per guest frame over the window, from
     hakuX-pace) are printed; they decide only if the prediction names
     S_pause_slow_min (a pause at a line's end looks the same).
"""
import argparse
import json
import math
import os
import re
import statistics
from datetime import datetime

TS = re.compile(r'^(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d\.\d+)')


def ts(line):
    m = TS.match(line)
    if not m:
        return None
    mo, dd, hh, mi, ss = m.groups()
    return datetime.strptime('2026-%s-%s %s:%s:%s' % (mo, dd, hh, mi, ss),
                             '%Y-%m-%d %H:%M:%S.%f').timestamp()


def db_sum(levels):
    e = sum(10 ** (x / 10.0) for x in levels if x > -199)
    return 10 * math.log10(e) if e > 0 else -200.0


def db_minus(total, part):
    e = 10 ** (total / 10.0) - 10 ** (part / 10.0)
    return 10 * math.log10(e) if e > 1e-20 else -200.0


def med(v):
    return statistics.median(v) if v else float('nan')


class Leg:
    def __init__(self, tag, d, speech, music):
        self.tag, self.d = tag, d
        self.name = os.path.basename(os.path.normpath(d))
        self.mark = None
        self.meter_on = False
        self.norm = None
        self.win = []        # (t, w, 3d, 2d, top{}, pause{})
        self.hrtf = []       # (v, l1L, l1R, l2L, l2R, dcL, dcR)
        self.sslempty = 0
        self.pace = []       # (t, ms per frame)
        self.clipped = None
        self.speech, self.music = speech, music
        lc = os.path.join(d, 'logcat.txt')
        last_pace_f = None
        clip = {}
        for line in open(lc, errors='replace') if os.path.exists(lc) else []:
            t = ts(line)
            if 'hakuX-route' in line and 'mark cinematic' in line and self.mark is None:
                self.mark = t
            elif 'apu_meter: on' in line:
                self.meter_on = True
            elif 'hrtf_norm:' in line and self.norm is None:
                self.norm = line.split('hrtf_norm:', 1)[1].split()[0]
            elif 'apumeter w=' in line:
                m = re.search(r'apumeter w=(\d+) 3d=(\S+) 2d=(\S+) top=(\S*) pause=(\S+)', line)
                if m:
                    top, pause = {}, {}
                    for x in m.group(4).split(','):
                        if ':' in x:
                            v, lv = x.split(':')
                            top[int(v)] = float(lv)
                    for x in m.group(5).split(','):
                        if ':' in x:
                            v, n = x.split(':')
                            pause[int(v)] = int(n)
                    self.win.append((t, int(m.group(1)), float(m.group(2)),
                                     float(m.group(3)), top, pause))
            elif 'apuhrtf v=' in line:
                m = re.search(r'apuhrtf v=(\d+) h=\d+ l1=(\S+)/(\S+) l2=(\S+)/(\S+) '
                              r'dc=(\S+)/(\S+)', line)
                if m and (self.mark is None or t >= self.mark):
                    self.hrtf.append((int(m.group(1)),) + tuple(float(x) for x in m.groups()[1:]))
            elif 'apuvoice sslempty v=%d ' % speech in line:
                if self.mark is not None and t >= self.mark:
                    self.sslempty += 1
            elif 'hakuX-pace' in line and ' ms=' in line:
                f = re.search(r' f=(\d+)', line)
                ms = re.search(r' ms=([\d.]+)', line)
                if f and ms:
                    f, ms = int(f.group(1)), float(ms.group(1))
                    if last_pace_f is not None and f > last_pace_f and ms > 0:
                        self.pace.append((t - ms / 1000.0, t, f - last_pace_f))
                    last_pace_f = f
            elif re.search(r'level [LR]: .*clipped', line):
                c = re.search(r'level ([LR]): .*clipped (\d+)', line)
                if c:   # cumulative per channel; the last L plus the last R
                    clip[c.group(1)] = int(c.group(2))
                    self.clipped = sum(clip.values())
        shots = os.path.join(d, 'route-frames')
        self.cine = sum(1 for s in os.listdir(shots) if s.endswith('-cine.png')) \
            if os.path.isdir(shots) else 0
        self.rows = []
        self.nosp = 0
        for t, w, d3, d2, top, pause in self.win:
            if self.mark is None or t < self.mark:
                continue
            if speech not in top:
                self.nosp += 1
                continue
            s = top[speech]
            mus = db_sum([top[v] for v in music if v in top])
            rest = db_minus(db_sum([d3, d2]), s)
            self.rows.append(dict(t=t, w=w, d3=d3, d2=d2, S=s, M=mus, SM=s - mus,
                                  SB=s - d3, SR=s - rest, mus_n=sum(1 for v in music if v in top),
                                  pause=pause))

    def slow_at(self, t):
        """ms per guest frame over the meter window ending at t (5 s), from the
        hakuX-pace windows (start, end, frames) that overlap it."""
        secs = frames = 0.0
        for s, e, n in self.pace:
            ov = min(e, t) - max(s, t - 5.0)
            if ov > 0:
                secs += ov
                frames += n * ov / (e - s)
        return 1000.0 * secs / frames if frames else None

    def summary(self):
        return dict(B=med([r['d3'] for r in self.rows]), SR=med([r['SR'] for r in self.rows]),
                    SM=med([r['SM'] for r in self.rows]), SB=med([r['SB'] for r in self.rows]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('legs', nargs='+', help='TAG=<result dir>, TAG in A C R H')
    ap.add_argument('--expect', required=True)
    ap.add_argument('--speech', type=int, default=65)
    ap.add_argument('--music', default='85,86,88')
    o = ap.parse_args()
    ex = json.load(open(o.expect))['expect']
    music = [int(x) for x in o.music.split(',')]
    want = {'A': 'l1', 'C': 'cap', 'R': 'raw', 'H': 'off'}
    legs = {}
    for a in o.legs:
        tag, d = a.split('=', 1)
        legs[tag] = Leg(tag, d, o.speech, music)

    for tag in sorted(legs):
        g = legs[tag]
        print('## %s: %s  (hrtf_norm %s, apu_meter %s, mark %s, cine shots %d, clipped %s)\n' % (
            tag, g.name, g.norm, 'on' if g.meter_on else 'OFF',
            datetime.fromtimestamp(g.mark).strftime('%H:%M:%S') if g.mark else 'MISSING',
            g.cine, g.clipped))
        print('| t-mark s | w | 3d | 2d | S | M | S-M | S-B | S-R | music voices | ms/f | pause |')
        print('|' + '---|' * 12)
        for r in g.rows:
            msf = g.slow_at(r['t'])
            print('| %.0f | %d | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f | %d | %s | %s |' % (
                r['t'] - g.mark, r['w'], r['d3'], r['d2'], r['S'], r['M'], r['SM'], r['SB'], r['SR'],
                r['mus_n'], '%.0f' % msf if msf else '-',
                ','.join('%d:%d' % kv for kv in sorted(r['pause'].items())) or '-'))
        s = g.summary()
        print('\nmedians over %d speech windows (%d without v%d): 3d %.1f, S-M %.1f, S-B %.1f, S-R %.1f; '
              'sslempty v%d after mark: %d\n' % (len(g.rows), g.nosp, o.speech, s['B'], s['SM'], s['SB'],
                                                 s['SR'], o.speech, g.sslempty))
        top2d = {}
        for t, w, d3, d2, top, pause in g.win:
            if g.mark and t >= g.mark:
                for v in top:
                    if v >= 64:
                        top2d[v] = top2d.get(v, 0) + 1
        print('2D voices by windows in top=: %s\n' % ', '.join(
            'v%d:%d' % kv for kv in sorted(top2d.items(), key=lambda kv: -kv[1])[:8]))
        if g.hrtf:
            by = {}
            for h in g.hrtf:
                by.setdefault(h[0], []).append(h[1:])
            print('| 3D voice | binds | l1 L/R | l2 L/R | dc L/R |')
            print('|---|---|---|---|---|')
            for v in sorted(by):
                c = list(zip(*by[v]))
                print('| %d | %d | %.3f/%.3f | %.3f/%.3f | %.3f/%.3f |' % (
                    v, len(by[v]), med(c[0]), med(c[1]), med(c[2]), med(c[3]), med(c[4]), med(c[5])))
            print()

    print('## Verdict\n')
    ok = True
    for tag in sorted(legs):
        g = legs[tag]
        mus_ok = sum(1 for r in g.rows if r['mus_n']) * 2 >= len(g.rows) if g.rows else False
        v = [g.mark is not None, g.cine >= ex['V_min_cine_shots'], g.meter_on,
             g.norm == want.get(tag), len(g.rows) >= ex['V_min_speech_windows'], mus_ok]
        print('- V %s: %s (mark, cine>=%d, meter, norm=%s, speech windows>=%d, music in half)' % (
            tag, '/'.join('ok' if x else 'NO' for x in v), ex['V_min_cine_shots'],
            want.get(tag), ex['V_min_speech_windows']))
        ok &= all(v)
    if 'A' not in legs:
        print('no A leg: nothing to judge')
        return
    A = legs['A']
    sa = A.summary()
    print('- B: %s  A median S-M %.1f dB (>= %.1f)' % (
        'HIT' if sa['SM'] >= ex['B_sm_min_db'] else 'MISS', sa['SM'], ex['B_sm_min_db']))
    l1s = [x for h in A.hrtf for x in (h[1], h[2])]
    print('- L: %s  median l1 over A\'s 3D binds %.3f (< %.2f; %d binds)' % (
        'HIT' if l1s and med(l1s) < ex['L_l1_max'] else 'MISS', med(l1s), ex['L_l1_max'], len(A.hrtf)))
    nhit = False
    for tag in ('C', 'R'):
        if tag not in legs:
            continue
        s = legs[tag].summary()
        drop, gain = sa['B'] - s['B'], s['SR'] - sa['SR']
        clip = legs[tag].clipped is not None and A.clipped is not None and legs[tag].clipped <= A.clipped
        hit = drop >= ex['N_bed_drop_db'] and gain >= ex['N_sr_gain_db'] and clip
        nhit |= hit
        print('- N %s: %s  bed %.1f dB under A (>= %.1f), S-R %+.1f dB over A (>= %.1f), clipped %s vs A %s' % (
            tag, 'HIT' if hit else 'MISS', drop, ex['N_bed_drop_db'], gain, ex['N_sr_gain_db'],
            legs[tag].clipped, A.clipped))
    print('- N: %s' % ('HIT' if nhit else 'MISS'))
    if 'H' in legs:
        s = legs['H'].summary()
        print('- U (not judged): off moves the bed %.1f dB and S-R %+.1f dB against A' % (
            sa['B'] - s['B'], s['SR'] - sa['SR']))
    slowp = 0
    for r in A.rows:
        msf = A.slow_at(r['t'])
        if msf and msf >= 40.0 and r['pause'].get(o.speech):
            slowp += r['pause'][o.speech]
    for t, w, d3, d2, top, pause in A.win:
        if A.mark and t >= A.mark and o.speech not in top and pause.get(o.speech):
            msf = A.slow_at(t)
            if msf and msf >= 40.0:
                slowp += pause[o.speech]
    s_hit = A.sslempty >= ex['S_sslempty_min'] or (
        'S_pause_slow_min' in ex and slowp >= ex['S_pause_slow_min'])
    print('- S: %s  A sslempty v%d %d (>= %d); v%d pauses in windows under 25 fps %d (%s)' % (
        'HIT' if s_hit else 'MISS', o.speech, A.sslempty, ex['S_sslempty_min'], o.speech, slowp,
        '>= %d' % ex['S_pause_slow_min'] if 'S_pause_slow_min' in ex else 'printed, not judged'))
    if not ok:
        print('\nVOID: a V check failed; the legs above are printed, not scored.')


if __name__ == '__main__':
    main()
