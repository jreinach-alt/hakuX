#!/usr/bin/env python3
"""Load the two board files from where the board actually lives.

The board -- territory.toml and nv2a_issues.toml -- is being moved off the
code branch onto an orphan branch named `board`, so that no lane ever carries
a copy frozen at its branch point and no fold can silently revert it (both
happened; see docs/ORCHESTRATION-DESIGN.md §5 and §7.2).

During the transition both copies exist. This helper prefers the branch and
falls back to the working tree, and says which it used, so a checker can
print its source instead of quoting a stale read as a live one.

    from board_files import load, source
    terr = load("territory.toml")

HAKUX_BOARD_REF names the ref (default origin/board); empty disables it.
"""
import os
import subprocess
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.environ.get("HAKUX_BOARD_REF", "origin/board")
_src = {}


def _from_ref(name):
    if not REF:
        return None
    try:
        out = subprocess.run(["git", "-C", HERE, "show", "%s:%s" % (REF, name)],
                             capture_output=True, timeout=15)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def load(name):
    raw = _from_ref(name)
    if raw is not None:
        _src[name] = REF
        return tomllib.loads(raw.decode("utf-8"))
    _src[name] = "working tree"
    with open(os.path.join(HERE, name), "rb") as fh:
        return tomllib.load(fh)


def source(name):
    """Where the last load() of `name` came from, for the reader's benefit."""
    return _src.get(name, "not loaded")
