#!/usr/bin/env python3
"""One title soak, read the #462 way: the gameplay window only, every reader.

    titleread.py <result-id> [--from S] [--to S]

The window starts at the route's `mark play` (survey route; `mark gameplay`
if the route wrote one) plus --from seconds (default 30), and ends --to
seconds after the mark (default: 10 s before `soak end`). Then it runs, over
that same absolute window, each reader an earlier lane wrote and validated,
converting the window to the time base that reader uses:

  aufire412/splitread.py  phase/cpu/work/stall medians (base: first hakuX/xemu line)
  aufire412b/pace.py      VBLANKs per flip, vCPU busy        (base: logcat line 1)
  aufire412b/vbl.py       guest VBLANK rate, clamps, lateness (base: logcat line 1)
  tbchurn424/churn.py     #424 churn on the vCPU thread       (base: logcat line 1, --from/--to)

and prints the build, device and route provenance from result.json, so no
number leaves this tool without them.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
HERE = os.path.dirname(os.path.abspath(__file__))
LANES = os.path.dirname(HERE)
TS = re.compile(r"^(\d\d-\d\d \d\d:\d\d:\d\d\.\d+)\s+\w/([\w-]+)\s*\(")


def ts(s):
    return datetime.strptime("2026-" + s, "%Y-%m-%d %H:%M:%S.%f").timestamp()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rid")
    ap.add_argument("--from", dest="frm", type=float, default=30.0)
    ap.add_argument("--to", type=float, default=None)
    ap.add_argument("--window", default=None,
                    help="lo,hi seconds after logcat line 1, picked from timeline.py and the shots; "
                         "overrides the route mark (the survey route's `mark play` can fall after the gameplay)")
    a = ap.parse_args()
    rdir = f"{D}/results/{a.rid}"
    res = json.load(open(f"{rdir}/result.json"))
    log = f"{rdir}/logcat.txt"
    print("result %s: apk %s ref %s device %s (%s) title %s seconds %s status %s" % (
        a.rid, res.get("apk_sha"), res.get("ref"), res.get("device_label"), res.get("device_serial"),
        res.get("title"), res.get("seconds"), res.get("status", "-")))
    reg = f"{rdir}/perf_regimen.json"
    if os.path.exists(reg):
        g = json.load(open(reg))
        print("regimen: %s perf_mode %s fan_mode %s (restored %s)" % (
            g.get("regimen"), g.get("perf_mode"), g.get("fan_mode"), g.get("perf_restored")))
    else:
        print("regimen: no perf_regimen.json in the result dir")
    first = first_hx = mark = end = None
    marks = {}
    for line in open(log, errors="replace"):
        m = TS.match(line)
        if not m:
            continue
        t = ts(m.group(1))
        if first is None:
            first = t
        tag = m.group(2)
        if first_hx is None and tag.startswith(("hakuX", "xemu")):
            first_hx = t
        if tag == "hakuX-route":
            body = line.split("):", 1)[1].strip()
            marks.setdefault(body, t)
    # pace.py/vbl.py/churn.py take L[0]; if line 1 is not a timestamped line they would fail anyway
    for key in ("mark gameplay", "mark play"):
        if key in marks:
            mark = marks[key]
            print("window mark: %s at +%.1f s (logcat line 1 base)" % (key, mark - first))
            break
    if a.window:
        lo, hi = (first + float(x) for x in a.window.split(","))
        print("window: %.1f-%.1f s after line 1 (%.0f s), given explicitly" % (lo - first, hi - first, hi - lo))
    else:
        if mark is None:
            sys.exit("no `mark play`/`mark gameplay` in the logcat: the route never reached play; no window")
        end = marks.get("soak end")
        lo = mark + a.frm
        hi = mark + a.to if a.to is not None else ((end - 10) if end else None)
        if hi is None:
            sys.exit("no `soak end` mark and no --to")
        print("window: %.1f-%.1f s after line 1 (%.0f s of play, from mark+%.0f)" % (lo - first, hi - first, hi - lo, a.frm))
    # churn.py's base is the route's `mark gameplay` when the route wrote one
    # and logcat line 1 only when it did not. The survey route writes `mark
    # play`, so the five titles were read from line 1; gta-sa writes `mark
    # gameplay`, and passing line-1 offsets read the wrong 53 s (GTA, 09-27).
    churn_base = marks.get("mark gameplay", first)
    runs = [
        ["aufire412/splitread.py", log, "--window", "%.1f,%.1f" % (lo - first_hx, hi - first_hx)],
        ["aufire412b/pace.py", "%.1f" % (lo - first), "%.1f" % (hi - first), a.rid],
        ["aufire412b/vbl.py", "%.1f" % (lo - first), "%.1f" % (hi - first), a.rid],
        ["tbchurn424/churn.py", "--from", "%.1f" % (lo - churn_base), "--to", "%.1f" % (hi - churn_base), a.rid],
    ]
    for r in runs:
        print("\n== " + r[0])
        p = subprocess.run([sys.executable, os.path.join(LANES, r[0])] + r[1:], capture_output=True, text=True)
        sys.stdout.write(p.stdout)
        if p.returncode:
            print("  (%s exited %d) %s" % (r[0], p.returncode, p.stderr.strip()[-400:]))


if __name__ == "__main__":
    main()
