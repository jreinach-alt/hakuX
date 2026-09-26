#!/usr/bin/env python3
"""Print targets.toml entries for population 1: canonical title_id and name
from the xemu compat CSV, ISO per device from the staging batch TSV."""
import csv

CSV = "/home/justin/hakux-work/titles/xemu-compat-2026-09-25.csv"
BATCH = "/home/justin/hakux-work/logs/titlepipe/batch-20260925.tsv"

rows = list(csv.DictReader(open(CSV)))
print("# CSV columns:", list(rows[0].keys()))
by_id = {}
for r in rows:
    for k in ("title_id", "canonical_title_id"):
        if r.get(k):
            by_id.setdefault(r[k].upper(), r)
seen = set()
for b in csv.DictReader(open(BATCH), delimiter="\t"):
    tid = b["title_id"].upper()
    if tid in seen:
        continue
    seen.add(tid)
    r = by_id.get(tid)
    canon = (r.get("canonical_title_id") or tid).upper() if r else tid
    name = r["name"] if r and "name" in r else b["name"]
    print(f'\n[titles."{canon}"]')
    print(f'name = "{name}"')
    print(f'iso = {{ {b["device"]} = "{b["iso"]}" }}')
    print('notes = "Staged 2026-09-26 (#265 batch); own target not yet measured, so the 30 default."'
          + ("" if r else "  # NOT IN CSV"))
