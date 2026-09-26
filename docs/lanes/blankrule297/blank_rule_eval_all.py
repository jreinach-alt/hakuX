#!/usr/bin/env python3
"""Old `blank` rule vs score_sweep.is_blank() on every ok/blank row on disk.

cloud-297's blank_rule_eval.py looks only at captures the old rule tagged
`blank`, so it can show a release but not the reverse. This walks every
`ok` and `blank` row in $DISPATCH_DIR/results/*/scores*.tsv whose capture is
still on disk, scores it with the OLD rule (as score_sweep.py had it at
036e6c191f) and the NEW one, and reports every transition. Both are
evaluated on packed RGB keys for speed; the shipped score_sweep.is_blank is
then re-run on every row that changed and on a random sample of flat rows,
and any disagreement is printed.

`label-differs` and `white-content` override `blank` in score_sweep.py, so
those rows cannot change and are skipped.

Usage: blank_rule_eval_all.py [--jobs N]
"""
import argparse
import csv
import glob
import hashlib
import os
import random
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


def pack(a):
    """RGB packed into one int32 per pixel. Sorts in the same (r, g, b) order
    as np.unique(axis=0), so argmax picks the same dominant colour."""
    return ((a[..., 0].astype(np.int32) << 16) | (a[..., 1].astype(np.int32) << 8)
            | a[..., 2].astype(np.int32))


def ours_flat(o):
    """The flatness clause both rules share."""
    _, counts = np.unique(pack(o).ravel(), return_counts=True)
    return counts.max() / counts.sum() > 0.90 and len(counts) <= 4


def fast_rules(o, g):
    """(old, new, lost) for a flat `o`, on packed keys. np.unique(axis=0) costs
    ~3 s a call on this host, and ~6% of 96k rows are flat, so the direct
    calls would take hours; `main` checks these against the shipped
    score_sweep.is_blank on every changed row and a sample of flat ones."""
    ok, gk = pack(o), pack(g)
    ocols, oc = np.unique(ok.ravel(), return_counts=True)
    gcols, gc = np.unique(gk.ravel(), return_counts=True)
    ink = gk != gcols[gc.argmax()]
    ink[:LABEL_ROWS] = False
    lost = int((ink & (ok == ocols[oc.argmax()])).sum())
    many = len(gcols) > 4
    return (many, many and lost >= score_sweep.BLANK_MIN_LOST * ok.size, lost)


_memo = {}


def shipped(job):
    """score_sweep.is_blank itself, for the cross-check."""
    cap, gp = job
    o = np.asarray(Image.open(cap).convert("RGBA"), dtype=np.int16)
    g = np.asarray(Image.open(gp).convert("RGBA"), dtype=np.int16)
    return score_sweep.is_blank(o, g, LABEL_ROWS)


def judge(job):
    tsv, suite, test, status, differing, cap = job
    gp = os.path.join(GOLDENS, suite, test + ".png")
    try:
        o = np.asarray(Image.open(cap).convert("RGBA"), dtype=np.int16)
        with Image.open(gp) as gi:
            gsize = gi.size
    except Exception:
        return None
    if (gsize[1], gsize[0]) != o.shape[:2]:
        return None
    # Both rules require ours flat; when it is not, both say ok and the
    # golden need not be decoded.
    npx = o.shape[0] * o.shape[1]
    if not ours_flat(o):
        return (tsv, suite, test, status, differing, False, False, 0, npx,
                False, cap, gp)
    key = (gp, hashlib.sha1(o.tobytes()).hexdigest())
    if key not in _memo:
        try:
            g = np.asarray(Image.open(gp).convert("RGBA"), dtype=np.int16)
        except Exception:
            return None
        _memo[key] = fast_rules(o, g)
    old, new, lost = _memo[key]
    return (tsv, suite, test, status, differing, old, new, lost, npx,
            True, cap, gp)


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
    ap.add_argument("--check", type=int, default=100,
                    help="flat rows to re-run through the shipped is_blank")
    a = ap.parse_args()
    work = list(jobs())
    print(f"{len(work)} ok/blank rows with a capture on disk, "
          f"{len({w[0] for w in work})} TSVs")
    trans = Counter()
    recorded_vs_old = Counter()
    changed = {}
    flat_rows, check = [], {}
    with ProcessPoolExecutor(a.jobs) as ex:
        for res in ex.map(judge, work, chunksize=64):
            if res is None:
                trans["unreadable/size"] += 1
                continue
            (tsv, suite, test, status, differing, old, new, lost, npx,
             flat, cap, gp) = res
            o, n = ("blank" if old else "ok"), ("blank" if new else "ok")
            trans[(o, n)] += 1
            recorded_vs_old[(status, o)] += 1
            if flat:
                flat_rows.append(((cap, gp), new))
            if old != new:
                k = (suite, test, o, n)
                c = changed.setdefault(k, [0, set(), lost, npx])
                c[0] += 1
                c[1].add(differing)
                check.setdefault(k, ((cap, gp), new))
        # Cross-check the packed rules against the shipped is_blank: one row
        # per changed capture, and a random sample of the other flat rows.
        random.seed(297)
        sample = list(check.values()) + random.sample(
            flat_rows, min(a.check, len(flat_rows)))
        got = list(ex.map(shipped, [s[0] for s in sample]))
    bad = [s[0][0] for s, g in zip(sample, got) if g != s[1]]
    print(f"{len(flat_rows)} rows had ours flat; shipped is_blank re-run on "
          f"{len(sample)} of them ({len(check)} changed + a sample): "
          f"{len(bad)} disagree with the packed rule")
    for b in bad:
        print(f"  DISAGREE {b}")
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
