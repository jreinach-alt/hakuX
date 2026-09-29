"""lane.battadmit-2: the Nova's runs over the last N days (argv[1], default 3),
by the lowest battery level each reached, against the Windows adb.log link
errors on ee317437 (NOTES.md, "The Nova's link floor"). Reads the dispatch dir.
"""
import os, glob, json, re, datetime, time, sys
from zoneinfo import ZoneInfo
D = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch')
ADB_LOG = '/mnt/c/Users/Justin/AppData/Local/Temp/adb.log'
tz = ZoneInfo('America/Los_Angeles')
DAYS = float(sys.argv[1]) if len(sys.argv) > 1 else 3
errs = []
for line in open(ADB_LOG, errors='ignore'):
    if 'ee317437' in line and 'terminated' in line:
        m = re.match(r'(\d\d-\d\d \d\d:\d\d:\d\d)', line)
        errs.append(datetime.datetime.strptime('2026-' + m.group(1), '%Y-%m-%d %H:%M:%S').replace(tzinfo=tz).timestamp())
runs = []
seen = set()
for p in glob.glob(D + '/results/*/thermal.jsonl'):
    rd = os.path.realpath(os.path.dirname(p))
    if rd in seen:
        continue
    seen.add(rd)
    if os.path.getmtime(p) < time.time() - DAYS * 86400:
        continue
    try:
        res = json.load(open(rd + '/result.json'))
    except Exception:
        continue
    if res.get('device_label') != 'nova':
        continue
    caps = []
    for line in open(p, errors='ignore'):
        try:
            r = json.loads(line)
            caps.append((float(r['t']), float(r['pw']['battery']['capacity'])))
        except Exception:
            pass
    if len(caps) < 2:
        continue
    t0, t1 = caps[0][0], caps[-1][0]
    # A link cut ends the samples, so look 120 s past the last one.
    n = sum(1 for e in errs if t0 - 60 <= e <= t1 + 120)
    runs.append((t0, t1, caps[0][1], min(c for _, c in caps), n, os.path.basename(rd)))
runs.sort()
bands = {}
for t0, t1, c0, cmin, n, rid in runs:
    b = int(cmin // 10) * 10
    s = bands.setdefault(b, [0, 0, 0.0])
    s[0] += 1
    s[1] += 1 if n else 0
    s[2] += (t1 - t0) / 3600
    print('%s  %5.1f min  cap %3d->%3d  errs %2d  %s' % (
        datetime.datetime.fromtimestamp(t0, tz).strftime('%m-%d %H:%M'), (t1 - t0) / 60, c0, cmin, n, rid))
print()
print('band(min cap)  runs  runs_with_link_error  hours')
for b in sorted(bands):
    s = bands[b]
    print('%3d-%3d  %4d  %4d  %5.2f' % (b, b + 9, s[0], s[1], s[2]))
