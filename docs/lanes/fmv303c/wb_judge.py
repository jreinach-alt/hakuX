#!/usr/bin/env python3
"""Join #303's surface write-back lines to the guest-buffer tint lines.

usage: wb_judge.py <logcat.txt> [<logcat.txt> ...]

Reads, in file order (logcat orders the pfifo and display threads by time):
  [fmv303] wbc ft=F n=N in=I        one per flip stall, cumulative counts
  [fmv303] wb addr=A len=L ... ft=F n=K in=0|1 path=P surf=S WxH
  [fmv303] f=D tex0 color=.. lin 640x368 ... addr=X len=Y ...  (bound buffer)
  [fmv303] f=D tex0 tint mb=M lit=L of=O ...
Each tint line with lit >= 100 is one lit frame, stamped with the newest
guest flip count seen before it (ft_at). It is tinted when mb/lit > 0.1 and
clean when mb == 0, as guest_tint.py counts them. Two joins:
  NEAR   a write-back landing in 0x3000000..0x3400000 has ft in
         [ft_at - 2, ft_at] (the brief's window).
  SINCE  a landing overlaps the displayed buffer (the tex0 line's addr, len)
         with ft in (the ft this buffer was last displayed at, ft_at]. Clean
         frames come singly between runs of tinted ones (probe v2 logcats),
         so NEAR's window spans both states; SINCE asks about the one buffer
         the frame shows, over the interval the decoder refilled it in. A
         buffer shown again at the same ft keeps its last SINCE value.

M0 per run, else VOID: the probe is on, wbc lines exist, the last wbc shows
write-backs (n > 0), >= 100 lit tinted frames, and no fewer in-region wb
lines were received than the last wbc `in` count (none dropped by logd), and
at least 90% of lit tinted frames show a buffer inside the region (the probe
logs every landing only there; a disc build that put the FMV buffers
elsewhere would otherwise read as a false EXONERATED).

Verdict over the valid runs (two needed), pooled:
  EXONERATED  no write-back landed in the region at all.
  HIT         P(NEAR | tinted) - P(NEAR | clean) >= 0.5, or the same for
              SINCE.
  UNORDERED   landings in the region exist, but neither join separates
              tinted from clean frames (both differences < 0.5).
Also prints the write-back surfaces by address, so a writer outside the
region is visible even when the verdict is EXONERATED.
"""
import re
import sys
from collections import Counter

WBC = re.compile(r'\[fmv303\] wbc ft=(-?\d+) n=(\d+) in=(\d+)')
WB = re.compile(r'\[fmv303\] wb addr=([0-9a-f]+) len=([0-9a-f]+) color=(\d) '
                r'fmt=(-?\d+) ft=(-?\d+) n=(\d+) in=(\d) path=(\S+) '
                r'surf=([0-9a-f]+) (\d+)x(\d+)')
TEX0 = re.compile(r'\[fmv303\] f=(\d+) tex0 color=\w+ lin (\d+)x(\d+) '
                  r'pitch=(\d+) addr=([0-9a-f]+) len=(\d+)')
REGION = (0x3000000, 0x3400000)
TINT = re.compile(r'\[fmv303\] f=(\d+) tex0 tint mb=(\d+) lit=(\d+) of=(\d+)')


def overlaps(a, ln, buf):
    return a < buf[0] + buf[1] and buf[0] < a + ln


