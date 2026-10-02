#!/usr/bin/env python3
"""Build pathclass's frame pool from on-disk run frames (no device).

    python3 pool.py --out <dir>          writes <dir>/pool.tsv

Sources: $WORK/dispatch/results/*/{route-frames,frames}/ and $WORK/wt/*/scratch/**/{route-frames,frames}/.
A frame's title comes from the request.json beside its frames dir, or from the run id in its path, or from
pathfind's runs/<slug>/ layout. Frames are near-deduplicated per title (16x12 grey thumbnail, mean abs diff),
so the pool is the set of DISTINCT screens per title, not 300 copies of one menu.

Test hygiene: pathknow's eval frames (eval_set.tsv) are the held-out test set. Their source frames and every
frame of the same run are excluded, and half of the eval titles (a fixed hash split, `heldout_titles()`) are
excluded entirely, so the test has an unseen-title half.

pool.tsv columns: path, title (normalised key), title_raw, run, step (the weak label from the file name),
order (index in its run), heldout (0/1: a held-out title; such rows are kept but never trained on).
"""
import argparse
import glob
import hashlib
import json
import os
import re
import sys

WORK = os.path.expanduser("~/hakux-work")
RESULTS = os.path.join(WORK, "dispatch", "results")
EVAL_TSV = os.environ.get("PATHCLASS_EVAL_TSV", os.path.join(WORK, "wt", "pathknow", "scratch", "eval_set.tsv"))
RUN_ID = re.compile(r"(?:\d+-)*\d{10}-[A-Za-z0-9_.]+-\d+")


def title_key(raw):
    """'4541000D-007_Agent_Under_Fire.xiso.iso' and '007 Agent Under Fire (USA)' -> '007agentunderfire'."""
    t = os.path.basename(raw or "")
    t = re.sub(r"(\.xiso)?\.iso$", "", t, flags=re.I)
    t = re.sub(r"^[0-9A-Fa-f]{8}-", "", t)
    t = re.sub(r"\([^)]*\)", "", t)
    return re.sub(r"[^a-z0-9]", "", t.lower())


def heldout_titles(keys):
    """Half of the eval titles, by a fixed hash: these never train."""
    return {k for k in keys if int(hashlib.sha1(k.encode()).hexdigest(), 16) % 2 == 0}


def load_eval():
    rows = []
    if not os.path.exists(EVAL_TSV):
        return rows
    with open(EVAL_TSV) as f:
        hdr = f.readline().rstrip("\n").split("\t")
        for line in f:
            r = dict(zip(hdr, line.rstrip("\n").split("\t")))
            r["key"] = title_key(r.get("title", ""))
            rows.append(r)
    return rows


def step_of(name):
    m = re.match(r"\d{6}-(?:\d{3}-)?(.*)\.(png|jpe?g)$", name, re.I)
    if not m:
        return ""
    return re.sub(r"\d+$", "", m.group(1))


def run_title(run, cache={}):
    if run not in cache:
        t = ""
        p = os.path.join(RESULTS, run, "request.json")
        if os.path.exists(p):
            try:
                t = json.load(open(p)).get("title", "") or ""
            except Exception:
                pass
        cache[run] = t
    return cache[run]


def frame_dirs():
    for d in glob.glob(os.path.join(RESULTS, "*")):
        for sub in ("route-frames", "frames"):
            p = os.path.join(d, sub)
            if os.path.isdir(p):
                yield p, os.path.basename(d)
    for root, dirs, _ in os.walk(os.path.join(WORK, "wt")):
        rel = os.path.relpath(root, os.path.join(WORK, "wt")).split(os.sep)
        if len(rel) >= 2 and rel[1] != "scratch":
            dirs[:] = []
            continue
        if "pathclass" in rel[:1]:
            dirs[:] = []
            continue
        base = os.path.basename(root)
        if base in ("route-frames", "frames"):
            m = RUN_ID.search(root)
            yield root, m.group(0) if m else root
            dirs[:] = []


def dir_title(path, run):
    p = os.path.join(os.path.dirname(path), "request.json")
    if os.path.exists(p):
        try:
            t = json.load(open(p)).get("title", "")
            if t:
                return t
        except Exception:
            pass
    t = run_title(run) if not run.startswith("/") else ""
    if t:
        return t
    m = re.search(r"/pathfind/scratch/runs/([^/]+)/", path)
    return m.group(1) if m else ""


def thumb(path):
    from PIL import Image
    try:
        im = Image.open(path).convert("L").resize((16, 12))
    except Exception:
        return None
    return list(im.getdata())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-title", type=int, default=80)
    ap.add_argument("--thresh", type=float, default=6.0, help="mean abs grey diff below which two frames are one")
    a = ap.parse_args()
    ev = load_eval()
    eval_runs = set()
    eval_src = set()
    for r in ev:
        src = r.get("source", "")
        eval_src.add(src)
        m = RUN_ID.search(src)
        if m:
            eval_runs.add(m.group(0))
    held = heldout_titles({r["key"] for r in ev})
    by_title = {}
    seen_runs = set()
    for d, run in frame_dirs():
        if run in eval_runs:
            continue
        t = dir_title(d, run)
        k = title_key(t)
        if not k:
            continue
        names = sorted(f for f in os.listdir(d) if f.lower().endswith((".png", ".jpg", ".jpeg")))
        for i, n in enumerate(names):
            by_title.setdefault(k, []).append((os.path.join(d, n), t, run, step_of(n), i))
        seen_runs.add(run)
    os.makedirs(a.out, exist_ok=True)
    out = open(os.path.join(a.out, "pool.tsv"), "w")
    out.write("path\ttitle\ttitle_raw\trun\tstep\torder\theldout\n")
    total = 0
    for k in sorted(by_title):
        items = by_title[k]
        # spread the candidates across runs and time before dedup so the cap does not keep one run's boot
        items.sort(key=lambda x: (hashlib.md5(x[0].encode()).hexdigest()))
        kept = []
        for it in items:
            if len(kept) >= a.per_title:
                break
            th = thumb(it[0])
            if th is None:
                continue
            if any(sum(abs(p - q) for p, q in zip(th, o)) / len(th) < a.thresh for _, o in kept):
                continue
            kept.append((it, th))
        for it, _ in kept:
            out.write("\t".join([it[0], k, os.path.basename(it[1]), it[2], it[3], str(it[4]), "1" if k in held else "0"]) + "\n")
        total += len(kept)
        print(f"{k}\t{len(items)}\t{len(kept)}{'  HELDOUT' if k in held else ''}", file=sys.stderr)
    print(f"pool: {total} frames, {len(by_title)} titles, {len(held)} held-out titles, eval runs excluded {len(eval_runs)}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
