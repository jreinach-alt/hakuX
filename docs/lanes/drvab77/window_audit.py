#!/usr/bin/env python3
"""Did anything but this lane run on the thor while a swapped driver was on it?

`swap_driver.sh` is an out-of-band adb write. While T26 or the stock Adreno
driver is installed, EVERY request the dispatcher claims for that device runs
on it, and nothing in the other lane's result would say so. This lists every
result directory whose run OVERLAPS one of the two swap windows and flags any
that is not one of this lane's four runs.

OVERLAP, NOT FINISH TIME. The first version of this file asked `window_start
<= mtime <= window_end`, i.e. "did it FINISH inside the window". That misses
the largest-exposure case there is: a request claimed before the window opens
and finishing after T30 is restored spends its whole measurement on the
swapped driver and its mtime is in neither window. A run is exposed if
`start <= window_end and end >= window_start`, which is what is tested here.

The two timestamps:
  * START is `request.json`'s `queued_utc`, falling back to the epoch prefix
    of the result id (the two agree on every dir this lane checked; 604 of
    the 968 dirs on disk carry no epoch prefix at all, and 142 carry no
    `queued_utc`, so both readers are needed). Queue time is at or before the
    run began, so an overlap test on it is conservative: it can over-report
    exposure, never under-report it.
  * END is the directory mtime, as before.
  * A dir with NEITHER start is not dropped. Exposure needs `end >= window
    start`, and that half is testable without a start, so such a dir is
    listed with start `?` whenever its mtime is at or after the window
    opened. This file exists to find what it was not expecting; an
    unreadable directory has to be loud rather than quietly absent.

AND THEN A SECOND DISCRIMINATOR, BECAUSE QUEUE TIME IS NOT RUN TIME. A
request can sit in `queue/` for hours -- `1789893938-arms-remote-base-4039343`
was queued 01:45 and ran 21:53-22:00 on the thor -- so `[queued, done]` spans
both of this lane's windows while the run itself was nowhere near them. A
check that calls that CONTAMINATED is the same defect as a gap detector that
fires on every run: it is always right and therefore never read. So each
candidate is also asked when the WORKER first wrote into the directory
(`request.json` excluded -- the dispatcher writes that at queue time). A first
artifact more than `seconds + RUN_SLACK` after a window closed means the run
began after the window and is reported as QUEUED-THRU rather than EXPOSED.
Nothing is dropped by this: both classes are listed, and only EXPOSED counts
as contamination.

An empty flag list is reported as an empty flag list. It is evidence that
this particular pair of windows was clean, not that the practice is safe.

THE WINDOW BOUNDS ARE THE ONE THING THIS CANNOT DERIVE. `swap_driver.sh`
writes no log and no marker file -- it is an adb push and nothing else -- so
the bounds below are what the operator recorded at the time and a later
reader has no artifact to check them against. Overridable via `--window` so
the next driver experiment does not have to edit the file; the real fix is
R6's, a `driver` field on the request that the worker installs and restores,
which would leave the dispatcher's own log as the record.

    python3 window_audit.py [--results DIR] [--window TAG:START:END ...]
                            [--mine REQUESTER ...]
"""
import argparse
import calendar
import json
import os
import re
import time

D_DEFAULT = os.environ.get("HAKUX_RESULTS",
                           "/home/justin/hakux-work/dispatch/results")

# Epoch bounds, recorded by the operator at the time: swap verified -> T30
# restored. No artifact backs these; see the docstring.
WINDOWS = [("t26", 1789949701, 1789950285),
           ("stock", 1789950291, 1789950990)]

MINE = {"drvab77-t26-1", "drvab77-t26-2",
        "drvab77-stock-1", "drvab77-stock-2"}

ID_EPOCH = re.compile(r"^(\d{9,})-")

# How long before its first artifact a run may have been executing: boot,
# install, the emulator coming up. Deliberately generous (10 min against a
# 220 s soak) because this slack is what protects against calling an exposed
# run QUEUED-THRU, and that is the error that loses a contamination.
RUN_SLACK = 600


