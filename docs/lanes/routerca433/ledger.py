#!/usr/bin/env python3
"""Ledger of route-related dispatch runs (routerca433, #433).

Read-only over $DISPATCH_DIR/results (default ~/hakux-work/dispatch/results).
One row per result dir whose requester is a route/title lane, from 09-24 on.
Writes TSV to stdout.  The outcome class here is AUTOMATIC (from run.log,
verdict.json and the withdraw/void notes); the frame-reviewed overrides live in
REVIEW below, and every override cites what was looked at.

Classes (brief's letters):
  a  died or hung before the mark (route never emitted `mark`)
  b  reached the mark, then stalled/static/looped (frame-judged only)
  c  reached the mark / live play, but under 600 s of gameplay
  d  600 s of live play, judged by frames
  e  void: adb drop, heat, foreground loss, harness fault
  f  wrong state: menu, name entry, save prompt, a different launch
  m  reached the mark, no verdict and no frame review (route check / survey)
"""
import json, os, re, sys, time

R = os.path.join(os.environ.get('DISPATCH_DIR', os.path.expanduser('~/hakux-work/dispatch')), 'results')
SINCE = time.mktime((2026, 9, 24, 0, 0, 0, 0, 0, 0)) - time.timezone
SCOPE = {'titleroutes', 'titleroutes2', 'titleplay', 'titlebench', 'host-titlebench', 'lane.verdict433',
         'autoverdict', 'routedriver', 'lane.local', 'lanelocal', 'titlestate'}
# hostops runs only when they are #433 confirmations
HOSTOPS_433 = re.compile(r'#433')

# Frame-reviewed overrides: id -> (class, what was looked at).  Filled from
# the sample review recorded in NOTES.md.
REVIEW = {}
if os.path.exists(os.path.join(os.path.dirname(__file__), 'review.tsv')):
    for line in open(os.path.join(os.path.dirname(__file__), 'review.tsv')):
        if line.startswith('#') or not line.strip():
            continue
        f = line.rstrip('\n').split('\t')
        REVIEW[f[0]] = (f[1], f[2] if len(f) > 2 else '')


def rd(p):
    try:
        return open(p, errors='replace').read()
    except OSError:
        return ''


def epoch_of(name, q):
    m = re.search(r'(17\d{8})', name)
    return int(m.group(1)) if m else 0


