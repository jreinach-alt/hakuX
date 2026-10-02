#!/usr/bin/env python3
"""Read lane.ibcache's env-pair and jcsize soaks (#507).

    soakread.py <request id> ...

Copies each dispatch result dir to scratch/res/<id> (title_verdict.py writes
into the dir it reads, and the dispatch copy is not ours), runs
title_verdict.py there, and prints one row per run: void note, device, ref,
env, the `[ibc507]` line, `mark gameplay`, gameplay seconds, crash/hang,
fps window median, J/frame, battery W, and the median `[rr425] hc` (helper
lookups per 2 s window) from mark gameplay + 10 s to the end.
"""
import json
import os
import re
import shutil
import statistics
import subprocess
import sys

D = "/home/justin/hakux-work/dispatch/results"
HERE = os.path.dirname(os.path.abspath(__file__))
TOP = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
SCR = os.path.join(TOP, "scratch", "res")
TV = os.path.join(TOP, "docs", "testing", "title_verdict.py")


def secs(hms):
    h, m, s = hms.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def read(rid):
    src = os.path.join(D, rid)
    dst = os.path.join(SCR, rid)
    if not os.path.isdir(dst):
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("route-frames"))
    req = json.load(open(os.path.join(dst, "request.json")))
    void = ""
    vp = os.path.join(dst, "VOID.txt")
    if os.path.exists(vp):
        void = open(vp).read().strip()
    subprocess.run([sys.executable, TV, dst], capture_output=True, text=True)
    vj = os.path.join(dst, "verdict.json")
    v = json.load(open(vj)) if os.path.exists(vj) else {}
    ibc, mark, hcs = "", None, []
    rl = os.path.join(dst, "run.log")
    if os.path.exists(rl):
        for line in open(rl, errors="replace"):
            m = re.match(r"ROUTE (\d\d:\d\d:\d\d\.\d+) mark gameplay", line)
            if m:
                mark = secs(m.group(1))
    rr = re.compile(r"^\d\d-\d\d (\d\d:\d\d:\d\d\.\d+) .*\[rr425\] .* hc=(\d+)")
    for line in open(os.path.join(dst, "logcat.txt"), errors="replace"):
        if "[ibc507] on=" in line and not ibc:
            ibc = line.split("[ibc507] ", 1)[1].strip()
        m = rr.match(line)
        if m and mark is not None and secs(m.group(1)) >= mark + 10:
            hcs.append(int(m.group(2)))
    p = v.get("power") or {}
    return {
        "id": rid, "void": void, "device": req.get("device"),
        "ref": req.get("ref"), "env": " ".join(req.get("env") or []) or "-",
        "apk": v.get("apk_sha"), "ibc": ibc,
        "mark": mark is not None, "gameplay_s": v.get("gameplay_s"),
        "crash": v.get("crash"), "hang": v.get("hang"),
        "tv_void": v.get("void"), "pauses": (v.get("thermal") or {}).get("pauses"),
        "fps_med": v.get("fps_window_median"), "fps_ok": v.get("fps_ok_share"),
        "jpf": p.get("j_per_frame"), "bat_w": p.get("battery_w"),
        "net_w": p.get("net_w"),
        "hc_med": statistics.median(hcs) if hcs else None, "hc_n": len(hcs),
        "late100": (v.get("pace") or {}).get("late_per_100"),
        "title": v.get("name") or req.get("title"),
    }


def main():
    os.makedirs(SCR, exist_ok=True)
    for rid in sys.argv[1:]:
        r = read(rid)
        print(json.dumps(r))


if __name__ == "__main__":
    main()
