#!/usr/bin/env python3
"""Read the #569 P6 DOA soaks (P and C legs) and judge them against
docs/testing/predictions/uberspike569-doa-soak.json.

    soak_read.py --a DIR[,DIR] --b DIR[,DIR] [--judge PREDICTION.json]

Per result directory (logcat.txt, request.json):
  * the runtime reader: `psh-uber: ON` lines (hakuX-perf), and the family
    module lines `psh-uber: family module N: B bytes GLSL, T ms`;
  * fps: the `gfps=` hakuX-perf line is written every 60 guest frames, so a
    window's fps is 60 / (gap between consecutive lines), as doa413b's
    ab_read.py reads it; the FIGHT window is the last `--window` seconds of
    the log (the survey route plays from ~200 s to the end);
  * compiles: the last `[shd413]` line's pm (pipeline misses) and sm (shader
    binding misses).
"""
import argparse
import json
import os
import re
import statistics
import sys

TS = re.compile(r"^(\d\d-\d\d) (\d\d):(\d\d):(\d\d\.\d+)")
KV = re.compile(r"(\w+)=(-?[\d.]+)")
FAM = re.compile(r"psh-uber: family module (\d+): (\d+) bytes GLSL, ([\d.]+) ms")


def secs(line):
    m = TS.match(line)
    if not m:
        return None
    return int(m.group(2)) * 3600 + int(m.group(3)) * 60 + float(m.group(4))


def read(rdir, window):
    req = json.load(open(os.path.join(rdir, "request.json")))
    out = dict(dir=os.path.basename(rdir.rstrip("/")), env=req.get("env"),
               ref=req.get("ref"), device=req.get("device"), on=0, fams=[],
               gfps_t=[], shd=None)
    with open(os.path.join(rdir, "logcat.txt"), errors="replace") as f:
        for line in f:
            if "psh-uber: ON" in line:
                out["on"] += 1
            m = FAM.search(line)
            if m:
                out["fams"].append((int(m.group(2)), float(m.group(3))))
            if "hakuX-perf" in line and "gfps=" in line:
                t = secs(line)
                if t is not None:
                    out["gfps_t"].append(t)
            if "[shd413]" in line:
                out["shd"] = dict(KV.findall(line.split("[shd413]", 1)[1]))
    ts = out["gfps_t"]
    fps = [60.0 / (b - a) for a, b in zip(ts, ts[1:]) if b > a]
    fight = [60.0 / (b - a) for a, b in zip(ts, ts[1:])
             if b > a and ts and b >= ts[-1] - window]
    out["fight_n"] = len(fight)
    out["fight_fps"] = statistics.median(fight) if fight else None
    out["all_fps"] = statistics.median(fps) if fps else None
    return out


def show(tag, r):
    fam_ms = [ms for _, ms in r["fams"]]
    print("%s %-44s env=%s on=%d fams=%d%s fight=%s (%d lines) pm=%s sm=%s" % (
        tag, r["dir"], r["env"], r["on"], len(r["fams"]),
        " (glslang+module ms median %.1f, max %.1f; GLSL %d B)" % (
            statistics.median(fam_ms), max(fam_ms), r["fams"][0][0])
        if fam_ms else "",
        "%.2f" % r["fight_fps"] if r["fight_fps"] else "-", r["fight_n"],
        (r["shd"] or {}).get("pm"), (r["shd"] or {}).get("sm")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--window", type=float, default=150.0)
    ap.add_argument("--judge")
    a = ap.parse_args()
    A = [read(d, a.window) for d in a.a.split(",")]
    B = [read(d, a.window) for d in a.b.split(",")]
    for r in A:
        show("A", r)
    for r in B:
        show("B", r)
    fa = [r["fight_fps"] for r in A if r["fight_fps"]]
    fb = [r["fight_fps"] for r in B if r["fight_fps"]]
    ratio = statistics.median(fb) / statistics.median(fa) if fa and fb else None
    print("fight fps median of runs: A %s, B %s, B/A %s" % (
        "%.2f" % statistics.median(fa) if fa else "-",
        "%.2f" % statistics.median(fb) if fb else "-",
        "%.3f" % ratio if ratio else "-"))
    if not a.judge:
        return 0
    exp = json.load(open(a.judge))["expect"]
    rules = []
    rules.append(("M0/a_uber_off", all(r["on"] == 0 for r in A)))
    rules.append(("M0/b_uber_on", all(r["on"] > 0 and r["fams"] for r in B)))
    rules.append(("M1/fight_lines_min", all(r["fight_n"] >= exp["M1/fight_lines_min"]
                                            for r in A + B)))
    valid = all(ok for _, ok in rules)
    p1 = ratio is not None and ratio >= exp["P1/b_over_a_fight_fps_min"]
    for name, ok in rules:
        print("  %-28s %s" % (name, "ok" if ok else "FAILED (void: the arms are not the arms)"))
    print("  %-28s %s (B/A %s, floor %.2f)" % (
        "P1/b_over_a_fight_fps_min", "PASS" if p1 else "FAIL",
        "%.3f" % ratio if ratio else "-", exp["P1/b_over_a_fight_fps_min"]))
    print("verdict: %s" % ("VOID" if not valid else ("PASS" if p1 else "FAIL")))
    return 0 if valid and p1 else 1


if __name__ == "__main__":
    sys.exit(main())
