#!/usr/bin/env python3
"""regimen_read.py -- the reader of predictions/sustain507-regimen.json.

    python3 docs/lanes/sustain507/regimen_read.py <result id or dir> ...
    python3 docs/lanes/sustain507/regimen_read.py --pair <MAX run> <default run>
    python3 docs/lanes/sustain507/regimen_read.py --json <run> ...

One title soak per argument, read off the files the dispatcher leaves
(logcat.txt, thermal.jsonl, perf_regimen.json). It reuses title_verdict.py's
logcat parser and thermal_state.py's pause episodes and power average, so a
number here means what it means in a verdict. Unlike title_verdict.py it does
NOT void the fps windows after a MAX pause: the pause's collapse is one of the
things this lane measures. It reports both the whole window and the clean span
before the first pause, and labels which is which.

THE WINDOW. t = 0 at the route's `mark gameplay` (logcat time). The window is
[0, 1800 s], cut at `soak end` (`short` says by how much). "Minute m" is
[60 (m-1), 60 m) s from the mark, so "minutes 2-10" is [60, 600) s and
"minutes 20-30" is [1140, 1800) s.

FPS. Each pair of consecutive hakuX-perf lines after the mark is one window
of 60 guest flips: fps = 60 / dt (title_verdict.py, FRAME RATE). A window
belongs to the span that holds its end. Median and p10 are TIME-weighted
(a slow window counts for as long as it lasted), over the window.
  stability = median fps over minutes 20-30 / median fps over minutes 2-10.

THERMAL. Times are seconds from the run's `start` sample (just before
`am start`) and, after the slash, from the mark. A mitigation event is the
first sample in which any cooling device's cur_state is above its value in
the `start` sample. Excluded: the panel backlights (they hold brightness, not
mitigation). A pause is thermal_state.first_pause(). Both are bounded, as
`after X by Y`: the last sample without the event and the first with it.
xo-therm max is over every readable sample from `start` to the window's end.
  plateau: the first sample after which every sample up to the window's end
  stays within 1.5 C of the median xo-therm over the window's last 300 s.
  Reported as minutes from the mark. `none` when the last 300 s themselves
  spread more than 3 C (still rising).

POWER. thermal_state.power_over() over the window: battery_w (+ is
discharging), usb_w, net_w = battery_w + usb_w. j_per_frame = net_w x the
windows' seconds / their flips. The battery's full energy is not assumed: each
run reports the energy the battery gave up (the integral of battery_w) and the
fall in `capacity` %, and --pool divides one by the other over all the runs
given, which is what `hours` uses: hours = E_full / net_w, the time a full
battery lasts at the run's net draw with no charger. `hours` is blank unless
the range the 1 % steps allow is narrow (max <= 1.3 x min).

--pair MAX DEF. The like-for-like power comparison: net_w of both runs over
[0, S] from the mark, where S is the MAX run's clean span (its first pause's
`after` bound, from the mark), capped at 1800 s. S under 120 s is `unreadable`.
"""
import argparse
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "testing"))
import thermal_state  # noqa: E402
import title_verdict as tv  # noqa: E402

RESULTS = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch") + "/results"
WINDOW_S = 1800.0
PLATEAU_BAND_C = 1.5
PLATEAU_TAIL_S = 300.0
NOT_MITIGATION = ("panel0-backlight", "panel1-backlight")


def rdir_of(arg):
    if os.path.isdir(arg):
        return arg
    hits = [d for d in os.listdir(RESULTS) if d == arg or d.endswith("-" + arg)]
    if len(hits) != 1:
        raise SystemExit("regimen_read: %r matches %d result dirs" % (arg, len(hits)))
    return os.path.join(RESULTS, hits[0])


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
            return f
    return ws[-1][1]


def bound(after, by):
    if by is None:
        return None
    return dict(after=None if after is None else round(after, 1), by=round(by, 1))


