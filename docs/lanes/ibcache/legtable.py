#!/usr/bin/env python3
"""One row per run and the per-arm means for an env A/B leg (#507, 5c/5d).

    legtable.py <soakread.out> <headread.out> <idleread.out>

Arms come from the `[ibc507]` line (on=0 is A, on=1 is B). The means are over
runs that pass the validity gate here (mark, no crash, no hang, no thermal
pause, not void); the frame check is by eye and recorded in NOTES.
"""
import json
import statistics
import sys

s = [json.loads(l) for l in open(sys.argv[1])]
h = {j["id"]: j for j in map(json.loads, open(sys.argv[2]))}
d = {j["id"]: j for j in map(json.loads, open(sys.argv[3]))}
arms = {"A": [], "B": []}
for r in s:
    i = r["id"]
    arm = "B" if r["ibc"].startswith("on=1") else "A"
    ok = (r["mark"] and not r["crash"] and not r["hang"] and not r["pauses"]
          and not r["void"] and not r["tv_void"])
    print(i, arm, r["ibc"][:14], "valid" if ok else "INVALID",
          "gp_s", r["gameplay_s"], "fps", h[i]["fps_tw"], "jpf", r["jpf"],
          "net_w", r["net_w"], "idle", d[i]["guest_idle_med"],
          "oncpu", d[i]["vcpu_oncpu_med"], "rd/s", d[i]["pgraph_rd_per_s"],
          "hc", r["hc_med"], "static", h[i]["static"])
    if ok:
        arms[arm].append((h[i]["fps_tw"], r["jpf"], r["net_w"]))
m = {}
for a, xs in arms.items():
    if xs:
        m[a] = [statistics.mean(x[k] for x in xs) for k in range(3)]
        print(a, "n", len(xs), "fps %.3f jpf %.4f net_w %.3f" % tuple(m[a]))
if "A" in m and "B" in m:
    print("B/A: fps %.4f jpf %.4f net_w %.4f; fps B-A %.3f" % (
        m["B"][0] / m["A"][0], m["B"][1] / m["A"][1], m["B"][2] / m["A"][2],
        m["B"][0] - m["A"][0]))
