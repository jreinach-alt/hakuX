#!/usr/bin/env python3
"""Train pathclass's linear head on cached embeddings and score it on pathknow's eval frames. Venv python.

    python train.py --model ViT-B-16-SigLIP2-384 --pool <dir> [--save head.npz]

Training rows: <pool>/labels.jsonl (language-model labels on NOT held-out titles; pool.py) plus any
<pool>/extra_labels.jsonl (same shape: distilled pathfind answers). The eval frames are never trained on.
Reports: eval accuracy (primary or accepted label), split into titles seen in training and held-out titles,
the gameplay confusion both ways, the known false passes, and a confusion matrix.
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", ".."))
from pool import title_key, heldout_titles  # noqa: E402
from prompts import STATES  # noqa: E402
from zeroshot_eval import eval_rows  # noqa: E402

MODELS = os.path.expanduser("~/hakux-work/models/pathclass")


def embeddings(model, pretrained, paths):
    tag = f"{model}-{pretrained}".replace("/", "_")
    cache = os.path.join(MODELS, "emb", tag + ".npz")
    lst = os.path.join(MODELS, "emb", tag + ".list")
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(lst, "w") as f:
        f.write("\n".join(paths) + "\n")
    subprocess.run([sys.executable, os.path.join(HERE, "embed.py"), "--model", model, "--pretrained", pretrained,
                    "--list", lst, "--cache", cache], check=True)
    z = np.load(cache, allow_pickle=True)
    idx = {p: i for i, p in enumerate(z["paths"])}
    return np.stack([z["emb"][idx[p]] for p in paths]).astype(np.float32)


class Softmax:
    """Class-balanced multinomial logistic regression (L2 = 1/C), full-batch L-BFGS on the GPU.
    sklearn's does the same fit but took minutes on this host's loaded CPU."""

    def __init__(self, C):
        self.C = C

    def fit(self, X, y):
        import torch
        self.classes_ = np.array(sorted(set(y)))
        yi = torch.tensor([list(self.classes_).index(v) for v in y], device="cuda")
        Xt = torch.tensor(X, device="cuda")
        cnt = torch.bincount(yi, minlength=len(self.classes_)).float()
        w = (len(y) / (len(self.classes_) * cnt))[yi]
        W = torch.zeros(len(self.classes_), X.shape[1], device="cuda", requires_grad=True)
        b = torch.zeros(len(self.classes_), device="cuda", requires_grad=True)
        opt = torch.optim.LBFGS([W, b], max_iter=500, line_search_fn="strong_wolfe")

        def closure():
            opt.zero_grad()
            loss = (torch.nn.functional.cross_entropy(Xt @ W.T + b, yi, reduction="none") * w).sum()
            loss = loss + 0.5 / self.C * (W ** 2).sum()
            loss.backward()
            return loss

        opt.step(closure)
        self.coef_, self.intercept_ = W.detach().cpu().numpy(), b.detach().cpu().numpy()
        return self

    def predict_proba(self, X):
        z = X @ self.coef_.T + self.intercept_
        p = np.exp(z - z.max(1, keepdims=True))
        return p / p.sum(1, keepdims=True)

    def predict(self, X):
        return self.classes_[self.predict_proba(X).argmax(1)]


def fit(X, y, C):
    mu, sd = X.mean(0), X.std(0) + 1e-6
    return Softmax(C).fit((X - mu) / sd, y), mu, sd


def predict(clf, mu, sd, X):
    return clf.predict_proba((X - mu) / sd)



def text_state_for(pathclass, state, items):
    if state not in pathclass.OCR_STATES:
        return None
    return pathclass.text_state(state, items)


def report(name, ev, pred, conf, seen, full=True):
    if True:

        def score(mask):
            n = sum(mask)
            k = sum(m and p in r["ok"] for m, p, r in zip(mask, pred, ev))
            return k, n

        k, n = score([True] * len(ev))
        ks, ns = score(seen)
        kh, nh = score([not s for s in seen])
        gfp = [(r["frame"], r["primary"], r.get("note", "")) for p, r in zip(pred, ev)
               if p == "gameplay" and "gameplay" not in r["ok"]]
        gfn = [(r["frame"], p, r.get("note", "")) for p, r in zip(pred, ev) if p != "gameplay" and r["primary"] == "gameplay"]
        nong = sum("gameplay" not in r["ok"] for r in ev)
        print(f"EVAL {name}: {k}/{n} = {100 * k / n:.1f}%  (seen titles {ks}/{ns}, held-out titles {kh}/{nh})")
        print(f"  said gameplay on non-gameplay: {len(gfp)}/{nong} = {100 * len(gfp) / max(nong, 1):.1f}%  {gfp}")
        print(f"  said not-gameplay on gameplay: {len(gfn)}  {gfn}")
        fps = [(r["frame"], p, r["note"]) for p, r in zip(pred, ev) if r.get("note", "").startswith("FP:")]
        print("  known false passes: " + "; ".join(f"{f} {p} ({n_})" for f, p, n_ in fps))
        for t in (0.5, 0.6, 0.7, 0.8):
            m = conf >= t
            kk = sum(mm and p in r["ok"] for mm, p, r in zip(m, pred, ev))
            print(f"  confidence >= {t}: answers {m.sum()}/{len(ev)}, right {kk}/{m.sum()} = {100 * kk / max(m.sum(), 1):.0f}%")
        # confusion matrix: rows truth (primary), cols prediction; a prediction in `accepted` counts on the diagonal
        st = [s for s in STATES if any(r["primary"] == s for r in ev) or s in pred]
        M = np.zeros((len(st), len(st)), int)
        for p, r in zip(pred, ev):
            M[st.index(r["primary"]), st.index(r["primary"] if p in r["ok"] else p)] += 1
        ab = {s: s[:6] for s in st}
        print("  confusion (rows truth, cols predicted; accepted alternatives count as right):")
        print("  " + " " * 18 + " ".join(f"{ab[s]:>6}" for s in st))
        for i, s in enumerate(st):
            print(f"  {s:>18} " + " ".join(f"{v:>6}" if v else "     ." for v in M[i]))
        misses = [(r["frame"], r["primary"], p, round(float(c), 2), r.get("note", "")) for p, c, r in zip(pred, conf, ev)
                  if p not in r["ok"]]
        print("  misses: " + "\n    ".join(str(m) for m in misses))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="ViT-B-16-SigLIP2-384")
    ap.add_argument("--pretrained", default="webli")
    ap.add_argument("--pool", required=True)
    ap.add_argument("--C", type=float, default=0)
    ap.add_argument("--save")
    ap.add_argument("--ocr", help="ocr_eval.py's cache: also score the OCR text rules")
    a = ap.parse_args()
    lab = []
    for fn in ("labels.jsonl", "extra_labels.jsonl"):
        p = os.path.join(a.pool, fn)
        if os.path.exists(p):
            lab += [json.loads(l) for l in open(p) if l.strip()]
    ev = eval_rows()
    held = heldout_titles({title_key(r["title"]) for r in ev})
    lab = [r for r in lab if r["title"] not in held and os.path.exists(r["path"])]
    paths = [r["path"] for r in lab] + [r["path"] for r in ev]
    E = embeddings(a.model, a.pretrained, paths)
    X, Xe = E[:len(lab)], E[len(lab):]
    y = np.array([r["state"] for r in lab])
    groups = np.array([r["title"] for r in lab])
    print(f"train {len(lab)} frames, {len(set(groups))} titles; labels: "
          + ", ".join(f"{s}={int((y == s).sum())}" for s in STATES if (y == s).any()))
    # C by grouped CV over titles (leave titles out, like the real use)
    from sklearn.model_selection import GroupKFold
    Cs = [a.C] if a.C else [0.01, 0.03, 0.1, 0.3, 1.0]
    best = None
    for C in Cs:
        acc = []
        for tr, te in GroupKFold(5).split(X, y, groups):
            clf, mu, sd = fit(X[tr], y[tr], C)
            acc.append((clf.predict((X[te] - mu) / sd) == y[te]).mean())
        print(f"  C={C}: grouped-CV agreement with the labeller {np.mean(acc):.3f}")
        if best is None or np.mean(acc) > best[1]:
            best = (C, np.mean(acc))
    clf, mu, sd = fit(X, y, best[0])
    P = predict(clf, mu, sd, Xe)
    cls = list(clf.classes_)
    pred = [str(cls[i]) for i in P.argmax(1)]
    conf = P.max(1)
    seen = [title_key(r["title"]) not in held for r in ev]
    report(f"{a.model} image only", ev, pred, conf, seen, full=not a.ocr)
    if a.ocr:
        import pathclass
        ocr = {json.loads(l)["frame"]: json.loads(l)["items"] for l in open(a.ocr) if l.strip()}
        pred2, conf2 = [], conf.copy()
        for i, (p, r) in enumerate(zip(pred, ev)):
            ts = text_state_for(pathclass, p, ocr.get(r["frame"], []))
            pred2.append(ts or p)
            if ts and ts != p:
                conf2[i] = max(conf2[i], 0.8)
        report(f"{a.model} image + OCR text rules", ev, pred2, conf2, seen, full=True)
        ms = [json.loads(l)["ms"] for l in open(a.ocr) if l.strip()]
        print(f"  OCR ms: median {np.median(ms):.0f}, p90 {np.percentile(ms, 90):.0f}, max {max(ms)}")
    if a.save:
        np.savez(a.save, W=clf.coef_.astype(np.float32), b=clf.intercept_.astype(np.float32),
                 mu=mu.astype(np.float32), sd=sd.astype(np.float32), states=np.array(cls),
                 model=np.array(a.model), pretrained=np.array(a.pretrained), C=np.array(best[0]),
                 n_train=np.array(len(lab)))
        print(f"saved {a.save} ({os.path.getsize(a.save)} bytes)")


if __name__ == "__main__":
    main()
