#!/usr/bin/env python3
"""Queue title soaks ahead of routine lane work, as `0-0-y-` requests.

    queue.py --ref <sha> --seconds 420 --tag p1 plan.tsv

plan.tsv: device <TAB> iso <TAB> route <TAB> label, one run per line, `#`
comments. Each line goes through request.sh (so the route is parsed and its
text embedded exactly as request.sh does) into a private staging queue; the
record is then re-keyed `0-0-y-<ts>-titleplay-<tag>-<label>` and renamed into
the real queue, which is the only way a request id carries a priority prefix.
Prints one `<id>\t<device>\t<iso>\t<route>` line per request queued.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REQ = os.path.join(HERE, "..", "..", "..", "testing", "request.sh")
D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")

ap = argparse.ArgumentParser()
ap.add_argument("plan")
ap.add_argument("--ref", required=True)
ap.add_argument("--seconds", type=int, default=420)
ap.add_argument("--tag", required=True)
ap.add_argument("--dry", action="store_true")
a = ap.parse_args()

rows = []
for ln in open(a.plan):
    ln = ln.rstrip("\n")
    if not ln.strip() or ln.lstrip().startswith("#"):
        continue
    dev, iso, route, label = ln.split("\t")
    rows.append((dev, iso, route, label))

ts = int(time.time())
stage = tempfile.mkdtemp(prefix="titleplay-q-")
for dev, iso, route, label in rows:
    env = dict(os.environ, DISPATCH_DIR=stage)
    p = subprocess.run(
        ["bash", REQ, "--who", "titleplay", "--ref", a.ref,
         "--purpose", f"#397 gameplay fps, {a.tag}: {label} on the {route} route",
         "--title", iso, "--seconds", str(a.seconds), "--device", dev,
         "--route", route,
         "--no-expect", "a measurement of a title, not a test of a change"],
        env=env, capture_output=True, text=True)
    if p.returncode != 0 or not p.stdout.startswith("queued "):
        sys.exit(f"request.sh refused {label}: {p.stdout}{p.stderr}")
    sid = p.stdout.split()[-1]
    src = os.path.join(stage, "queue", sid + ".req")
    r = json.load(open(src))
    nid = f"0-0-y-{ts}-titleplay-{a.tag}-{label}"
    r["id"] = nid
    assert r["device"] == dev and r["title"] == iso and r["route"]
    if a.dry:
        print(f"DRY {nid}\t{dev}\t{iso}\t{route}")
        continue
    tmp = os.path.join(D, "queue", f".{nid}.req.tmp")
    with open(tmp, "w") as f:
        json.dump(r, f, indent=2)
    json.load(open(tmp))
    os.rename(tmp, os.path.join(D, "queue", nid + ".req"))
    print(f"{nid}\t{dev}\t{iso}\t{route}")
