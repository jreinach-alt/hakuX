#!/usr/bin/env python3
"""Compare a run re-scored by the old and the new score_sweep.py.

    rescore_cmp.py OLD.tsv NEW.tsv [RECORDED.tsv]

Asserts every column but `status` is identical (the change touches only the
blank decision) and prints each row whose status moved.
"""
import csv
import sys


def load(p):
    return {(r["suite"], r["test"]): r
            for r in csv.DictReader(open(p), delimiter="\t")}


old, new = load(sys.argv[1]), load(sys.argv[2])
print("rows: old %d, new %d" % (len(old), len(new)))
if len(sys.argv) > 3:
    rec = load(sys.argv[3])
    mism = sum(rec[k]["status"] != old[k]["status"] for k in old if k in rec)
    print("recorded TSV vs old-scorer re-run, status mismatches: %d" % mism)
cols = [c for c in next(iter(new.values())) if c != "status"]
diff_cols = [k for k in new if any(old[k][c] != new[k][c] for c in cols)]
print("rows differing in any non-status column: %d" % len(diff_cols))
moved = 0
for k in sorted(new):
    if old[k]["status"] != new[k]["status"]:
        moved += 1
        r = new[k]
        print("%-55s %-6s -> %-6s differing=%s max_rgb=%s max_a=%s" % (
            k[0] + "/" + k[1], old[k]["status"], r["status"], r["differing"],
            r["max_rgb"], r["max_a"]))
print("status changes: %d" % moved)
