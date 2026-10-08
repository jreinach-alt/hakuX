#!/usr/bin/env python3
"""stuckdetect.py -- a stuck/menu detector for pathfind's 600-s hold (#433).

    stuckdetect.py selftest                 stdlib-only synthetic legs: no image, no PIL/numpy
    stuckdetect.py validate                 replays stored hold runs (needs PIL/numpy and the
                                             run dirs; skips, never fails, when either is absent)

The 600 s hold (docs/testing/titles/pathfind.py, hold_play) sends a model-free genre loop of
inputs and looks at the screen only every HOLD_CHECK_S (90 s), or when it suspects play ended.
Three Nova runs on 2026-10-07 burned 30-40 min each stuck where the existing checks did not
catch it:

  Arx Fatalis (n-44430002-1007): the view pressed to a wall; every hold_look call read the
    screen as "gameplay" (12 of 12 checks), so the look-state signal never saw a problem, and
    the offline position check (hitch_report.position_change) compares first-vs-last and a
    consecutive-pairs share, not every sample pair; a jittering camera against a wall can still
    pass it on a lucky draw.
  Cel Damage (n-45410011-1007): a car against a canyon wall.
  Gui Yi (n-58500001-1007): the genre loop's own A/X presses walked the player back into a
    merchant NPC and reopened its shop; HOLD_SHED sheds one loop button, but only on the single
    frame play flips to off (`if off and was_play`) -- once off-play persists, `was_play` is
    false on every later check, so a second, better shed never fires. hold.jsonl for this run
    shows exactly one shed (n=67, hold_s 565) then 229 more "menu" checks over the next ~1700 s,
    trying A, START and B in turn with no escape: the menu was not reopened by one fixed button,
    it was reopened by the loop's own walk-back-into-the-NPC movement, which no button-shed can
    fix (see NOTES.md, "why HOLD_SHED did not fire for Gui Yi").

This module is a standalone, importable piece with no pathfind.py or classify.py dependency (a
territory boundary: those are lane.pathfind's and lane.local's files). It needs numpy/PIL to
read real frames (frame_signature), but every stuck/menu/cluster decision operates on plain
Signature tuples, so the CI selftest runner (which has neither) can drive it with synthetic
signatures and never touch an image file.

HOOK API (what pathfind.py's hold_play would call once a grant lands the integration):

    sig = frame_signature(jpg_or_png_path)              # needs PIL/numpy
    history.append(sig)
    decision = stuck_step(history, genre, rung=rung, menu_states=states_history)
    if decision["stuck"]:
        if decision["abort"]:
            ...  # stuck_abort: end the run early, a FAIL with telemetry, not a Playable
        else:
            send(decision["action"]); rung += 1
    else:
        rung = 0  # unstuck: reset the ladder

See `stuck_step` and `StuckWatch` (a thin stateful wrapper around it) below.
"""

import glob
import os
import sys
from collections import namedtuple

try:
    import numpy as np
    from PIL import Image
except ImportError:
    np = None
    Image = None

# ---------------------------------------------------------------- signature

GRID = (16, 12)      # grey grid shape: same as pathfind.SIG, so a grey_bar carries over if merged
HIST_BINS = 8         # coarse grey-level histogram buckets
CORNER_FRAC = (0.10, 0.06)   # top-left (width frac, height frac) blacked out: the FPS: NN overlay

Signature = namedtuple("Signature", "grid hist")


def _mask_corner(arr):
    """Zero the top-left FPS-overlay corner of a 2-D grey array, in place semantics (returns a
    copy): the overlay's own digits change every frame and would read as "changed" on an
    otherwise frozen wall or menu, masking the exact signal this module exists to catch."""
    h, w = arr.shape
    cw, ch = int(w * CORNER_FRAC[0]), int(h * CORNER_FRAC[1])
    arr = arr.copy()
    arr[:ch, :cw] = 0
    return arr