def row(name):
    d = os.path.join(R, name)
    try:
        q = json.load(open(os.path.join(d, 'request.json')))
    except Exception:
        return None
    req = q.get('requester', '')
    if req not in SCOPE and not (req == 'hostops' and HOSTOPS_433.search(q.get('purpose', ''))):
        return None
    t0 = epoch_of(name, q)
    if t0 < SINCE:
        return None
    res = {}
    try:
        res = json.load(open(os.path.join(d, 'result.json')))
    except Exception:
        pass
    v = {}
    try:
        v = json.load(open(os.path.join(d, 'verdict.json')))
    except Exception:
        pass
    log = rd(os.path.join(d, 'run.log'))
    held = sum(int(x) for x in re.findall(r'^held .* for (\d+)s', log, re.M))
    cool = sum(int(x) for x in re.findall(r'^COOLDOWN: waited (\d+) s', log, re.M))
    overhead = (res.get('battery') or {}).get('overhead_s') or 0
    started = 'ROUTE started' in log or re.search(r'^ROUTE \S+ start ', log, re.M) is not None
    marks = re.findall(r'^ROUTE (\S+) mark (\S+)', log, re.M)
    ended = re.search(r'^ROUTE \S+ end$', log, re.M) is not None
    steps = len(re.findall(r'^ROUTE \d', log, re.M))
    err = ''
    for pat in (r'^route\.sh: .*', r'^ROUTE (?:STOPPED|ABORTED|NOT PLAYED).*', r'^soak aborted.*',
                r'^guest never appeared.*', r'^guest exited after.*'):
        m = re.search(pat, log, re.M)
        if m:
            err = m.group(0)[:140]
            break
    pauses = (v.get('thermal') or {}).get('pauses') or []
    wd = rd(os.path.join(d, 'WITHDRAWN.txt')).strip()
    vd = (rd(os.path.join(d, 'VOID.txt')) or rd(os.path.join(d, 'VOID')) or rd(os.path.join(d, 'ERROR'))).strip()
    oa = rd(os.path.join(d, 'OWNER_ACCEPTED.txt')).strip()
    rf = os.path.join(d, 'route-frames')
    nrf = len(os.listdir(rf)) if os.path.isdir(rf) else 0
    fr = os.path.join(d, 'frames')
    nfr = len(os.listdir(fr)) if os.path.isdir(fr) else 0
    gs = v.get('gameplay_s')
    # Frame coverage after the mark: route-frames are named HHMMSS-label.png on
    # the same host clock as the ROUTE lines.  The soak captures no frames of
    # its own (frames.every is 0 on every run here), so these are the only
    # pictures of the window.
    def secs(hms):
        return int(hms[0:2]) * 3600 + int(hms[2:4]) * 60 + int(hms[4:6])
    post_n, post_span = 0, 0
    gm = [m for m in marks if m[1] == 'gameplay'] or marks[-1:]
    if gm and os.path.isdir(rf):
        t_mark = secs(gm[0][0].replace(':', '')[:6])
        for f in os.listdir(rf):
            if re.match(r'\d{6}-', f):
                dt = (secs(f[:6]) - t_mark) % 86400
                if 0 < dt < 7200:
                    post_n += 1
                    post_span = max(post_span, dt)
    # automatic class; e carries its cause
    dev = res.get('device_label') or q.get('device') or ''
    if err.startswith('ROUTE STOPPED') and dev == 'thor':
        cls = 'e:heat'     # thor_coldconfirm's HEAT STOP at xo 70 C (logs/thor-coldconfirm.log)
    elif err.startswith('ROUTE STOPPED'):
        cls = 'x'          # the guest exited on the Nova: an emulator crash, not a route fault
    elif err.startswith(('ROUTE ABORTED', 'ROUTE NOT PLAYED', 'soak aborted')) or 'not-foreground' in str(v.get('void')):
        cls = 'e:fg'
    elif vd or v.get('void') or err.startswith('guest never'):
        cls = 'e:' + ('heat' if 'thermal' in (str(v.get('void')) + vd) else 'other')
    elif q.get('route_name') is None and not started:
        cls = 'n'          # hands-off launch, no route at all
    elif started and not marks:
        cls = 'a'
    elif not started:
        cls = 'e:other'
    elif gs is not None and gs >= 600 and v.get('pass'):
        cls = 'd?'         # passes the gate; frames decide
    elif gs is not None and gs >= 600:
        cls = 'c+'         # >=600 s after the mark but failed another bar
    elif gs is not None:
        cls = 'c'
    else:
        cls = 'm'
    if pauses and cls[0] not in ('a', 'e', 'x') and (gs or 0) < 600:
        cls = 'e:heat'
    p = q.get('purpose', '')
    if re.search(r'route check|route replay|replay', p, re.I) and not re.search(r'Playable confirmation \(', p):
        kind = 'routecheck'
    elif re.search(r'Playable confirmation', p):
        kind = 'confirm'
    elif re.search(r'survey', p, re.I) or (q.get('route_name') == 'survey' and re.search(r'screen', p, re.I) is None):
        kind = 'survey'
    elif re.search(r'screen', p, re.I):
        kind = 'screen'
    elif re.search(r'bench|fps', p, re.I):
        kind = 'bench'
    else:
        kind = 'other'
    rv = REVIEW.get(q.get('id') or name)
    final = rv[0] if rv else cls
    return {
        'id': q.get('id') or name, 'dir': name, 'utc': time.strftime('%m-%d %H:%M', time.gmtime(t0)), 'requester': req, 'kind': kind,
        'device': res.get('device_label') or q.get('device') or '', 'title': (q.get('title') or '')[:40],
        'route': q.get('route_name') or '', 'req_s': q.get('seconds') or 0, 'held_s': held, 'cool_s': cool,
        'over_s': round(overhead), 'steps': steps, 'marks': ','.join(m[1] for m in marks)[:40],
        'ended': int(ended), 'gameplay_s': gs if gs is not None else '', 'pass': v.get('pass', ''),
        'pass_kind': v.get('pass_kind', ''), 'failing': (v.get('failing') or '')[:80],
        'human_review': (v.get('human_review') or '')[:60], 'rframes': nrf, 'frames': nfr, 'post_frames': post_n, 'post_span_s': post_span,
        'withdrawn': wd[:100].replace('\n', ' '), 'void': vd[:80].replace('\n', ' '), 'owner_accepted': int(bool(oa)),
        'err': err.replace('\t', ' '), 'auto': cls, 'class': final, 'review': rv[1] if rv else '',
        'purpose': q.get('purpose', '')[:120].replace('\t', ' '),
    }


def main():
    # A request can have two result dirs (the queue-prefixed dir and a bare-id
    # alias); keep one per request id, the one with the longer run.log.
    best = {}
    for n in sorted(os.listdir(R)):
        x = row(n)
        if not x:
            continue
        size = os.path.getsize(os.path.join(R, n, 'run.log')) if os.path.exists(os.path.join(R, n, 'run.log')) else -1
        if x['id'] not in best or size > best[x['id']][0]:
            best[x['id']] = (size, x)
    rows = [b[1] for b in best.values()]
    rows.sort(key=lambda x: (x['utc'], x['id']))
    cols = list(rows[0].keys())
    print('\t'.join(cols))
    for x in rows:
        print('\t'.join(str(x[c]) for c in cols))


if __name__ == '__main__':
    main()
