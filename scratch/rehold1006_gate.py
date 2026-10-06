#!/usr/bin/env python3
"""Gate before each Nova hold (lane.local 06:35 10-06, and the 01:49 / 08:42 rules).

  rehold1006_gate.py ready <release_epoch>   exit 0 = take the hold; exit 2 = Nova not clean (stop the queue)

Clean means: the newest Nova result is on master (its ref is origin/master or an ancestor of it), env is empty,
perflog is off, and .env_pref.nova is absent. A Nova-bound request in the queue waits the lane up to 25 min
after the last release, then the take goes ahead.
"""
import glob
import json
import os
import subprocess
import sys
import time

BASE = "/home/justin/hakux-work/dispatch"
WAIT_S = 1500


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)) + "/..")


def newest_nova_result():
    best = None
    for d in glob.glob(BASE + "/results/*"):
        rq, rs = os.path.join(d, "request.json"), os.path.join(d, "result.json")
        if not (os.path.exists(rq) and os.path.exists(rs)):
            continue
        try:
            req = json.load(open(rq))
        except Exception:
            continue
        if req.get("device") != "nova":
            continue
        m = os.path.getmtime(rs)
        if best is None or m > best[0]:
            best = (m, os.path.basename(d), req)
    return best


def clean():
    b = newest_nova_result()
    if b is None:
        return False, "no Nova result to read"
    _, name, req = b
    ref = str(req.get("ref") or "")
    if not ref:
        return False, f"{name}: no ref"
    if sh("git", "merge-base", "--is-ancestor", ref, "origin/master").returncode != 0:
        return False, f"{name}: ref {ref} is not on origin/master"
    if req.get("env"):
        return False, f"{name}: env {req.get('env')}"
    if req.get("perflog"):
        return False, f"{name}: perflog on"
    if os.path.exists(BASE + "/.env_pref.nova"):
        return False, ".env_pref.nova exists"
    return True, f"{name} ref {ref[:10]} env [] perflog off"


def nova_queued():
    for f in glob.glob(BASE + "/queue/*.req"):
        try:
            if json.load(open(f)).get("device") == "nova":
                return True
        except Exception:
            if "nova" in open(f).read():
                return True
    return False


def main():
    if len(sys.argv) < 3 or sys.argv[1] != "ready":
        print(__doc__)
        return 1
    release = float(sys.argv[2])
    ok, why = clean()
    if not ok:
        print("NOT CLEAN:", why, flush=True)
        return 2
    print("clean:", why, flush=True)
    while nova_queued() and (release == 0 or time.time() - release < WAIT_S):
        print("waiting: a Nova-bound request is queued", time.strftime("%H:%M:%S"), flush=True)
        time.sleep(30)
    print("ready", time.strftime("%H:%M:%S"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
