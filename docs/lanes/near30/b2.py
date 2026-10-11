#!/usr/bin/env python3
"""lane.near30: the hands for a HELD Blinx 2 session on the Nova (#433).

    python3 b2.py <out_dir> <step>...
      shot <label>          frame -> <out_dir>/<n>-<label>.png (path printed)
      press <BTN> [ms]      one press through perf/pad.sh
      axis <AX> <val>       set an axis (min/mid/max or a raw value)
      wait <s>
      mark <label>          logcat `hakuX-route: mark <label>` (device clock)
      batt                  battery level, current, status, plugged
      launch                force-stop, wake, start Blinx 2 (pathfind.Device)

Every step is appended to <out_dir>/steps.tsv with the host time. Inputs go
through pad.sh only (AGENTS.md: `input keyevent` ends the emulator).
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing", "titles"))
import pathfind  # noqa: E402

ISO = ("/storage/E6C6-D7AA/Games/XBox/"
       "4D530065-Blinx_2_Battle_of_Time_Space_Blinx_2_Masters_of_Time_Space.xiso.iso")
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
dev = pathfind.Device("nova")
log = open(os.path.join(OUT, "steps.tsv"), "a")


def note(*f):
    log.write("\t".join([time.strftime("%H:%M:%S")] + [str(x) for x in f]) + "\n")
    log.flush()


def batt():
    out = dev.sh("cd /sys/class/power_supply/battery; cat capacity current_now status; "
                 "dumpsys battery | grep -E 'AC powered|USB powered'")
    return " ".join(out.split())


args = sys.argv[2:]
i = 0
while i < len(args):
    a = args[i]
    if a == "shot":
        n = len([f for f in os.listdir(OUT) if f.endswith(".png")]) + 1
        p = os.path.join(OUT, f"{n:03d}-{time.strftime('%H%M%S')}-{args[i + 1]}.png")
        dev.capture(p)
        print(p)
        note("shot", p)
        i += 2
    elif a == "press":
        has_ms = i + 2 < len(args) and args[i + 2].isdigit()
        ms = args[i + 2] if has_ms else "120"
        dev.pad("press", args[i + 1], ms)
        note("press", args[i + 1], ms)
        i += 3 if has_ms else 2
    elif a == "axis":
        dev.pad("axis", args[i + 1], args[i + 2])
        note("axis", args[i + 1], args[i + 2])
        i += 3
    elif a == "wait":
        time.sleep(float(args[i + 1]))
        i += 2
    elif a == "mark":
        dev.sh(f"log -t hakuX-route 'mark {args[i + 1]}'")
        note("mark", args[i + 1])
        i += 2
    elif a == "batt":
        b = batt()
        print(b)
        note("batt", b)
        i += 1
    elif a == "launch":
        dev.launch(ISO)
        note("launch", ISO)
        i += 1
    else:
        sys.exit(f"b2.py: unknown step {a}")
