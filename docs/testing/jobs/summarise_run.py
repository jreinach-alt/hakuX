#!/usr/bin/env python3
"""One TSV line per claude -p run: when, which job, turns, seconds, error, the
first line of the result. The index that replaces reading transcripts.

    summarise_run.py <log.json> <job> [model]
"""
import datetime
import json
import os
import sys

path, job = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "?"
model = sys.argv[3] if len(sys.argv) > 3 else "?"
ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
turns = secs = cost = "?"
err = "?"
head = ""
try:
    raw = open(path, encoding="utf-8", errors="replace").read()
    # --output-format json emits one object; be tolerant of a trailing log line.
    start = raw.find("{")
    d = json.loads(raw[start:raw.rfind("}") + 1]) if start >= 0 else {}
    turns = d.get("num_turns", "?")
    secs = round(d.get("duration_ms", 0) / 1000) if d.get("duration_ms") else "?"
    cost = d.get("total_cost_usd", "?")
    err = "ERR" if d.get("is_error") else "ok"
    head = (d.get("result") or "").strip().splitlines()[0][:120] if d.get("result") else ""
except Exception as e:
    err = "UNPARSED:%s" % type(e).__name__
print("\t".join(str(x) for x in (ts, job, model, turns, secs, cost, err, os.path.basename(path), head)))
