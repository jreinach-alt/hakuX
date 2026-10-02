#!/usr/bin/env python3
"""Zero-shot accuracy of a backbone on pathknow's eval frames (the held-out test set). Venv python.

    python zeroshot_eval.py --model ViT-B-16-SigLIP2-384 [--pretrained webli]

A frame is right when the prediction is its primary label or one of its accepted alternatives.
Also prints the warm per-frame latency (one frame at a time, decode and preprocessing included).
"""
import argparse
import os
import sys
import time

EVAL_DIR = os.environ.get("PATHCLASS_EVAL_DIR", os.path.expanduser("~/hakux-work/wt/pathknow/scratch"))


def eval_rows():
    rows = []
    with open(os.path.join(EVAL_DIR, "eval_set.tsv")) as f:
        hdr = f.readline().rstrip("\n").split("\t")
        for line in f:
            r = dict(zip(hdr, line.rstrip("\n").split("\t")))
            r["path"] = os.path.join(EVAL_DIR, "eval_frames", r["frame"])
            r["ok"] = {r["primary"]} | {x for x in r.get("accepted", "").split(",") if x}
            rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--pretrained", default="webli")
    a = ap.parse_args()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from embed import load
    rows = eval_rows()
    c, _ = load(a.model, a.pretrained)
    pred = []
    for r in rows:
        p = c.classify_image(r["path"])
        pred.append(max(p, key=p.get))
    right = sum(p in r["ok"] for p, r in zip(pred, rows))
    gp_fp = sum(p == "gameplay" and "gameplay" not in r["ok"] for p, r in zip(pred, rows))
    gp_fn = sum(p != "gameplay" and r["primary"] == "gameplay" for p, r in zip(pred, rows))
    t0 = time.time()
    for r in rows[:30]:
        c.classify_image(r["path"])
    ms = (time.time() - t0) / 30 * 1000
    print(f"{a.model}: zero-shot {right}/{len(rows)} = {100 * right / len(rows):.0f}%  "
          f"gameplay FP {gp_fp} FN {gp_fn}  warm {ms:.0f} ms/frame")


if __name__ == "__main__":
    main()