def read(path):
    run = dict(path=path, probe_on=False, wbc=0, last_n=0, last_in=0,
               in_lines=0, wb_lines=0, frames=[], surfs=Counter(),
               outside=Counter())
    ft_at = None
    buf = None
    landings = []  # (ft, addr, len) in the region
    last_disp, last_since = {}, {}
    for line in open(path, errors='replace'):
        if '[fmv303]' not in line:
            continue
        if '[fmv303] probe on' in line:
            run['probe_on'] = True
            continue
        m = WBC.search(line)
        if m:
            ft, n, i = map(int, m.groups())
            run['wbc'] += 1
            run['last_n'], run['last_in'] = n, i
            ft_at = ft if ft_at is None else max(ft_at, ft)
            continue
        m = WB.search(line)
        if m:
            addr, ln = int(m[1], 16), int(m[2], 16)
            ft, inr = int(m[5]), int(m[7])
            run['wb_lines'] += 1
            run['surfs'][(m[9], m[3], m[4], m[10] + 'x' + m[11], inr)] += 1
            if inr:
                run['in_lines'] += 1
                landings.append((ft, addr, ln))
            ft_at = ft if ft_at is None else max(ft_at, ft)
            continue
        m = TEX0.search(line)
        if m:
            buf = (int(m[5], 16), int(m[6]))
            continue
        m = TINT.search(line)
        if not m or ft_at is None:
            continue
        mb, lit = int(m[2]), int(m[3])
        if lit < 100:
            continue
        state = 'tinted' if mb / lit > 0.1 else 'clean' if mb == 0 else None
        near = any(ft_at - 2 <= f <= ft_at for f, _, _ in landings)
        since = False
        if buf:
            prev = last_disp.get(buf[0])
            if prev is not None and prev == ft_at:
                since = last_since.get(buf[0], False)
            else:
                lo = ft_at - 2 if prev is None else prev
                since = any(lo < f <= ft_at and overlaps(a, ln, buf)
                            for f, a, ln in landings)
            last_disp[buf[0]] = ft_at
            last_since[buf[0]] = since
        if state == 'tinted' and (not buf or buf[0] < REGION[0]
                                  or buf[0] + buf[1] > REGION[1]):
            run['outside'][buf[0] if buf else -1] += 1
        if state:
            run['frames'].append((state, near, since))
    tinted = sum(s == 'tinted' for s, _, _ in run['frames'])
    why = []
    if not run['probe_on']:
        why.append('probe not on')
    if not run['wbc']:
        why.append('no wbc lines (apk lacks the hunk?)')
    elif not run['last_n']:
        why.append('wbc shows zero write-backs anywhere')
    if tinted < 100:
        why.append(f'{tinted} lit tinted frames < 100')
    if run['in_lines'] < run['last_in']:
        why.append(f"in-region wb lines {run['in_lines']} < wbc in "
                   f"{run['last_in']} (dropped)")
    if sum(run['outside'].values()) > 0.1 * max(tinted, 1):
        bufs = ', '.join('%x' % a if a >= 0 else 'none'
                         for a in sorted(run['outside']))
        why.append(f"{sum(run['outside'].values())} lit tinted frames show "
                   f"a buffer outside the probe region ({bufs})")
    run['void'] = why
    return run


def rate(frames, state, idx):
    xs = [f[idx] for f in frames if f[0] == state]
    return (sum(xs) / len(xs) if xs else 0.0), len(xs)


def main(paths):
    runs = [read(p) for p in paths]
    for r in runs:
        tp, tn = rate(r['frames'], 'tinted', 1)
        cp, cn = rate(r['frames'], 'clean', 1)
        sp, _ = rate(r['frames'], 'tinted', 2)
        sc, _ = rate(r['frames'], 'clean', 2)
        m0 = 'VOID: ' + '; '.join(r['void']) if r['void'] else 'OK'
        print(f"{r['path']}\n  M0 {m0}\n"
              f"  wbc {r['wbc']}  wb total {r['last_n']}  in-region "
              f"{r['last_in']} (lines {r['in_lines']})  wb lines "
              f"{r['wb_lines']}\n"
              f"  tinted {tn}: NEAR {tp:.3f} SINCE {sp:.3f}  "
              f"clean {cn}: NEAR {cp:.3f} SINCE {sc:.3f}")
        for k, v in r['surfs'].most_common(12):
            print(f'    surf={k[0]} color={k[1]} fmt={k[2]} {k[3]} '
                  f'in={k[4]}: {v}')
    valid = [r for r in runs if not r['void']]
    if len(valid) < 2:
        print(f'VERDICT: NONE ({len(valid)} valid runs, need 2)')
        return 2
    frames = [f for r in valid for f in r['frames']]
    inr = sum(r['last_in'] for r in valid)
    tp, tn = rate(frames, 'tinted', 1)
    cp, cn = rate(frames, 'clean', 1)
    sp, _ = rate(frames, 'tinted', 2)
    sc, _ = rate(frames, 'clean', 2)
    print(f'pooled: in-region landings {inr}; tinted {tn}: NEAR {tp:.3f} '
          f'SINCE {sp:.3f}; clean {cn}: NEAR {cp:.3f} SINCE {sc:.3f}')
    if inr == 0:
        v = 'EXONERATED'
    elif tp - cp >= 0.5 or sp - sc >= 0.5:
        v = 'HIT'
    else:
        v = 'UNORDERED'
    print(f'VERDICT: {v}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
