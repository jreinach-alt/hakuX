#!/usr/bin/env python3
"""pathbook.py -- a title's recorded way into gameplay: built from drive.py's own runs,
replayed by the next run of that title (#433, lane routebuild1021).

    pathbook.py build <result dir> --title-id T [--dir D]   route-trail.json -> D/<T>.json, if better
    pathbook.py show <T> [--dir D]                            the path drive.py would replay for T

WHY (owner, 2026-10-21). "The classifier should track the screenshots and the inputs
used, and that information should be reviewed by a path builder, who records the
optimal path and timing needed to reach that gameplay, which becomes our new path."
drive.py's generic profile reached a new title's gameplay by trial: the classifier's
lean, the learned table, the exploration ladder. Without a book, the next run of that
title repeats every wrong press. With one, it replays the presses that worked, at the
screens they worked on, and goes back to trial only where the book has nothing.

THE TRAIL. drive.py writes <out>/route-trail.json: one entry per press it made, with the
screen's signature before the press, what the classifier called that screen, whether
it was a menu (`menu`), and what the next capture showed (`after_state`; `after_d`, the
signature distance; `after_changed`, the motion fraction). It also records whether
confirmed gameplay had already been reached (`in_play`).

THE PATH. build() keeps the presses that did something before gameplay: the next
capture's screen moved past SIG_MATCH, the state moved later in the profile's `order`,
or (a menu press) anything on the screen moved at all, since a cursor row moves too
little for the signature to see. A press that changed nothing is dropped. So is a
loop that holds no menu step: a press back on a screen the run had already pressed
past, after leaving it (a title that fell back into its attract video and came round
again), cuts everything since the first press there. A loop through a menu is KEPT:
the signature does not see the cursor, so cutting an A into Options and a B back out
would replay the cursor moves before it onto the wrong row. Repeated presses on one
screen (DOWN, DOWN, A) never left it, so they are not a loop. Each step's `at_s` and
`wait_s` are its time from the start and from the step before. The schema is
pathfind.py's own (pathknow/paths/<TID>.json, `steps: [{state, why, action, wait_s,
useful, sig}]`), with the same 16x12 signature and SIG_MATCH. So drive.py replays
either builder's path: the 164 complete pathfind paths already recorded serve
re-runs of those titles.

BETTER. A run's path replaces the stored one only if score() is higher:
  1. a path that reached gameplay beats one that did not;
  2. between two that did, the faster one wins;
  3. between two that did not, the one that got further in `order` wins --
     except that an unfinished pathfind path is never replaced by an unfinished
     drive one: its states are pathfind's own, not on the profile's `order`, so
     how far it got cannot be compared, and a drive run outranks it only by
     reaching play (43 of the 207 repo paths are unfinished; most still end on
     a step pathfind called gameplay).
A pathfind path in the repo is read, never written. A drive path goes to
HAKUX_PATHS_DIR (the dispatcher's $D/paths). load() replays whichever of the two
scores higher, so an unfinished drive path never hides a complete pathfind one.

LOCAL ONLY: no model call, no network (#433). numpy + PIL, the same as classify.py.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import classify  # noqa: E402
from PIL import Image  # noqa: E402
import numpy as np  # noqa: E402

SIG = (16, 12)                 # pathfind.py's SIG: grey, box-averaged, FPS corner masked
SIG_MATCH = 9.0                # pathfind.py's: mean grey-level distance under which two screens are the same
WINDOW = 4                     # replay looks this many steps past its cursor (pathfind.py's replay())
REPO_PATHS = os.path.join(HERE, "pathknow", "paths")
UNCHANGED = 0.01               # pathfind.py's: a motion fraction under this is a screen that did not move
# pathfind.py's Agent.MENU_STATES: a step on one of these is a menu step when the trail
# has no `menu` field (a pathfind-built path)
MENU_STATES = ("title_screen", "main_menu", "submenu", "save_load_prompt", "controller_prompt",
               "name_entry", "profile_creation", "publisher_logo")


def signature(path):
    """pathfind.py's signature(): the same numbers for the same frame, so either
    builder's steps match either runner's captures."""
    g = classify.masked(classify.open_grey(path), [classify.FPS_CORNER])
    return np.asarray(g.resize(SIG, Image.BOX), dtype=np.float32)


def sig_dist(a, b):
    return float(np.abs(np.asarray(a, dtype=np.float32) - np.asarray(b, dtype=np.float32)).mean())


def sig_list(sig):
    return [[int(round(float(v))) for v in row] for row in np.asarray(sig)]


def paths_dir():
    return os.environ.get("HAKUX_PATHS_DIR") or None


def _read(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def load(tid, dirs=None):
    """The path to replay for title id `tid`: the higher-scoring of the drive-built one
    (HAKUX_PATHS_DIR) and the repo's pathfind-built one, the drive one on a tie; None if
    neither exists. Returns (path dict, file)."""
    best = (None, None)
    if not tid:
        return best
    for d in (dirs if dirs is not None else [paths_dir(), REPO_PATHS]):
        if not d:
            continue
        f = os.path.join(d, "%s.json" % tid.upper())
        p = _read(f)
        if p and p.get("steps") and (best[0] is None or score(p) > score(best[0])):
            best = (p, f)
    return best


def match(steps, cursor, sig, skip=()):
    """A replayable step whose screen matches `sig`, at or a little past `cursor`:
    (index, step) or None. Gameplay steps are never replayed: a book ends where play
    begins, and play is the policy's job."""
    for j in range(cursor, min(cursor + WINDOW, len(steps))):
        s = steps[j]
        if j in skip or s.get("sig") is None or not s.get("useful", True) or s.get("state") == "gameplay":
            continue
        if sig_dist(s["sig"], sig) <= SIG_MATCH:
            return j, s
    return None


