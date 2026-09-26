#!/usr/bin/env python3
"""Print the pass-1 plan (device, iso, route, label) for population 1, from
the staging batch's TSV. One line per title; requeue rows are folded."""
import csv
import sys

BATCH = "/home/justin/hakux-work/logs/titlepipe/batch-20260925.tsv"
LABEL = {
    "4541000D": "aufire", "4D530013": "blinx", "54430007": "doax",
    "45410083": "black", "45410026": "nightfire", "4D530003": "pgr",
    "4541005D": "goldeneye-ra", "4D53006E": "forza", "56550042": "50cent",
    "45530018": "25tolife", "5451000D": "wweraw2", "4541005B": "burnout3",
    "4156005D": "cod3", "4D53004B": "pgr2", "45410076": "burnout-rev",
    "4D530065": "blinx2", "54430006": "doa1u", "56550016": "brucelee",
    "54540079": "mc3", "56550036": "twinsanity",
}
route = sys.argv[1] if len(sys.argv) > 1 else "survey"
seen = set()
for r in csv.DictReader(open(BATCH), delimiter="\t"):
    if r["title_id"] in seen:
        continue
    seen.add(r["title_id"])
    print("\t".join([r["device"], r["iso"], route, LABEL[r["title_id"]]]))
