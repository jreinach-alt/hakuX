#!/usr/bin/env python3
"""Old `blank` rule vs score_sweep.is_blank() on every ok/blank row on disk.

cloud-297's blank_rule_eval.py looks only at captures the old rule tagged
`blank`, so it can show a release but not the reverse. This walks every
`ok` and `blank` row in $DISPATCH_DIR/results/*/scores*.tsv whose capture is
still on disk, scores it with the OLD rule (inline, as score_sweep.py had it
at 036e6c191f) and with the NEW one (imported from the tree's score_sweep.py,
so this measures the code that ships), and reports every transition.

`label-differs` and `white-content` override `blank` in score_sweep.py, so
those rows cannot change and are skipped.

Usage: blank_rule_eval_all.py [--jobs N]
"""
import argparse
import csv
import glob
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "testing"))
import score_sweep  # noqa: E402

GOLDENS = os.environ.get("GOLDENS", "/home/justin/goldens/results")
RESULTS = os.path.join(os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch"),
                       "results")
LABEL_ROWS = 64


def old_rule(o, g):
    flat = o[..., :3].reshape(-1, 3)
    _, counts = np.unique(flat, axis=0, return_counts=True)
    gold_colours = len(np.unique(g[..., :3].reshape(-1, 3), axis=0))
    return bool(counts.max() / flat.shape[0] > 0.90 and len(counts) <= 4
                and gold_colours > 4)


def lost_px(o, g):
    gcols, gc = np.unique(g[..., :3].reshape(-1, 3), axis=0, return_counts=True)
    ocols, oc = np.unique(o[..., :3].reshape(-1, 3), axis=0, return_counts=True)
    ink = (g[..., :3] != gcols[gc.argmax()]).any(axis=2)
    ink[:LABEL_ROWS] = False
    return int((ink & (o[..., :3] == ocols[oc.argmax()]).all(axis=2)).sum())


def judge(job):
    tsv, suite, test, status, differing, cap = job
    gp = os.path.join(GOLDENS, suite, test + ".png")
    try:
        g = np.asarray(Image.open(gp).convert("RGBA"), dtype=np.int16)
        o = np.asarray(Image.open(cap).convert("RGBA"), dtype=np.int16)
    except Exception:
        return None
    if g.shape != o.shape:
        return None
    old = old_rule(o, g)
    new = score_sweep.is_blank(o, g, LABEL_ROWS)
    lost = lost_px(o, g) if (old or new) else 0
    return (tsv, suite, test, status, differing, old, new, lost,
            g.shape[0] * g.shape[1])


def jobs():
    for tsv in sorted(glob.glob(os.path.join(RESULTS, "*", "scores*.tsv"))):
        cap_dir = os.path.join(os.path.dirname(tsv),
                               "captures" + os.path.basename(tsv)[6:-4])
        if not os.path.isdir(cap_dir):
            continue
        try:
            rows = list(csv.DictReader(open(tsv), delimiter="\t"))
        except Exception:
            continue
        for r in rows:
            if r.get("status") not in ("ok", "blank"):
                continue
            cap = os.path.join(cap_dir, f"{r['suite']}::{r['test']}.png")
            if os.path.exists(cap):
                yield (tsv, r["suite"], r["test"], r["status"],
                       r.get("differing", ""), cap)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    a = ap.parse_args()
    work = list(jobs())
    print(f"{len(work)} ok/blank rows with a capture on disk, "
          f"{len({w[0] for w in work})} TSVs")
    trans = Counter()
    recorded_vs_old = Counter()
    changed = {}
    with ProcessPoolExecutor(a.jobs) as ex:
        for res in ex.map(judge, work, chunksize=64):
            if res is None:
                trans["unreadable/size"] += 1
                continue
            tsv, suite, test, status, differing, old, new, lost, npx = res
            o, n = ("blank" if old else "ok"), ("blank" if new else "ok")
            trans[(o, n)] += 1
            recorded_vs_old[(status, o)] += 1
            if old != new:
                k = (suite, test, o, n)
                c = changed.setdefault(k, [0, set(), lost, npx])
                c[0] += 1
                c[1].add(differing)
    print("\nrecorded status vs old rule re-run (a mismatch = the TSV was "
          "written by a different scorer):")
    for k, v in sorted(recorded_vs_old.items(), key=str):
        print(f"  recorded {k[0]:5s}  old-rule {k[1]:5s}  {v:7d}")
    print("\nold rule -> new rule:")
    for k, v in sorted(trans.items(), key=str):
        print(f"  {k}  {v:7d}")
    print(f"\n{'capture':62s} {'old':>5} -> {'new':5s} {'rows':>5} "
          f"{'lost':>7} {'lost%':>6}  differing")
    for (suite, test, o, n), (cnt, diffs, lost, npx) in sorted(changed.items()):
        print(f"{suite + '/' + test:62s} {o:>5} -> {n:5s} {cnt:5d} {lost:7d} "
              f"{100 * lost / npx:5.2f}%  {','.join(sorted(diffs, key=lambda d: int(d or 0)))}")
    ok_to_blank = sum(v for k, v in trans.items() if k == ("ok", "blank"))
    print(f"\nok -> blank transitions: {ok_to_blank}")


if __name__ == "__main__":
    main()