def _later(order, a, b):
    """True when state b is later than state a in the profile's order."""
    return a in order and b in order and order.index(b) > order.index(a)


def build(trail, order, meta):
    """The path (pathfind.py's schema) from one run's trail. `meta`: title_id, name,
    device, result, complete, time_to_play_s, furthest, run."""
    kept = []
    for e in trail:
        if e.get("in_play"):
            break
        if e.get("sig") is None or e.get("after_state") is None:
            continue
        moved = (e.get("after_d") or 0.0) > SIG_MATCH
        nudged = bool(e.get("menu")) and (e.get("after_changed") or 0.0) > UNCHANGED
        if not (moved or nudged or _later(order, e["state"], e["after_state"])):
            continue
        for k, prev in enumerate(kept):
            loop = kept[k:]
            if (sig_dist(prev["sig"], e["sig"]) <= SIG_MATCH
                    and any(sig_dist(prev["sig"], q["sig"]) > SIG_MATCH for q in loop[1:])
                    and not any(q.get("menu") for q in loop)):
                kept = kept[:k]          # left this screen and came back to it: the loop is cut
                break
        kept.append(e)
    steps, last = [], 0.0
    for e in kept:
        steps.append(dict(state=e.get("cls") or e["state"], why=(e.get("why") or "")[:160],
                          action=e["button"].split(), menu=bool(e.get("menu")), at_s=round(e["t"], 1),
                          wait_s=round(e["t"] - last, 1), useful=True, sig=sig_list(e["sig"])))
        last = e["t"]
    complete = bool(meta.get("complete"))
    return dict(title_id=(meta.get("title_id") or "").upper(), name=meta.get("name"), device=meta.get("device"),
                recorded=time.strftime("%Y-%m-%d %H:%M %Z"), builder="drive", run=meta.get("run"),
                minutes=None if meta.get("time_to_play_s") is None else round(meta["time_to_play_s"] / 60.0, 2),
                time_to_play_s=meta.get("time_to_play_s"), furthest=99 if complete else meta.get("furthest", -1),
                model_calls=0, complete=complete, result=meta.get("result"), steps=steps)


FURTHEST_PATHFIND = 98         # an unfinished pathfind path: above any `order` index (see BETTER)


def score(p):
    """(complete, furthest, -seconds to play). pathfind's paths carry `minutes`, not
    `time_to_play_s`, and no `furthest`: a complete one ranks as furthest, an
    unfinished one as FURTHEST_PATHFIND."""
    if not p:
        return (False, -2, -1e12)
    secs = p.get("time_to_play_s")
    if secs is None and p.get("minutes") is not None:
        secs = float(p["minutes"]) * 60.0
    complete = bool(p.get("complete"))
    if complete:
        furthest = 99
    elif p.get("builder") != "drive":
        furthest = FURTHEST_PATHFIND
    else:
        furthest = p.get("furthest")
    return (complete, furthest if furthest is not None else -1, -(secs if secs is not None and complete else 1e12))


def save(path, dest_dir):
    """Write `path` as dest_dir/<TID>.json if it scores higher than what load() would
    replay now. Returns (written, why)."""
    tid = path.get("title_id")
    if not tid or not dest_dir:
        return False, "no title id or no paths dir"
    if not path.get("steps"):
        return False, "no step did anything before play"
    cur, f = load(tid, [dest_dir, REPO_PATHS])
    if score(path) <= score(cur):
        return False, "kept %s (score %s >= this run's %s)" % (f, score(cur), score(path))
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "%s.json" % tid)
    tmp = dest + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(path, fh, indent=0)
        fh.write("\n")
    os.replace(tmp, dest)
    return True, "wrote %s (%d steps, score %s over %s)" % (dest, len(path["steps"]), score(path), score(cur))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("result_dir")
    b.add_argument("--title-id", required=True)
    b.add_argument("--dir", default=paths_dir())
    b.add_argument("--dry-run", action="store_true", help="print the path, write nothing")
    s = sub.add_parser("show")
    s.add_argument("title_id")
    s.add_argument("--dir", default=paths_dir())
    a = ap.parse_args(argv)
    if a.cmd == "show":
        p, f = load(a.title_id, [a.dir, REPO_PATHS])
        if not p:
            print("pathbook: no path for %s" % a.title_id)
            return 1
        print("%s  complete=%s builder=%s score=%s" % (f, p.get("complete"), p.get("builder", "pathfind"), score(p)))
        for j, st in enumerate(p["steps"]):
            print("  %2d  %-18s %-14s wait %5.1f  %s" % (j, st.get("state"), " ".join(st.get("action") or []),
                                                       st.get("wait_s") or 0, "" if st.get("useful", True) else "(not useful)"))
        return 0
    tr = _read(os.path.join(a.result_dir, "route-trail.json"))
    if not tr:
        print("pathbook: no route-trail.json in %s" % a.result_dir)
        return 1
    p = build(tr["trail"], tr.get("order", []), dict(tr.get("meta", {}), title_id=a.title_id))
    if a.dry_run:
        print(json.dumps(dict(p, steps=[dict(st, sig="...") for st in p["steps"]]), indent=1))
        return 0
    ok, why = save(p, a.dir)
    print("pathbook: %s" % why)
    return 0


if __name__ == "__main__":
    sys.exit(main())
