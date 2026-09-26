#!/usr/bin/env python3
"""Find suites where one test poisons the tests that run after it.

This is the `RenderTextureLoop` shape, generalised. That test is the first in
`Texture render target` alphabetically, and the last thing it does is disable
texture stage 0 without restoring it. The 40 `TexFmt_*` tests that follow never
enable the stage themselves -- they rely on the suite's one-time `Initialize()`
-- so every one of them draws a flat black quad. The suite measures 3,209,634
px that way and 324,349 px with the test skipped, on an unchanged binary. The
difference is the disc, not the renderer, and it silently inflated the
scoreboard for months (see #4, #19, #27).

`crossmatch.py` answers a different question -- "does another golden in this
suite fit our output better than its own?" -- and it needs the substituted
image to *be* another test's golden. Poisoning does not have to look like
that. A disabled stage draws black, which is nobody's golden; crossmatch
accused only the two `TexFmt_*` captures whose own content happened to be
least black. So crossmatch under-counts this by construction, and a scan for
the poisoning signature itself is a separate instrument.

The signature, none of which needs a device:

  1. **A shared difference mask.** Many captures in the suite differ from their
     goldens on *exactly the same pixels*. Independent per-format decode bugs
     do not agree pixel-for-pixel across formats; one piece of stuck state
     does. In `Texture render target` 39 of 40 masks are identical.

  2. **Flat content inside it.** Our capture holds one colour across the whole
     differing region, in test after test, while the goldens hold many. A
     renderer drawing the right thing wrongly produces structure; a renderer
     drawing nothing produces a constant.

  3. **The suspect is exact.** The poisoning test itself passes -- it ran with
     the state it set up. `RenderTextureLoop` is pixel-exact.

  4. **It runs first.** `RunAll` iterates a `std::map`, so the suite runs in
     alphabetical order and only a test that sorts early can poison anything.

A suite scoring high on 1+2 is a candidate for `--skip-test SUITE::TEST`. It
is *not* proof: a missing state bit that we implement as "off" can also make a
whole suite draw the same wrong thing. Only the disc settles it -- build the
suite with the suspect skipped and see whether the rest change. What this tool
does is tell you which of a hundred suites are worth that disc.

Usage:
    poison_scan.py <dir> [<dir>...] --goldens /home/justin/goldens/results
    poison_scan.py --sweep /home/justin/hakux-work/dispatch/results --goldens ...

Each <dir> is a dispatcher result directory or a captures directory; captures
are `Suite_name::Test_name.png` and goldens `<goldens>/Suite_name/Test_name.png`.
"""
import argparse
import collections
import glob
import hashlib
import os
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("poison_scan.py needs numpy and pillow: pip install numpy pillow")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import captures as captures_mod  # noqa: E402

# Compare RGBA. A run of this scan that dropped alpha would have called
# Context_switch's 64-count alpha difference a colour-only defect.
MODE = "RGBA"

# A group of masks this size or larger is worth reporting. Two captures
# agreeing is unremarkable -- sibling tests with near-identical goldens do it
# all the time -- and three is where a shared cause starts to be the cheaper
# explanation.
MIN_GROUP = 3

# Fraction of the differing region that must hold a single colour before the
# region counts as "flat". The disabled-stage case is 1.000; leave room for a
# test that draws a flat quad plus a label.
FLAT_FRACTION = 0.98


def load(path):
    return np.asarray(Image.open(path).convert(MODE), dtype=np.uint8)


def scan_suite(suite, pairs):
    """pairs: list of (test, capture_path, golden_path). Returns a dict or None."""
    rows = []
    for test, cap_path, gold_path in pairs:
        try:
            cap = load(cap_path)
            gold = load(gold_path)
        except Exception as exc:
            rows.append({"test": test, "error": str(exc)})
            continue
        if cap.shape != gold.shape:
            rows.append({"test": test, "error": "shape %s vs %s" % (cap.shape, gold.shape)})
            continue
        mask = (cap != gold).any(axis=2)
        n = int(mask.sum())
        row = {"test": test, "differing": n, "total": int(mask.size)}
        if n:
            row["mask"] = hashlib.sha256(np.packbits(mask).tobytes()).hexdigest()[:12]
            # What does OUR capture hold where it differs? Flat means one colour.
            ours = cap[mask]
            vals, counts = np.unique(ours.reshape(-1, ours.shape[-1]), axis=0, return_counts=True)
            top = int(counts.max())
            row["our_colours"] = int(len(vals))
            row["flat"] = top / float(n)
            row["modal"] = tuple(int(v) for v in vals[counts.argmax()])
            theirs = gold[mask]
            row["gold_colours"] = int(len(np.unique(theirs.reshape(-1, theirs.shape[-1]), axis=0)))
            row["max_delta"] = int(np.abs(cap.astype(np.int16) - gold.astype(np.int16)).max())
        rows.append(row)
    return {"suite": suite, "rows": rows}


