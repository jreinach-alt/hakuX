"""Exact-match text edits on a carved generator file; any edit that does not
match exactly the expected number of times stops the build."""
import sys
from pathlib import Path


def edit(srcdir, fname, pairs):
    p = Path(srcdir) / fname
    t = p.read_text()
    for old, new, *count in pairs:
        want = count[0] if count else 1
        got = t.count(old)
        if got != want:
            sys.exit(f"{fname}: expected {want} of {old!r}, found {got}")
        t = t.replace(old, new)
    p.write_text(t)
