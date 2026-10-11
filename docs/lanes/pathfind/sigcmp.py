"""How close are the same menu screens across ESPN 2K5 siblings, by pathfind's signature and by a
layout-normalised one? Rows: hoops frames; cols: nhl frames with the same state."""
import glob, json, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, "docs/testing/titles")
import pathfind as p


def norm_sig(path):
    g = np.asarray(p.grey(path).resize((16, 12), Image.BOX), dtype=np.float32)
    return (g - g.mean()) / (g.std() + 1e-3)


def steps(run):
    out = []
    for l in open(f"scratch/runs/{run}/steps.jsonl"):
        d = json.loads(l)
        if d.get("frame") and d.get("state") in p.Agent.MENU_STATES:
            out.append((d["n"], d["state"], d.get("why", "")[:40], os.path.join("scratch/runs", run, d["frame"])))
    return out


A = steps("espn-college-hoops-2k5.replay")
B = steps("espn-nhl-2k5.sibguided") + steps("espn-nhl-2k5.baseline-try1")
for na, sa, wa, fa in A:
    best = []
    for nb, sb, wb, fb in B:
        if not os.path.exists(fb):
            continue
        d1 = p.sig_dist(p.signature(fa), p.signature(fb))
        d2 = float(np.abs(norm_sig(fa) - norm_sig(fb)).mean())
        best.append((d1, d2, sb, wb))
    best.sort()
    if best:
        print(f"{sa:16s} {wa:40s} -> nearest {best[0][2]:16s} {best[0][3]:40s} raw {best[0][0]:5.1f} norm {best[0][1]:.2f}")
    # same-title baseline: different screens' distances
