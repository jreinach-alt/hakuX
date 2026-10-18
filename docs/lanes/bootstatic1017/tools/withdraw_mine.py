#!/usr/bin/env python3
"""Move this lane's own queued requests into dispatch/withdrawn/ and say why in its README.why.

usage: withdraw_mine.py REASON ID [ID ...]

Only an id that is in queue/ and names lane.bootstatic1017 is moved; one already running or done is left alone and
reported. Nothing is deleted.
"""
import os
import sys
import time

D = "/home/justin/hakux-work/dispatch"


def main():
    reason, ids = sys.argv[1], sys.argv[2:]
    moved = []
    for i in ids:
        if "lane.bootstatic1017" not in i:
            print("refused (not this lane's): %s" % i)
            continue
        src = os.path.join(D, "queue", i + ".req")
        if not os.path.exists(src):
            print("not in queue (running or done), left alone: %s" % i)
            continue
        os.rename(src, os.path.join(D, "withdrawn", i + ".req"))
        moved.append(i)
        print("withdrawn: %s" % i)
    if moved:
        with open(os.path.join(D, "withdrawn", "README.why"), "a") as f:
            f.write("\n%s (lane.bootstatic1017): %s withdrawn before they ran: %s\n" % (
                time.strftime("%Y-%m-%d %H:%M %Z"), ", ".join(m + ".req" for m in moved), reason))
    return 0


if __name__ == "__main__":
    sys.exit(main())
