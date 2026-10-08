#!/usr/bin/env python3
"""Print a pathfind run's steps, one line each, and the genre loop its hold
played (lane.gpunonrender). Input for docs/lanes/fps20786/steps2route.py.

    stepsdump.py <pathfind run dir>
"""
import json, re, sys

run = sys.argv[1]
v = json.load(open(run + "/verdict.json"))
print("verdict:", {k: v.get(k) for k in ("title", "reached_gameplay", "gameplay_s",
                                          "fps_window_median", "fps_bar")})
for line in open(run + "/steps.jsonl"):
    d = json.loads(line)
    print(d.get("n"), d.get("t"), d.get("state"), d.get("action"), str(d.get("why", ""))[:90])
for line in open(run + "/run.log", errors="replace"):
    if re.search(r"loop|genre|hold", line, re.I):
        print("run.log:", line.rstrip()[:200])
with open(run + "/hold.jsonl") as f:
    for i, line in enumerate(f):
        if i >= 3:
            break
        print("hold:", line.rstrip()[:300])