def queued_epoch(name, req):
    """When the run was QUEUED: `queued_utc` first, then the id's own prefix.

    Returns None when neither is present, which is a real case on this disk
    (a hand-made directory, or one from before the field existed).
    """
    q = (req or {}).get("queued_utc")
    if q:
        try:
            return calendar.timegm(time.strptime(q, "%Y-%m-%dT%H:%M:%SZ"))
        except ValueError:
            pass
    m = ID_EPOCH.match(name)
    return int(m.group(1)) if m else None


def first_artifact(dirpath):
    """When the worker first wrote into this result dir, or None.

    A time the run demonstrably WAS executing. `request.json` is excluded
    because the dispatcher writes it when the request is queued, which may be
    many hours earlier.
    """
    ts = []
    try:
        names = os.listdir(dirpath)
    except OSError:
        return None
    for f in names:
        if f == "request.json":
            continue
        try:
            ts.append(os.path.getmtime(os.path.join(dirpath, f)))
        except OSError:
            pass
    return min(ts) if ts else None


def began_after(window_end, art, seconds):
    """True if the run's own artifacts put its start after the window closed.

    False whenever that cannot be shown -- no artifact, or a first write early
    enough that the run could have been under way inside the window.
    """
    if art is None:
        return False
    return art - (seconds or 0) - RUN_SLACK > window_end


def overlaps(start, end, a, b):
    """True if a run [start, end] touches window [a, b] at all.

    With no start, the `start <= b` half cannot be evaluated, so the run is
    reported whenever the half that CAN be evaluated holds -- a run that
    finished before the window opened was provably never exposed, and one
    that finished after it opened might have been.
    """
    if start is None:
        return end >= a
    return start <= b and end >= a


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=D_DEFAULT)
    ap.add_argument("--window", action="append", metavar="TAG:START:END",
                    help="repeatable; overrides the recorded windows")
    ap.add_argument("--mine", action="append", metavar="REQUESTER",
                    help="repeatable; overrides this lane's four requesters")
    args = ap.parse_args(argv)

    windows = WINDOWS
    if args.window:
        windows = []
        for w in args.window:
            tag, a, b = w.split(":")
            windows.append((tag, int(a), int(b)))
    mine = set(args.mine) if args.mine else MINE

    def fmt(t):
        return "?" if t is None else time.strftime("%H:%M:%S",
                                                   time.localtime(t))

    rows, exposed, foreign = [], [], []
    for n in sorted(os.listdir(args.results)):
        rdir = os.path.join(args.results, n)
        rp = os.path.join(rdir, "request.json")
        if not os.path.exists(rp):
            continue
        try:
            req = json.load(open(rp))
        except ValueError:
            continue
        try:
            end = os.path.getmtime(rdir)
        except OSError:
            continue
        start = queued_epoch(n, req)
        art = None
        for tag, a, b in windows:
            if not overlaps(start, end, a, b):
                continue
            if art is None:
                art = first_artifact(rdir)
            who = (req.get("requester") or "?")
            late = began_after(b, art, req.get("seconds"))
            row = ("QUEUED-THRU" if late else "EXPOSED", tag, fmt(start),
                   fmt(art), fmt(end), who,
                   req.get("device") or "(unpinned)", n)
            rows.append(row)
            if not late:
                exposed.append(row)
                if who not in mine:
                    foreign.append(row)

    hdr = ("state", "window", "queued", "1st art", "done", "requester",
           "device", "result")
    print("  %-11s %-6s %-8s %-8s %-8s %-18s %-10s %s" % hdr)
    for r in sorted(rows, key=lambda x: x[4]):
        print("  %-11s %-6s %-8s %-8s %-8s %-18s %-10s %s" % r)
    print("%d run(s) overlapped a swap window by queue time; %d were "
          "executing inside one; %d of those are not this lane's"
          % (len(rows), len(exposed), len(foreign)))
    for f in foreign:
        print("  FOREIGN: %s -- that lane's result was measured on a driver "
              "it did not ask for" % (f,))
    for r in rows:
        if r not in exposed:
            print("  queued through a window but first wrote at %s, after it "
                  "closed: %s" % (r[3], r[7]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
