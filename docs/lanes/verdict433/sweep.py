#!/usr/bin/env python3
"""sweep.py OUTDIR [SINCE_EPOCH] [DEVICE]: judge a copy of every finished
route soak on DEVICE (default nova) since SINCE_EPOCH (default 1790560000,
2026-09-28 ~19:00 PDT) with judge_copy.py, and print one line per run:
share at 28.5+, gameplay s, audio short, hang, verdict reason. Writes nothing
into the live results. Use it to find titles at the bar with no confirmation."""
import glob
import json
import os
import re
import subprocess
import sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
HERE = os.path.dirname(os.path.abspath(__file__))
out = sys.argv[1]
since = int(sys.argv[2]) if len(sys.argv) > 2 else 1790560000
dev = sys.argv[3] if len(sys.argv) > 3 else "nova"

ids = []
for p in glob.glob(os.path.join(D, "results", "*", "request.json")):
    rid = p.split("/")[-2]
    m = re.search(r"(\d{10})-", rid)
    if not m or int(m.group(1)) < since:
        continue
    try:
        with open(p) as f:
            j = json.load(f)
    except (OSError, ValueError):
        continue
    if j.get("device") != dev or not j.get("route"):
        continue
    if not os.path.exists(os.path.join(D, "results", rid, "DONE")):
        continue
    ids.append(rid)

for i in range(0, len(ids), 20):
    r = subprocess.run([sys.executable, os.path.join(HERE, "judge_copy.py"), out] + ids[i:i + 20],
                       capture_output=True, text=True)
    for ln in r.stdout.splitlines():
        if " VERDICT " in ln:
            print(ln)
