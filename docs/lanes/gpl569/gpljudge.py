#!/usr/bin/env python3
"""#569 P5: score the graphics-pipeline-library soaks against
docs/testing/predictions/gpl569-doa-soak.json (and -blinx-soak.json).

    gpljudge.py --a <result dir> --b <result dir> [--b2 <result dir>]
    gpljudge.py --selftest

Each arm is one dispatcher result dir of a --perflog title soak. Read per arm:

  cleared      result.json shader_cache says the caches were cleared (cold)
  init         the [gpl569] ext=.. lib=.. fast=.. interp=.. mode=.. line
  last_gpl     the last [gpl569] mode=.. links=.. line (library counters)
  pc_ms, pm    the last [shd413] line's running create ms and pipeline misses
  ms_per_miss  pc_ms / pm, the stall leg's whole-run reading
  load         the first load after `mark play`: the first window with
               dpm >= 1 after the mark, extended while no run of three
               dpm == 0 windows intervenes; its summed dpc_ms and dpm
  play         [shd413]/xemu-gpu/gfps lines from `mark play` + 60 s to the
               end: median GPU Tot ms (xemu-gpu "GPU: Tot:") and median gfps

All of it is fixed here before any run; the verdicts are printed against the
factors the prediction names.
"""
import argparse
import json
import os
import re
import statistics
import sys

TS = re.compile(r"^\d\d-\d\d (\d\d):(\d\d):(\d\d\.\d+) ")
MARK = re.compile(r"hakuX-route.*: mark (\S+)")
KV = re.compile(r"(\w+)=(\S+)")
GPU = re.compile(r"GPU: Tot:([\d.]+) ")
GFPS = re.compile(r"hakuX-perf.*: gfps=(\d+) ")
PLAY_SKIP_S = 60
QUIET = 3


def secs(line):
    m = TS.match(line)
    return None if not m else int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def num(s):
    try:
        return float(s)
    except ValueError:
        return None


def parse(lines):
    a = {"wins": [], "marks": [], "gpu": [], "gfps": [], "init": None, "gpl": []}
    day, last = 0.0, None
    for line in lines:
        t = secs(line)
        if t is None:
            continue
        if last is not None and t + day < last - 43200:
            day += 86400
        t += day
        last = t
        m = MARK.search(line)
        if m:
            a["marks"].append((t, m.group(1)))
            continue
        i = line.find("[shd413]")
        if i >= 0:
            kv = dict(KV.findall(line[i:]))
            w = {k: num(kv[k]) for k in ("dpm", "dpc_ms", "pc_ms", "pm", "dt_ms") if k in kv}
            if len(w) == 5 and None not in w.values():
                w["t"] = t
                a["wins"].append(w)
            continue
        i = line.find("[gpl569]")
        if i >= 0:
            kv = dict(KV.findall(line[i:]))
            if "ext" in kv:
                a["init"] = kv
            elif "links" in kv:
                kv["t"] = t
                a["gpl"].append(kv)
            continue
        m = GPU.search(line)
        if m:
            a["gpu"].append((t, float(m.group(1))))
            continue
        m = GFPS.search(line)
        if m:
            a["gfps"].append((t, int(m.group(1))))
    return a


def first_load(wins, play_t):
    idx = [i for i, w in enumerate(wins) if w["t"] > play_t and w["dpm"] >= 1]
    if not idx:
        return None
    start = end = idx[0]
    zeros = 0
    for j in range(start + 1, len(wins)):
        if wins[j]["dpm"] >= 1:
            end, zeros = j, 0
        else:
            zeros += 1
            if zeros >= QUIET:
                break
    return wins[start:end + 1]