def frame_signature(path):
    """A Signature from an image file: a GRID-shaped box-averaged grey map (FPS corner masked)
    and a HIST_BINS-bucket grey-level histogram, both as plain float tuples. Needs PIL/numpy;
    raises ImportError if neither is importable (callers should catch this and skip, same as
    hitch_report.static_window does for an unmeasured window)."""
    if np is None or Image is None:
        raise ImportError("stuckdetect.frame_signature needs PIL and numpy")
    im = Image.open(path)
    im.load()
    grey = im.convert("L")
    arr = np.asarray(grey, dtype=np.float32)
    arr = _mask_corner(arr)
    small = np.asarray(Image.fromarray(arr.astype(np.uint8)).resize(GRID, Image.BOX), dtype=np.float32)
    hist, _ = np.histogram(arr, bins=HIST_BINS, range=(0, 255))
    total = hist.sum()
    hist = (hist / total) if total else hist.astype(np.float64)
    return Signature(grid=tuple(float(v) for v in small.flatten()), hist=tuple(float(v) for v in hist))


def sig_distance(a, b):
    """(grid_dist, hist_dist): grid_dist is the mean abs grey-level difference over GRID cells
    (0-255 scale, directly comparable to pathfind.SIG_MATCH=9.0); hist_dist is half the L1
    distance between the two histograms (0: identical, 1: disjoint)."""
    grid_d = sum(abs(x - y) for x, y in zip(a.grid, b.grid)) / len(a.grid)
    hist_d = sum(abs(x - y) for x, y in zip(a.hist, b.hist)) / 2.0
    return grid_d, hist_d


# near-identical bars, both set from the validation table in NOTES.md (14 stored hold runs: 3
# must-flag stuck/menu runs, 11 banked Playables). pathfind's own SIG_MATCH (9.0 mean grey-level
# distance) is "the same menu screen" for its replay matcher, but that bar is too loose here: a
# dark-hangar patrol (Blowout, a banked Playable) sits at 8.7-9.3 between real steps and false-
# triggered a 4-sample run at 9.0. GRID_BAR in [6, 8] cleanly separates every must-flag run
# (shortest true stuck run: 5 consecutive samples, Cel Damage) from every must-not-flag run
# (longest incidental run: 3, Blowout's dark patrol) at any HIST_BAR in [0.03, 0.08]; 7.0 is the
# middle of that clean range, with a 2-sample margin either side.
GRID_BAR = 7.0
HIST_BAR = 0.05


def near_identical(a, b, grid_bar=GRID_BAR, hist_bar=HIST_BAR):
    grid_d, hist_d = sig_distance(a, b)
    return grid_d <= grid_bar and hist_d <= hist_bar


# ------------------------------------------------------------------- stuck

STUCK_MIN_SAMPLES = 4   # near-identical for this many consecutive kept samples (~20-30 s cadence) = stuck


def stuck_run(history, grid_bar=GRID_BAR, hist_bar=HIST_BAR):
    """The length of the current run of consecutive near-identical samples ending at the last
    element of `history` (a list of Signature, chronological, oldest first). 0 or 1 when there
    are too few samples or the last pair already differs."""
    if len(history) < 2:
        return len(history)
    run = 1
    for i in range(len(history) - 1, 0, -1):
        if near_identical(history[i], history[i - 1], grid_bar, hist_bar):
            run += 1
        else:
            break
    return run


def is_stuck(history, min_samples=STUCK_MIN_SAMPLES, grid_bar=GRID_BAR, hist_bar=HIST_BAR):
    """(bool, run_length): True when the last `min_samples` kept samples are ALL pairwise
    consecutive near-identical -- every step in the window stayed still, not just its first and
    last frame (the weaker rule a first-vs-last-only check applies; see
    docs/lanes/stuckdetect1007/NOTES.md for why Arx Fatalis's jittering wall view can still pass
    a first-vs-last test)."""
    run = stuck_run(history, grid_bar, hist_bar)
    return run >= min_samples, run


# -------------------------------------------------------------- menu-stuck

def menu_stuck(history, states, shed_states, min_samples=STUCK_MIN_SAMPLES, grid_bar=GRID_BAR, hist_bar=HIST_BAR):
    """True when the trailing `min_samples` samples are near-identical (stuck()) AND every
    look-state recorded over that same span is one of `shed_states` (pathfind's HOLD_SHED_STATES:
    menu, pause, other). `states` is a list parallel to `history`, each entry the hold_look
    state string for that sample or None (play, or no look taken that cycle: a None breaks the
    "every look agrees" test, since an untouched play sample cannot be read as a menu)."""
    stuck, run = is_stuck(history, min_samples, grid_bar, hist_bar)
    if not stuck:
        return False
    tail = states[-run:]
    return bool(tail) and all(s in shed_states for s in tail)


