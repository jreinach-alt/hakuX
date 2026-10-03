#!/usr/bin/env python3
"""gmemread.py -- every number lane.gmem474's legs name, per run, one window.

    python3 docs/lanes/gmem474/gmemread.py --from S --to S <result id or dir> ...
    python3 docs/lanes/gmem474/gmemread.py --json --from S --to S <run> ...

Reads only the files the dispatcher leaves (result.json, logcat.txt,
thermal.jsonl, perf_regimen.json, pulled/). It never opens a prediction.

THE WINDOW. Seconds from the logcat's first line, which is soak_title.sh's
`soak start` (written after the #519 cool-down gate, 0.2 s before the app
starts), as in flip474's sysmemjudge.py. Every figure below is over it.

WHAT RAN (the mode proof, per run):
  render_mode  the app's `render_mode:` line (hakuX-build): mode, source and
               the TU_DEBUG the driver was handed
  env          result.json's env, as queued
  mesa         the driver's own start-up lines from the pulled MESA_LOG_FILE
               (TU_DEBUG=startup): `TU_DEBUG=0x..` is the parsed flag word
               (fleet T30 table: startup 0x1, nobin 0x4, sysmem 0x8,
               forcebin 0x10, gmem 0x1000), `TU_AUTOTUNE_ALGO=N (name)` the
               parsed algorithm (1 = profiled), and any `Unknown
               TU_AUTOTUNE_ALGO` warning. `none` when nothing was pulled.
  shader_cache result.json's: the first run of an apk on a device clears it

FRAME RATE. Consecutive hakuX-perf `gfps=` lines, both inside the window and
not across a capture gap, are one window of 60 guest flips (title_verdict.py,
FRAME RATE): fps = 60 / dt. gfps_med is the TIME-weighted median, gfps_p10
the time-weighted 10th percentile.

GPU. hakuX-phase lines in the window with GPU > 0: medians of GPU, R, X and
Tot as printed, and the median of each line's X/R. Only ratios inside one
device are read (the period is the build's, not calibrated here).

POWER. thermal_state.power_over() over the window: battery_w (+ is
discharging), usb_w, net_w = battery_w + usb_w. j_per_frame = net_w x the fps
windows' seconds / their flips, the same as title_verdict.py's.
`samples` is the number of power readings inside the window (30 s apart).

HEAT. `pause` lists thermal-pause episodes that may overlap the window
(thermal_state.in_window); a run with one is VOID for fps and J/frame
(#507). xo_start is the first readable xo-therm sample, xo_max the hottest
up to the window's end. regimen is perf_regimen.json's.

QUERIES. hakuX-rpbrk lines in the window and those with qry > 0 (render
passes ended for an occlusion query; #527's ZPASS caveat).
"""
import argparse
import glob
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing"))
import thermal_state  # noqa: E402
import title_verdict as tv  # noqa: E402

RESULTS = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results"
GFPS = re.compile(r"gfps=(\d+)")
RPBRK = re.compile(r"RP:(\d+)\(fin\d+ fb\d+ qry(\d+)")
MESA = re.compile(r"(TU_DEBUG=0x[0-9a-fA-F]+|TU_AUTOTUNE_ALGO=\d+ \(\S+\)|Unknown TU_AUTOTUNE_ALGO[^\n]*)")


def rdir_of(arg):
    if os.path.isdir(arg):
        return arg
    hits = [d for d in os.listdir(RESULTS) if d == arg or d.endswith("-" + arg)]
    if len(hits) != 1:
        raise SystemExit("gmemread: %r matches %d result dirs" % (arg, len(hits)))
    return os.path.join(RESULTS, hits[0])


def num(key, msg):
    m = re.search(r"(?<![A-Za-z])" + key + r":([0-9.]+)", msg)
    return float(m.group(1)) if m else None


