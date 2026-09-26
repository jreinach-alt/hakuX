#!/usr/bin/env python3
"""Where the PNGs are, given whatever directory someone passed.

The dispatcher writes a result directory like this::

    1789269088-issue59-fix-1501484/
        DONE  result.json  request.json  run1.log  scores1.tsv
        captures1/
            <Suite>::<test>.png
            ...

so the PNGs are one level down, one directory per run. Tools get handed both
shapes -- a result directory from a dispatcher id, or a captures directory
someone tab-completed -- and on 2026-09-12 two falsifiers crashed or reported
MISSING because they only understood the second.

That is the most dangerous possible failure for a falsifier. Reporting a
capture MISSING on an arm that contains it reads exactly like a run that
failed to render, and `signed_blend_source_halves.py` did precisely that on
#43's arm -- a change that had in fact passed perfectly, 0 of 856,098 channels
wrong. A falsifier that cannot find its own evidence is worse than no
falsifier, because it answers.

Use ``resolve()`` on anything a caller hands you.
"""
import glob
import os


def resolve(d, pattern="*.png"):
    """Return the directory actually holding captures.

    Accepts a dispatcher result directory or a captures directory. Prefers the
    lowest-numbered ``captures<N>`` when several runs are present, because run
    1 is the one every single-run arm has and the one tools have always meant.
    Returns ``d`` unchanged when nothing matches, so the caller's own error
    message is what the user sees rather than a confusing redirect.
    """
    if glob.glob(os.path.join(d, pattern)):
        return d
    for sub in sorted(glob.glob(os.path.join(d, "captures*"))):
        if glob.glob(os.path.join(sub, pattern)):
            return sub
    return d


def find(d, suite, test, pattern=None):
    """Locate one capture by suite and test name, in either directory shape."""
    root = resolve(d, pattern or "%s::*.png" % suite)
    for name in ("%s::%s.png" % (suite, test), "%s.png" % test):
        p = os.path.join(root, name)
        if os.path.exists(p):
            return p
    return None