def report(result, verbose=False):
    suite = result["suite"]
    rows = [r for r in result["rows"] if "error" not in r]
    errs = [r for r in result["rows"] if "error" in r]
    if not rows:
        return None
    exact = [r["test"] for r in rows if r["differing"] == 0]
    failing = [r for r in rows if r["differing"] > 0]
    groups = collections.defaultdict(list)
    for r in failing:
        groups[r["mask"]].append(r)
    big = sorted((g for g in groups.values() if len(g) >= MIN_GROUP), key=len, reverse=True)

    verdict = None
    if big:
        g = big[0]
        flat = [r for r in g if r["flat"] >= FLAT_FRACTION]
        # Order matters: only a test sorting before the group can have poisoned it.
        first = sorted(r["test"] for r in rows)[0]
        first_exact = first in exact
        score = 0
        score += 2 if len(flat) >= MIN_GROUP else 0          # shared mask AND flat
        score += 1 if len(g) >= 0.5 * len(failing) else 0    # dominates the suite
        score += 1 if first_exact and first not in [r["test"] for r in g] else 0
        verdict = {
            "suite": suite, "captures": len(rows), "exact": len(exact),
            "failing": len(failing), "group": len(g), "flat_in_group": len(flat),
            "mask": g[0]["mask"], "first": first, "first_exact": first_exact,
            "modal": g[0]["modal"], "gold_colours": max(r["gold_colours"] for r in g),
            "px_each": g[0]["differing"], "max_delta": max(r["max_delta"] for r in g),
            "score": score, "members": sorted(r["test"] for r in g),
        }
    if verbose:
        print("--- %s: %d captures, %d exact, %d failing, %d errors"
              % (suite, len(rows), len(exact), len(failing), len(errs)))
        for r in sorted(failing, key=lambda r: -r["differing"])[:12]:
            print("      %-46s %8d px  mask %s  flat %.3f  ourcol %5d  goldcol %5d  max %3d"
                  % (r["test"][:46], r["differing"], r["mask"], r["flat"],
                     r["our_colours"], r["gold_colours"], r["max_delta"]))
        for r in errs:
            print("      %-46s ERROR %s" % (r["test"][:46], r["error"]))
    return verdict


def collect(d, goldens):
    """Return {suite: [(test, cap, gold)]} for one result/captures directory."""
    root = captures_mod.resolve(d)
    out = collections.defaultdict(list)
    for p in sorted(glob.glob(os.path.join(root, "*.png"))):
        name = os.path.basename(p)[:-4]
        if "::" not in name:
            continue
        suite, test = name.split("::", 1)
        gold = os.path.join(goldens, suite, test + ".png")
        if os.path.exists(gold):
            out[suite].append((test, p, gold))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="*")
    ap.add_argument("--sweep", help="scan every result directory under here")
    ap.add_argument("--goldens", default="/home/justin/goldens/results")
    ap.add_argument("--suite", help="only this suite")
    ap.add_argument("--min-score", type=int, default=1)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    dirs = list(args.dirs)
    if args.sweep:
        dirs += sorted(glob.glob(os.path.join(args.sweep, "*")))
    merged = collections.defaultdict(list)
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for suite, pairs in collect(d, args.goldens).items():
            if args.suite and suite != args.suite:
                continue
            # First directory wins for a suite, so a sweep's own run is not
            # mixed with an A/B arm's captures of the same suite.
            if suite not in merged:
                merged[suite] = pairs
    verdicts = []
    for suite in sorted(merged):
        v = report(scan_suite(suite, merged[suite]), verbose=args.verbose)
        if v:
            verdicts.append(v)
    verdicts.sort(key=lambda v: (-v["score"], -v["group"]))
    print("\n=== candidates (score >= %d), %d suites scanned ===" % (args.min_score, len(merged)))
    print("%-38s %4s %5s %5s %6s %5s %-13s %-24s %s"
          % ("suite", "cap", "exact", "fail", "shared", "flat", "mask", "modal colour", "first test (exact?)"))
    for v in verdicts:
        if v["score"] < args.min_score:
            continue
        print("%-38s %4d %5d %5d %6d %5d %-13s %-24s %s%s   score=%d px/cap=%d maxd=%d"
              % (v["suite"][:38], v["captures"], v["exact"], v["failing"], v["group"],
                 v["flat_in_group"], v["mask"], str(v["modal"]), v["first"][:34],
                 " EXACT" if v["first_exact"] else "", v["score"], v["px_each"], v["max_delta"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
