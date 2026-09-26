#!/usr/bin/env python3
"""Check wparamclip223-wedge.json's legs against a real scores1.tsv: every
glob matches, no capture that takes the new path is guarded as must-not-move,
and every capture outside the new path IS guarded.

Usage: check_legs.py PREDICTION.json SCORES1.TSV
"""
import csv
import fnmatch
import json
import sys

pred, tsv = sys.argv[1], sys.argv[2]
e = json.load(open(pred))
keys = ["%s/%s" % (r["suite"], r["test"])
        for r in csv.DictReader(open(tsv), delimiter="\t")]
newpath = (["W_param/prog_w_zero_inf__bitri_w" + s for s in
            "-0.00 -0.25 -0.50 -0.96e-34 -1.00 -1.50e-36 -1.88e-37 -2.00 "
            "-3.08e-33 -3.76e-37 -4.00 -7.52e-37 -inf".split()] +
           ["W_param/ff_w_zero_inf__bitri_w" + s for s in
            "-0.25 -0.50 -1.00 -2.00 -4.00 -inf".split()])
bad = 0
cov = set()
for g in e["must_not_move"]:
    hit = [k for k in keys if fnmatch.fnmatch(k, g)]
    cov |= set(hit)
    if not hit:
        print("NO MATCH", g)
        bad = 1
leak = [k for k in newpath if k in cov]
missing = [k for k in newpath if k not in keys]
unguarded = sorted(set(keys) - cov - set(newpath))
print("captures %d, guarded %d, new path %d" % (len(keys), len(cov), len(newpath)))
print("new-path rows inside a must-not-move glob:", leak)
print("new-path rows absent from the tsv:", missing)
print("unguarded rows outside the new path:", unguarded)
print("a_ref %s  b_ref %s" % (e["a_ref"], e["b_ref"]))
sys.exit(1 if (bad or leak or missing or unguarded) else 0)
