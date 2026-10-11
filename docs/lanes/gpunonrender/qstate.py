#!/usr/bin/env python3
"""Dispatcher state for this lane's requests: running, queued (in order), holds,
and which of the given request ids have a DONE result (lane.gpunonrender).

    qstate.py [request-id ...]
"""
import os, sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
print("running:", sorted(os.listdir(D + "/running")))
queue = sorted(x for x in os.listdir(D + "/queue") if not x.startswith("."))
print("queue (%d):" % len(queue))
for x in queue[:25]:
    print("   ", x)
for f in sorted(os.listdir(D + "/hold")):
    if os.path.isdir(os.path.join(D, "hold", f)):
        continue
    print("hold %s: %s" % (f, open(os.path.join(D, "hold", f)).read().strip()[:160]))
for rid in sys.argv[1:]:
    r = os.path.join(D, "results", rid)
    state = ("DONE" if os.path.exists(r + "/DONE") else
             "result dir" if os.path.isdir(r) else "no result")
    print(rid, state)
