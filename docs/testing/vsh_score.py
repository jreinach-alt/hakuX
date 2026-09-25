#!/usr/bin/env python3
"""Diff an nxdk_vsh_tests run's printed values against silicon's, exactly.

    vsh_score.py <results-dir> [--reference DIR ...] [--suite NAME ...]
                 [--json OUT] [--tsv OUT]

Every nxdk_vsh_tests test writes ``<Suite_dir>/<name>.txt`` beside its PNG:
the exact values the vertex program produced, as the program printed them. The
console ran the same program with the same font (2026-09-25, lane.xbox, PR
#225), so a hakuX run and a console run of one test should agree to the byte,
and any line that does not is a value hakuX computes differently. That is a
stronger oracle than a pixel diff and it needs no tolerance.

The verdict per test is one of

    IDENTICAL     the .txt matches the console's byte for byte
    DIFFERS       it does not; the differing lines are printed
    MISSING       the console has it, this run ran that suite, and no file came back
    STALE         a file came back but is older than this run's log.txt -- the
                  program's output directory persists across runs, so this is an
                  earlier run's answer and is not scored
    NO-REFERENCE  this run wrote it and the console has nothing to compare with

The PNG is secondary and reported beside the verdict: `png=identical` (same
bytes), `png=<n>px` (decoded, n pixels differ; needs PIL), or `png=bytes-differ`
when PIL is not installed. It never changes the verdict.

A pgraph result is not a vsh result and nothing here reads goldens. The
dispatcher runs this INSTEAD of score_sweep.py for a `program: vsh` request.

<results-dir> is what extract_results.py writes: flat ``Suite::name.txt`` files
plus ``log.txt``, and ``.fatx_times.json`` when run_disc.sh asked for it. A
nested ``Suite/name.txt`` tree (the console's layout) is accepted too, so two
console runs can be diffed against each other.
"""

import argparse
import datetime
import difflib
import json
import os
import sys

RUNS = "/home/justin/hakux-work/hardware/runs/2026-09-25-vsh"
# stage1b is the first console run with .txt dumps (stage1 predates them);
# stage2 holds the suites with no 2022 golden, Exceptional Float among them.
DEFAULT_REFERENCES = (os.path.join(RUNS, "stage1b", "console"),
                      os.path.join(RUNS, "stage2", "console"))
COMPLETED = "Testing completed normally"
# FATX times have a 2 s resolution; a file written in the same tick the log was
# created is this run's.
FATX_SLACK = datetime.timedelta(seconds=2)


def suite_dir(name):
    """The results-directory spelling of a suite name: 'ILU RCP Tests' -> 'ILU_RCP_Tests'."""
    return name.strip().replace(" ", "_")


def index_tree(root):
    """{'Suite_dir/stem': {'txt': path, 'png': path}} for a flat or nested tree."""
    out = {}
    for dirpath, _dirs, files in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        for fn in files:
            stem, ext = os.path.splitext(fn)
            ext = ext.lower().lstrip(".")
            if ext not in ("txt", "png"):
                continue
            if rel == ".":
                if "::" not in stem:
                    continue          # log.txt, config.cnf, ...
                suite, _, stem = stem.partition("::")
            else:
                suite = rel.replace(os.sep, "/")
            out.setdefault("%s/%s" % (suite, stem), {})[ext] = os.path.join(dirpath, fn)
    return out


def read_log(root):
    """(completed, [suite names started]) from log.txt, flat or nested."""
    for cand in (os.path.join(root, "log.txt"),):
        if os.path.exists(cand):
            text = open(cand, errors="replace").read()
            started = []
            for line in text.splitlines():
                if line.startswith("Starting ") and "::" in line:
                    s = line[len("Starting "):].split("::", 1)[0]
                    if s not in started:
                        started.append(s)
            return COMPLETED in text, started
    return False, []


def _parse(ts):
    return datetime.datetime.fromisoformat(ts) if ts else None


def stale_keys(root):
    """Keys whose .txt predates this run's log.txt, per .fatx_times.json.

    Returns (set, note). The run's start is log.txt's CREATED time: main.cpp
    deletes the log and opens it fresh before the first suite.
    """
    path = os.path.join(root, ".fatx_times.json")
    if not os.path.exists(path):
        return set(), "no .fatx_times.json: staleness NOT checked"
    times = json.load(open(path))
    start = _parse((times.get("log.txt") or {}).get("created"))
    if start is None:
        return set(), "no log.txt time in the manifest: staleness NOT checked"
    stale = set()
    for name, t in times.items():
        if "::" not in name or not name.endswith(".txt"):
            continue
        mod = _parse(t.get("modified"))
        if mod is None or mod + FATX_SLACK < start:
            suite, _, rest = name.partition("::")
            stale.add("%s/%s" % (suite, rest[:-4]))
    return stale, "run started %s (log.txt created)" % start.isoformat()


