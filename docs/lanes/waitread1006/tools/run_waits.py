#!/usr/bin/env python3
"""Per-run wait figures from a dispatch run's logcat.txt (no device access).

Usage: run_waits.py <result-dir-name>[@HH:MM:SS] [...]

The optional @time keeps only log lines at or after that device time (the
gameplay frame named in route-frames/, so load and menu windows are excluded).

Reads ~/hakux-work/dispatch/results/<name>/logcat.txt and prints, per run:
  phase    hakuX-phase lines (one per 60 frames). Medians of the printed
           per-frame fields Tot, Draw, Pipe, Fin, Fen, Idle, GPU R, GPU RP.
  pace     hakuX-pace lines (one per 60 frames). ms = wall ms for those 60
           frames (1000 at 60 Hz). lost = sum of (ms - 1000) over windows, a
           wall-time figure, not a share. max = the longest single frame.
  shader   [shd413] lines (one per 60 frames). Sums of dpc_ms (inside every
           pipeline create), dgl_ms (glslang), dsnu_ms (new-module stages), dsm.
  stalls   pace windows with max >= 500 ms, with the same-frame [shd413] values.

Every figure is a median or sum of printed fields. Nothing is scaled or inferred.
"""
import os
import re
import statistics
import sys

BASE = os.path.expanduser("~/hakux-work/dispatch/results")
PACE = re.compile(r"hakuX-pace\(.*?\): f=(\d+) v0=(\d+) v1=(\d+) v2=(\d+) v3=(\d+) v4=(\d+) vb=(\d+) max=([\d.]+) ms=([\d.]+)")
PHASE = re.compile(r"hakuX-phase\(.*?\): (.*)$")
KV = re.compile(r"([A-Za-z]+):(-?\d+(?:\.\d+)?)")
KVS = re.compile(r"([A-Za-z_]+)=(-?\d+(?:\.\d+)?)")


def first_fields(pattern, text):
    out = {}
    for k, v in pattern.findall(text):
        out.setdefault(k, float(v))
    return out


def parse(name, start=None):
    path = os.path.join(BASE, name, "logcat.txt")
    phases, paces, shd, buckets = [], [], [], []
    with open(path, errors="replace") as f:
        for line in f:
            if start and line.split()[1:2] and line.split()[1] < start:
                continue
            if "hakuX-pace(" in line:
                m = PACE.search(line)
                if m:
                    # (frame, max_ms, wall_ms, time)
                    paces.append((int(m.group(1)), float(m.group(8)),
                                  float(m.group(9)), line.split()[1]))
                    buckets.append([int(m.group(i)) for i in range(2, 7)])
                continue
            if "hakuX-phase(" in line:
                m = PHASE.search(line)
                if m:
                    phases.append(first_fields(KV, m.group(1)))
                continue
            if "[shd413] f=" in line:
                kv = first_fields(KVS, line.split("[shd413]", 1)[1])
                shd.append(kv)
    return phases, paces, shd, buckets


def run(arg):
    name, _, start = arg.partition("@")
    phases, paces, shd, buckets = parse(name, start or None)
    print("== %s%s" % (name, " from " + start if start else ""))
    print("  windows  phase=%d pace=%d shd413=%d" % (len(phases), len(paces), len(shd)))
    for label, k in [("Tot", "Tot"), ("Surf", "Surf"), ("Tex", "Tex"), ("Shd", "Shd"),
                     ("Draw", "Draw"), ("Vtx", "Vtx"), ("Pipe", "Pipe"), ("PipeSh", "Sh"),
                     ("PipeLu", "Lu"), ("Setup", "Setup"), ("Cmd", "Cmd"),
                     ("Fin", "Fin"), ("Sub", "Sub"), ("Fen", "Fen"),
                     ("Idle", "Idle"), ("IdleFr", "Fr"), ("IdleSt", "St"),
                     ("GPU_R", "R"), ("GPU_X", "X"), ("GPU_RP", "RP")]:
        vals = [p[k] for p in phases if k in p]
        if vals:
            print("  phase %-7s median %6.2f ms/frame  max %7.1f  (n=%d)" % (
                label, statistics.median(vals), max(vals), len(vals)))
    if paces:
        mx = max(paces, key=lambda p: p[1])
        lost = sum(max(0.0, p[2] - 1000.0) for p in paces)
        n500 = sum(1 for p in paces if p[1] >= 500)
        print("  pace     windows=%d  windows with max>=500ms=%d  lost(sum ms-1000)=%.0f ms  "
              "worst frame=%.1f ms at %s" % (len(paces), n500, lost, mx[1], mx[3]))
    if paces and phases and len(paces) == len(phases):
        # hakuX-pace and hakuX-phase print at the same 60th frame, so line i of
        # each is the same window. Frame time is wall ms / 60; Tot is the
        # renderer's accounted ms per frame. The rest is outside the renderer.
        frame_ms = [p[2] / 60.0 for p in paces]
        tot = [ph["Tot"] for ph in phases if "Tot" in ph]
        gap = [f - t for f, t in zip(frame_ms, tot)]
        print("  frame    median wall %.2f ms/frame (%.1f fps); median Tot %.2f; "
              "median (wall - Tot) %.2f ms/frame" % (
                  statistics.median(frame_ms), 1000.0 / statistics.median(frame_ms),
                  statistics.median(tot), statistics.median(gap)))
    if buckets:
        tot_f = [sum(b[i] for b in buckets) for i in range(5)]
        n = sum(tot_f) or 1
        print("  vblank   frames by vblanks-per-frame v0..v4 (v0=0, v4=4+): %s  (60fps = v1 share)" % (
            " ".join("%d" % x for x in tot_f)))
    if shd:
        print("  shader  dpc_ms sum=%.0f  dgl_ms sum=%.0f  dsnu_ms sum=%.0f  dsm sum=%d  "
              "windows with dsm>0=%d" % (
                  sum(s.get("dpc_ms", 0) for s in shd), sum(s.get("dgl_ms", 0) for s in shd),
                  sum(s.get("dsnu_ms", 0) for s in shd), sum(s.get("dsm", 0) for s in shd),
                  sum(1 for s in shd if s.get("dsm", 0) > 0)))
    big = [p for p in paces if p[1] >= 500]
    if big:
        by_f = {int(s["f"]): s for s in shd if "f" in s}
        print("  stalls (pace max>=500 ms):")
        for fnum, mx_ms, wall, t in big:
            s = by_f.get(fnum, {})
            print("    %s f=%d max=%.1f wall=%.0f  shd dsm=%s dpc=%s dgl=%s dsnu=%s" % (
                t, fnum, mx_ms, wall, s.get("dsm"), s.get("dpc_ms"),
                s.get("dgl_ms"), s.get("dsnu_ms")))


if __name__ == "__main__":
    for n in sys.argv[1:]:
        run(n)  # name or name@HH:MM:SS to start the windows at a gameplay frame
