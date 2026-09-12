#!/usr/bin/env python3
"""Turn the overnight #19 runs into one verdict per accused test.

`crossmatch.py` says "this test rendered *that* test's image". That is an
accusation, not a diagnosis: it has two causes that need opposite fixes.

  **contamination**    the test is right when run alone, so state from an
                       earlier test leaked into it. Order-dependent, and the
                       fix is an invalidation or a reset we are missing.

  **missing-state**    still wrong alone, so we never implement the state bit
                       that distinguishes it from the test it reproduces. Not
                       order-dependent, and it names a specific missing
                       feature, which makes it the more actionable of the two.

Both arms have to come from the same binary or an improvement has two
explanations, so this refuses to score a row whose solo APK sha differs from
the company arm's.

A solo run only counts if its own progress log shows the test as `[1/1]`.
Neither file mtimes nor "the PNG exists" can substitute: a truncated run
silently leaves the previous run's image in place, and that reads as a pass.

    night19_report.py ~/hakux-work/night19 --goldens ~/goldens/results
"""
import argparse
import glob
import os
import subprocess
import sys

try:
    import numpy as np
    from PIL import Image
except ImportError:
    sys.exit("night19_report.py needs numpy and pillow")

# Same metric and threshold as crossmatch.py, deliberately: the two arms have
# to be measured the same way for the comparison between them to mean anything.
FAIL_THRESHOLD = 2.0


def load(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)


def err(a, b):
    """Mean absolute per-subpixel error, or None if the shapes disagree."""
    if a.shape != b.shape:
        return None
    return float(np.abs(a - b).mean())


def differing(a, b):
    if a.shape != b.shape:
        return None
    return int((np.abs(a - b).max(axis=2) > 0).sum())


def read_crossmatch(path):
    """(suite, test, impersonated, own_err, other_err) from the padded table."""
    out = []
    for line in open(path, encoding="utf-8", errors="replace"):
        f = line.split()
        if len(f) != 5:
            continue
        try:
            own, other = float(f[3]), float(f[4])
        except ValueError:
            continue
        out.append((f[0], f[1], f[2], own, other))
    return out


def solo_dirs(state):
    """spec -> (result_dir, apk_sha) for every solo run that was recorded."""
    found = {}
    for done in glob.glob(os.path.join(state, "sq_*", "done.tsv")):
        sq = os.path.dirname(done)
        for line in open(done, encoding="utf-8", errors="replace"):
            f = line.rstrip("\n").split("\t")
            if len(f) < 3 or not f[1]:
                continue
            found[f[0]] = (os.path.join(sq, "out", f[1]), f[2])
    return found


def ran_solo(result_dir):
    log = os.path.join(result_dir, "pgraph_progress_log.txt")
    if not os.path.exists(log):
        return False
    return "[1/1]" in open(log, encoding="utf-8", errors="replace").read()


def company_sha(state):
    rows = os.path.join(state, "rows.tsv")
    if not os.path.exists(rows):
        return None
    shas = {f[3] for f in (l.rstrip("\n").split("\t") for l in open(rows))
            if len(f) >= 4 and f[0] == "company"}
    if len(shas) == 1:
        return shas.pop()
    # No rows and several rows mean opposite things, and calling both of them
    # "mixed" reads as a binary mix-up when it is really an empty run.
    return "" if not shas else None


