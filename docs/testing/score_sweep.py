#!/usr/bin/env python3
"""Score a whole isolation sweep against the hardware goldens.

    score_sweep.py --out sweep.state/out --goldens goldens/results \
                   --tsv scores.tsv

Each directory under ``--out`` is one guest run: a progress log naming the
test(s) that actually executed, and the framebuffer(s) they captured. The
sweep exists so that every test runs alone, which is the only way a result
means what it says -- 328 of 864 tests were previously rendering a *previous*
test's image. The progress log is the proof: ``[1/1]`` is a solo run, anything
else is a shared disc and is reported as such rather than quietly trusted.

What it reports, per test:

  * differing pixels, as a count and a share of the frame
  * max delta over R, G and B, and separately over A
  * whether the capture is *blank* -- one colour over more than 90% of a frame
    whose golden is richer than that. A blank frame is a different failure from
    a wrong one: nothing drew, or the capture beat the draw to it. Mixed into a
    pixel-difference average it reads as dozens of subtly broken tests instead
    of one thing that did not run, so it is counted separately.

The split matters. A mean cannot tell "this format is not decoded at all"
(max 255) from "rounding" (max 8), and that is the whole triage decision; and
comparing RGB alone once hid 1,279 differing alpha pixels behind a clean score.
Suites are ranked by the share of their tests that are bit-identical, because
that is the only claim that needs no threshold to defend.
"""

import argparse
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("needs numpy and pillow: pip install numpy pillow")

STARTING = re.compile(r"Starting \[(\d+)/(\d+)\] (.+?)::(.+)")


def read_log(path):
    """(solo, [test names]) for one run directory."""
    names, total = [], 1
    try:
        with open(path, errors="replace") as f:
            for line in f:
                m = STARTING.match(line.strip())
                if m:
                    total = int(m.group(2))
                    names.append(m.group(4).strip())
    except OSError:
        return True, []
    return total == 1, names


def score_dir(args):
    run_dir, goldens = args
    solo, _ = read_log(os.path.join(run_dir, "pgraph_progress_log.txt"))
    rows = []
    for name in sorted(os.listdir(run_dir)):
        if not name.endswith(".png") or "::" not in name:
            continue
        suite, test = name[:-4].split("::", 1)
        gp = os.path.join(goldens, suite, test + ".png")
        if not os.path.exists(gp):
            rows.append((suite, test, solo, "no-golden", 0, 0, 0, 0))
            continue
        g = np.asarray(Image.open(gp).convert("RGBA"), dtype=np.int16)
        o = np.asarray(Image.open(os.path.join(run_dir, name)).convert("RGBA"),
                       dtype=np.int16)
        if g.shape != o.shape:
            rows.append((suite, test, solo, "size", 0, 0, 0, g.shape[0] * g.shape[1]))
            continue
        d = np.abs(g - o)
        rgb = d[..., :3].max(axis=2)
        alpha = d[..., 3]
        differing = int(((rgb > 0) | (alpha > 0)).sum())

        flat = o[..., :3].reshape(-1, 3)
        _, counts = np.unique(flat, axis=0, return_counts=True)
        gold_colours = len(np.unique(g[..., :3].reshape(-1, 3), axis=0))
        blank = (counts.max() / flat.shape[0] > 0.90 and len(counts) <= 4
                 and gold_colours > 4)

        rows.append((suite, test, solo, "blank" if blank else "ok", differing,
                     int(rgb.max()), int(alpha.max()), g.shape[0] * g.shape[1]))
    return rows


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="sweep state's out/ directory")
    ap.add_argument("--goldens", required=True)
    ap.add_argument("--tsv", help="write the per-test table here")
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    args = ap.parse_args()

    dirs = [os.path.join(args.out, d) for d in sorted(os.listdir(args.out))
            if os.path.isdir(os.path.join(args.out, d))]
    rows = []
    with ProcessPoolExecutor(max_workers=args.jobs) as ex:
        for got in ex.map(score_dir, [(d, args.goldens) for d in dirs],
                          chunksize=8):
            rows.extend(got)

    if args.tsv:
        with open(args.tsv, "w") as f:
            f.write("suite\ttest\tsolo\tstatus\tdiffering\tmax_rgb\tmax_a\tpixels\n")
            for r in sorted(rows):
                f.write("\t".join(str(x) for x in r) + "\n")

    scored = [r for r in rows if r[3] in ("ok", "blank")]
    blanks = [r for r in rows if r[3] == "blank"]
    exact = [r for r in scored if r[4] == 0]
    nogold = [r for r in rows if r[3] == "no-golden"]
    sized = [r for r in rows if r[3] == "size"]
    shared = {r[0] for r in rows if not r[2]}

    print(f"{len(rows)} captures from {len(dirs)} runs\n")
    print(f"  bit-identical to hardware : {len(exact):5d}  "
          f"({len(exact)/max(len(scored),1)*100:.1f}% of scored)")
    print(f"  differ                    : {len(scored)-len(exact)-len(blanks):5d}")
    print(f"  blank -- nothing drew     : {len(blanks):5d}")
    if sized:
        print(f"  wrong size                : {len(sized):5d}")
    if nogold:
        print(f"  no golden to compare      : {len(nogold):5d}")

    suites = {}
    for suite, test, solo, status, differing, mrgb, ma, px in scored:
        s = suites.setdefault(suite, {"n": 0, "exact": 0, "px": 0, "tot": 0,
                                      "mrgb": 0, "ma": 0, "blank": 0})
        s["n"] += 1
        s["exact"] += differing == 0
        s["px"] += differing
        s["tot"] += px
        s["mrgb"] = max(s["mrgb"], mrgb)
        s["ma"] = max(s["ma"], ma)
        s["blank"] += status == "blank"

    order = sorted(suites.items(), key=lambda kv: (kv[1]["exact"] / kv[1]["n"],
                                                   -kv[1]["px"] / max(kv[1]["tot"], 1)))
    w = max(len(k) for k in suites) + 1
    print(f"\n{'suite':<{w}} {'exact':>11} {'blank':>7} {'px differing':>13} "
          f"{'max RGB':>8} {'max A':>6}")
    print("-" * (w + 50))
    for name, s in order:
        share = s["px"] / max(s["tot"], 1) * 100
        mark = " *" if name in shared else ""
        blank = f"{s['blank']}" if s["blank"] else "-"
        print(f"{name:<{w}} {s['exact']:>4}/{s['n']:<6} {blank:>7} {share:>12.2f}% "
              f"{s['mrgb']:>8} {s['ma']:>6}{mark}")
    if shared:
        print("\n  * ran on a shared disc, not one test per run — these are the "
              "suites\n    the isolation build could not split, so contamination "
              "between their\n    own tests is not ruled out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