# --------------------------------------------------------------- distinct views

def distinct_views(history, bar=GRID_BAR):
    """Count of distinct scene clusters over the whole hold: a single-pass greedy clustering
    (each sample joins the first existing cluster whose representative is within `bar`, else
    starts a new one). This is the whole-hold counterpart to is_stuck's trailing window: a run
    that wanders between two or three near-identical corners (a wall-pressed loop that steers
    into a different wall every few minutes) can still fail every trailing-window stuck test
    while visiting almost nothing new -- the position check this module reports alongside the
    existing first-vs-last test."""
    reps = []
    for sig in history:
        if not any(sig_distance(sig, r)[0] <= bar for r in reps):
            reps.append(sig)
    return len(reps)


# ------------------------------------------------------------------- the hook

def stuck_step(history, genre, rung=0, states=None, shed_states=(), unstick_ladder=None,
                fallback_ladder=(), min_samples=STUCK_MIN_SAMPLES, max_rungs=3):
    """The hook pathfind.py's hold_play calls once per kept sample.

    history: list of Signature, chronological, oldest first (the hold's kept frames, one every
        HOLD_FRAME_S, or the cheaper hold.jsonl cadence -- either works, both are tested).
    genre: the HOLD_GENRES key in use; only used to label the decision, the caller supplies the
        actual ladder (see unstick_ladder/fallback_ladder) so this module never hardcodes a copy
        of pathfind.HOLD_UNSTICK that could drift from the real one.
    rung: how many unstick attempts have already been sent in the CURRENT stuck episode (0 on
        first detection; the caller increments it after sending an action and resets it to 0 the
        moment is_stuck/menu_stuck goes false again).
    states: optional list parallel to `history`, each entry the last hold_look state for that
        sample or None; when given, a menu-stuck episode is reported with menu=True and its
        action is a "back out" action (B) rather than the genre's positional unstick ladder.
    shed_states: pathfind.HOLD_SHED_STATES-equivalent set ("menu", "pause", "other"), required
        to use the menu path; without it only the positional stuck test runs.
    unstick_ladder: the genre's own unstick sequence (pathfind.HOLD_UNSTICK[genre], a list of
        token-lists), when the genre has one.
    fallback_ladder: tokens to try one at a time when the genre has no unstick_ladder (pathfind's
        UNLOCK_LADDER), each wrapped in its own single-token list.
    max_rungs: ladder rungs to try before a stuck_abort (owner: an early FAIL with telemetry, not
        a blind rerun -- never a Playable).

    Returns {"stuck": False} when nothing is wrong, else a dict with "stuck": True, "menu": bool,
    "run": the trailing near-identical run length, "reason": a one-line string, "action": the
    next rung's tokens (None when the ladder is exhausted), "abort": True once `rung` has already
    used every rung without a change."""
    stuck, run = is_stuck(history, min_samples)
    if not stuck:
        return {"stuck": False, "run": run}
    menu = bool(states) and menu_stuck(history, states, shed_states, min_samples)
    ladder = list(unstick_ladder) if unstick_ladder else [[t] for t in fallback_ladder]
    ladder = ladder[:max_rungs] if ladder else []
    reason = (f"menu/pause/other unchanged for {run} consecutive samples" if menu
              else f"scene unchanged for {run} consecutive samples (genre {genre})")
    if not ladder or rung >= len(ladder):
        return {"stuck": True, "menu": menu, "run": run, "reason": reason, "action": None, "abort": True}
    action = ["B"] + ladder[rung] if menu else ladder[rung]
    return {"stuck": True, "menu": menu, "run": run, "reason": reason, "action": action, "abort": False}


