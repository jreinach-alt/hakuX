#!/usr/bin/env python3
"""judge_copy.py OUTDIR ID...: copy each result dir's inputs (not its frames)
from $DISPATCH_DIR/results to OUTDIR/<id> and run title_verdict.py there, so a
benchmark soak can be read against the bar without writing a verdict.json into
the live results. Adapted from lane.verdict433's judge_copy.py for #433
defect triage (analysis only, no device runs)."""
import os
import shutil
import subprocess
import sys

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
HERE = os.path.dirname(os.path.abspath(__file__))
VERDICT = os.path.join(HERE, "..", "..", "testing", "title_verdict.py")
FILES = ("request.json", "result.json", "run.log", "logcat.txt", "perf_regimen.json", "thermal.jsonl")

out = sys.argv[1]
require = "confirmation" if "--require=confirmation" in sys.argv else "screening"
reviewed = "yes" if "--reviewed=yes" in sys.argv else ("no" if "--reviewed=no" in sys.argv else None)
for rid in [a for a in sys.argv[2:] if not a.startswith("--")]:
    src = os.path.join(D, "results", rid)
    dst = os.path.join(out, rid)
    os.makedirs(dst, exist_ok=True)
    for f in FILES:
        if os.path.exists(os.path.join(src, f)):
            shutil.copy(os.path.join(src, f), dst)
    cmd = [sys.executable, VERDICT, dst, "--require", require]
    if reviewed:
        cmd += ["--reviewed-gameplay", reviewed]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(rid, (r.stdout or r.stderr).strip()[:600])
