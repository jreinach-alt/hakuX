#!/usr/bin/env python3
"""Run the OCR menu reader over pathknow's eval frames; cache its text per frame and time it. Venv python.

    python ocr_eval.py --out <dir>/ocr_eval.jsonl

One line per frame: {frame, primary, ms, items: [{text, box, conf, intent, highlighted}]}.
train.py --ocr <file> reads this cache to score the OCR keyword rules without re-running OCR.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from zeroshot_eval import eval_rows  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--list", help="frame paths to read instead of the eval set (one per line)")
    a = ap.parse_args()
    import pathclass
    c = pathclass.Classifier(head=None, ocr=True)
    if a.list:
        rows = [{"frame": l.strip(), "path": l.strip(), "primary": ""} for l in open(a.list) if l.strip()]
    else:
        rows = eval_rows()
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(l)["frame"] for l in open(a.out) if l.strip()}
    c.read_menu(rows[0]["path"])  # warm
    with open(a.out, "a") as f:
        for r in rows:
            if r["frame"] in done:
                continue
            t0 = time.time()
            try:
                items = c.read_menu(r["path"])
            except Exception as e:
                items = []
                print(f"{r['frame']}: {e}", file=sys.stderr)
            f.write(json.dumps({"frame": r["frame"], "primary": r["primary"], "ms": round((time.time() - t0) * 1000),
                                "items": items}) + "\n")
            f.flush()


if __name__ == "__main__":
    main()
