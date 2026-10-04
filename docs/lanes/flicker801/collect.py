#!/usr/bin/env python3
"""Re-score every burst of the 10-04 Nova sessions with the shipped flicker_score.py and write the evidence the
repo keeps: runs/<session>/<title-dir>/<burst>/{capture.json, flicker.tsv, worst.jpg}. The mp4s (about 10 MB each)
stay in the worktree's .flkscratch and are not committed.

    collect.py <scratch dir with s1 s2 s3> > table.md
"""

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing"))
import flicker_score  # noqa: E402
from PIL import Image  # noqa: E402

NAMES = {"4D53000F": "RalliSport Challenge", "4947002B": "Panzer Dragoon Orta",
         "4D530004": "Halo: Combat Evolved", "53450029": "Spikeout: Battle Street"}


def main():
    src = sys.argv[1]
    rows = []
    for mp4 in sorted(glob.glob(os.path.join(src, "s*", "*", "b*", "burst.mp4"))):
        bdir = os.path.dirname(mp4)
        rel = os.path.relpath(bdir, src)
        sess, tdir, burst = rel.split(os.sep)
        out = os.path.join(HERE, "runs", rel)
        res = flicker_score.run(mp4, out)
        meta = json.load(open(os.path.join(bdir, "capture.json")))
        meta["flicker"] = res
        json.dump(meta, open(os.path.join(out, "capture.json"), "w"), indent=1)
        png = os.path.join(out, "flicker_worst.png")
        if os.path.exists(png):
            Image.open(png).convert("RGB").save(os.path.join(out, "worst.jpg"), quality=80)
            os.remove(png)
        tid = tdir.split("-")[0]
        mode = "race start / claim" if "claim" in tdir else "hold-play"
        rows.append((sess, NAMES.get(tid, tid), mode, burst, meta.get("seconds"), res))
    print("| session | title | when | burst | s | verdict | p90 | rate/100 | max | triples | unique fps |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for sess, name, mode, burst, secs, r in rows:
        print("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            sess, name, mode, burst, secs, r["verdict"], r["p90"], r["rate"], r["max"], r["triples"],
            r.get("unique_fps", "-")))


if __name__ == "__main__":
    main()
