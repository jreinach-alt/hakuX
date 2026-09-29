#!/usr/bin/env python3
"""Rewrite PR #618's header lines (Base, Files, Prediction) from the branch; print the new body.

    pr_body.py <old body file> <new body file>
"""
import hashlib
import subprocess
import sys

old = open(sys.argv[1]).read().splitlines()


def git(*a):
    return subprocess.check_output(["git", *a], text=True).strip()


files = git("diff", "--name-only", "origin/master...HEAD").splitlines()
base = git("rev-parse", "--short=10", "origin/master")
preds = ["docs/testing/predictions/uberspike569-gpl-pixels.json",
         "docs/testing/predictions/uberspike569-gpl-doa-soak.json"]
pred = "; ".join("%s @ %s" % (p, hashlib.sha256(open(p, "rb").read()).hexdigest())
                 for p in preds)
out = []
for line in old:
    if line.startswith("Base:"):
        line = "Base: master @ %s (merged in at 23543417aa; #581 and #594 folded)" % base
    elif line.startswith("Files:"):
        line = "Files: " + ", ".join(files)
    elif line.startswith("Prediction:"):
        line = "Prediction: " + pred
    out.append(line)
open(sys.argv[2], "w").write("\n".join(out) + "\n")
print("\n".join(out[:6])[:1500])
