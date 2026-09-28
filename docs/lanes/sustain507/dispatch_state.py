"""Where the dispatcher stands: does its tree and its bin snapshot accept
PERF_REGIMEN=default, what holds are in force, and what is queued or running."""
import glob
import json
import os

D = '/home/justin/hakux-work/dispatch'
TREE = os.environ.get('DISPATCH_TREE', '/home/justin/hakuX')
for p in (TREE + '/docs/testing/soak_title.sh', D + '/bin/soak_title.sh'):
    try:
        txt = open(p).read()
    except OSError as e:
        print(p, 'unreadable', e)
        continue
    line = [ln for ln in txt.splitlines() if 'max|rest|off' in ln]
    print(p, '->', line[0].strip() if line else 'no regimen case line')
for f in sorted(glob.glob(D + '/hold/*')):
    if os.path.isdir(f):
        continue
    print('hold', os.path.basename(f), open(f, errors='replace').read()[:200].replace('\n', ' '))
for sub in ('queue', 'running'):
    for f in sorted(glob.glob('%s/%s/*.req' % (D, sub))):
        try:
            q = json.load(open(f))
        except Exception:
            q = {}
        print(sub, os.path.basename(f), q.get('device'), q.get('seconds'), (q.get('title') or '')[:30])
