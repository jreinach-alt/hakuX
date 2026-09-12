#!/usr/bin/env python3
"""Decompose issue #10's bump captures into failure classes, and measure how
much each golden can actually discriminate.

Two things this answers that the scoreboard cannot:

  * ``structural`` px (differing minus the off-by-one bucket) split by where
    they sit, so the 818,008 px of #10 can be attributed to a texture-source
    path rather than to "bump arithmetic" as a whole;
  * how many distinct colours the GOLDEN holds *inside the structural mask*.
    The corpus-wide discrimination sheet counts colours over the whole
    differing mask, which for these suites is dominated by the one-step
    bucket -- so it reports 85-117 colours for captures whose structural
    pixels hold two. A golden holding two colours where we are structurally
    wrong cannot fit a bump matrix; it can only say which side of a
    boundary a pixel fell. See docs/investigations/bump-rule-2026-09-12.md.

Usage: bump_decompose.py [--captures DIR ...] [--goldens DIR] [--tsv OUT]
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

DEF_CAPS = [
    "/home/justin/hakux-work/dispatch/results/z-sweep-010-Bump_map/captures1",
    "/home/justin/hakux-work/dispatch/results/z-sweep-009-Bump_env_lum/captures1",
]
DEF_GOLD = "/home/justin/goldens/results"


def load(p):
    return np.asarray(Image.open(p).convert("RGBA"), dtype=np.int16)


def rowspan(mask):
    r = np.flatnonzero(mask.any(axis=1))
    c = np.flatnonzero(mask.any(axis=0))
    if not len(r):
        return (0, 0, 0, 0)
    return (int(r[0]), int(r[-1]), int(c[0]), int(c[-1]))


def analyse(gp, op):
    g, o = load(gp), load(op)
    if g.shape != o.shape:
        return None
    d = np.abs(g - o)
    rgb = d[..., :3].max(axis=2)
    alpha = d[..., 3]
    diff = (rgb > 0) | (alpha > 0)
    ob1 = (rgb <= 1) & (alpha <= 1) & diff
    struct = diff & ~ob1

    def ncol(mask):
        if not mask.any():
            return 0
        return len(np.unique(g[..., :3][mask], axis=0))

    def pairs(mask, k=6):
        if not mask.any():
            return []
        both = np.concatenate([o[mask], g[mask]], axis=1)
        u, c = np.unique(both, axis=0, return_counts=True)
        idx = np.argsort(-c)[:k]
        return [(tuple(int(x) for x in u[i][:4]),
                 tuple(int(x) for x in u[i][4:]), int(c[i])) for i in idx]

    alpha_only = int(((alpha > 0) & (rgb == 0)).sum())
    a_diff = int((alpha > 0).sum())
    apairs = []
    if a_diff:
        m = alpha > 0
        u, c = np.unique(np.stack([o[..., 3][m], g[..., 3][m]], axis=1),
                         axis=0, return_counts=True)
        idx = np.argsort(-c)[:4]
        apairs = [((int(u[i][0]), int(u[i][1])), int(c[i])) for i in idx]

    return dict(
        differing=int(diff.sum()), off_by_one=int(ob1.sum()),
        structural=int(struct.sum()),
        max_rgb=int(rgb.max()), max_a=int(alpha.max()),
        gold_colours_diff=ncol(diff), gold_colours_struct=ncol(struct),
        struct_pairs=pairs(struct), struct_span=rowspan(struct),
        diff_span=rowspan(diff),
        alpha_diff=a_diff, alpha_only=alpha_only, alpha_pairs=apairs,
        struct_rows=int(struct.any(axis=1).sum()),
        struct_cols=int(struct.any(axis=0).sum()),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures", nargs="*", default=DEF_CAPS)
    ap.add_argument("--goldens", default=DEF_GOLD)
    ap.add_argument("--tsv")
    ap.add_argument("--pairs", action="store_true",
                    help="print the top (ours, gold) pairs per capture")
    a = ap.parse_args()

    out = []
    for cd in a.captures:
        for name in sorted(os.listdir(cd)):
            if not name.endswith(".png") or "::" not in name:
                continue
            suite, test = name[:-4].split("::", 1)
            gp = os.path.join(a.goldens, suite, test + ".png")
            if not os.path.exists(gp):
                print(f"no-golden\t{suite}\t{test}", file=sys.stderr)
                continue
            r = analyse(gp, os.path.join(cd, name))
            if r is None:
                print(f"size\t{suite}\t{test}", file=sys.stderr)
                continue
            r["suite"], r["test"] = suite, test
            out.append(r)

    cols = ["suite", "test", "differing", "off_by_one", "structural",
            "max_rgb", "max_a", "gold_colours_diff", "gold_colours_struct",
            "struct_rows", "struct_cols", "alpha_diff", "alpha_only"]
    lines = ["\t".join(cols)]
    for r in sorted(out, key=lambda x: -x["structural"]):
        lines.append("\t".join(str(r[c]) for c in cols))
    text = "\n".join(lines) + "\n"
    if a.tsv:
        with open(a.tsv, "w") as f:
            f.write(text)
    print(text, end="")

    tot = sum(r["structural"] for r in out)
    print(f"\n{len(out)} captures, structural {tot}, "
          f"differing {sum(r['differing'] for r in out)}, "
          f"off_by_one {sum(r['off_by_one'] for r in out)}", file=sys.stderr)

    if a.pairs:
        for r in sorted(out, key=lambda x: -x["structural"]):
            print(f"\n== {r['suite']}::{r['test']}  struct={r['structural']} "
                  f"span={r['struct_span']} goldcol={r['gold_colours_struct']}")
            for ours, gold, n in r["struct_pairs"]:
                print(f"   ours {ours} gold {gold}  {n}")
            if r["alpha_pairs"]:
                print(f"   alpha pairs (ours,gold): {r['alpha_pairs']}")


if __name__ == "__main__":
    main()