def blend_section(state):
    """Score any fresh Blend tests arm against silicon's blend model.

    The company arm is a capture set produced on one known binary, which is
    exactly what the surface-as-texture decode fix needs to be checked on --
    the Adreno half of that finding was measured on a corpus run from an
    older APK and is one binary short of quotable until this runs. So the
    sweep finishes the measurement itself instead of leaving it for someone
    to remember in the morning.

    Prediction on the books, from the remote lane: 10,026 of 18,000 before
    the fix, 16,379 after it, with the residue collapsing to one step.
    """
    arms = [d for d in glob.glob(os.path.join(state, "company", "*"))
            if glob.glob(os.path.join(d, "Blend_tests::#spot_*.png"))]
    if not arms:
        return
    here = os.path.dirname(os.path.abspath(__file__))
    print("## Blend tests, against silicon's blend model\n")
    for arm in sorted(arms):
        n = len(glob.glob(os.path.join(arm, "Blend_tests::#spot_*.png")))
        print(f"`{os.path.basename(arm)}`, {n} #spot_ captures:\n")
        r = subprocess.run(
            [sys.executable, os.path.join(here, "blend_channel_order.py"),
             "--captures", arm],
            capture_output=True, text=True)
        out = (r.stdout or r.stderr).strip()
        print("```\n" + out + "\n```\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("state")
    ap.add_argument("--goldens", required=True)
    args = ap.parse_args()

    csha = company_sha(args.state)
    solo = solo_dirs(args.state)
    groups = sorted(glob.glob(os.path.join(args.state, "crossmatch_*.txt")))

    print("# Issue #19: what the accused tests do when run alone\n")
    if csha:
        print(f"Company arm APK: `{csha}`\n")
    elif csha == "":
        print("No company arm measured yet.\n")
    else:
        print("Company arm APK: **MIXED — see rows.tsv**, so no row below is"
              " safe to compare.\n")

    verdicts = {"contamination": [], "missing-state": [], "partial": [],
                "no-run": [], "mismatched-binary": []}
    for xm in groups:
        g = os.path.basename(xm)[len("crossmatch_"):-len(".txt")]
        rows = read_crossmatch(xm)
        print(f"## Group `{g}` — {len(rows)} accused\n")
        if not rows:
            print("Nothing accused; every failing capture in this group fits its"
                  " own golden better than any other in the suite.\n")
            continue
        print("| test | renders instead | in company | alone | verdict |")
        print("|---|---|---|---:|---|")
        for suite, test, other, own, _oe in rows:
            spec = f"{suite}::{test}"
            rec = solo.get(spec)
            if rec is None:
                verdicts["no-run"].append(spec)
                print(f"| `{suite}::{test}` | `{other}` | {own:.2f} | — | not reached |")
                continue
            rdir, ssha = rec
            if csha and ssha != csha:
                verdicts["mismatched-binary"].append(spec)
                print(f"| `{suite}::{test}` | `{other}` | {own:.2f} | — |"
                      f" solo APK `{ssha}` ≠ company `{csha}` |")
                continue
            if not ran_solo(rdir):
                verdicts["no-run"].append(spec)
                print(f"| `{suite}::{test}` | `{other}` | {own:.2f} | — |"
                      " no `[1/1]` in the progress log |")
                continue
            ours = os.path.join(rdir, f"{suite}::{test}.png")
            gold = os.path.join(args.goldens, suite, f"{test}.png")
            if not (os.path.exists(ours) and os.path.exists(gold)):
                verdicts["no-run"].append(spec)
                print(f"| `{suite}::{test}` | `{other}` | {own:.2f} | — |"
                      " capture or golden missing |")
                continue
            e = err(load(ours), load(gold))
            if e is None:
                verdicts["no-run"].append(spec)
                note = "size differs from the golden"
            elif e == 0.0:
                verdicts["contamination"].append(spec)
                note = "**contamination** — exact alone"
            elif e < FAIL_THRESHOLD:
                verdicts["partial"].append(spec)
                note = "contamination, plus a residual of its own"
            elif e < own / 3.0:
                verdicts["partial"].append(spec)
                note = "mostly contamination — much better alone"
            else:
                verdicts["missing-state"].append(spec)
                note = "**missing-state** — as wrong alone"
            shown = "—" if e is None else f"{e:.2f}"
            print(f"| `{suite}::{test}` | `{other}` | {own:.2f} | {shown} | {note} |")
        print()

    blend_section(args.state)

    print("## Totals\n")
    order = ["contamination", "partial", "missing-state", "no-run",
             "mismatched-binary"]
    for k in order:
        print(f"- **{k}**: {len(verdicts[k])}")
    print()
    if verdicts["missing-state"]:
        print("### Missing-state tests, which name a feature rather than an"
              " ordering bug\n")
        for spec in verdicts["missing-state"]:
            print(f"- `{spec}`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