class StuckWatch:
    """A thin stateful wrapper around stuck_step: keeps the trailing history, the look-state
    list and the current ladder rung, so a caller only has to feed samples in and read actions
    out. Not required -- stuck_step is the documented hook -- but it is what pathfind.py's loop
    would actually hold if this is wired in."""

    def __init__(self, genre, shed_states=(), unstick_ladder=None, fallback_ladder=(),
                 min_samples=STUCK_MIN_SAMPLES, max_rungs=3, keep=12):
        self.genre = genre
        self.shed_states = shed_states
        self.unstick_ladder = unstick_ladder
        self.fallback_ladder = fallback_ladder
        self.min_samples = min_samples
        self.max_rungs = max_rungs
        self.keep = keep
        self.history = []
        self.states = []
        self.rung = 0

    def sample(self, sig, state=None):
        self.history.append(sig)
        self.states.append(state)
        if len(self.history) > self.keep:
            self.history.pop(0)
            self.states.pop(0)
        decision = stuck_step(self.history, self.genre, self.rung, self.states, self.shed_states,
                              self.unstick_ladder, self.fallback_ladder, self.min_samples, self.max_rungs)
        self.rung = 0 if not decision["stuck"] else self.rung + (0 if decision["abort"] else 1)
        return decision


# -------------------------------------------------------------------- selftest

def _sig(grid_val, hist=None):
    """A synthetic Signature: every grid cell at `grid_val`, a one-hot histogram (or the given
    one). No image decode anywhere in this helper -- the selftest never needs PIL/numpy."""
    n = GRID[0] * GRID[1]
    if hist is None:
        bucket = min(HIST_BINS - 1, int(grid_val / 256 * HIST_BINS))
        hist = tuple(1.0 if i == bucket else 0.0 for i in range(HIST_BINS))
    return Signature(grid=tuple(float(grid_val) for _ in range(n)), hist=hist)


