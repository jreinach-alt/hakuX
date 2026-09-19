#!/usr/bin/env python3
"""Mutants for the suite-direction gate: does each new check actually trip?

A check that would also pass against the broken code tests nothing. The new
checks in docs/testing/jobs/selftest.d/75-nv2a-index.sh assert four things
about a tests tree that is SHORT of the committed index; this breaks each
mechanism in turn, in a COPY under /tmp, and prints which predicates notice.

    python3 docs/lanes/indexcheck/suite_gate_mutants.py

Every mutant must turn at least one PASS into a FAIL. A row that is all-PASS
means the check it corresponds to is inert -- it is confirming the shape of
the message rather than the behaviour behind it.

The real path is never swapped: each mutant is written to /tmp and imported
from there, so a crashed run cannot leave broken code in the tree.
"""

import contextlib
import importlib.util
import io
import json
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SRC = os.path.join(REPO, "docs", "testing", "nv2a_index.py")
BASE = "/tmp/indexcheck-mutant"


def load(path, idx):
    spec = importlib.util.spec_from_file_location("mut", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.INDEX_PATH = idx
    return m


def table(names):
    return {n: {"sources": ["src/tests/%s.cpp" % n], "symbols": []} for n in names}


def probes(m, idx):
    """The predicates the new selftest checks assert, as booleans."""
    committed = table(["Alpha func", "Fog", "Surface as vertex array"])
    fresh = table(["Alpha func", "Fog"])
    json.dump({"suites": committed}, open(idx, "w"))
    missing, extra, changed = m.suite_drift(committed, fresh)
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rc = m.suite_removal_gate(
            {"suites": fresh, "provenance": {"tests_root": "/tmp/tree"}}, False)
    text = "\n".join([m.stale_headline(bool(missing))]
                     + m.describe_suite_drift(missing, extra, changed, "/tmp/tree")
                     + [err.getvalue()])
    return {
        "names the missing suite":
            "MISSING 1 suite(s) the index has: Surface as vertex array" in text,
        "headline omits 'regenerate'":
            "regenerate with: nv2a_index.py build" not in text,
        "build refuses (rc=4)": rc == 4,
        "names what would be deleted":
            "would be deleted: Surface as vertex array" in text,
    }


MUTANTS = {
    "(unmutated)":
        lambda s: s,
    "M1 headline always says regenerate":
        lambda s: s.replace("    if tree_is_short:\n        return (",
                            "    if False:\n        return ("),
    "M2 removal gate never refuses":
        lambda s: s.replace("    return 0 if allow_removal else 4",
                            "    return 0"),
    "M3 drift drops the missing branch":
        lambda s: s.replace("    if missing:\n        out.append(",
                            "    if False:\n        out.append("),
}


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE)
    src = open(SRC).read()
    worst = 0
    for name, mutate in MUTANTS.items():
        body = mutate(src)
        if name != "(unmutated)" and body == src:
            print("!! %-36s MUTATION DID NOT APPLY (the code moved; "
                  "fix the mutant)" % name)
            worst = 2
            continue
        path = os.path.join(BASE, re.sub(r"\W+", "_", name) + ".py")
        open(path, "w").write(body)
        idx = path + ".json"
        res = probes(load(path, idx), idx)
        tripped = [k for k, v in res.items() if not v]
        print("%-36s %s" % (name, "  ".join(
            ("ok " if v else "TRIPPED ") + k for k, v in res.items())))
        if name == "(unmutated)" and tripped:
            print("   !! the unmutated file fails its own checks")
            worst = 2
        if name != "(unmutated)" and not tripped:
            print("   !! INERT: no check noticed this mutation")
            worst = max(worst, 1)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