def read(rdir):
    lc, gaps, _ = tv.parse_logcat(os.path.join(rdir, "logcat.txt"))
    perf = [t for t, lv, tag, msg in lc if tag == "hakuX-perf" and tv.PERF.search(msg)]
    marks = [t for t, lv, tag, msg in lc if tag == "hakuX-route" and msg.strip() == "mark gameplay"]
    ends = [t for t, lv, tag, msg in lc if tag == "hakuX-route" and msg.strip() == "soak end"]
    req = tv.load_json(os.path.join(rdir, "request.json"))
    reg = tv.load_json(os.path.join(rdir, "perf_regimen.json"))
    out = dict(id=os.path.basename(rdir.rstrip("/")), title=(req.get("title") or "")[:40],
               device=tv.load_json(os.path.join(rdir, "result.json")).get("device_label"),
               regimen=reg.get("regimen"), perf_mode=reg.get("perf_mode"), fan_mode=reg.get("fan_mode"))
    if not marks:
        out["error"] = "no mark gameplay"
        return out
    m0 = marks[0]
    end = ends[-1] if ends else (lc[-1][0] if lc else m0)
    hi = min(end, m0 + WINDOW_S)
    out["window_s"] = round(hi - m0, 1)
    out["short_s"] = round(max(0.0, m0 + WINDOW_S - end), 1)
    after = [t for t in perf if t >= m0]
    wins = []   # (t_end_rel, dt, fps)
    for a, b in zip(after, after[1:]):
        if b > hi:
            break
        if b > a and not tv.lost_in(a, b, gaps):
            wins.append((b - m0, b - a, tv.FRAMES_PER_LINE / (b - a)))
    span = lambda lo, up: [(d, f) for e, d, f in wins if lo <= e < up]
    allw = span(0, WINDOW_S + 1)
    out["fps_median"] = wpct(allw, 0.5)
    out["fps_p10"] = wpct(allw, 0.10)
    early, late = wpct(span(60, 600), 0.5), wpct(span(1140, 1800.001), 0.5)
    out["fps_min2_10"], out["fps_min20_30"] = early, late
    out["stability"] = round(late / early, 3) if early and late is not None else None

    therm = thermal_state.load(os.path.join(rdir, "thermal.jsonl")) or []
    ok = [r for r in therm if thermal_state.paused(r) is not None and thermal_state.dev_ts(r) is not None]
    if not ok:
        out["thermal"] = "unread"
        return out
    t0 = thermal_state.origin(ok)
    out["mark_from_start_s"] = round(m0 - t0, 1)
    ok.sort(key=thermal_state.dev_ts)
    base = [r for r in ok if r.get("label") == "start"] or ok[:1]
    base_state = {c[1]: c[2] for c in base[0].get("cool") or []}
    last_clean, mit = None, None
    for r in ok:
        t = thermal_state.dev_ts(r)
        if t < t0:
            continue
        rose = [c for c in r.get("cool") or []
                if c[1] not in NOT_MITIGATION and c[2] > base_state.get(c[1], 0)]
        if rose:
            mit = (last_clean, t, ["%s %d/%d" % (c[1], c[2], c[3]) for c in rose])
            break
        last_clean = t
    rel = lambda t, z: None if t is None else t - z
    if mit:
        out["mitigation_from_start"] = bound(rel(mit[0], t0), rel(mit[1], t0))
        out["mitigation_from_mark"] = bound(rel(mit[0], m0), rel(mit[1], m0))
        out["mitigation_devices"] = mit[2][:6]
    else:
        out["mitigation_from_start"] = None
    fe = thermal_state.first_episode(therm)
    if fe:
        e, _ = fe
        out["pause_from_start"] = bound(rel(e["after"], t0), rel(e["first"], t0))
        out["pause_from_mark"] = bound(rel(e["after"], m0), rel(e["first"], m0))
        clean_end = e["after"] if e["after"] is not None else t0
    else:
        out["pause_from_start"] = None
        clean_end = None
    if clean_end is not None:
        cw = [(d, f) for e_, d, f in wins if e_ + m0 <= clean_end]
        out["clean_span_s"] = round(max(0.0, min(clean_end, hi) - m0), 1)
        out["fps_median_clean"] = wpct(cw, 0.5)
        out["fps_median_after_pause"] = wpct([(d, f) for e_, d, f in wins if e_ + m0 > clean_end], 0.5)
    xo = [(thermal_state.dev_ts(r), thermal_state.zone_c(r, "xo-therm")) for r in ok]
    xo = [(t, c) for t, c in xo if c is not None and t0 <= t <= hi + thermal_state.EVERY_S]
    out["xo_start_c"] = xo[0][1] if xo else None
    out["xo_max_c"] = max(c for _, c in xo) if xo else None
    tail = [c for t, c in xo if t >= hi - PLATEAU_TAIL_S]
    out["plateau_min"] = None
    if len(tail) >= 3 and max(tail) - min(tail) <= 2 * PLATEAU_BAND_C:
        ref = statistics.median(tail)
        out["xo_tail_c"] = round(ref, 1)
        start_idx = len(xo)
        for i in range(len(xo) - 1, -1, -1):
            if abs(xo[i][1] - ref) <= PLATEAU_BAND_C:
                start_idx = i
            else:
                break
        if start_idx < len(xo):
            out["plateau_min"] = round((xo[start_idx][0] - m0) / 60.0, 1)
    pw = thermal_state.power_over(therm, m0, hi)
    out.update(battery_w=pw["battery_w"], usb_w=pw["usb_w"], net_w=pw["net_w"],
               usb_bound=pw["usb_bound"], sign_suspect=pw["sign_suspect"])
    secs = sum(d for d, _ in allw)
    flips = tv.FRAMES_PER_LINE * len(allw)
    out["j_per_frame"] = round(pw["net_w"] * secs / flips, 4) if pw["net_w"] is not None and flips else None
    # Energy the battery gave up over the window, and the capacity it cost.
    pts = [(thermal_state.dev_ts(r), thermal_state.power(r), r) for r in ok]
    pts = [p for p in pts if p[1] is not None]
    if pw["battery_w"] is not None:
        out["battery_wh"] = round(pw["battery_w"] * (hi - m0) / 3600.0, 3)
        caps = [(t, (r.get("pw") or {}).get("battery", {}).get("capacity")) for t, _, r in pts]
        caps = [(t, c) for t, c in caps if isinstance(c, int)]
        before = [c for t, c in caps if t <= m0] or [c for t, c in caps][:1]
        at_end = [c for t, c in caps if t <= hi]
        out["capacity_pct"] = (before[-1], at_end[-1]) if before and at_end else None
    return out