def score_arm(lines, shader_cache):
    a = parse(lines)
    r = {"shader_cache": shader_cache, "lines": len(a["wins"]), "init": a["init"],
         "last_gpl": a["gpl"][-1] if a["gpl"] else None}
    r["cleared"] = isinstance(shader_cache, str) and "cleared" in shader_cache
    if a["wins"]:
        lw = a["wins"][-1]
        r["pc_ms"], r["pm"] = lw["pc_ms"], lw["pm"]
        r["ms_per_miss"] = lw["pc_ms"] / lw["pm"] if lw["pm"] else None
    play = [t for t, n in a["marks"] if n == "play"]
    r["play_mark"] = bool(play)
    if play and a["wins"]:
        ld = first_load(a["wins"], play[0])
        if ld:
            r["load_dpc_ms"] = sum(w["dpc_ms"] for w in ld)
            r["load_dpm"] = sum(w["dpm"] for w in ld)
            r["load_windows"] = len(ld)
    if play:
        t0 = play[0] + PLAY_SKIP_S
        g = [v for t, v in a["gpu"] if t >= t0]
        f = [v for t, v in a["gfps"] if t >= t0]
        r["play_gpu_ms"] = statistics.median(g) if g else None
        r["play_gpu_n"] = len(g)
        r["play_gfps"] = statistics.median(f) if f else None
        r["play_gfps_n"] = len(f)
    return r


def load_dir(d):
    lc = [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.startswith("logcat")]
    lines = []
    for p in lc:
        with open(p, errors="replace") as fh:
            lines.extend(fh)
    sc = None
    rp = os.path.join(d, "result.json")
    if os.path.exists(rp):
        try:
            sc = json.load(open(rp)).get("shader_cache")
        except ValueError:
            pass
    return lines, sc


def ratio(b, a):
    return None if a in (None, 0) or b is None else b / a


def verdicts(A, B, B2, f):
    """f: the prediction's factors (see the prediction's legs)."""
    v = {}
    v["M0"] = (A.get("cleared") and B.get("cleared") and A.get("lines", 0) >= f["min_lines"] and
               B.get("lines", 0) >= f["min_lines"] and bool(B.get("init")) and
               B["init"].get("mode") == "1" and bool(B.get("last_gpl")) and
               int(B["last_gpl"].get("links", "0")) > 0)
    rm = ratio(B.get("ms_per_miss"), A.get("ms_per_miss"))
    v["S1_ratio"] = rm
    v["S1"] = rm is not None and rm <= f["s1_max"]
    v["S1_below_bound"] = rm is not None and rm < f["bound"]
    rl = ratio(B.get("load_dpc_ms"), A.get("load_dpc_ms"))
    v["S2_ratio"] = rl
    v["S2"] = rl is not None and rl <= f["s2_max"]
    g = B.get("last_gpl") or {}
    try:
        new_pr = int(g["new"].split("/")[1])
        hit_pr = int(g["hit"].split("/")[1])
        v["S3_pr_hit_share"] = hit_pr / (hit_pr + new_pr) if hit_pr + new_pr else None
    except (KeyError, IndexError, ValueError):
        v["S3_pr_hit_share"] = None
    v["S3"] = v["S3_pr_hit_share"] is not None and v["S3_pr_hit_share"] >= f["s3_min"]
    rg = ratio(B.get("play_gpu_ms"), A.get("play_gpu_ms"))
    rf = ratio(B.get("play_gfps"), A.get("play_gfps"))
    v["D1_gpu_ratio"], v["D1_gfps_ratio"] = rg, rf
    v["D1"] = (rg is not None and rg <= f["d1_gpu_max"] and
               rf is not None and rf >= f["d1_gfps_min"])
    if B2:
        rg2 = ratio(B2.get("play_gpu_ms"), A.get("play_gpu_ms"))
        v["D2_gpu_ratio"] = rg2
        g2 = B2.get("last_gpl") or {}
        try:
            swapped = int(g2["lto"].split("/")[2])
        except (KeyError, IndexError, ValueError):
            swapped = 0
        v["D2_swapped"] = swapped
        v["D2"] = rg2 is not None and rg2 <= f["d2_gpu_max"] and swapped > 0
    g = B.get("last_gpl") or {}
    v["MEM_heap_mb"] = num(g.get("heap_mb", "")) if g else None
    v["MEM_libs"] = g.get("libs")
    return v


