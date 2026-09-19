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
# DATA, NOT DISPLAY -- STAYS UTC, and this is the site most likely to be
# "finished" by mistake. This `ts` is column 1 of logs/<job>/index.tsv, and
# status.sh selects its 24h window with `awk '$1 >= c'` where c comes from
# since_iso() in UTC. That is a LEXICAL string comparison: it is correct only
# because UTC "%FT%TZ" sorts chronologically. Writing local time here would
# shift every row seven hours against an unchanged cutoff -- rows silently
# missing from the page -- and across the November fall-back, where
# 01:00-02:00 happens twice, two distinct instants would compare in the wrong
# order. status.sh converts this column to the display zone where it PRINTS
# it (jobs/localtime.sh:local_hm), which is where the conversion belongs.
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
    # MAXTURNS is not ERR: the run did its work and was cut at the cap.
    # Collapsing the two hid three consecutive capped board ticks behind a
    # word that reads as "this run failed".
    if d.get("subtype") == "error_max_turns":
        err = "MAXTURNS"
    elif d.get("is_error"):
        err = "ERR"
    else:
        err = "ok"
    head = (d.get("result") or "").strip().splitlines()[0][:120] if d.get("result") else ""
except Exception as e:
    err = "UNPARSED:%s" % type(e).__name__
print("\t".join(str(x) for x in (ts, job, model, turns, secs, cost, err, os.path.basename(path), head)))
