#!/usr/bin/env python3
"""Embed frames with an open_clip backbone; cache by path. Run with the pathclass venv's python.

    python embed.py --model ViT-B-16-SigLIP2-384 --pretrained webli --list <paths.txt> --cache <file.npz>

Uses pathclass.Classifier's own preprocessing (GPU resize), so a head trained on these features sees the
same numbers at serve time. The cache holds `paths` and `emb` (L2-normalised float16); paths already
cached are skipped, so a growing pool only pays for its new frames.
"""
import argparse
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
import pathclass  # noqa: E402


def load(model, pretrained):
    """(classifier, tokenizer) for a backbone, no head, no OCR."""
    import open_clip
    pathclass.BACKBONE = (model, pretrained)
    c = pathclass.Classifier(head=None, ocr=False)
    return c, open_clip.get_tokenizer(model)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--pretrained", default="webli")
    ap.add_argument("--list", required=True)
    ap.add_argument("--cache", required=True)
    a = ap.parse_args()
    paths = [l.strip() for l in open(a.list) if l.strip()]
    have_p, have_e = [], None
    if os.path.exists(a.cache):
        z = np.load(a.cache, allow_pickle=True)
        have_p, have_e = list(z["paths"]), z["emb"]
    hs = set(have_p)
    todo = [p for p in dict.fromkeys(paths) if p not in hs]
    print(f"{len(todo)} to embed, {len(have_p)} cached", file=sys.stderr)
    if not todo:
        return
    c, _ = load(a.model, a.pretrained)
    t0 = time.time()
    e = c.embed_batch(todo).astype(np.float16)
    print(f"embedded {len(todo)} in {time.time() - t0:.1f}s", file=sys.stderr)
    allp = have_p + todo
    alle = e if have_e is None else np.concatenate([have_e, e])
    os.makedirs(os.path.dirname(os.path.abspath(a.cache)), exist_ok=True)
    np.savez(a.cache, paths=np.array(allp, dtype=object), emb=alle)


if __name__ == "__main__":
    main()