def selftest():
    fails = []

    def check(name, cond):
        print(("ok   " if cond else "FAIL ") + name)
        if not cond:
            fails.append(name)

    # 1. identical signatures are near-identical; a big jump is not
    a, b, c = _sig(100), _sig(101), _sig(220)
    check("near-identical: same grid and bucket", near_identical(a, b))
    check("not near-identical: a big grey jump", not near_identical(a, c))

    # 2. is_stuck: 4 consecutive near-identical samples trips, 3 does not
    still = [_sig(100), _sig(100), _sig(101), _sig(100)]
    stuck, run = is_stuck(still)
    check("4 consecutive near-identical samples: stuck", stuck and run == 4)
    stuck3, _ = is_stuck(still[1:])
    check("3 consecutive near-identical samples: not yet (min_samples=4)", not stuck3)

    # 3. a moving scene (a real Playable) never trips, however long the history
    moving = [_sig(v) for v in (20, 90, 150, 60, 200, 30, 170, 80, 210, 40)]
    check("a moving scene never trips is_stuck", not is_stuck(moving)[0])

    # 4. one differing sample in the middle breaks the run (Black Stone's sword swing: small but
    # real per-step motion must not look identical to a wall)
    jitter = [_sig(100), _sig(100), _sig(140), _sig(100), _sig(100)]
    check("a real mid-window change breaks the stuck run", stuck_run(jitter) < STUCK_MIN_SAMPLES)

    # 5. menu_stuck: same signature AND every look-state in the window is a shed state
    menu_hist = [_sig(50)] * 5
    menu_states = ["menu", "menu", "menu", "menu", "menu"]
    check("menu_stuck: unchanged screen, every look a menu/pause/other",
          menu_stuck(menu_hist, menu_states, ("menu", "pause", "other")))
    mixed_states = [None, "menu", "gameplay", "menu", "menu"]
    check("menu_stuck: a 'gameplay' look in the window breaks it",
          not menu_stuck(menu_hist, mixed_states, ("menu", "pause", "other")))

    # 6. distinct_views: a hold that only ever visits two corners counts 2, a wandering one many
    two_corners = [_sig(40), _sig(40), _sig(200), _sig(200), _sig(41), _sig(199)]
    check("distinct_views: two corners, back and forth, counts 2", distinct_views(two_corners) == 2)
    wander = [_sig(v) for v in (10, 60, 110, 160, 210, 250)]
    check("distinct_views: six well-spread samples count 6", distinct_views(wander) == 6)

    # 7. stuck_step: the positional ladder, genre WITH an unstick_ladder (drive-style)
    ladder = [["LT+left:3", "RT+right:3"], ["LT+right:3", "RT+left:3"]]
    hist = [_sig(100)] * 4
    d0 = stuck_step(hist, "drive", rung=0, unstick_ladder=ladder)
    check("stuck_step rung 0: the ladder's first rung, not aborted",
          d0["stuck"] and not d0["abort"] and d0["action"] == ladder[0])
    d1 = stuck_step(hist, "drive", rung=1, unstick_ladder=ladder)
    check("stuck_step rung 1: the ladder's second rung", d1["action"] == ladder[1])
    d2 = stuck_step(hist, "drive", rung=2, unstick_ladder=ladder, max_rungs=2)
    check("stuck_step past the ladder (max_rungs=2): abort, no action",
          d2["abort"] and d2["action"] is None)

    # 8. stuck_step: genre with NO unstick_ladder falls back to single-token rungs
    fb = ("X", "B", "Y")
    d0 = stuck_step(hist, "team", rung=0, fallback_ladder=fb)
    check("stuck_step fallback ladder rung 0", d0["action"] == ["X"])
    d2 = stuck_step(hist, "team", rung=2, fallback_ladder=fb)
    check("stuck_step fallback ladder rung 2", d2["action"] == ["Y"])

    # 9. stuck_step: a menu episode prefixes B to the ladder rung, so the caller backs out first
    dm = stuck_step(hist, "other", rung=0, states=["menu"] * 4, shed_states=("menu", "pause", "other"),
                     fallback_ladder=fb)
    check("stuck_step menu episode: B is prefixed to the rung's action",
          dm["menu"] and dm["action"][0] == "B" and dm["action"][1:] == ["X"])

    # 10. stuck_step: not stuck at all when the scene keeps changing
    dn = stuck_step(moving, "drive", unstick_ladder=ladder)
    check("stuck_step: a moving history is never stuck", not dn["stuck"])

    # 11. the fixture a "first vs last only" rule (hitch_report.position_fail's own shape, kept
    # on the offline verdict; see NOTES.md) gets WRONG: Arx Fatalis's wall-pressed camera drifts a
    # little every sample (never still enough for a frame-to-frame diff to look dramatic) but
    # never actually goes anywhere -- each step is under GRID_BAR, the accumulated drift over the
    # window is not. A first-vs-last check reads "far enough apart: still moving" and clears it;
    # is_stuck must not be fooled the same way.
    drifting_wall = [_sig(v) for v in (100, 103, 106, 109, 112)]
    first_last_d = abs(drifting_wall[0].grid[0] - drifting_wall[-1].grid[0])
    check("fixture is honest: first and last differ by more than GRID_BAR (a weak rule clears it)",
          first_last_d > GRID_BAR)
    check("fixture is honest: every consecutive pair is still near-identical",
          all(near_identical(drifting_wall[i], drifting_wall[i + 1]) for i in range(len(drifting_wall) - 1)))
    check("is_stuck catches the drifting wall a first-vs-last check would clear",
          is_stuck(drifting_wall, min_samples=4)[0])

    if fails:
        print(f"stuckdetect selftest: {len(fails)} failed")
        return 1
    print("stuckdetect selftest: all ok")
    return 0


# --------------------------------------------------------------- offline validation

# The must-flag/must-not-flag table this module was tuned against (NOTES.md has the full
# numbers). Paths are relative to --runs-dir; the default is lane.pathfind's own run tree on
# this host, which will not exist in CI or on a clean checkout -- `validate` reports that as
# "skip", never as a failure, the same way hitch_report.static_window treats a window it cannot
# read as unmeasured rather than failed.
MUST_FLAG = {
    "n-44430002-1007": "Arx Fatalis (view pressed to a wall)",
    "n-45410011-1007": "Cel Damage (car against a canyon wall)",
    "n-58500001-1007": "Gui Yi (stuck in the shop menu)",
}
MUST_NOT_FLAG = {
    "n-4947007B-1007": "Indigo Prophecy",
    "n-41560005-1007": "Blade II",
    "n-43430008-1007": "Capcom vs SNK 2 EO",
    "n-43560007-1007": "Future Tactics: The Uprising",
    "armageddon1006d": "Mortal Kombat: Armageddon",
    "fightclub-1006": "Fight Club",
    "blowout-val2": "Blowout (dark hangar patrol: the closest false-positive risk)",
    "nbalive04-1006": "NBA Live 2004",
    "cod3-1006b": "Call of Duty 3",
    "sweep-5343000E": "Rogue Trooper",
    "sweep-54510109": "Ratatouille",
    "sweep-4B4E002F": "World Soccer Winning Eleven 9",
}
DEFAULT_RUNS_DIR = os.environ.get("STUCKDETECT_RUNS_DIR",
                                   "/home/justin/hakux-work/wt/pathfind/docs/lanes/pathfind/runs")