def pair(max_dir, def_dir):
    a, b = read(max_dir), read(def_dir)
    s = a.get("clean_span_s")
    s = WINDOW_S if a.get("pause_from_start") is None else s
    res = dict(max=a["id"], default=b["id"], span_s=s)
    if s is None or s < 120:
        res["verdict"] = "unreadable: MAX clean span %s s < 120 s" % s
        return res
    for key, rdir in (("max", max_dir), ("default", def_dir)):
        therm = thermal_state.load(os.path.join(rdir, "thermal.jsonl")) or []
        lc, _, _ = tv.parse_logcat(os.path.join(rdir, "logcat.txt"))
        m0 = [t for t, lv, tag, msg in lc if tag == "hakuX-route" and msg.strip() == "mark gameplay"][0]
        res[key + "_net_w"] = thermal_state.power_over(therm, m0, m0 + s)["net_w"]
    if res["max_net_w"] is not None and res["default_net_w"] is not None:
        res["cut_w"] = round(res["max_net_w"] - res["default_net_w"], 3)
    return res


def pool(rows):
    wh = sum(r.get("battery_wh") or 0 for r in rows if r.get("capacity_pct"))
    pct = sum(r["capacity_pct"][0] - r["capacity_pct"][1] for r in rows if r.get("capacity_pct"))
    if pct <= 0 or wh <= 0:
        return None
    # capacity is an integer %: each run's fall is known to +-1, pooled +-n.
    n = sum(1 for r in rows if r.get("capacity_pct"))
    return dict(e_full_wh=round(100.0 * wh / pct, 2), pct=pct, wh=round(wh, 3),
                range_wh=(round(100.0 * wh / (pct + n), 2), round(100.0 * wh / max(pct - n, 1), 2)))


def fmt(v, nd=1):
    return "-" if v is None else ("%.*f" % (nd, v) if isinstance(v, float) else str(v))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--pair", action="store_true", help="two runs: MAX then default")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    dirs = [rdir_of(x) for x in a.runs]
    if a.pair:
        if len(dirs) != 2:
            raise SystemExit("--pair takes two runs, MAX then default")
        print(json.dumps(pair(*dirs), indent=1))
        return
    rows = [read(d) for d in dirs]
    pooled = pool(rows)
    # Hours only when the 1 % steps leave the pooled capacity narrow.
    narrow = bool(pooled) and pooled["range_wh"][1] <= 1.3 * pooled["range_wh"][0]
    for r in rows:
        r["hours"] = (round(pooled["e_full_wh"] / r["net_w"], 2)
                      if narrow and r.get("net_w") else None)
    if a.json:
        print(json.dumps(dict(runs=rows, pool=pooled), indent=1))
        return
    hdr = ("id", "reg", "med", "p10", "stab", "mit s", "pause s", "xo max", "plat", "net W", "J/fr", "h")
    print(" | ".join(hdr))
    for r in rows:
        if r.get("error"):
            print(r["id"], r["error"])
            continue
        mit = r.get("mitigation_from_start")
        pz = r.get("pause_from_start")
        print(" | ".join([
            r["id"][-22:], fmt(r.get("regimen")), fmt(r.get("fps_median")), fmt(r.get("fps_p10")),
            fmt(r.get("stability"), 2),
            "none" if not mit else "%s-%s" % (fmt(mit["after"], 0), fmt(mit["by"], 0)),
            "none" if not pz else "%s-%s" % (fmt(pz["after"], 0), fmt(pz["by"], 0)),
            fmt(r.get("xo_max_c")), fmt(r.get("plateau_min")), fmt(r.get("net_w"), 2),
            fmt(r.get("j_per_frame"), 3), fmt(r.get("hours"), 1)]))
        if r.get("short_s"):
            print("    short: window %s s, %s s under 1800" % (r["window_s"], r["short_s"]))
    print("pool:", pooled)


if __name__ == "__main__":
    main()