def png_compare(a, b):
    if open(a, "rb").read() == open(b, "rb").read():
        return "identical"
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return "bytes-differ"
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    if ia.size != ib.size:
        return "size %dx%d vs %dx%d" % (ia.size + ib.size)
    diff = ImageChops.difference(ia, ib).convert("L").point(lambda v: 255 if v else 0)
    return "%dpx" % sum(1 for v in diff.getdata() if v)


def score(results, references, suites=None):
    completed, started = read_log(results)
    ran = [suite_dir(s) for s in (suites or started)]
    ours = index_tree(results)
    ref = {}
    ref_dupes = []
    for r in references:
        for key, paths in index_tree(r).items():
            if key in ref and "txt" in ref[key] and "txt" in paths and \
                    open(ref[key]["txt"], "rb").read() != open(paths["txt"], "rb").read():
                ref_dupes.append(key)
            ref.setdefault(key, {}).update(paths)
    stale, stale_note = stale_keys(results)

    keys = sorted({k for k in ref if k.split("/", 1)[0] in ran} |
                  {k for k in ours if "txt" in ours[k]})
    tests = {}
    for key in keys:
        o, c = ours.get(key, {}), ref.get(key, {})
        row = {"verdict": None, "diff": [], "png": None}
        if "txt" not in o:
            row["verdict"] = "MISSING"
        elif key in stale:
            row["verdict"] = "STALE"
        elif "txt" not in c:
            row["verdict"] = "NO-REFERENCE"
        else:
            a = open(c["txt"], "rb").read()
            b = open(o["txt"], "rb").read()
            if a == b:
                row["verdict"] = "IDENTICAL"
            else:
                row["verdict"] = "DIFFERS"
                row["diff"] = [ln for ln in difflib.unified_diff(
                    a.decode("latin-1").splitlines(), b.decode("latin-1").splitlines(),
                    "console", "hakuX", n=0, lineterm="")]
        if "png" in o and "png" in c and row["verdict"] != "STALE":
            row["png"] = png_compare(c["png"], o["png"])
        tests[key] = row

    counts = {}
    for row in tests.values():
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    return {"program": "vsh", "log_completed": completed, "suites": ran,
            "references": list(references), "reference_conflicts": ref_dupes,
            "staleness": stale_note, "counts": counts, "tests": tests}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results")
    ap.add_argument("--reference", action="append", default=[], metavar="DIR",
                    help="console output tree, repeatable (default: the "
                         "2026-09-25 stage1b and stage2 console runs)")
    ap.add_argument("--suite", action="append", default=[],
                    help="suites this run was asked for (default: those its "
                         "log.txt started). A suite asked for and never started "
                         "is then reported MISSING, not silently absent.")
    ap.add_argument("--json", metavar="OUT")
    ap.add_argument("--tsv", metavar="OUT")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.results):
        print("no such results dir: %s" % args.results, file=sys.stderr)
        return 2
    refs = args.reference or list(DEFAULT_REFERENCES)
    for r in refs:
        if not os.path.isdir(r):
            print("no such reference dir: %s" % r, file=sys.stderr)
            return 2
    out = score(args.results, refs, args.suite or None)

    if not out["log_completed"]:
        print("*** log.txt has no '%s': this run did not finish, and anything "
              "MISSING below is missing for that reason" % COMPLETED)
    print("staleness: %s" % out["staleness"])
    for key in out["reference_conflicts"]:
        print("*** the references disagree on %s; the later --reference wins" % key)
    for key, row in out["tests"].items():
        png = ("  png=%s" % row["png"]) if row["png"] else ""
        print("%-12s %s%s" % (row["verdict"], key, png))
        for line in row["diff"]:
            if not line.startswith(("---", "+++")):
                print("             %s" % line)
    print("counts: %s" % ", ".join("%s %d" % kv for kv in sorted(out["counts"].items())))

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(out, fh, indent=1)
    if args.tsv:
        with open(args.tsv, "w") as fh:
            fh.write("key\tverdict\tdiff_lines\tpng\n")
            for key, row in out["tests"].items():
                fh.write("%s\t%s\t%d\t%s\n" % (
                    key, row["verdict"],
                    sum(1 for ln in row["diff"] if ln[:1] in "+-" and
                        not ln.startswith(("---", "+++"))),
                    row["png"] or ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
