#!/usr/bin/env python3
"""Did anything but this lane run on the thor while a swapped driver was on it?

`swap_driver.sh` is an out-of-band adb write. While T26 or the stock Adreno
driver is installed, EVERY request the dispatcher claims for that device runs
on it, and nothing in the other lane's result would say so. This lists every
result directory that finished inside one of the two swap windows and flags
any that is not one of this lane's four runs.

An empty flag list is reported as an empty flag list. It is evidence that
this particular pair of windows was clean, not that the practice is safe.

    python3 window_audit.py
"""
import json
import os
import time

D = "/home/justin/hakux-work/dispatch/results"

# Epoch bounds, recorded at the time: swap verified -> T30 restored.
WINDOWS = [("t26", 1789949701, 1789950285),
           ("stock", 1789950291, 1789950990)]

MINE = {"drvab77-t26-1", "drvab77-t26-2",
        "drvab77-stock-1", "drvab77-stock-2"}


def main():
    rows, foreign = [], []
    for n in sorted(os.listdir(D)):
        rp = os.path.join(D, n, "request.json")
        if not os.path.exists(rp):
            continue
        try:
            req = json.load(open(rp))
        except ValueError:
            continue
        try:
            mt = os.path.getmtime(os.path.join(D, n))
        except OSError:
            continue
        for tag, a, b in WINDOWS:
            if a <= mt <= b:
                who = (req.get("requester") or "?")
                rows.append((tag, time.strftime("%H:%M:%S", time.localtime(mt)),
                             who, req.get("device") or "(unpinned)", n))
                if who not in MINE:
                    foreign.append(rows[-1])

    for r in sorted(rows, key=lambda x: x[1]):
        print("  %-6s %s  %-18s %-10s %s" % r)
    print("%d run(s) finished inside a swap window; %d not this lane's"
          % (len(rows), len(foreign)))
    for f in foreign:
        print("  FOREIGN: %s -- that lane's result was measured on a driver "
              "it did not ask for" % (f,))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
