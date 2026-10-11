"""Per belowbar1005 survey row: finish kinds per flip, from the hakuX-stall
RPBreaks Finish:(...) counts over the whole log (lane.gpunonrender). A title
with `sd` finishes had its GPU stamps counted twice before 5c35880d0a.

    sdscan.py      (run from the worktree root)
"""
import os, re
D = "/home/justin/hakux-work/dispatch/results/"
rows = open("docs/lanes/belowbar1005/xfrsurvey.tsv").read().splitlines()[1:]
for row in rows:
    rid = row.split()[-1]
    title = row[:40].strip()
    p = D + rid + "/logcat.txt"
    if not os.path.exists(p):
        print("%-40s %s no log" % (title, rid))
        continue
    parts, seen = {}, set()
    for l in open(p, errors="replace"):
        if "RPBreaks" not in l:
            continue
        key = l[:18] + l[l.find("RPBreaks"):]
        if key in seen:
            continue
        seen.add(key)
        f = re.search(r"Finish:(\d+)\(([^)]*)\)", l)
        if f:
            for k, x in re.findall(r"([A-Za-z]+)(\d+)", f.group(2)):
                parts[k] = parts.get(k, 0) + int(x)
    flip = max(parts.get("flip", 0), 1)
    keep = ("sd", "vtx", "sc", "buf", "fb", "flu", "pres", "stl")
    print("%-40s sd/flip %5.2f  %s" % (
        title, parts.get("sd", 0) / flip,
        " ".join("%s%.2f" % (k, parts.get(k, 0) / flip) for k in keep if parts.get(k))))
