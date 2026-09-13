#!/usr/bin/env python3
"""Fail if the territory allocation has gone backwards, or overlaps.

    check_territory.py

Two checks, and the first is the reason this exists.

MONOTONE WAVE. `territory.toml`'s `wave` is compared against the highest wave
any commit ever recorded, stored in `.territory_wave`. A fold that reverts the
allocation -- which happens whenever a lane branch carrying an older copy is
cherry-picked -- lowers `wave` and fails here. Before this, the revert was
silent: the fifth-wave table was written on 2026-09-13, two lane branches were
folded, and the file went back to the fourth wave with no conflict and no
error. The next brief was written from the reverted table and told a lane a
file was free when the table said otherwise.

NO TWO LANES HOLD ONE FILE. An overlap is the bug the table exists to prevent,
so it is worth one loop rather than one more paragraph asking people to check.
"""
import os
import re
import subprocess
import sys
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
TOML = os.path.join(HERE, "territory.toml")


def committed_high_water():
    """The highest `wave` ever committed, read from git history.

    THIS USED TO BE A STAMP FILE AND THAT WAS A REAL BUG, not a style
    preference. `.territory_wave` was tracked, so writing it dirtied the shared
    working tree -- and `dispatcher.sh` refuses to build any ref while the tree
    has a tracked modification, because with several implementers holding
    uncommitted work "run my build" is ambiguous. So a CHECKER stalled the
    build path: 129 requeues, every queued arm needing a new binary bouncing
    every 30 seconds, and it was a loop -- each preflight run rewrote the stamp
    and re-dirtied the tree. Reported by a lane that noticed its own arms
    requeueing.

    A checker must have no side effects on the tree it checks. The high-water
    mark is derivable from the history of the file it is about, so derive it:
    every committed value of `wave` is in `git log -p`, the maximum cannot be
    forged by a fold, and nothing is written anywhere.
    """
    try:
        out = subprocess.run(
            ["git", "-C", HERE, "log", "-p", "--", "territory.toml"],
            capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return 0
    waves = [int(m) for m in re.findall(r"^\+wave\s*=\s*(\d+)", out, re.M)]
    return max(waves) if waves else 0


def main():
    with open(TOML, "rb") as fh:
        d = tomllib.load(fh)

    wave = d.get("wave")
    if not isinstance(wave, int):
        print("FAIL: territory.toml has no integer `wave`", file=sys.stderr)
        return 2

    high = committed_high_water()
    if wave < high:
        print("FAIL: territory.toml is at wave %d but wave %d was already "
              "recorded.\n"
              "  The allocation has gone BACKWARDS. The usual cause is folding\n"
              "  a lane branch: it carries whatever territory.toml said when it\n"
              "  branched, and the cherry-pick restores that silently.\n"
              "  Re-apply the current allocation before writing another brief --\n"
              "  a stale row is indistinguishable from a live claim."
              % (wave, high), file=sys.stderr)
        return 1
    # No file claimed twice. `free` is checked against the lanes too: a file
    # cannot be both free and held, and that is exactly the state a partial
    # revert leaves behind.
    owner = {}
    problems = []
    for lane, meta in (d.get("lane") or {}).items():
        for f in meta.get("files", []):
            if f in owner:
                problems.append("%s is claimed by both %s and %s"
                                % (f, owner[f], lane))
            owner[f] = lane
    for f in (d.get("free") or {}).get("files", []):
        if f in owner:
            problems.append("%s is listed FREE but claimed by %s" % (f, owner[f]))

    # Issues split from a common parent must not be concurrent. Only the pairs
    # this campaign has actually confused are listed; a guess here would be
    # worse than nothing.
    SPLIT = [("16", "52"), ("9", "53"), ("9", "38"), ("53", "38"), ("43", "50")]
    live = {}
    for lane, meta in (d.get("lane") or {}).items():
        for i in meta.get("issues", []):
            live[i] = lane
    for a, b in SPLIT:
        if a in live and b in live and live[a] != live[b]:
            problems.append("#%s (%s) and #%s (%s) are split from a common "
                            "parent and must not be concurrent in two lanes"
                            % (a, live[a], b, live[b]))

    if problems:
        print("FAIL: territory.toml", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1

    print("territory ok (wave %d, %d lanes, %d files claimed)"
          % (wave, len(d.get("lane") or {}), len(owner)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
