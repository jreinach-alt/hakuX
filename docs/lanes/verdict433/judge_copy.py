#!/usr/bin/env python3
"""judge_copy.py OUTDIR ID...: copy each result dir's inputs (not its frames)
from $DISPATCH_DIR/results to OUTDIR/<id> and run title_verdict.py there, so a
benchmark soak can be read against the bar without writing a verdict.json into
the live results (the status page takes the newest verdict per title and
device, and a 300 s benchmark would land there as a duration failure)."""
import os
import shutil
import subprocess
import sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
HERE = os.path.dirname(os.path.abspath(__file__))
VERDICT = os.path.join(HERE, "..", "..", "testing", "title_verdict.py")
FILES = ("request.json", "result.json", "run.log", "logcat.txt", "perf_regimen.json", "thermal.jsonl")

out = sys.argv[1]
for rid in sys.argv[2:]:
    src = os.path.join(D, "results", rid)
    dst = os.path.join(out, rid)
    os.makedirs(dst, exist_ok=True)
    for f in FILES:
        if os.path.exists(os.path.join(src, f)):
            shutil.copy(os.path.join(src, f), dst)
    r = subprocess.run([sys.executable, VERDICT, dst, "--require", "screening"],
                       capture_output=True, text=True)
    print(rid, (r.stdout or r.stderr).strip()[:400])
