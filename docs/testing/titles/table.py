#!/usr/bin/env python3
"""table.py [--results DIR]... [--judge] [--csv]

The latest verdict per (title, device, ref), for the owner's per-title table.

Reads <results>/*/verdict.json (default: $DISPATCH_DIR/results). "Latest" is
by `judged_utc`, then by the request id, which starts with the queue time.
--judge first runs title_verdict.py on every soak result dir that played a
route and has no verdict.json yet.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VERDICT = os.path.join(HERE, "..", "title_verdict.py")


def load(p):
    try:
        with open(p) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def judge_missing(dirs):
    for d in dirs:
        for rdir in sorted(glob.glob(os.path.join(d, "*"))):
            if os.path.exists(os.path.join(rdir, "verdict.json")):
                continue
            req = load(os.path.join(rdir, "request.json")) or {}
            if req.get("title") and req.get("route") and os.path.exists(os.path.join(rdir, "run.log")):
                subprocess.call([sys.executable, VERDICT, rdir])


def rows(dirs):
    latest = {}
    for d in dirs:
        for p in glob.glob(os.path.join(d, "*", "verdict.json")):
            v = load(p)
            if not v:
                continue
            key = (v.get("name") or v.get("title") or "?", v.get("device") or "?", v.get("ref") or "?")
            order = (v.get("judged_utc") or "", v.get("request_id") or "")
            if key not in latest or order > latest[key][0]:
                latest[key] = (order, v)
    return [v for _, v in sorted(latest.values(), key=lambda x: (x[1].get("name") or x[1].get("title") or ""))]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--results", action="append")
    ap.add_argument("--judge", action="store_true")
    ap.add_argument("--csv", action="store_true")
    a = ap.parse_args()
    dirs = a.results or [os.path.join(os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch"), "results")]
    if a.judge:
        judge_missing(dirs)
    cols = ["title", "device", "ref", "result", "scale", "gameplay_s", "fps_ok", "own_tgt",
            "crash", "hang", "audio_short", "by", "request"]
    out = []
    for v in rows(dirs):
        res = ("PASS " + (v.get("rating_candidate") or "?")) if v.get("pass") else \
              "FAIL " + (v.get("failing") or "?").split(":")[0]
        out.append([v.get("name") or v.get("title") or "?", v.get("device") or "?",
                    str(v.get("ref") or "?")[:12], res, str(v.get("surface_scale")),
                    str(v.get("gameplay_s")), str(v.get("fps_ok_share")),
                    ("BELOW %g" % v["target_fps"]) if v.get("below_own_target") else str(v.get("target_fps")),
                    str(v.get("crash")), str(v.get("hang")), str(v.get("audio_starve_share")),
                    str(v.get("gameplay_by")), str(v.get("request_id"))])
    if a.csv:
        import csv
        w = csv.writer(sys.stdout)
        w.writerow(cols)
        w.writerows(out)
        return 0
    if not out:
        print("no verdicts under %s" % ", ".join(dirs))
        return 0
    wid = [max(len(c), *(len(r[i][:40]) for r in out)) for i, c in enumerate(cols)]
    print("  ".join(c.ljust(wid[i]) for i, c in enumerate(cols)))
    for r in out:
        print("  ".join(x[:40].ljust(wid[i]) for i, x in enumerate(r)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
