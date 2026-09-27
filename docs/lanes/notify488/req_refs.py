"""Print each result's requested ref, device and completion time (arm labels come from the request, not the order)."""
import json
import os
import sys

R = os.environ.get('DISPATCH_DIR', '/home/justin/hakux-work/dispatch') + '/results/'
for rid in sys.argv[1:]:
    rq = json.load(open(R + rid + '/request.json'))
    done = os.path.getmtime(R + rid + '/DONE') if os.path.exists(R + rid + '/DONE') else None
    print(rid, {k: rq.get(k) for k in ('ref', 'device', 'serial', 'purpose') if k in rq}, 'DONE', done)
