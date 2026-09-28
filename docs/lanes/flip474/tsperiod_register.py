#!/usr/bin/env python3
"""Write the two device predictions for the timestamp-period calibration.

    python3 docs/lanes/flip474/tsperiod_register.py <a_ref> <b_ref>

Each file is serialised and parsed back before it is written.
"""
import json
import subprocess
import sys

A = subprocess.check_output(['git', 'rev-parse', sys.argv[1]]).decode().strip()
B = subprocess.check_output(['git', 'rev-parse', sys.argv[2]]).decode().strip()
NOW = subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ']).decode().strip()

NOTE = ("EMPTY ON PURPOSE: a soak writes no captures. The legs are read off "
        "the start-up 'GPU timestamp period' line and hakuX-phase lines "
        "(docs/lanes/flip474/phaseread.py), and the shots by eye.")
INERT = ["pgraph: docs/testing/predictions/flip474-tsperiod-pgraph-inert.json "
         "(12 suites, identical captures, same refs)"]


def legs(k1):
    return {
        "M0 (instrument)": ">= 30 hakuX-phase lines with GPU > 0 in the window "
        "in each run, and the route's shots show gameplay. Otherwise VOID, "
        "rerun once.",
        "K0 (the line)": "B's logcat has exactly one 'init: GPU timestamp "
        "period reported=' line, with an uncertainty (+-) under 1%. A has the "
        "old 'GPU timestamps enabled (period=' line. KILL: B has no such line, "
        "or it says 'not measured'.",
        "K1 (the value)": k1,
        "K2 (the choice)": "B's using= equals measured= when they differ by "
        "more than 2%, else reported=. A mismatch is a code bug: KILL.",
        "G1 (the stats follow)": "B's phase GPU median / A's phase GPU median "
        "is within 15% of (B's using= / A's period=). Same route and window, "
        "so the GPU work is the same to within the day's variation, and the "
        "ratio is the period's.",
        "G2 (physically possible)": "B's phase GPU median <= 1.05 x B's Tot "
        "median. A frame's GPU span cannot exceed the frame by more than the "
        "pipelining slack; a period set too long breaks this first.",
        "P1 (no regression)": "B gfps median >= A - 1. The change adds about "
        "100 ms once, at start-up.",
        "H0 (no hang)": "B: longest gap between hakuX-perf lines in the window "
        "<= 3 s, lines to the end, no tombstone in logcat -b crash.",
    }


def base(title, device, seconds, route, lo, hi):
    return {
        "registered_utc": NOW, "who": "lane.flip474", "issue": "474",
        "title": title, "device": device, "seconds": seconds, "route": route,
        "perflog": True, "frames_every": 0, "runs_per_arm": 1,
        "a_ref": A, "b_ref": B,
        "queue_order": "A1 B1, each request.sh --title, --device %s, --route "
        "%s, --seconds %d, --perflog, --expect this file"
        % (device, route, seconds),
        "judge": "grep 'GPU timestamp' logcat.txt in each result; python3 "
        "docs/lanes/flip474/phaseread.py --from %d --to %d <A1> <B1>; the "
        "route's shots in the window, by eye; logcat -b crash in each result"
        % (lo, hi),
        "must_not_move": INERT,
    }


doa = base("54430006-Dead_or_Alive_1_Ultimate.xiso.iso", "nova", 300,
           "survey", 151, 288)
doa["prediction"] = (
    "#474: the GPU timestamp period measured at start-up. On the Nova, "
    "o4clock.py fitted 52.083 ns per tick (19.200 MHz) against the CPU clock, "
    "and limits.timestampPeriod says 33.11 ns (30.2 MHz). B measures it at "
    "init and uses the measured value. DOA's fight is the scene where the "
    "error was found: A's phase GPU reads ~40 ms a frame and the true span "
    "is ~64.")
doa["legs"] = legs(
    "B's measured= is 52.08 ns +-1% (51.56 to 52.60), reported= is 33.11 "
    "+-0.05, and using= is the measured value. KILL: measured outside 49.5 "
    "to 54.7 ns.")

cr = base("Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko)"
          ".xiso.iso", "thor", 240, "crimson-skies", 110, 240)
cr["prediction"] = (
    "#474, the Thor check. Nothing on disk measures the Thor's timestamp "
    "period. The Thor's SoC is the Nova's, so the guess is the same 19.2 MHz "
    "counter behind the same reported 30.2 MHz. K1 is that guess, labelled as "
    "one; K0, K2, G1 and G2 test the mechanism whatever the value is.")
cr["legs"] = legs(
    "A GUESS, labelled: B's reported= is 33.11 and measured= is 52.08 ns "
    "+-1%. If the Thor's driver reports its period correctly, measured= "
    "agrees with reported= within 2% and using= is reported; that refutes "
    "the guess, not the change.")

for name, d in (("flip474-tsperiod-doa-nova.json", doa),
                ("flip474-tsperiod-crimson-thor.json", cr)):
    d.update({"expect": {}, "expect_counts": {}, "expect_note": NOTE})
    s = json.dumps(d, indent=2) + "\n"
    json.loads(s)
    with open("docs/testing/predictions/" + name, "w") as f:
        f.write(s)
    print(name, A[:10], B[:10])