def kept_frame_paths(run_dir):
    """The hold's kept frames in time order: route-frames/*.png (pathfind.route_frame's hardlink
    name, HHMMSS-hold.png) when present, else `unmeasured` -- an older run (before route_frame()
    existed) or one with too few post-mark frames is not silently treated as clear."""
    return sorted(glob.glob(os.path.join(run_dir, "route-frames", "*.png")))


def evaluate_run(run_dir, min_samples=STUCK_MIN_SAMPLES, grid_bar=GRID_BAR, hist_bar=HIST_BAR):
    """-> dict: frames, flagged_at (1-based index of the first flag, or None), max_run,
    distinct_views; or {"unmeasured": reason} with too few kept frames to read."""
    frames = kept_frame_paths(run_dir)
    if len(frames) < min_samples:
        return {"unmeasured": f"{len(frames)} kept frame(s), need >= {min_samples}"}
    sigs = [frame_signature(f) for f in frames]
    flagged_at = None
    max_run = 0
    for i in range(1, len(sigs) + 1):
        stuck, run = is_stuck(sigs[:i], min_samples, grid_bar, hist_bar)
        max_run = max(max_run, run)
        if stuck and flagged_at is None:
            flagged_at = i
    return {"frames": len(frames), "flagged_at": flagged_at, "max_run": max_run,
            "distinct_views": distinct_views(sigs, grid_bar)}


def validate(runs_dir=DEFAULT_RUNS_DIR, must_flag=None, must_not_flag=None):
    """Print the must-flag/must-not-flag table and return 0 only if every must-flag run flags
    and every must-not-flag run stays clear. Any run dir missing, or PIL/numpy unavailable,
    is reported as skipped (never a failure: this is host-data-dependent, not CI-portable)."""
    if np is None or Image is None:
        print("stuckdetect validate: skip (no PIL/numpy on this host)")
        return 0
    must_flag = must_flag if must_flag is not None else MUST_FLAG
    must_not_flag = must_not_flag if must_not_flag is not None else MUST_NOT_FLAG
    print(f"{'run':55s} {'want':6s} {'frames':7s} {'flag@':7s} {'views':6s} {'max_run':7s}")
    ok, seen = True, 0
    for tid, (label, want) in {**{k: (v, "FLAG") for k, v in must_flag.items()},
                               **{k: (v, "clear") for k, v in must_not_flag.items()}}.items():
        run_dir = os.path.join(runs_dir, tid)
        if not os.path.isdir(run_dir):
            print(f"{label:55s} {want:6s} skip: {run_dir} not found")
            continue
        r = evaluate_run(run_dir)
        seen += 1
        if "unmeasured" in r:
            print(f"{label:55s} {want:6s} skip: {r['unmeasured']}")
            continue
        flagged = r["flagged_at"] is not None
        wrong = flagged != (want == "FLAG")
        ok = ok and not wrong
        mark = " <-- WRONG" if wrong else ""
        print(f"{label:55s} {want:6s} {r['frames']:<7d} {str(r['flagged_at']):7s} "
              f"{r['distinct_views']:<6d} {r['max_run']:<7d}{mark}")
    if seen == 0:
        print("stuckdetect validate: skip (no run dirs found under " + runs_dir + ")")
        return 0
    print("stuckdetect validate: " + ("all correct" if ok else "SEPARATION FAILED"))
    return 0 if ok else 1


def main(argv):
    if argv[:1] == ["selftest"]:
        return selftest()
    if argv[:1] == ["validate"]:
        return validate()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