FACTORS = {"min_lines": 20, "s1_max": 0.70, "s2_max": 0.70, "bound": 0.23, "s3_min": 0.50,
           "d1_gpu_max": 1.10, "d1_gfps_min": 0.90, "d2_gpu_max": 1.03}


def selftest():
    def arm(mode, pc, pm, gpu, gfps, gpl=True, load_ms=100.0):
        L = ["09-28 10:00:00.000 I/hakuX-build( 1): [gpl569] ext=1 lib=1 fast=1 "
             "interp=1 requested=%d mode=%d\n" % (mode, mode),
             "09-28 10:00:10.000 I/hakuX-route( 1): mark play\n"]
        t = 20
        for i, dpm in enumerate([0, 3, 5, 0, 2, 0, 0, 0, 1, 0]):
            L.append("09-28 10:00:%02d.000 I/hakuX-perf( 1): [shd413] f=%d dt_ms=1000 "
                     "ph=0 pm=%d dph=0 dpm=%d pc_ms=%.1f dpc_ms=%.1f\n"
                     % (t, i, pm if i == 9 else 0, dpm, pc if i == 9 else 0, dpm * load_ms))
            t += 3
        for s in range(75, 90, 5):
            L.append("09-28 10:01:%02d.000 I/xemu-gpu( 1): GPU: Tot:%.1f Rnd:1 Xfr:1 RP:3\n"
                     % (s - 60, gpu))
            L.append("09-28 10:01:%02d.000 I/hakuX-perf( 1): gfps=%d G:1\n" % (s - 60, gfps))
        if gpl:
            L.append("09-28 10:01:59.000 I/hakuX-perf( 1): [gpl569] mode=%d links=10 "
                     "link_ms=5 link_fail=0 fb=0 new=2/4/3/2 hit=8/6/7/8 fail=0/0/0/0 "
                     "lib_ms=1/2/3/4 libs=2/4/3/2 flush=0 lto=5/0/%d lto_ms=9 heap_mb=12.5\n"
                     % (mode, 3 if mode == 2 else 0))
        return L
    A = score_arm(arm(0, 1000.0, 10, 10.0, 30, gpl=False), "cleared: apk a -> b")
    B = score_arm(arm(1, 500.0, 10, 10.5, 29, load_ms=50.0), "cleared: apk b -> c")
    B2 = score_arm(arm(2, 500.0, 10, 10.1, 30), "kept")
    assert A["ms_per_miss"] == 100.0 and B["ms_per_miss"] == 50.0, (A, B)
    assert A["load_dpm"] == 10 and A["load_windows"] == 4, A
    assert A["play_gpu_ms"] == 10.0 and A["play_gfps"] == 30, A
    F = dict(FACTORS, min_lines=5)
    v = verdicts(A, B, B2, F)
    assert v["M0"] and v["S1"] and v["S2"] and not v["S1_below_bound"], v
    assert abs(v["S3_pr_hit_share"] - 0.6) < 1e-9 and v["S3"], v
    assert v["D1"] and v["D2"] and v["D2_swapped"] == 3, v
    # the other side of every threshold
    Bslow = score_arm(arm(1, 800.0, 10, 11.5, 26), "cleared: x")
    v = verdicts(A, Bslow, None, F)
    assert not v["S1"] and not v["S2"] and not v["D1"], v
    Awarm = score_arm(arm(0, 1000.0, 10, 10.0, 30, gpl=False), "kept")
    assert not verdicts(Awarm, B, None, F)["M0"]
    Boff = score_arm(arm(0, 500.0, 10, 10.0, 30), "cleared: x")
    assert not verdicts(A, Boff, None, F)["M0"]
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a")
    ap.add_argument("--b")
    ap.add_argument("--b2")
    ap.add_argument("--selftest", action="store_true")
    o = ap.parse_args()
    if o.selftest:
        selftest()
        return
    A = score_arm(*load_dir(o.a))
    B = score_arm(*load_dir(o.b))
    B2 = score_arm(*load_dir(o.b2)) if o.b2 else None
    out = {"A": A, "B": B, "B2": B2, "factors": FACTORS,
           "verdicts": verdicts(A, B, B2, FACTORS)}
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
