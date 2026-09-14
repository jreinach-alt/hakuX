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

    `--all`, AND IT IS THE WHOLE POINT OF THIS FUNCTION IN A WORKTREE. Without
    it `git log` walks only the history of the branch it is standing on, so a
    LANE WORKTREE derives its own branch point as the high-water mark and every
    wave committed after it branched is invisible. That is not a corner case:
    it is the normal state of every lane, because a lane branches once and the
    allocation moves on without it.

    Measured, on 2026-09-13: the #31/#10 lane branched at wave 12 and ran for
    its whole life against a table where `glsl/psh.c` sat in `[free]` with no
    owner at all. The live table had claimed it for that very lane at wave 13.
    The lane's preflight printed "territory ok" every time, and the checker was
    right about the file it was given -- it was given a file four waves stale.
    Nothing collided only because the file the lane saw as free happened to be
    allocated TO IT; a lane in that position can take a file another lane
    claimed after it branched, and its preflight will pass.

    The lane reported this as an overlap in wave 13 ("psh.c is in both
    [lane.psh] and [free]"). No committed wave ever contained that overlap.
    The two halves of that sentence came from two different files: `[lane.psh]`
    from the live table it had been briefed from, `[free]` from its own frozen
    copy. A stale read and a live read, indistinguishable once quoted.
    """
    try:
        out = subprocess.run(
            ["git", "-C", HERE, "log", "-p", "--all", "--", "territory.toml"],
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

    # WHOSE BLOCKER DID THIS CLAIM JUST WALL?
    #
    # A lane claims files. Some OTHER open issue's `blocked_on` names files by
    # path, because that is how this campaign records "the fix needs these
    # together". Nothing connected the two, so a claim could silently become
    # another issue's blocker and the board would show both as covered.
    #
    # Measured, on the same day, by the orchestrator: #59's blocker said it was
    # ordered behind lane.signfold. lane.signfold had been RETIRED and its
    # files were free -- check_coverage.py's grant-request NOTE reported the
    # wall as gone, twice. I read that note and then claimed vk/draw.c and
    # vk/surface.c for lane.stencil without checking who else wanted them,
    # rebuilding two thirds of the same wall for a different issue.
    #
    # ADVISORY, not a failure. Ordering lanes is legitimate and sometimes
    # necessary. What is not legitimate is doing it without saying so, leaving
    # a blocker naming a predecessor that finished months ago while the real
    # one is the lane claimed this morning.
    walled = []
    try:
        with open(os.path.join(HERE, "nv2a_issues.toml"), "rb") as fh:
            tracker = tomllib.load(fh)["issue"]
    except Exception:
        tracker = {}
    for num, v in sorted(tracker.items()):
        blocker = (v.get("blocked_on") or "")
        if not blocker:
            continue
        named = set(re.findall(r"[A-Za-z0-9_./-]+\.[ch]\b", blocker))
        if not named:
            continue
        hits = {}
        for f, lane in owner.items():
            if num in (d.get("lane") or {}).get(lane, {}).get("issues", []):
                continue          # the lane that owns the issue is not a wall
            for n in named:
                # Suffix match at a directory boundary, the same rule
                # check_coverage.py settled on: `vk/draw.c` must not be
                # satisfied by `gl/draw.c`, and there are two of each here.
                if f == n or f.endswith("/" + n):
                    hits.setdefault(lane, set()).add(n)
        for lane, ns in hits.items():
            if lane not in blocker:
                walled.append((num, lane, sorted(ns)))

    if problems:
        print("FAIL: territory.toml", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 1

    print("territory ok (wave %d, %d lanes, %d files claimed)"
          % (wave, len(d.get("lane") or {}), len(owner)))
    # After the summary line: idle-watchdog.sh reads `sed -n 1p` of this.
    for num, lane, ns in walled:
        print("NOTE: #%s's blocker names %s, held by %s, which does not own "
              "#%s and is not mentioned in the blocker -- say so, or release "
              "them" % (num, ", ".join(ns), lane, num))
    return 0


if __name__ == "__main__":
    sys.exit(main())
