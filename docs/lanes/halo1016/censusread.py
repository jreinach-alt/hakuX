#!/usr/bin/env python3
"""lane.halo1016: judge of docs/testing/predictions/halo1016-census.json.

usage: censusread.py <A result dir> <B result dir> [--expect PREDICTION.json]

Written before either result was read. Both arms are perflog soaks of the
halo-cinematic route on 214445e90e, which adds the [ovl1018] overlap-eviction
census beside [evict372]. A: frametrace and the PFIFO wait probe. B: the same
plus HAKUX_S2T_CVT=1.

cinesplit (#1018) found the plateau's off-CPU time is synchronous
SURFACE_DOWN finishes, ~61 a frame at ~0.5 ms each. This run asks whose.
A SURFACE_DOWN finish is submitted in one of three places (OPT_SURF_TO_TEX_
INLINE builds): a deferred-download completion (the stall line's cDef; its
caller is on the [sdcall] line), an inline download_surface_to_buffer (sd[dl];
its source is on dif[] and txr[]), or the pending/dirty synchronous fallbacks.

The span: [mark+131 s, mark+191 s], cinesplit A's measured plateau (11 pace
windows >= 50 ms/frame; cinesplit B was slow over the same seconds, so the
scene is locked to time after `mark cinematic`). A 60-frame block is in the
span if its line's time t has span0 < t <= span1 + 2. Rates are per guest
frame: a stall block is 60 frames, an [sdcall] line says its frames=, and the
cumulative [ovl1018] / [evict372] counters are read at the last 5-s tick at
or before span0 and the first at or after span1, divided by the guest frames
between those ticks (hakuX-pace's cumulative f=, interpolated).

Legs:
  V  both arms: `mark cinematic`; >= V_min_blocks stall blocks and [sdcall]
     lines in the span; [ovl1018] ticks bracketing it; B's logcat says
     `[s2tcvt] on` and A's does not; A's ms per guest frame over the span
     (sum of pace ms / sum of frames) >= V_a_span_msf_min (the slow scene
     reproduced under perflog). A void run is not a miss.
  O  overlap eviction feeds the finishes. A over the span: [ovl1018]
     draw-dirty evictions (every relation bin, active and shelf) >=
     O_ovl_share_min x Finish sd, and the other named sources (txr dl +
     scdl + [sdcall] range fin) <= O_other_share_max x Finish sd. An active
     eviction completes at surfupd (or reuse/record), a shelved one downloads
     inline (sd[dl], after a tobuf completion), so no single caller is the
     overlap's; the 10-03 perflog soak (effb0d001b) showed both.
  K  the texture path. A: txr dl + scdl >= K_share_min x Finish sd.
  R  CPU-range downloads. A: [sdcall] range fin >= R_share_min x Finish sd.
  C  HAKUX_S2T_CVT removes them. B's Finish sd per frame over the span <=
     C_sd_ratio_max x A's, and B's ms per frame there <= C_msf_ratio_max x A's.

Printed whatever the verdict: the per-block timeline over [mark+40, mark+260],
the span's account for each arm, and the [ovl1018] / [evict372] pairs.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cineread  # noqa: E402
from cineread import ts, mean  # noqa: E402

SPAN = (131.0, 191.0)
VIEW = (40.0, 260.0)
CALLERS = ['range', 'tobuf', 'deffull', 'pend', 'pendfb', 'dirty', 'dirtyfb',
           'expire', 'surfupd', 'reuse', 'record', 'prerec', 'ext']

FIN = re.compile(r'Finish:(\d+)\(vtx(\d+) sc(\d+) sd(\d+) buf(\d+) fb(\d+) '
                 r'pres(\d+) flip(\d+)')
SDX = re.compile(r' sd\[ev(\d+) noCb(\d+) dl(\d+) cDef(\d+) cDefC(\d+) '
                 r'pDl(\d+) dDl(\d+)\]')
DIF = re.compile(r'dif\[ovl(\d+) ovlSh(\d+) exp(\d+) expSh(\d+) blt(\d+) '
                 r'flu(\d+) dds(\d+) oth(\d+)\]')
DIFK = ['ovl', 'ovlSh', 'exp', 'expSh', 'blt', 'flu', 'dds', 'oth']
TXR = re.compile(r'txr\[ct(\d+) bt(\d+)/(\d+) dl(\d+)/(\d+)K sc(\d+) '
                 r'scdl(\d+) img(\d+) pool(\d+) s2tc(\d+) s2td(\d+)\]'
                 r'(?: txdl\[lv(\d+) dim(\d+) cube(\d+) pitch(\d+) swz(\d+) '
                 r'cvt(\d+) bpp(\d+) upl(\d+) oth(\d+)\])?')
TXDLK = ['lv', 'dim', 'cube', 'pitch', 'swz', 'cvt', 'bpp', 'upl', 'oth']
SDC = re.compile(r' (\w+)=fin(\d+)/fence(\d+)/pre(\d+)/dl(\d+)/([\d.]+)ms')
SPL = re.compile(r' spl=def(\d+)/up(\d+)/dl(\d+)/(\d+)kB/cmpl(\d+)')
WHY = re.compile(r' why=new(\d+)/inv(\d+)/stale(\d+)/hoff(\d+)/cpuw(\d+)/'
                 r'gap(\d+)/oth(\d+)')
BINS = re.compile(r' ([rm][0-9a-f]{2}):(\d+)/(\d+)')


class Census(cineread.Arm):
    def read_log(self, path):
        super().read_log(path)
        self.blocks = []     # dicts, one per hakuX-stall Finish line
        self.sdcall = []     # dicts, one per [sdcall] line
        self.ovl = []        # (t, {bin: (dirty, clean)}, [pair lines])
        self.ev = []         # likewise for [evict372]
        self.s2tcvt = False
        cur = None
        for line in open(path, errors='replace'):
            if '[s2tcvt] on' in line:
                self.s2tcvt = True
            if 'hakuX-stall' in line:
                f = FIN.search(line)
                if f:
                    s, d = SDX.search(line), DIF.search(line)
                    cur = {'t': ts(line), 'fin': int(f.group(1)),
                           'sd': int(f.group(4)), 'flip': int(f.group(8))}
                    if s:
                        cur.update(ev=int(s.group(1)), sddl=int(s.group(3)),
                                   cdef=int(s.group(4)), cdefc=int(s.group(5)),
                                   pdl=int(s.group(6)), ddl=int(s.group(7)))
                    if d:
                        for i, k in enumerate(DIFK):
                            cur['dif_' + k] = int(d.group(i + 1))
                    self.blocks.append(cur)
                    continue
                x = TXR.search(line)
                if x and cur is not None and 'txdl' not in cur:
                    cur.update(txr_dl=int(x.group(4)),
                               txr_scdl=int(x.group(7)),
                               s2tc=int(x.group(10)), s2td=int(x.group(11)))
                    cur['txdl'] = ({k: int(x.group(12 + i))
                                    for i, k in enumerate(TXDLK)}
                                   if x.group(12) else {})
                    continue
            if '[sdcall] frames=' in line:
                r = {'t': ts(line),
                     'frames': cineread.num(r'frames=(\d+)', line, int, 0)}
                for c, fin, fence, pre, dl, ms in SDC.findall(line):
                    r[c] = (int(fin), int(fence), int(pre), int(dl), float(ms))
                m = SPL.search(line)
                r['spl'] = tuple(int(v) for v in m.groups()) if m else None
                m = WHY.search(line)
                r['why'] = tuple(int(v) for v in m.groups()) if m else None
                r['su_upl'] = cineread.num(r' su_upl=(\d+)', line, int, 0)
                r['su_def'] = cineread.num(r' su_deferred=(\d+)', line, int, 0)
                self.sdcall.append(r)
            elif '[ovl1018] dirty/clean' in line:
                self.ovl.append((ts(line), {b: (int(dd), int(cc)) for b, dd, cc
                                            in BINS.findall(line)}, []))
            elif '[ovl1018] pair' in line and self.ovl:
                self.ovl[-1][2].append(line.split('[ovl1018] ', 1)[1].strip())
            elif '[evict372] dirty/clean' in line:
                self.ev.append((ts(line), {b: (int(dd), int(cc)) for b, dd, cc
                                           in BINS.findall(line)}, []))
            elif '[evict372] pair' in line and self.ev:
                self.ev[-1][2].append(line.split('[evict372] ', 1)[1].strip())

    def frame_at(self, t):
        """Cumulative guest frame count at wall t, from hakuX-pace f=."""
        p = [(w, f) for w, f, _, _ in self.pace if w is not None]
        if not p:
            return None
        if t <= p[0][0]:
            return p[0][1]
        for (w0, f0), (w1, f1) in zip(p, p[1:]):
            if w0 <= t <= w1:
                return f0 + (f1 - f0) * (t - w0) / (w1 - w0) if w1 > w0 else f1
        return p[-1][1]

    def span(self, lo, hi):
        return (self.mark + lo, self.mark + hi)

    def blocks_in(self, s0, s1):
        return [b for b in self.blocks if b['t'] and s0 < b['t'] <= s1 + 2.0]

    def sdcall_in(self, s0, s1):
        return [r for r in self.sdcall if r['t'] and s0 < r['t'] <= s1 + 2.0]

    def msf(self, s0, s1):
        ms, fr = 0.0, 0
        for i, (t, f, m, _) in enumerate(self.pace):
            if i and m is not None and s0 < t <= s1 + 2.0:
                df = f - self.pace[i - 1][1]
                if df > 0:
                    ms += m
                    fr += df
        return ms / fr if fr else float('nan')

    def bracket(self, ticks, s0, s1):
        """(start tick, end tick, guest frames between) or None."""
        before = [k for k in ticks if k[0] and k[0] <= s0]
        after = [k for k in ticks if k[0] and k[0] >= s1]
        if not before or not after:
            return None
        a, b = before[-1], after[0]
        fa, fb = self.frame_at(a[0]), self.frame_at(b[0])
        if fa is None or fb is None or fb <= fa:
            return None
        return a, b, fb - fa


def per(blocks, key):
    n = sum(b.get(key, 0) for b in blocks)
    return n / (60.0 * len(blocks)) if blocks else float('nan')


def account(arm, s0, s1, label):
    bl, sc = arm.blocks_in(s0, s1), arm.sdcall_in(s0, s1)
    out = {'blocks': len(bl), 'sdcall': len(sc), 'msf': arm.msf(s0, s1)}
    print('### %s: %s, %s (%d stall blocks, %d [sdcall] lines)\n' %
          (label, arm.name, '[mark+%.0f, mark+%.0f]' % (s0 - arm.mark, s1 - arm.mark),
           len(bl), len(sc)))
    print('- ms per guest frame (pace): %.1f' % out['msf'])
    for k in ('fin', 'sd', 'flip', 'cdef', 'cdefc', 'sddl', 'pdl', 'ddl', 'ev'):
        out[k] = per(bl, k)
    print('- Finish %.2f/f: sd %.2f (cDef %.2f, cDefC %.2f, sd[dl] %.2f, pDl %.2f, '
          'dDl %.2f, ev %.2f), flip %.2f' %
          (out['fin'], out['sd'], out['cdef'], out['cdefc'], out['sddl'],
           out['pdl'], out['ddl'], out['ev'], out['flip']))
    print('- dif[] per frame: ' + ' '.join(
        '%s %.2f' % (k, per(bl, 'dif_' + k)) for k in DIFK))
    for k in ('txr_dl', 'txr_scdl', 's2tc', 's2td'):
        out[k] = per(bl, k)
    why = {k: sum(b.get('txdl', {}).get(k, 0) for b in bl) for k in TXDLK}
    print('- txr per frame: dl %.2f scdl %.2f s2tc %.2f s2td %.2f; txdl reasons '
          '(span total): %s' % (out['txr_dl'], out['txr_scdl'], out['s2tc'],
                                out['s2td'], ' '.join('%s %d' % kv for kv in why.items())))
    out['txdl_why'] = why
    fr = sum(r['frames'] for r in sc)
    rows = []
    for c in CALLERS:
        v = [r[c] for r in sc if c in r]
        if not v:
            out['sdc_' + c] = 0.0
            continue
        fin, fence, pre, dl, ms = (sum(x[i] for x in v) for i in range(5))
        out['sdc_' + c] = fin / fr if fr else float('nan')
        rows.append('| %s | %.2f | %.2f | %.2f | %.2f | %.2f |' %
                    (c, fin / fr, fence / fr, pre / fr, dl / fr, ms / fr))
    print('\n| [sdcall] caller | fin/f | fence/f | pre/f | dl/f | ms/f |')
    print('|---|---|---|---|---|---|')
    print('\n'.join(rows) if rows else '| (none) | | | | | |')
    spl = [r['spl'] for r in sc if r['spl']]
    if spl and fr:
        s = [sum(x[i] for x in spl) / fr for i in range(5)]
        print('\n- spl per frame: def %.2f up %.2f dl %.2f kB %.1f cmpl %.2f' % tuple(s))
    whys = [r['why'] for r in sc if r['why']]
    if whys and fr:
        s = [sum(x[i] for x in whys) / fr for i in range(7)]
        print('- su_upl %.2f/f, su_deferred %.2f/f; why per frame: new %.2f inv %.2f '
              'stale %.2f hoff %.2f cpuw %.2f gap %.2f oth %.2f' %
              ((sum(r['su_upl'] for r in sc) / fr, sum(r['su_def'] for r in sc) / fr)
               + tuple(s)))
    for name, ticks in (('ovl1018', arm.ovl), ('evict372', arm.ev)):
        br = arm.bracket(ticks, s0, s1)
        if not br:
            print('- [%s]: no ticks bracket the span' % name)
            out[name] = None
            continue
        a, b, nf = br
        d = {k: (b[1][k][0] - a[1].get(k, (0, 0))[0],
                 b[1][k][1] - a[1].get(k, (0, 0))[1]) for k in b[1]}
        tot = sum(v[0] for v in d.values())
        out[name] = tot / nf
        print('- [%s] %s -> %s, %.0f guest frames: draw-dirty %.2f/f, by bin '
              'dirty/clean per frame: %s' %
              (name, cineread.hms(a[0]), cineread.hms(b[0]), nf, tot / nf,
               ' '.join('%s %.2f/%.2f' % (k, v[0] / nf, v[1] / nf)
                        for k, v in sorted(d.items()) if v[0] or v[1]) or '(none)'))
        for p in b[2]:
            print('  - end tick: %s' % p)
    print()
    return out


def block_timeline(arm):
    print('### per-block timeline: %s\n' % arm.name)
    print('| t-mark s | ms/f | sd | cDef | sd[dl] | dif ovl | ovlSh | exp | oth '
          '| txr dl | scdl | s2td | surfupd fin | range fin |')
    print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    v0, v1 = arm.span(*VIEW)
    sdc = [r for r in arm.sdcall if r['t']]
    for b in arm.blocks:
        if not (b['t'] and v0 <= b['t'] <= v1):
            continue
        near = [r for r in sdc if abs(r['t'] - b['t']) <= 1.0]
        r = near[0] if near else {}
        win = cineread.nearest([(w[1], w) for w in arm.windows()], b['t'])
        print('| %.0f | %s | %d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
            b['t'] - arm.mark, '%.1f' % win[1][2] if win else '-', b['sd'],
            b.get('cdef', '-'), b.get('sddl', '-'), b.get('dif_ovl', '-'),
            b.get('dif_ovlSh', '-'), b.get('dif_exp', '-'), b.get('dif_oth', '-'),
            b.get('txr_dl', '-'), b.get('txr_scdl', '-'), b.get('s2td', '-'),
            r['surfupd'][0] if 'surfupd' in r else '-',
            r['range'][0] if 'range' in r else '-'))
    print()


def leg(name, ok, text):
    print('- %s: %s  %s' % (name, 'HIT' if ok else 'MISS', text))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('--expect')
    o = ap.parse_args()
    e = json.load(open(o.expect))['expect'] if o.expect else {}
    A, B = Census(o.a), Census(o.b)
    void = []
    for arm in (A, B):
        if arm.mark is None:
            void.append('%s: no mark cinematic' % arm.name)
    if void:
        print('VOID: ' + '; '.join(void))
        return 2
    for arm in (A, B):
        block_timeline(arm)
    a0, a1 = A.span(*SPAN)
    b0, b1 = B.span(*SPAN)
    ra = account(A, a0, a1, 'A over the span')
    rb = account(B, b0, b1, 'B over the span (same seconds after mark)')
    account(A, *A.span(*VIEW), label='A over [mark+40, mark+260] (not judged)')
    account(B, *B.span(*VIEW), label='B over [mark+40, mark+260] (not judged)')

    # A's checks void the verdict; B's void only leg C, the one B is for
    nb = e.get('V_min_blocks', 5)
    vmsf = e.get('V_a_span_msf_min', 50.0)
    void_b = []
    for arm, r, out in (('A', ra, void), ('B', rb, void_b)):
        if r['blocks'] < nb or r['sdcall'] < nb:
            out.append('%s: %d stall blocks, %d [sdcall] lines in the span (< %d)'
                       % (arm, r['blocks'], r['sdcall'], nb))
        if r['ovl1018'] is None:
            out.append('%s: no [ovl1018] ticks bracket the span' % arm)
    if A.s2tcvt:
        void.append('[s2tcvt] on in A')
    if not B.s2tcvt:
        void_b.append('no [s2tcvt] on in B')
    if not ra['msf'] >= vmsf:
        void.append('A span %.1f ms/f < %.0f: the slow scene did not reproduce'
                    % (ra['msf'], vmsf))
    print('### verdict\n')
    if void:
        print('- V: VOID  ' + '; '.join(void + void_b))
        return 2
    print('- V: valid (A %.1f ms/f over the span, B %.1f)%s' %
          (ra['msf'], rb['msf'],
           '; B void for C: ' + '; '.join(void_b) if void_b else ''))
    sd = ra['sd']
    tx = ra['txr_dl'] + ra['txr_scdl']
    oth = tx + ra['sdc_range']
    leg('O', ra['ovl1018'] >= e.get('O_ovl_share_min', 0.6) * sd and
        oth <= e.get('O_other_share_max', 0.3) * sd,
        '[ovl1018] draw-dirty %.2f/f vs Finish sd %.2f/f (ratio %.2f, >= %.2f); '
        'txr dl + scdl + range fin %.2f/f (share %.2f, <= %.2f)' %
        (ra['ovl1018'], sd, ra['ovl1018'] / sd if sd else float('nan'),
         e.get('O_ovl_share_min', 0.6), oth, oth / sd if sd else float('nan'),
         e.get('O_other_share_max', 0.3)))
    leg('K', tx >= e.get('K_share_min', 0.6) * sd,
        'txr dl + scdl %.2f/f vs Finish sd %.2f/f (share %.2f, >= %.2f)' %
        (tx, sd, tx / sd if sd else float('nan'), e.get('K_share_min', 0.6)))
    rg = ra['sdc_range']
    leg('R', rg >= e.get('R_share_min', 0.6) * sd,
        'range fin %.2f/f vs Finish sd %.2f/f (share %.2f, >= %.2f)' %
        (rg, sd, rg / sd if sd else float('nan'), e.get('R_share_min', 0.6)))
    if void_b:
        print('- C: VOID  ' + '; '.join(void_b))
        return 0
    sr = rb['sd'] / sd if sd else float('nan')
    mr = rb['msf'] / ra['msf']
    leg('C', sr <= e.get('C_sd_ratio_max', 0.5) and mr <= e.get('C_msf_ratio_max', 0.8),
        'B/A Finish sd per frame %.2f (<= %.2f), ms per frame %.2f (<= %.2f)' %
        (sr, e.get('C_sd_ratio_max', 0.5), mr, e.get('C_msf_ratio_max', 0.8)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
