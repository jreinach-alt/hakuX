"""Read both VUID survey runs side by side: count_vuids.py output, the
feature line, and per-capture scores/status. usage: survey_ab.py <A id> <B id>"""
import csv
import os
import subprocess
import sys

R = "/home/justin/hakux-work/dispatch/results"
HERE = os.path.dirname(os.path.abspath(__file__))
COUNT = os.path.join(HERE, "..", "vklayer34", "count_vuids.py")
scores = {}
for rid in sys.argv[1:3]:
    rdir = os.path.join(R, rid)
    print("=" * 20, rid)
    print(subprocess.run([sys.executable, COUNT, rdir], capture_output=True,
                         text=True).stdout)
    for line in open(os.path.join(rdir, "logcat1.txt"), errors="replace"):
        if "shaderTessellationAndGeometryPointSize" in line:
            print("feature:", line.strip()[-90:])
            break
    with open(os.path.join(rdir, "scores1.tsv")) as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    print("columns:", list(rows[0].keys()) if rows else None)
    print("rows:", len(rows))
    scores[rid] = rows
a, b = (scores[k] for k in sys.argv[1:3])
if a and b:
    key = next(k for k in a[0] if k.lower() in ("test", "capture", "name", "key"))
    val = next((k for k in a[0] if k.lower() in ("differing", "diff", "px")), None)
    st = next((k for k in a[0] if k.lower() == "status"), None)
    bm = {r[key]: r for r in b}
    moved = 0
    for r in a:
        o = bm.get(r[key])
        if o is None:
            print("missing in B:", r[key])
            continue
        if val and r[val] != o[val]:
            moved += 1
            print("moved:", r[key], r[val], "->", o[val])
        if st and ("unreadable" in (r[st], o[st])):
            print("unreadable:", r[key], r[st], o[st])
    print("captures compared:", len(a), "moved:", moved)
