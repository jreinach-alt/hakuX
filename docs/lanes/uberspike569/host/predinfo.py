#!/usr/bin/env python3
"""Print this lane's registered predictions: sha256, title, route, seconds, refs (lane.uberspike569)."""
import glob
import hashlib
import json

KEYS = ('title', 'route', 'seconds', 'a_ref', 'b_ref', 'h_ref', 'device')
for f in sorted(glob.glob('docs/testing/predictions/uberspike569-gpl-*.json')):
    b = open(f, 'rb').read()
    d = json.loads(b)
    print(f, hashlib.sha256(b).hexdigest()[:12], dict((k, d.get(k)) for k in KEYS))