def wpct(windows, q):
    """Time-weighted q-quantile of [(dt, fps)]."""
    if not windows:
        return None
    ws = sorted(windows, key=lambda w: w[1])
    tot = sum(w[0] for w in ws)
    acc = 0.0
    for dt_s, f in ws:
        acc += dt_s
        if acc >= q * tot:
            return round(f, 2)
    return round(ws[-1][1], 2)


def med(xs, nd=2):
    return round(statistics.median(xs), nd) if xs else None


def read(rdir, lo_s, hi_s):
    res = tv.load_json(os.path.join(rdir, "result.json"))
    reg = tv.load_json(os.path.join(rdir, "perf_regimen.json"))
    out = dict(id=os.path.basename(rdir.rstrip("/")), device=res.get("device_label"),
               apk=res.get("apk_sha"), ref=str(res.get("ref"))[:10], env=res.get("env"),
               shader_cache=res.get("shader_cache"), regimen=reg.get("regimen"),
               perf_mode=reg.get("perf_mode"))
    lc, gaps, _ = tv.parse_logcat(os.path.join(rdir, "logcat.txt"))
    if not lc:
        out["error"] = "no logcat"
        return out
    t0 = lc[0][0]
    lo, hi = t0 + lo_s, t0 + hi_s
    out["last_line_s"] = round(lc[-1][0] - t0, 1)

    rm = [msg for t, lv, tag, msg in lc if tag == "hakuX-build" and msg.startswith("render_mode:")]
    out["render_mode"] = rm[0] if rm else None
    mesa = []
    for p in sorted(glob.glob(os.path.join(rdir, "pulled", "*"))):
        with open(p, errors="replace") as f:
            mesa += MESA.findall(f.read())
    out["mesa"] = mesa or None

    perf = [(t, GFPS.search(msg)) for t, lv, tag, msg in lc if tag == "hakuX-perf"]
    perf = [t for t, m in perf if m]
    wins = []
    for a, b in zip(perf, perf[1:]):
        if lo <= a and b <= hi and b > a and not tv.lost_in(a, b, gaps):
            wins.append((b - a, tv.FRAMES_PER_LINE / (b - a)))
    out["fps_windows"] = len(wins)
    out["gfps_med"] = wpct(wins, 0.5)
    out["gfps_p10"] = wpct(wins, 0.10)
    inside = [t for t in perf if lo <= t <= hi]
    out["last_gfps_s"] = round(perf[-1] - t0, 1) if perf else None
    out["longest_window_s"] = round(max(d for d, _ in wins), 2) if wins else None

    ph = [msg for t, lv, tag, msg in lc if tag == "hakuX-phase" and lo <= t <= hi]
    g = [(num("GPU", m), num("R", m), num("X", m), num("Tot", m)) for m in ph]
    g = [x for x in g if x[0]]
    out["phase_lines"] = len(ph)
    out["phase_gpu_lines"] = len(g)
    out["gpu_ms"] = med([x[0] for x in g])
    out["r_ms"] = med([x[1] for x in g if x[1] is not None])
    out["x_ms"] = med([x[2] for x in g if x[2] is not None])
    out["tot_ms"] = med([x[3] for x in g if x[3] is not None])
    out["x_over_r"] = med([x[2] / x[1] for x in g if x[1] and x[2] is not None])

    rp = [RPBRK.search(msg) for t, lv, tag, msg in lc if tag == "hakuX-rpbrk" and lo <= t <= hi]
    rp = [m for m in rp if m]
    out["rpbrk_lines"] = len(rp)
    out["qry_lines"] = sum(1 for m in rp if int(m.group(2)) > 0)
    out["qry_max"] = max((int(m.group(2)) for m in rp), default=None)

    out["crash"] = sum(1 for t, lv, tag, msg in lc
                       if (tag == "hakuX-crash" and lv in "EF") or (tag in ("libc", "DEBUG") and lv == "F"))

    therm = thermal_state.load(os.path.join(rdir, "thermal.jsonl")) or []
    ok = [r for r in therm if thermal_state.paused(r) is not None and thermal_state.dev_ts(r) is not None]
    if not ok:
        out["thermal"] = "unread"
        return out
    hit = thermal_state.in_window(therm, lo, hi)
    out["pause"] = [thermal_state.describe(e, t0) for e in hit] or None
    fe = thermal_state.first_episode(therm)
    out["first_pause"] = thermal_state.describe(fe[0], t0) if fe else None
    xo = [(thermal_state.dev_ts(r), thermal_state.zone_c(r, "xo-therm")) for r in ok]
    xo = [(t, c) for t, c in xo if c is not None and t <= hi + thermal_state.EVERY_S]
    out["xo_start_c"] = xo[0][1] if xo else None
    out["xo_max_c"] = max(c for _, c in xo) if xo else None
    bz = [thermal_state.zone_c(r, "battery") for r in ok]
    out["battery_start_c"] = next((c for c in bz if c is not None), None)

    pw = thermal_state.power_over(therm, lo, hi)
    out.update(samples=pw["samples"], battery_w=pw["battery_w"], usb_w=pw["usb_w"],
               net_w=pw["net_w"], usb_bound=pw["usb_bound"], sign_suspect=pw["sign_suspect"])
    secs = sum(d for d, _ in wins)
    flips = tv.FRAMES_PER_LINE * len(wins)
    ok_pw = pw["measured"] and flips and not pw["sign_suspect"]
    out["j_per_frame"] = (round(pw["net_w"] * secs / flips, 4)
                          if ok_pw and pw["net_w"] is not None else None)
    out["j_per_frame_battery"] = (round(pw["battery_w"] * secs / flips, 4)
                                  if ok_pw and pw["battery_w"] is not None else None)
    out["void"] = bool(hit)
    return out


