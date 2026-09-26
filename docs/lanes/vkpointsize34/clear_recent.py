"""Print the six moved Clear captures from recent result dirs that scored Clear.
usage: clear_recent.py [n]"""
import csv
import glob
import json
import os
import sys

R = "/home/justin/hakux-work/dispatch/results"
KEYS = ["SCF_R5G6B5", "SCF_X1A7R8G8B8_O1A7R8G8B8", "SCF_X1A7R8G8B8_Z1A7R8G8B8",
        "SCF_X8R8G8B8_O8R8G8B8", "SCF_X8R8G8B8_Z8R8G8B8", "SFC_A8R8G8B8"]
n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
dirs = sorted(glob.glob(os.path.join(R, "*")), key=os.path.getmtime)[-n:]
for d in dirs:
    tsv = os.path.join(d, "scores1.tsv")
    if not os.path.exists(tsv):
        continue
    with open(tsv) as f:
        rows = {r["test"]: r for r in csv.DictReader(f, delimiter="\t")
                if r.get("suite") == "Clear"}
    if not all(k in rows for k in KEYS):
        continue
    try:
        res = json.load(open(os.path.join(d, "result.json")))
    except (OSError, ValueError):
        res = {}
    print(os.path.basename(d)[:44].ljust(44), str(res.get("ref", ""))[:10].ljust(10),
          str(res.get("device", ""))[:6].ljust(6),
          " ".join(rows[k]["differing"].rjust(6) for k in KEYS))
