#!/usr/bin/env python3
"""Append the re-pilot section to the parked dir's README.md and to the repo copy.

The live README carries hostops' own lines (cold slot started, pilot failed),
so this appends rather than overwrites. Refuses to append twice.
Usage (from the worktree root): python3 docs/lanes/slowtier2/readme_append.py
"""
import os, sys

LIVE = "/home/justin/hakux-work/dispatch/parked/slowtier2-cold-20260928/README.md"
COPY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parked-README.md")
TEXT = """
RE-PILOT PARKED 09-28 ~10:5x PDT (lane.slowtier2): `1-1790615781-lane.slowtier2-otogi2870269.req`
in this dir. Otogi, same ref (97a6fa2b51), seconds (550), regimen (MAX) and
device as run 1; only the route differs: docs/lanes/slowtier2/routes/otogi.cold.route
presses START four times, 6 s apart, from +22 s (master's otogi.route presses
it once at +48 s). Run 1's first frame came at +4 s, 8 s earlier than the one
good run's (titleroutes-1129571, +12 s), so its START came ~37 s into the title
instead of ~28 s, and A never leaves the title. The route adds `shot title`
(+20 s) and `shot menu` (+50 s), and `mark gameplay` falls at ~+258 s.
Slot it FIRST, with a cold start, in place of run 1.

The other seven routes were checked against their last route-frames: every
`mark gameplay` frame shows play (MM3 1032854, Black 3358750, Burnout 1150288,
Alias 2113140, PGR 3587419, Crash 512742, BloodRayne 1530145r), and each
parked route is byte-identical to the route that run played. Those runs
logged their first frame at +4..+6 s, as run 1 did, except PGR (+22 s, three
STARTs 12-15 s apart) and MM3 (+54 s; the FMV before it is not counted, and
START at +39 s skips it). Neither turns on one START landing in a narrow window.

Order after the re-pilot is unchanged: run 2 (MM3) may follow it; runs 3-8
wait for `$DISPATCH_DIR/pilots/lane.slowtier2.ok`, which lane.slowtier2 writes
(and deletes PILOT-FAILED) only after reading the re-pilot's `gameplay` frame.
"""
for p in (LIVE, COPY):
    cur = open(p).read()
    if "RE-PILOT PARKED" in cur:
        sys.exit("already appended to %s" % p)
live = open(LIVE).read()
for p, base in ((LIVE, live), (COPY, live)):
    with open(p + ".tmp", "w") as f:
        f.write(base.rstrip("\n") + "\n" + TEXT)
    os.rename(p + ".tmp", p)
print("appended")
