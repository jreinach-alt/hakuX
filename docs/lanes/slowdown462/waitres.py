#!/usr/bin/env python3
"""Wait (bounded) for dispatch result ids to finish; print queue state while waiting.

    waitres.py <max seconds> <id> [<id> ...]

Exit 0 when every id has a result dir with DONE, 1 on timeout. Prints the Nova's
running request and battery-hold state each minute, so a wait that is really a
hold or a long queue says so.
"""
import os
import sys
import time

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
limit, ids = float(sys.argv[1]), sys.argv[2:]
t0 = time.time()
last = 0.0
while True:
    done = [i for i in ids if os.path.exists(f"{D}/results/{i}/DONE")]
    if len(done) == len(ids):
        print("all done:", " ".join(ids))
        sys.exit(0)
    now = time.time()
    if now - last >= 60:
        last = now
        run = sorted(f[:-6] for f in os.listdir(f"{D}/running") if f.endswith(".owner"))
        q = sorted(f[:-4] for f in os.listdir(f"{D}/queue") if f.endswith(".req"))
        holds = [h for h in os.listdir(f"{D}/hold") if not h.endswith(".why") and h != "lifted"]
        pos = {i: (q.index(i) if i in q else ("running" if i in run else "?")) for i in ids if i not in done}
        print(time.strftime("%H:%M:%SZ", time.gmtime()), "running", run, "holds", holds, "pending", pos, flush=True)
    if now - t0 > limit:
        sys.exit(1)
    time.sleep(10)
