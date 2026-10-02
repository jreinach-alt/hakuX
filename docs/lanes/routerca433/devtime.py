#!/usr/bin/env python3
"""Device-minutes by state and by work kind, from logs/devwatch/*.tsv (routerca433, #433).

devwatch samples each device about once a minute: local time, device, state
(running/idle/hands-on/...), a detail (the hold reason for hands-on), and the
running request id.  Each sample is counted as one minute.  Read-only.
"""
import collections, os, re, sys

D = os.path.expanduser('~/hakux-work/logs/devwatch')
ROUTE_REQ = re.compile(r'titleroutes|titleplay|titlebench|verdict433|autoverdict|routedriver|titlestate|lane\.local-|lanelocal|collapse433|hostops-?\d*$')
ROUTE_HOLD = re.compile(r'titleroute|routedriver|route|nav\.py|path-?find|verdict433|titlerun|titleplay|snapdrive|buffy|castlevania|sonic|monkey|forza|blood ?wake|bf2|playable|#397|#433', re.I)


def kind(state, detail, req):
    if state == 'running':
        if re.search(r'-(titleroutes2?|titleplay|titlebench|lane\.verdict433|autoverdict|routedriver|titlestate)-|titleplay-p1|titlebench', req):
            return 'run:route'
        if re.search(r'lane\.local-\d|lanelocal-\d', req):
            return 'run:route'          # the two lane.local #433 confirmations (checked by id in NOTES)
        return 'run:other'
    if state == 'hands-on':
        if re.search(r'coldslot', detail):
            return 'hold:coldslot'
        if ROUTE_HOLD.search(detail):
            return 'hold:route'
        return 'hold:other'
    return state or 'blank'


def main():
    since = sys.argv[1] if len(sys.argv) > 1 else '20260926'
    tot = collections.defaultdict(collections.Counter)
    day = collections.defaultdict(collections.Counter)
    holds = collections.Counter()
    for f in sorted(os.listdir(D)):
        if f[:8] < since:
            continue
        for line in open(os.path.join(D, f), errors='replace'):
            p = line.rstrip('\n').split('\t')
            if len(p) < 3:
                continue
            dev, state = p[1], p[2]
            # columns: time, device, state, flags, request id (running) or hold reason (hands-on)
            req = p[4] if len(p) > 4 else ''
            detail = req
            k = kind(state, detail, req)
            tot[dev][k] += 1
            day[(f[:8], dev)][k] += 1
            if k.startswith('hold:'):
                holds[(dev, k, re.sub(r'^\S+Z ', '', detail)[:90])] += 1
    for dev in sorted(tot):
        print(dev, 'total minutes', sum(tot[dev].values()))
        for k, v in tot[dev].most_common():
            print('   %-14s %6d min  %6.1f h' % (k, v, v / 60))
    print('\nper day')
    for (d, dev) in sorted(day):
        c = day[(d, dev)]
        print(d, dev, ' '.join('%s=%.1fh' % (k, v / 60) for k, v in c.most_common()))
    print('\nholds (minutes)')
    for (dev, k, why), v in sorted(holds.items(), key=lambda x: -x[1])[:60]:
        print('%5d %s %s %s' % (v, dev, k, why))


if __name__ == '__main__':
    main()