COLS = [("id", 34), ("gfps_med", 6), ("gfps_p10", 6), ("gpu_ms", 6), ("x_over_r", 5),
        ("net_w", 6), ("j_per_frame", 7), ("samples", 3), ("xo_start_c", 5), ("xo_max_c", 5),
        ("qry_lines", 4), ("void", 5)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="lo", type=float, required=True)
    ap.add_argument("--to", dest="hi", type=float, required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("runs", nargs="+")
    a = ap.parse_args()
    rows = [read(rdir_of(r), a.lo, a.hi) for r in a.runs]
    if a.json:
        print(json.dumps(rows, indent=1))
        return
    print(" ".join(k.ljust(w) for k, w in COLS))
    for r in rows:
        print(" ".join(str(r.get(k)).ljust(w)[:max(w, 34 if k == "id" else w)] for k, w in COLS))
    for r in rows:
        print("\n%s  dev=%s apk=%s ref=%s regimen=%s/%s cache=%s" % (
            r["id"], r.get("device"), r.get("apk"), r.get("ref"), r.get("regimen"),
            r.get("perf_mode"), r.get("shader_cache")))
        print("  env=%s" % r.get("env"))
        print("  render_mode=%s" % r.get("render_mode"))
        print("  mesa=%s" % r.get("mesa"))
        print("  fps_windows=%s phase=%s/%s R=%s X=%s Tot=%s rpbrk=%s qry_max=%s crash=%s" % (
            r.get("fps_windows"), r.get("phase_gpu_lines"), r.get("phase_lines"), r.get("r_ms"),
            r.get("x_ms"), r.get("tot_ms"), r.get("rpbrk_lines"), r.get("qry_max"), r.get("crash")))
        print("  battery_w=%s usb_w=%s usb_bound=%s jpf_batt=%s last_gfps=%s last_line=%s" % (
            r.get("battery_w"), r.get("usb_w"), r.get("usb_bound"), r.get("j_per_frame_battery"),
            r.get("last_gfps_s"), r.get("last_line_s")))
        print("  pause_in_window=%s first_pause=%s battery_start=%s" % (
            r.get("pause"), r.get("first_pause"), r.get("battery_start_c")))


if __name__ == "__main__":
    main()
