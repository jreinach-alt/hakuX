#!/usr/bin/env python3
"""Capture a burst of consecutive frames from a handheld you HOLD, then score it.

    burst_capture.py --device nova --hold-tag lane.<name> --seconds 4 --out DIR [--method rec|caps]

rec (default): `screenrecord` of the display, H.264 at 20 Mbit/s, native size.
SurfaceFlinger hands the virtual display a buffer on every composition, so the
capture runs at up to the panel's rate; flicker_score.py prints the rate it
actually got (unique_fps, dt_max_ms), which is the number to check against
the title's fps before reading a zero as "no flicker".

caps: back-to-back `exec-out screencap -p`, kept for the measurement that says
why rec is the default: each screencap takes on the order of a second.

The device is touched only when `hold.sh who <device>` names --hold-tag (take
it with `docs/testing/jobs/hold.sh take <dev> <tag> <why> && hold.sh wait-idle
<dev> 900`). Nothing here launches, stops or sends input to the app: drive the
title to play first (pathfind.py, a route), then burst.

Writes DIR/burst.mp4 (rec) or DIR/caps/NNN.png (caps), DIR/capture.json, and
flicker_score.py's flicker.tsv / flicker_worst.png, and prints its line.
"""

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SERIALS = {"nova": "ee317437", "thor": "bdc158a5"}
HOLD = os.path.join(HERE, "jobs", "hold.sh")
REMOTE = "/sdcard/Download/flk_burst.mp4"


def adb(serial, *args, **kw):
    return subprocess.run(["adb", "-s", serial] + list(args), **kw)


def held_by(device, tag):
    p = subprocess.run(["bash", HOLD, "who", device], capture_output=True, text=True)
    return p.returncode == 0 and (" by %s " % tag) in (p.stdout + " ")


def rec(serial, seconds, out):
    adb(serial, "shell", "rm", "-f", REMOTE, capture_output=True)
    t0 = time.time()
    p = adb(serial, "shell", "screenrecord", "--time-limit", str(seconds),
            "--bit-rate", "20000000", REMOTE, capture_output=True, text=True,
            timeout=seconds + 30)
    t1 = time.time()
    local = os.path.join(out, "burst.mp4")
    q = adb(serial, "pull", REMOTE, local, capture_output=True, text=True, timeout=120)
    adb(serial, "shell", "rm", "-f", REMOTE, capture_output=True)
    return {"method": "rec", "rc": p.returncode, "stderr": (p.stderr or "")[-400:],
            "pull_rc": q.returncode, "start": t0, "wall_s": round(t1 - t0, 2),
            "bytes": os.path.getsize(local) if os.path.exists(local) else 0}, local


def caps(serial, seconds, out):
    d = os.path.join(out, "caps")
    os.makedirs(d, exist_ok=True)
    t0, times, i = time.time(), [], 0
    while time.time() - t0 < seconds:
        s = time.time()
        with open(os.path.join(d, "%03d.png" % i), "wb") as f:
            adb(serial, "exec-out", "screencap", "-p", stdout=f, timeout=30)
        times.append(round(time.time() - s, 3))
        i += 1
    return {"method": "caps", "start": t0, "count": i, "each_s": times,
            "per_s": round(i / max(1e-9, time.time() - t0), 2)}, d


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--device", required=True, choices=sorted(SERIALS))
    ap.add_argument("--hold-tag", required=True)
    ap.add_argument("--seconds", type=int, default=4)
    ap.add_argument("--out", required=True)
    ap.add_argument("--method", choices=("rec", "caps"), default="rec")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if not held_by(a.device, a.hold_tag):
        print("burst_capture: %s is not held by %s; take the hold first" % (a.device, a.hold_tag),
              file=sys.stderr)
        return 3
    os.makedirs(a.out, exist_ok=True)
    serial = SERIALS[a.device]
    meta, burst = (rec if a.method == "rec" else caps)(serial, a.seconds, a.out)
    meta.update({"device": a.device, "serial": serial, "seconds": a.seconds, "note": a.note})
    sys.path.insert(0, HERE)
    import flicker_score
    try:
        res = flicker_score.run(burst, a.out)
    except SystemExit as e:
        res = {"error": str(e)}
    meta["flicker"] = res
    with open(os.path.join(a.out, "capture.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(flicker_score.fmt(res) if "error" not in res else res["error"], "out=" + a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
