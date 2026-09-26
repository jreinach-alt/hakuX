#!/usr/bin/env python3
"""Classify why each suite renders another test's image.

Reads the manifest written by `make_isolation_discs.py` together with the
results of each solo run, and decides which of two very different faults each
suite has:

  **contamination**   the test is correct when run alone, so state from an
                      earlier test was leaking into it. Order-dependent.

  **missing-state**   the test is still wrong alone, so we never implement the
                      state bit that distinguishes it from the test it
                      reproduces. Not order-dependent, and usually a far more
                      actionable finding: it names a specific missing feature.

Usage:
    classify_isolation.py discs/manifest.json --results-prefix res_iso_ \\
        --goldens goldens/results

Each solo run's directory must contain `pgraph_progress_log.txt`. A run whose
log does not record the test completing is reported as `NO-RUN` and given no
verdict — neither `--newer-than` nor FATX mtimes can substitute for that check,
and a truncated run silently returns the previous run's images.
"""
import argparse
import json
import os
import re
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("needs numpy and pillow: pip install numpy pillow")

# Mean absolute per-subpixel error below which we call the solo render correct.
# DXT1 interpolation rounding sits at 0.36 and is not a defect of this kind;
# a substituted image sits at 15-130.
CORRECT = 2.0


def load(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)


def err(a, b):
    if a.shape != b.shape:
        return float("nan")
    return float(np.abs(a - b).mean())


STARTING = re.compile(r"Starting \[(\d+)/(\d+)\]\s+(.+?)::(\S+)")


def ran_ok(logpath, test):
    """Did the suite's own log record this test running FIRST, and finishing?

    Running first is what makes the run an isolation test. A disc that enables
    one test can still execute others -- the skip list is built from tests the
    sweep recorded, and a test that aborts writes no output, so it is missing
    from that list and runs anyway. If anything preceded our test, contamination
    was possible and the run proves nothing.
    """
    if not os.path.exists(logpath):
        return False, "no progress log"
    text = open(logpath, encoding="utf-8", errors="replace").read()
    order = [(int(m.group(1)), int(m.group(2)), m.group(4))
             for m in STARTING.finditer(text)]
    if not order:
        return False, "no tests in progress log"
    ours = [i for i, _n, t in order if t == test]
    if not ours:
        return False, f"test never ran ({len(order)} others did)"
    if ours[0] != 1:
        preceded = next(t for i, _n, t in order if i == 1)
        return False, f"not first, ran after {preceded}"
    if "Testing completed normally" not in text:
        return False, "log does not say completed normally"
    return True, ""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manifest")
    ap.add_argument("--results-prefix", default="res_iso_",
                    help="solo result dirs are <prefix><suite> (default res_iso_)")
    ap.add_argument("--goldens", required=True)
    args = ap.parse_args()

    entries = json.load(open(args.manifest, encoding="utf-8"))
    rows, tally = [], {"contamination": 0, "missing-state": 0, "NO-RUN": 0,
                       "unclear": 0}

    for e in entries:
        suite, test = e["suite"], e["test"]
        rdir = f"{args.results_prefix}{suite}"
        ok, why = ran_ok(os.path.join(rdir, "pgraph_progress_log.txt"), test)
        png = os.path.join(rdir, f"{suite}::{test}.png")
        if not ok or not os.path.exists(png):
            rows.append((suite, test, e["impersonates"], e["own_err"], None,
                         "NO-RUN", why or "no output"))
            tally["NO-RUN"] += 1
            continue

        ours = load(png)
        own = err(ours, load(os.path.join(args.goldens, suite, f"{test}.png")))
        gp = os.path.join(args.goldens, suite, f"{e['impersonates']}.png")
        oth = err(ours, load(gp)) if os.path.exists(gp) else float("nan")

        if own <= CORRECT:
            verdict, note = "contamination", "correct alone"
        elif oth == oth and oth * 3 < own:
            verdict, note = "missing-state", "still renders the sibling"
        else:
            verdict, note = "unclear", "wrong alone, but not the sibling either"
        tally[verdict] += 1
        rows.append((suite, test, e["impersonates"], e["own_err"], own,
                     verdict, note))

    w = max(len(r[0]) for r in rows) + 1
    print(f"{'suite':<{w}} {'in sweep':>9} {'alone':>7}  {'verdict':<15} note")
    print("-" * (w + 60))
    order = {"contamination": 0, "missing-state": 1, "unclear": 2, "NO-RUN": 3}
    for suite, _t, _i, sweep, alone, verdict, note in sorted(
            rows, key=lambda r: (order[r[5]], r[0])):
        a = f"{alone:.2f}" if alone is not None else "—"
        print(f"{suite:<{w}} {sweep:>9.2f} {a:>7}  {verdict:<15} {note}")

    print()
    for k in ("contamination", "missing-state", "unclear", "NO-RUN"):
        if tally[k]:
            print(f"  {k:<15} {tally[k]}")
    if tally["NO-RUN"]:
        print("\nNO-RUN means the run does not support a verdict: the disc ran "
              "nothing (suite name guessed wrong), or something executed before "
              "our test so contamination was still possible. Rebuild that disc "
              "with a complete skip list and re-run; do not read anything into "
              "its images.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
