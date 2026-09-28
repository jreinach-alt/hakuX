#!/usr/bin/env python3
"""Park #462 phase 2b's re-pilot: Otogi on the timing-tolerant route.

The first pilot (0-0-s-1-1790609660-lane.slowtier2-otogi762702) never left
the title (NOTES.md, "Attempt 3"). This writes one request, in park.py's
shape, with routes/otogi.cold.route in place of master's otogi.route, into
the same parked dir. Same ref, seconds and regimen as the first pilot, so the
two differ only in the route. Refuses to run twice.
Usage (from the worktree root): python3 docs/lanes/slowtier2/park_otogi2.py
"""
import datetime, json, os, random, sys, time

D = os.path.join(os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch"),
                 "parked", "slowtier2-cold-20260928")
HERE = os.path.dirname(os.path.abspath(__file__))
ROUTE = os.path.join(HERE, "routes", "otogi.cold.route")
if any("lane.slowtier2-otogi2" in f for f in os.listdir(D)):
    sys.exit("already parked in %s" % D)
route = open(ROUTE).read()
rid = "1-%d-lane.slowtier2-otogi2%d" % (int(time.time()), random.randint(100000, 999999))
req = {
    "id": rid, "requester": "lane.slowtier2",
    "purpose": "#462 phase 2b run 1b (the re-pilot): Otogi perflog soak on master, on "
               "routes/otogi.cold.route (four STARTs from +22 s; the first pilot's single "
               "START at +48 s left it on the title). The renderer split for the "
               "renderer-side group; needs a COLD start (xo <= 50 C, battery <= 36 C)",
    "program": "pgraph", "suites": [], "tests": [], "skip_tests": [],
    "ref": "97a6fa2b51", "arm": "company", "runs": 1,
    "title": "46530002-Otogi_Myth_of_Demons.xiso.iso", "seconds": 550, "device": "thor",
    "pull_glob": "", "audio_capture": "", "base_iso": "",
    "perflog": "true", "only_tests": [],
    "env": ["PERF_REGIMEN=max"], "frames_every": 0,
    "route_name": "otogi.cold",
    "route": route,
    "expect": "", "expect_sha": "",
    "no_expect": "attribution soak (#462), not an A/B arm",
    "queued_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
text = json.dumps(req, indent=2)
json.loads(text)
p = os.path.join(D, rid + ".req")
with open(p + ".tmp", "w") as f:
    f.write(text)
os.rename(p + ".tmp", p)
print(rid)
