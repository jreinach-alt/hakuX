#!/usr/bin/env python3
"""Pick unlabelled pool frames for the next labelling round, rare predicted states first. Venv python.

    python pick.py --pool <dir> --n 300 --out <dir>/next.txt

Embeds every not-held-out, unlabelled pool frame (cached), scores it with the current head, and takes
frames round-robin over predicted states, rarest state first and least confident first within a state, so a
round spends its calls on pause/results/game_over/prompts rather than on the 156th gameplay frame.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from train import embeddings  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True)
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", required=True)
    ap.add_argument("--head", default=os.path.join(HERE, "head.npz"))
    a = ap.parse_args()
    done = set()
    for fn in ("labels.jsonl", "extra_labels.jsonl", "labels_sonnet.jsonl"):
        p = os.path.join(a.pool, fn)
        if os.path.exists(p):
            done |= {json.loads(l)["path"] for l in open(p) if l.strip()}
    rows = []
    with open(os.path.join(a.pool, "pool.tsv")) as f:
        hdr = f.readline().rstrip("\n").split("\t")
        for line in f:
            r = dict(zip(hdr, line.rstrip("\n").split("\t")))
            if r["heldout"] == "0" and r["path"] not in done and os.path.exists(r["path"]):
                rows.append(r)
    h = np.load(a.head, allow_pickle=True)
    E, G = embeddings(str(h["model"]), str(h["pretrained"]), [r["path"] for r in rows])
    import pathclass
    feats = str(h["feats"]) if "feats" in h.files else "pooled"
    F = np.stack([pathclass.head_input(feats.replace("+text", ""), E[i], G[i]) for i in range(len(rows))])
    if "+text" in feats:
        sys.exit("pick.py: a +text head needs OCR on every candidate; pick with an image-only head")
    z = ((F - h["mu"]) / h["sd"]) @ h["W"].T + h["b"]
    p = np.exp(z - z.max(1, keepdims=True))
    p /= p.sum(1, keepdims=True)
    states = [str(s) for s in h["states"]]
    pred = p.argmax(1)
    by = {}
    for i in np.argsort(p.max(1)):
        by.setdefault(states[pred[i]], []).append(i)
    order = sorted(by, key=lambda s: len(by[s]))
    print({s: len(by[s]) for s in order}, file=sys.stderr)
    pick, k = [], 0
    while len(pick) < a.n and any(k < len(by[s]) for s in order):
        for s in order:
            if k < len(by[s]) and len(pick) < a.n:
                pick.append(rows[by[s][k]]["path"])
        k += 1
    open(a.out, "w").write("\n".join(pick) + "\n")
    print(f"picked {len(pick)}", file=sys.stderr)


if __name__ == "__main__":
    main()
